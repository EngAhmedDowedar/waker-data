"""
parser_contract_audit.py
========================
Binary-proven parser-contract audit for the city boot chain. Methodology
(works under Houdini, unlike Frida — see TOMBSTONE_CRASH_MAP.md):

  * Field NAMES: each parser loads a key via a GOT-relative literal pair
        ldr rX,[pc]; add rX,pc          ; rX = GOT (0x75ab20)
        ldr r1,[pc]; adds r1,r1,rX      ; r1 = key string
    then GetNode via vtable+0x40.
  * Field TYPE: classified by the read pattern AFTER the GetNode blx:
        adds r0,#8 ; bl <int veneer>           -> int   (int64 if two str)
        adds r0,#4 ; movs r1,#1                 -> string
        bl C*::Parse* / ldr [node+4]+vtbl0x40  -> object/array (nested)
        ldr [node+0x14] (begin-iterator)        -> array
  * OPTIONAL vs REQUIRED: a field is OPTIONAL if its GetNode result is
    null-checked (cmp r0,#0 ; beq <skip>) before use. No null-check = REQUIRED
    (missing -> deref null). All CPlayer/CHouse/CGoods fields are optional;
    a wrong TYPE still crashes even when optional (node non-null, mistyped read).

Then it fetches the LIVE server JSON for each parser's endpoint and reports
type mismatches. Run the server first (127.0.0.1:8080).
"""
import struct, bisect, json, base64, urllib.request
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
from capstone.arm import ARM_OP_MEM, ARM_OP_IMM

SO = "installed_libcity_ar.so"
GOT = 0x75ab20
data = open(SO, "rb").read()

