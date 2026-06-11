"""
Response-path static analysis for libcity_ar.so.
Answers: (1) is the checkversion response decrypted/decompressed before parse,
(2) which opcode/state selects proceed vs notice/update, (3) where launchUrl("")
is selected, (4) plaintext vs encrypted/compressed payload expectation,
(5) what the 0x48f910 D0->E0 flip does to control flow.
"""
import os, struct, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM

HERE = os.path.dirname(os.path.abspath(__file__))
SO = os.path.join(HERE, '..', 'lib', 'armeabi', 'libcity_ar.so')
INSTALLED = os.path.join(HERE, '..', 'installed_libcity_ar.so')
data = open(SO, 'rb').read()

print("SO:", os.path.normpath(SO), "size", len(data))
if os.path.exists(INSTALLED):
    isz = os.path.getsize(INSTALLED)
    print("installed_libcity_ar.so size", isz, "(same build)" if isz == len(data) else "(DIFFERENT size!)")

# ---- ELF ----
e_phoff = struct.unpack_from('<I', data, 0x1c)[0]
e_phentsize = struct.unpack_from('<H', data, 0x2a)[0]
e_phnum = struct.unpack_from('<H', data, 0x2c)[0]
segs = []
for i in range(e_phnum):
    o = e_phoff + i*e_phentsize
    t, off, va, _, fsz, msz, *_ = struct.unpack_from('<8I', data, o)
    segs.append((t, off, va, fsz, msz))
def va_to_off(va):
    for t, off, vb, fsz, msz in segs:
        if t == 1 and vb <= va < vb+msz:
            fo = off + (va-vb)
            return fo if fo < len(data) else None
    return None

e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize = struct.unpack_from('<H', data, 0x2e)[0]
e_shnum = struct.unpack_from('<H', data, 0x30)[0]
e_shstrndx = struct.unpack_from('<H', data, 0x32)[0]
sh_str_off = struct.unpack_from('<I', data, e_shoff+e_shstrndx*e_shentsize+0x10)[0]
sections = {}
for i in range(e_shnum):
    b = e_shoff+i*e_shentsize
    nm, ty, fl, ad, of, sz, *_ = struct.unpack_from('<10I', data, b)
    name = data[sh_str_off+nm:].split(b'\x00',1)[0].decode('ascii','replace')
    sections[name] = dict(addr=ad, off=of, size=sz)

