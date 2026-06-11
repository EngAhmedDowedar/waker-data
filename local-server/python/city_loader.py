"""
city_loader.py — asset-driven game-data layer for the Waker local server.

Loads the decoded `.city` catalog tables (reverse-engineered binary format,
see analyze/docs/ASSET_SCHEMA.md) and exposes them to server.py at startup.

Two data sources, in priority order:
  1. A live `.city` assets directory (env CITY_ASSETS_DIR) — parsed on the fly
     with the same decoder as analyze/tools/city_extract.py.
  2. The committed `gamedata/` snapshot of decoded JSON (default, always present).

Public API:
  load_catalogs() -> dict   {table_name: Catalog}
  Catalog.records           list[dict]  (fields: id, f1.., name, ..)
  Catalog.by_id(i)          dict | None
  Catalog.ids()             list[int]

The .city columns are POSITIONAL (id first = the GetById key). The JSON KEY names
the network parsers expect are documented per-endpoint in server.py where real
data is served; this layer provides the raw real values (ids, prices, names).
"""
import os, json, glob, struct

_HERE = os.path.dirname(os.path.abspath(__file__))
_GAMEDATA = os.path.join(_HERE, 'gamedata')


def _u16(b, o): return struct.unpack_from('>H', b, o)[0]
def _u32(b, o): return struct.unpack_from('>I', b, o)[0]


def _printable(bs):
    return bool(bs) and all(0x20 <= c <= 0x7e for c in bs)


def _decode_city(b):
    """Decode one .city blob -> (schema, fields, records) or (None, None, None)."""
    if len(b) < 2:
        return None, None, None
    count = _u16(b, 0)
    n = len(b)

    def parse(schema):
        o = 2
        out = []
        for _ in range(count):
            rec = []
            for t in schema:
                if o + 4 > n:
                    return None, o
                if t == 'i':
                    rec.append(_u32(b, o)); o += 4
                else:
                    L = _u32(b, o); o += 4
                    if o + L > n:
                        return None, o
                    rec.append(b[o:o+L].decode('utf-8', 'latin-1')); o += L
            out.append(rec)
        return out, o

    candidates = []
    body = n - 2
    if count and body % count == 0 and (body // count) % 4 == 0:
        candidates.append(['i'] * ((body // count) // 4))
    # infer string/int schema from the first record
    s0, o = [], 2
    while o < n and len(s0) < 12:
        L = _u32(b, o)
        if 1 <= L <= 63 and o + 4 + L <= n and _printable(b[o+4:o+4+L]):
            s0.append('s'); o += 4 + L
        else:
            s0.append('i'); o += 4
    for k in range(len(s0), 0, -1):
        candidates.append(s0[:k])

    seen = set()
    for sch in candidates:
        key = ''.join(sch)
        if key in seen:
            continue
        seen.add(key)
        recs, end = parse(sch)
        if recs is not None and end == n:
            fields = []
            for i, t in enumerate(sch):
                if t == 's':
                    fields.append('name' if 'name' not in fields else f'str{i}')
                else:
                    fields.append('id' if i == 0 else f'f{i}')
            return ''.join(sch), fields, [dict(zip(fields, r)) for r in recs]
    return None, None, None


class Catalog:
    def __init__(self, name, count, schema, fields, records, status):
        self.name = name
        self.count = count
        self.schema = schema
        self.fields = fields
        self.records = records or []
        self.status = status
        self._by_id = {r['id']: r for r in self.records if 'id' in r}

    def by_id(self, i): return self._by_id.get(i)
    def ids(self): return [r['id'] for r in self.records if 'id' in r]
    def __len__(self): return len(self.records)


def load_catalogs():
    """Return {table_name: Catalog}. Prefers live .city dir, else gamedata JSON."""
    cats = {}
    live = os.environ.get('CITY_ASSETS_DIR')
    if live and os.path.isdir(live):
        for path in sorted(glob.glob(os.path.join(live, '*.city'))):
            name = os.path.basename(path)[:-5]
            b = open(path, 'rb').read()
            schema, fields, records = _decode_city(b)
            status = 'decoded' if schema else 'ambiguous'
            cats[name] = Catalog(name, _u16(b, 0) if len(b) >= 2 else 0,
                                 schema, fields, records, status)
        if cats:
            return cats
    # fallback: committed decoded JSON snapshot
    for path in sorted(glob.glob(os.path.join(_GAMEDATA, '*.city.json'))):
        d = json.load(open(path, encoding='utf-8'))
        name = d['file'][:-5]
        cats[name] = Catalog(name, d.get('count', 0), d.get('schema'),
                             d.get('fields'), d.get('records'),
                             d.get('status', 'unknown'))
    return cats


if __name__ == '__main__':
    c = load_catalogs()
    dec = sum(1 for k in c.values() if k.status == 'decoded')
    print(f'loaded {len(c)} catalogs ({dec} decoded) from '
          f'{"live .city" if os.environ.get("CITY_ASSETS_DIR") else "gamedata JSON"}')
    for n in ('job', 'product', 'property', 'crime', 'mission', 'subject'):
        if n in c:
            print(f'  {n:10} {len(c[n])} records, ids {c[n].ids()[:5]}...')