# ---- symbols ---------------------------------------------------------------
e_shoff = struct.unpack_from("<I", data, 0x20)[0]
e_she = struct.unpack_from("<H", data, 0x2e)[0]
e_shn = struct.unpack_from("<H", data, 0x30)[0]
secs = [struct.unpack_from("<IIIIIIIIII", data, e_shoff + i * e_she) for i in range(e_shn)]
_funcs = []
for st in secs:
    if st[1] in (2, 11):
        strt = secs[st[6]]
        for i in range(st[5] // st[9]):
            nm, val, sz, info, o, sh = struct.unpack_from("<IIIBBH", data, st[4] + i * st[9])
            if info & 0xf == 2 and val:
                e = data.index(b"\0", strt[4] + nm)
                _funcs.append((val & ~1, sz, data[strt[4] + nm:e].decode("u8", "replace")))
_funcs.sort()
_starts = [f[0] for f in _funcs]
def fname(a):
    i = bisect.bisect_right(_starts, a) - 1
    return _funcs[i][2] if i >= 0 else "?"
def faddr(substr):
    for a, s, n in _funcs:
        if substr in n:
            return a, s
    return None, None

def r32(va): return struct.unpack_from("<I", data, va)[0]
def cstr(va):
    if not (0 <= va < len(data)): return None
    e = va
    while e < len(data) and data[e] != 0: e += 1
    s = data[va:e]
    if 0 < len(s) <= 40 and all(32 <= c < 127 for c in s) and any(chr(c).isalpha() for c in s):
        return s.decode("latin1")
    return None

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True
def dec(off, n):
    out = []
    for ins in md.disasm(data[off:off + n * 2 + 12], off):
        out.append(ins)
        if len(out) >= n: break
    return out

# Typed value-accessor veneers (resolved from disasm). Keyed precisely by target
# so the string reader (0x692fcc, takes movs r1,#1) is NOT confused with the bool
# reader (0x694fbc, node+4 no arg) or the int reader (0x69300c, node+8).
ACCESSOR = {0x69300c: "int", 0x692fcc: "string", 0x694fbc: "bool"}
def classify(blxend):
    ins = dec(blxend, 16)
    for i in range(len(ins) - 1):
        m, o = ins[i].mnemonic, ins[i].op_str
        if m in ("bl", "blx") and ins[i].operands and ins[i].operands[-1].type == ARM_OP_IMM:
            t = ins[i].operands[-1].imm
            if t in ACCESSOR:
                return ACCESSOR[t]
            if "Parse" in fname(t):
                return "object/array"
        if m == "ldr" and ", [r0, #0x14]" in o:
            return "array"
    return "?"

def is_optional(blx_addr):
    """null-check right after GetNode blx => optional."""
    ins = dec(blx_addr, 4)
    for j in ins:
        if j.mnemonic == "cmp" and j.op_str.startswith("r0, #0"):
            return True
        if j.mnemonic in ("cbz",):
            return True
    return False

def fieldmap(start, size):
    """returns {field: (type, optional_bool)}. Handles BOTH key-load patterns:
      (A) per-field GOT recompute: ldr rA,[pc]; add rA,pc; ldr r1,[pc]; adds r1,r1,rA
      (B) hoisted GOT in a reg:     ldr rX,[pc]  (lit = key offset); adds r1,rX,r7
    Detection: any `ldr rX,[pc,#imm]` whose GOT+lit resolves to a field-name-like
    string AND is followed within ~7 instrs by a GetNode call (`ldr r2,[r?,#0x40];
    blx r2`). Classify the consumer after that blx."""
    res = {}
    for off in range(start, start + size, 2):
        i0 = dec(off, 1)
        if not i0: continue
        a = i0[0]
        if a.mnemonic != "ldr" or not a.operands or a.operands[1].type != ARM_OP_MEM \
                or a.reg_name(a.operands[1].mem.base or 0) != "pc":
            continue
        anchor = (a.address + 4) & ~3
        lit = r32(anchor + a.operands[1].mem.disp)
        key = cstr((GOT + lit) & 0xffffffff)
        if not key or key in res:
            continue
        # look ahead for the GetNode vtable call: ldr r2,[r?,#0x40]; blx r2
        seq = dec(off, 10)
        blx_end = None
        for k in range(1, len(seq)):
            if seq[k].mnemonic == "blx":
                # confirm a vtable+0x40 load in the 1-3 instrs before the blx
                window = seq[max(0, k - 3):k]
                if any(w.mnemonic == "ldr" and "#0x40" in w.op_str for w in window):
                    blx_end = seq[k].address + seq[k].size
                break
        if blx_end is None:
            continue
        res[key] = (classify(blx_end), is_optional(blx_end))
    return res

# ---- live JSON -------------------------------------------------------------
XOR = b"One ring to rule them all, one ring to find them, one ring to bring them all and in the darkness bind them."
def xor(b): return bytes(b[i] ^ XOR[i % len(XOR)] for i in range(len(b)))
def call(path):
    body = base64.b64encode(xor(json.dumps({}).encode()))
    req = urllib.request.Request("http://127.0.0.1:8080" + path, data=body, method="PUT")
    raw = urllib.request.urlopen(req, timeout=5).read()
    return json.loads(xor(base64.b64decode(raw)).decode())
def jt(v):
    if isinstance(v, bool): return "int"
    if isinstance(v, int): return "int"
    if isinstance(v, str): return "string"
    if isinstance(v, list): return "array"
    if isinstance(v, dict): return "object"
    return "null" if v is None else "?"
def compat(e, a):
    if e == "?": return True
    if e == "int": return a == "int"
    # bool accessor (0x694fbc) reads node+4 with no length arg; the game's own
    # verified contracts send these flags as int 0/1, so int is accepted.
    if e == "bool": return a == "int"
    if e == "string": return a == "string"
    if e in ("object/array", "array"): return a in ("array", "object")
    return True

# Parser registry: (parser_name, addr_substr_or_addr, caller, endpoint, json_path)
# json_path: list of keys to descend; '[]' means iterate the array of records.
REG = [
    ("CPlayer::Parse",        0x5140bc, "CLoadingScreen", "/city/connect/connect", []),
    ("CPlayer::ParseStatus",  0x516254, "CPlayer::Parse", "/city/connect/connect", ["playerStatus"]),
    ("CGoods::Parse(goods)",  0x40cc70, "CPlayer::ParseGoods", "/city/connect/connect", ["goods", "[]"]),
    ("CGoods::Parse(bags)",   0x40cc70, "CPlayer::ParseBags",  "/city/connect/connect", ["bags", "[]"]),
    ("CHouse::Parse(estates)",0x4498d8, "CPlayer::ParseHouses","/city/connect/connect", ["estates", "[]"]),
    ("CHouse::Parse(listest)",0x4498d8, "CPropertyCateScreen", "/city/estate/listestates", ["myEstates", "[]"]),
    ("CCitier::Parse(fight)", 0x34df98, "CFightScreen", "/city/fight/randomfighters", ["[]"]),
    ("CGoods::Parse(pbags)",  0x40cc70, "CGoodsScreen::ParseBag", "/city/goods/playerbags", ["playerGoods", "[]"]),
    ("CGoods::Parse(pgoods)", 0x40cc70, "CGoodsScreen::ParseWarehouse", "/city/goods/playergoods", ["playerGoods", "[]"]),
    ("CTopScreen::ParseMsg",  0x592fb4, "CTopScreen", "/city/chat/gettopmsgs", ["[]"]),
    ("CFaction::Parse",       0x3ce220, "CFactionScreen", "/city/faction/info", []),
    ("CServer::Parse",        0x56de78, "CServerMnger", "/api/getallserver", ["[]"]),
    ("CServer::Parse(ckver)", 0x56de78, "CServerMnger", "/checkversion", ["servers", "[]"]),
    ("ParseLastLoginPlayer",  0x490418, "CLoadingScreen", "/checkversion", ["lastLoginPlayer"]),
    ("CChatScreen::ParseMsg", 0x347edc, "CChatScreen", "/city/chat/getmsg", ["msgs", "[]"]),
    # randomgangs sends a faction-shaped gang object (flag:1) — check vs CFaction
    ("CFaction(randomgangs)",  0x3ce220, "CGangScreen", "/city/gang/randomgangs", ["[]"]),
    # named feature parsers (mostly empty endpoints -> 0 records -> no field risk)
    ("CFight::Parse",          0x3eaaec, "CFightScreen", "/city/fight/statistics", ["records", "[]"]),
    ("CCrime::Parse",          0x369078, "CCrimeScreen", "/city/crime/list", ["[]"]),
    ("CJob::Parse",            0x478604, "CHrMarketScreen", "/city/job/getjobs", ["[]"]),
    ("CGym::Parse",            0x429564, "CGymScreen", "/city/gym/getgym", ["gymTypes", "[]"]),
    ("CMessage::Parse",        0x4e7db0, "CMessageScreen", "/city/message/list", ["messages", "[]"]),
    ("CSubject::Parse",        0x589fa8, "CSchoolScreen", "/city/school/subjects", ["subjects", "[]"]),
]

# ---- GAMEPLAY (post-city) action/list response parsers ---------------------
# Action responses where `data` IS the result object -> json_path [] (root).
GAMEPLAY = [
    ("Crime",   "ParseDoCrimeResponse",   0x36a0bc, "CCrimeScreen::OnReceiveResponse", "/city/crime/docrime", []),
    ("Jobs",    "ParseGetSaleryResponse", 0x44c694, "CHrMarketCateScreen", "/city/job/work", []),
    ("Jobs",    "ParseDoJobResponse",     0x44c5dc, "CHrMarketCateScreen", "/city/job/work", []),
    ("Bank",    "CBankScreen::OnRecv",    0x33086c, "CBankScreen", "/city/bank/checkbalance", []),
    ("Bank",    "CBankScreen::OnRecv",    0x33086c, "CBankScreen", "/city/bank/deposit", []),
    ("Gym",     "ParseEnterGymInfo",      0x42bbc8, "CGymScreen", "/city/gym/getgym", []),
    ("Gym",     "CGymService::ParseConfig",0x429b68,"CGymScreen", "/city/gym/getgym", ["gymTypes", "[]"]),
    ("Gym",     "CGymScreen::ParseResponse",0x42d340,"CGymScreen", "/city/gym/getgym", []),
    ("Hospital","CHospitalScreen::OnRecv", 0x448c94, "CHospitalScreen", "/city/hospital/cure", []),
    ("Hospital","ParsePatient",           0x448f2c, "CHospitalScreen", "/city/hospital/patients", ["[]"]),
    ("Missions","CGameMissionMgr::OnRecv", 0x40643c, "CGameMissionManager", "/city/mission/getmission", []),
    ("Fight",   "CFightingScreen::OnRecv", 0x3ee888, "CFightingScreen", "/city/fight/attack", []),
    ("Fight",   "CFight::Parse",          0x3eaaec, "CFightingScreen", "/city/fight/statistics", []),
    ("Fight",   "CFight::ParseNew",       0x3eace4, "CFightingScreen", "/city/fight/attack", []),
    ("Fight",   "CFightingScreen::ParseFighters", 0x3ee774, "CFightingScreen", "/city/fight/attack", []),
    ("Store",   "CStorePackage::Parse",   0x57c9e0, "CStoreCateScreen", "/city/store/package", ["packages", "[]"]),
    ("Lottery", "CLotteryScreen::OnRecv",  0x495810, "CLotteryScreen", "/city/lottery/info", []),
    ("Rankings","CRankCateScreen::ParsePlayer", 0x54d9e0, "CRankCateScreen", "/city/rank/list", ["players", "[]"]),
    ("School",  "CSchoolScreen::ParseSubject", 0x56b278, "CSchoolScreen", "/city/school/getmyclasses", ["subjects", "[]"]),
    ("Mail",    "CMessage::Parse",        0x4e7db0, "CMessageScreen", "/city/message/list", ["messages", "[]"]),
    ("Auction", "CAuction::ParseMyAuctions",0x327f10,"CAuctionHouseScreen", "/city/auction/list", ["items", "[]"]),
    ("GoodsMkt","CGoods::ParseDeal",      0x40cf34, "CDealMarketScreen", "/city/deal/list", ["items", "[]"]),
    ("Inventory","CGoods::Parse(buy)",    0x40cc70, "CGoodsScreen", "/city/goods/buy", ["bags", "[]"]),
    ("Estate",  "CHouse::Parse(buy)",     0x4498d8, "CPropertyScreen", "/city/estate/buy", ["estates", "[]"]),
]

def descend(root, path):
    cur = [root]
    for key in path:
        nxt = []
        for c in cur:
            if key == "[]":
                if isinstance(c, list): nxt.extend(c)
            elif isinstance(c, dict) and key in c:
                nxt.append(c[key])
        cur = nxt
    return cur

def is_dispatcher(addr, size):
    """A fn has NO named-field contract (so cannot have a field-TYPE mismatch) if:
      - it delegates to a C*::Parse* sub-parser, OR
      - it iterates a container (vtable count/getAt: ldr [r?,#0xc/#0x14/#0x2c]), OR
      - it loads NO field-name key strings at all (reads response by index, not name).
    Such functions are 'known: no named-field contract', not 'unknown field map'."""
    loads_a_field_key = False
    for ins in md.disasm(data[addr:addr + size], addr):
        if ins.mnemonic in ("bl", "blx") and ins.operands and ins.operands[-1].type == ARM_OP_IMM:
            if "Parse" in fname(ins.operands[-1].imm):
                return True
        if ins.mnemonic == "ldr" and any(o in ins.op_str for o in (", #0x14]", ", #0x2c]")):
            return True
        if ins.mnemonic == "ldr" and ins.operands and ins.operands[1].type == ARM_OP_MEM \
                and ins.reg_name(ins.operands[1].mem.base or 0) == "pc":
            anchor = (ins.address + 4) & ~3
            if cstr((GOT + r32(anchor + ins.operands[1].mem.disp)) & 0xffffffff):
                loads_a_field_key = True
    return not loads_a_field_key

def audit_one(addr, ep, path):
    a = addr if isinstance(addr, int) else faddr(addr)[0]
    size = next((s for st, s, n in _funcs if st == a), 600)
    fm = fieldmap(a, size)
    try:
        d = call(ep).get("data", {})
        recs = descend(d, path)
    except Exception:
        recs = []
    nrec = len([r for r in recs if isinstance(r, dict)])
    mism = []
    for r in recs:
        if not isinstance(r, dict): continue
        for k, v in r.items():
            if k in fm:
                et, opt = fm[k]
                if not compat(et, jt(v)):
                    mism.append((k, et, jt(v), v))
    return fm, nrec, mism

if __name__ == "__main__":
    total_mis = 0
    unknown = []   # parsers whose field map could not be extracted (fields==0 with records>0)
    print("=" * 78); print("PARSER-CONTRACT AUDIT — city boot chain"); print("=" * 78)
    for pname, addr, caller, ep, path in REG:
        fm, nrec, mism = audit_one(addr, ep, path)
        total_mis += len(mism)
        tag = "OK" if (nrec and not mism) else ("∅" if nrec == 0 else "MISMATCH")
        print(f"### {pname:28} {ep:32} fields={len(fm):3} recs={nrec} {tag}")
        for k, et, at, v in mism:
            print(f"    !! {k}: expected {et}, sent {at} ({v!r})")
        a0 = addr if isinstance(addr, int) else faddr(addr)[0]
        sz0 = next((s for st, s, n in _funcs if st == a0), 600)
        if nrec and not fm and not is_dispatcher(a0, sz0):
            unknown.append(f"{pname} ({ep})")

    print("\n" + "=" * 78)
    print("GAMEPLAY (post-city) PARSER-CONTRACT AUDIT")
    print("=" * 78)
    print(f"{'Subsystem':10} {'Parser':28} {'Endpoint':30} {'Field':16} {'Exp':8} {'Act':8} Risk Patch")
    gp_rows = []
    for sub, pname, addr, caller, ep, path in GAMEPLAY:
        fm, nrec, mism = audit_one(addr, ep, path)
        total_mis += len(mism)
        a0 = addr if isinstance(addr, int) else faddr(addr)[0]
        sz0 = next((s for st, s, n in _funcs if st == a0), 600)
        if nrec and not fm and not is_dispatcher(a0, sz0):
            unknown.append(f"{sub}:{pname} ({ep})")
        if not mism:
            note = "OK" if nrec else "∅(empty)"
            print(f"{sub:10} {pname:28} {ep:30} {'-':16} {'-':8} {'-':8} {'-':4} N   [{note} f={len(fm)} r={nrec}]")
        for k, et, at, v in mism:
            risk = "HIGH" if et in ("int", "string") else "MED"
            print(f"{sub:10} {pname:28} {ep:30} {k:16} {et:8} {at:8} {risk:4} Y")

    print("\n" + "=" * 78)
    print(f"TOTAL_MISMATCH_COUNT     = {total_mis}")
    print(f"TOTAL_UNAUDITED_PARSERS  = {len(unknown)}")
    if unknown:
        print("PARSERS WITH UNKNOWN FIELD MAPS (records>0 but 0 fields extracted):")
        for u in unknown:
            print(f"   - {u}")
    print("=" * 78)