dynsym = sections['.dynsym']; dynstr = sections['.dynstr']
symbols = {}; sym_by_va = {}
for i in range(dynsym['size']//16):
    so = dynsym['off']+i*16
    st_name, st_value, st_size, st_info, st_other, st_shndx = struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm:
        symbols[nm] = (st_value, st_size)
        if st_value:
            sym_by_va[st_value & ~1] = nm
def nearest(va):
    best=None
    for s in sorted(sym_by_va):
        if s>va: break
        best=s
    return (best, sym_by_va[best]) if best is not None else (None,None)

# ---- PLT import map: GOT(JUMP_SLOT) -> name, then plt stub -> name ----
relplt = sections.get('.rel.plt')
got_to_name = {}
if relplt:
    for i in range(relplt['size']//8):
        r_off, r_info = struct.unpack_from('<II', data, relplt['off']+i*8)
        symidx = r_info >> 8
        so = dynsym['off']+symidx*16
        st_name = struct.unpack_from('<I', data, so)[0]
        nm = data[dynstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
        got_to_name[r_off] = nm
# decode ARM plt stubs to map stub_va -> got
plt = sections.get('.plt')
plt_to_name = {}
if plt:
    md_arm = Cs(CS_ARCH_ARM, CS_MODE_ARM)
    pcode = data[plt['off']:plt['off']+plt['size']]
    # ARM plt stub = 12 bytes: add ip,pc,#; add ip,ip,#; ldr pc,[ip,#]!
    va = plt['addr']
    i = 0
    # skip PLT0 (first 20 bytes typically); scan stubs of 12 bytes
    while i+12 <= len(pcode):
        ip = plt['addr']
        accum = 0; gotva=None
        try:
            insns = list(md_arm.disasm(pcode[i:i+12], plt['addr']+i))
            base = (plt['addr']+i) + 8  # pc
            for ins in insns:
                if ins.mnemonic.startswith('add') and 'ip, pc' in ins.op_str:
                    imm = int(ins.op_str.split('#')[-1],0); accum = base+imm
                elif ins.mnemonic.startswith('add') and 'ip, ip' in ins.op_str:
                    imm = int(ins.op_str.split('#')[-1],0); accum += imm
                elif ins.mnemonic.startswith('ldr') and 'pc, [ip' in ins.op_str:
                    imm = 0
                    if '#' in ins.op_str: imm = int(ins.op_str.split('#')[-1].rstrip(']!'),0)
                    gotva = accum+imm
            if gotva in got_to_name:
                plt_to_name[plt['addr']+i] = got_to_name[gotva]
        except Exception:
            pass
        i += 12

def resolve_call(t):
    nm = sym_by_va.get(t & ~1)
    if nm: return nm
    if (t & ~1) in plt_to_name: return plt_to_name[t & ~1]+' [PLT]'
    if t in plt_to_name: return plt_to_name[t]+' [PLT]'
    nv,nn = nearest(t & ~1)
    if nn: return f'{nn}+0x{(t-nv)&~1:x}'
    return None

def read_cstr(va, maxlen=80):
    o = va_to_off(va)
    if o is None: return None
    end = data.find(b'\x00', o, o+maxlen+1)
    if end<0: end=o+maxlen
    s = data[o:end]
    if len(s)>=2 and all(9<=b<127 for b in s):
        return s.decode('ascii','replace')
    return None

# ---- annotated disassembler ----
md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail=True
def disasm_fn(name_or_va, length=None, label=''):
    if isinstance(name_or_va,str):
        va, sz = symbols.get(name_or_va,(0,0))
    else:
        va, sz = name_or_va, length or 0
    if not va:
        print(f'  [symbol {name_or_va} not found]'); return
    start = va & ~1
    ln = length or sz or 0x200
    off = va_to_off(start)
    code = data[off:off+ln]
    print(f'\n===== {label or name_or_va}  va=0x{start:08x} off=0x{off:x} len=0x{ln:x} =====')
    regconst = {}  # reg -> (instr_addr, literal_value) for pc-rel ldr; movw/movt accum
    movacc = {}
    for ins in md.disasm(code, start):
        op = ins.op_str; mn = ins.mnemonic; an=''
        # calls
        if mn in ('bl','blx'):
            try:
                t = ins.operands[-1]
                if t.type==2:
                    r = resolve_call(t.value.imm)
                    if r: an += f'  ; -> {r}'
            except: pass
        # pc-relative ldr literal
        if mn in ('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm = int(op.split('#')[-1].rstrip(']'),0)
                lit = ((ins.address+4)&~3)+imm
                lo = va_to_off(lit)
                if lo:
                    val = struct.unpack_from('<I', data, lo)[0]
                    rt = op.split(',')[0].strip()
                    regconst[rt]=(ins.address,val)
                    an += f'  ; lit=0x{val:08x}'
                    s = read_cstr(val)
                    if s: an += f' "{s}"'
            except: pass
        # PIC: add rX, pc  -> string at (pc)+lit
        if mn in ('add','adds','add.w') and op.replace(' ','').endswith(',pc'):
            rt = op.split(',')[0].strip()
            if rt in regconst:
                _, lit = regconst[rt]
                tgt = (ins.address+4+lit)&0xFFFFFFFF
                s = read_cstr(tgt)
                an += f'  ; ={"0x%08x"%tgt}'
                if s: an += f' "{s}"'
                r = resolve_call(tgt)
                if r and not s: an += f' -> {r}'
        # movw/movt absolute
        if mn=='movw':
            rt=op.split(',')[0].strip(); imm=int(op.split('#')[-1],0); movacc[rt]=imm
        elif mn=='movt':
            rt=op.split(',')[0].strip(); imm=int(op.split('#')[-1],0)
            if rt in movacc:
                movacc[rt]|=(imm<<16); val=movacc[rt]
                s=read_cstr(val)
                an+=f'  ; {rt}=0x{val:08x}'
                if s: an+=f' "{s}"'
        # comparisons (opcode candidates)
        if mn in ('cmp','cmp.w','cmn','subs','sub.w') and '#' in op:
            an += '  <== CMP'
        if '#0x2ac' in op.lower() or '#684' in op:
            an += '  <== this+0x2AC'
        flag = '  *PATCH*' if start<=ins.address<=start+0x80 and ins.address in (0x48f910,0x48f911) else ''
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}{flag}')

# ============ (B) crypto/parse/compress symbol inventory ============
print('\n'+'='*72+'\n(B) crypto / parse / compress symbols in dynsym\n'+'='*72)
kw = ['RC4','rc4','ngRC4','ase64','crypt','Crypt','ecode','ncode','json','JSON','cJSON',
      'arse','nflate','ompress','zlib','gzip','md5','MD5','sha','SHA','XOR','xor','ngHttp','ngNet']
seen=set()
for nm,(va,sz) in sorted(symbols.items(), key=lambda x:x[1][0]):
    if any(k in nm for k in kw) and nm not in seen:
        seen.add(nm)
        print(f'  0x{va&~1:08x} {nm}')

# ============ (C) key functions ============
print('\n'+'='*72+'\n(C) key symbol resolution\n'+'='*72)
for q in ['_ZN11CHttpClient12CheckVersionEv','_ZN14CLoadingScreen14DoCheckVersionEv',
          '_ZN14CLoadingScreen11CheckUpdateEPKcS1_','_ZN14CLoadingScreen17OnReceiveResponseEiPv',
          '_ZN14CLoadingScreen14OnReceiveErrorEPKcS1_Pv','_ZN14CLoadingScreen15DoGetServerInfoEh']:
    va,sz=symbols.get(q,(0,0))
    print(f'  {q}: va=0x{va&~1:08x} size=0x{sz:x}')

# ============ (D)..(G) disassembly ============
disasm_fn('_ZN14CLoadingScreen17OnReceiveResponseEiPv', label='OnReceiveResponse')
disasm_fn('_ZN14CLoadingScreen11CheckUpdateEPKcS1_', label='CheckUpdate')
disasm_fn('_ZN14CLoadingScreen14DoCheckVersionEv', label='DoCheckVersion')
disasm_fn('_ZN14CLoadingScreen14OnReceiveErrorEPKcS1_Pv', label='OnReceiveError')
