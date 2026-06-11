#!/usr/bin/env python3
"""
city_extract.py — reverse-engineer and decode the `.city` binary catalog format.

Format (recovered from job.city / job_type.city byte analysis):
  - Header: u16 big-endian record COUNT.
  - Body:   COUNT records, each a FIXED per-file schema of ordered fields.
  - Field types:
        int    -> u32 big-endian
        string -> u32 big-endian length L, then L bytes (ASCII/UTF-8)
  - Strings may appear anywhere within a record.

The per-file field schema (sequence of 'i'/'s') is not stored in the file, so we
INFER it from the first record by classifying each 4-byte word: if it looks like a
plausible string length (small, followed by printable bytes) it's a string, else int.
We then LOCK that schema and require the whole file to parse into exactly COUNT
records with no trailing bytes. If it doesn't, we report the file as ambiguous and
fall back to a raw token stream (still real data: ids + name keys).

Output: assets_decoded/<name>.json  ->  {file, count, schema, fields, records[...]}
"""
import os, sys, json, glob, struct

ASSETS = sys.argv[1] if len(sys.argv) > 1 else \
    os.path.join(os.path.dirname(__file__), '..', 'baseline-apk-src', 'assets')
OUT = os.path.join(os.path.dirname(__file__), '..', 'assets_decoded')
os.makedirs(OUT, exist_ok=True)

def u16(b, o): return struct.unpack_from('>H', b, o)[0]
def u32(b, o): return struct.unpack_from('>I', b, o)[0]

def is_printable(bs):
    if not bs:
        return False
    for c in bs:
        # printable ASCII, plus common latin/underscore; reject control bytes
        if c < 0x20 or c > 0x7e:
            return False
    return True

def classify_record(b, o, end):
    """Infer a field schema starting at offset o by reading one record worth of
    fields until we hit the next record boundary is unknown — so we read a single
    record greedily: a word is a STRING if (len plausible AND bytes printable),
    else INT. We stop when consuming would exceed `end`. Returns (schema, next_o)."""
    schema = []
    while o < end:
        if o + 4 > end:
            break
        L = u32(b, o)
        # plausible string: 1..63 bytes, fits, printable
        if 1 <= L <= 63 and o + 4 + L <= end and is_printable(b[o+4:o+4+L]):
            schema.append('s')
            o += 4 + L
        else:
            schema.append('i')
            o += 4
        # heuristic stop: a record rarely exceeds ~10 fields; let validator decide
        if len(schema) >= 12:
            break
    return schema

def parse_with_schema(b, count, schema, start=2):
    o = start
    n = len(b)
    records = []
    for _ in range(count):
        rec = []
        for t in schema:
            if o + 4 > n:
                return None, o
            if t == 'i':
                rec.append(u32(b, o)); o += 4
            else:
                L = u32(b, o); o += 4
                if o + L > n:
                    return None, o
                try:
                    rec.append(b[o:o+L].decode('utf-8'))
                except UnicodeDecodeError:
                    rec.append(b[o:o+L].decode('latin-1'))
                o += L
        records.append(rec)
    return records, o

def best_schema(b, count):
    """Try schemas inferred from the first few records; pick the one that consumes
    the whole file (o == len) with exactly `count` records."""
    n = len(b)
    candidates = []
    # primary: infer from first record
    s0 = classify_record(b, 2, n)
    for k in range(len(s0), 0, -1):
        candidates.append(s0[:k])
    # also try a PURE-INT fixed-width schema when (n-2) divides evenly into count
    # records of a whole number of u32 words (catches all-integer tables like
    # mission.city: 14 u32/record, text stored as string-ids into assets/ar).
    body = n - 2
    if count > 0 and body % count == 0 and (body // count) % 4 == 0:
        w = (body // count) // 4
        candidates.insert(0, ['i'] * w)
    seen = set()
    for sch in candidates:
        key = ''.join(sch)
        if key in seen:
            continue
        seen.add(key)
        recs, o = parse_with_schema(b, count, sch)
        if recs is not None and o == n:
            return sch, recs
    return None, None

def name_fields(schema):
    """Heuristic field names: first int = id, string = name, others fieldN."""
    names, ii = [], 0
    for i, t in enumerate(schema):
        if t == 's':
            names.append('name' if 'name' not in names else f'str{i}')
        elif i == 0:
            names.append('id')
        else:
            names.append(f'f{i}')
    return names

summary = []
for path in sorted(glob.glob(os.path.join(ASSETS, '*.city'))):
    name = os.path.basename(path)
    b = open(path, 'rb').read()
    if len(b) < 2:
        continue
    count = u16(b, 0)
    schema, recs = best_schema(b, count)
    entry = {'file': name, 'size': len(b), 'count': count}
    if schema is not None:
        fields = name_fields(schema)
        entry['schema'] = ''.join(schema)
        entry['fields'] = fields
        entry['records'] = [dict(zip(fields, r)) for r in recs]
        entry['status'] = 'decoded'
    else:
        # fallback: raw token stream (ints + strings) — still real data
        toks, o = [], 2
        while o + 4 <= len(b):
            L = u32(b, o)
            if 1 <= L <= 63 and o+4+L <= len(b) and is_printable(b[o+4:o+4+L]):
                toks.append(b[o+4:o+4+L].decode('latin-1')); o += 4 + L
            else:
                toks.append(L); o += 4
        entry['schema'] = None
        entry['tokens'] = toks
        entry['status'] = 'ambiguous'
    json.dump(entry, open(os.path.join(OUT, name + '.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    summary.append({'file': name, 'count': count, 'schema': entry.get('schema'),
                    'status': entry['status'], 'size': len(b)})

json.dump(summary, open(os.path.join(OUT, '_summary.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
dec = sum(1 for s in summary if s['status'] == 'decoded')
print(f'{len(summary)} files: {dec} decoded, {len(summary)-dec} ambiguous')
for s in summary:
    if s['status'] != 'decoded':
        print(f"  AMBIGUOUS {s['file']} count={s['count']} size={s['size']}")
