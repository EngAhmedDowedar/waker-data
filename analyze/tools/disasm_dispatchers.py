"""Disassemble each JNI dispatcher helper called from nativeRender, so when
the ring-buffer dump comes back we can interpret its args.

Helpers (all from nativeRender's call sites at 0x5f4710..0x5f48ed):
  0x693c4c  - presumed C-string -> jstring converter (called many times)
  0x6bce9c  - first call in block A (perhaps Java event-target lookup)
  0x6bcaac  - dispatcher variant
  0x6bcabc  - dispatcher variant
  0x6bcacc  - dispatcher variant (takes jstrings in r1, r2)
  0x6bcadc  - dispatcher variant
  0x6bcb9c  - dispatcher variant
  0x6bcecc  - end-of-block helper (block A wrap-up)
  0x6bf62c  - alternate dispatcher
"""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

data=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','lib','armeabi','libcity_ar.so'),'rb').read()
e_phoff=struct.unpack_from('<I',data,0x1c)[0]
e_phentsize=struct.unpack_from('<H',data,0x2a)[0]
e_phnum=struct.unpack_from('<H',data,0x2c)[0]
segs=[]
for i in range(e_phnum):
    o=e_phoff+i*e_phentsize
    t,off,va,_,fsz,msz,*_=struct.unpack_from('<8I',data,o)
    segs.append((t,off,va,fsz,msz))
def va_to_off(va):
    for t,off,vb,_,msz in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)

e_shoff=struct.unpack_from('<I',data,0x20)[0]
e_shentsize=struct.unpack_from('<H',data,0x2e)[0]
e_shnum=struct.unpack_from('<H',data,0x30)[0]
e_shstrndx=struct.unpack_from('<H',data,0x32)[0]
shdr=e_shoff+e_shstrndx*e_shentsize
shstr=struct.unpack_from('<I',data,shdr+0x10)[0]
secs={}
for i in range(e_shnum):
    b=e_shoff+i*e_shentsize
    sn,st,_,sa,so,sz,*_=struct.unpack_from('<10I',data,b)
    nm=data[shstr+sn:].split(b'\x00',1)[0].decode('ascii','replace')
    secs[nm]=(sa,so,sz)
da,do,dz=secs['.dynsym']; dsa,dso,dsz=secs['.dynstr']
sym_by_va={}
for i in range(dz//16):
    o=do+i*16
    st_name,st_value,*_=struct.unpack_from('<IIIBBH',data,o)
    nm=data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm: sym_by_va[st_value & ~1]=nm
def near(va):
    best=None
    for s in sorted(sym_by_va):
        if s>va: break
        best=s
    return best, sym_by_va.get(best)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True

# Write to a fresh output file with a sentinel at end
_out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dispatchers_out.txt'), 'w', encoding='utf-8')
_old_print = print
def print(*args, **kwargs):
    _old_print(*args, **kwargs)
    _out.write(' '.join(str(a) for a in args) + '\n')
    _out.flush()

# Each entry: (va, length_to_dump, label)
TARGETS = [
    (0x693c4c, 80,  "S_str_conv (C-string -> jstring helper)"),
    (0x6bce9c, 96,  "D0 helper @ 0x6bce9c"),
    (0x6bcaac, 64,  "D1 helper @ 0x6bcaac"),
    (0x6bcabc, 64,  "D2 helper @ 0x6bcabc"),
    (0x6bcacc, 96,  "D3 helper @ 0x6bcacc (takes jstring args)"),
    (0x6bcadc, 96,  "D4 helper @ 0x6bcadc"),
    (0x6bcb9c, 96,  "D5 helper @ 0x6bcb9c"),
    (0x6bcecc, 96,  "D6 helper @ 0x6bcecc (end-of-block)"),
    (0x6bf62c, 96,  "D7 helper @ 0x6bf62c (alt dispatcher)"),
]

def resolve_pc_rel(ins):
    """If the instruction is a PC-relative ldr, resolve and return literal value as string annot."""
    if ins.mnemonic in ('ldr','ldr.w') and 'pc, #' in ins.op_str.replace(' ',''):
        try:
            imm = int(ins.op_str.split('#')[-1].rstrip(']'), 0)
            pc_lit = ((ins.address + 4) & ~3) + imm
            off = va_to_off(pc_lit)
            if off and off + 4 <= len(data):
                val = struct.unpack_from('<I', data, off)[0]
                return f'  ;; lit @0x{pc_lit:x} = 0x{val:08x}'
        except: pass
    return ''

for va, length, label in TARGETS:
    o = va_to_off(va)
    if o is None:
        print(f'\n=== {label}  va=0x{va:08x}  (NOT IN PT_LOAD) ===')
        continue
    code = data[o:o + length]
    print()
    print('=' * 72)
    print(f'  {label}')
    print(f'  va=0x{va:08x}  off=0x{o:08x}  len={length}')
    print('=' * 72)
    for ins in md.disasm(code, va):
        annot = ''
        if ins.mnemonic in ('bl','blx'):
            try:
                t = ins.operands[-1]
                if t.type == 2:
                    ta = t.value.imm & ~1
                    nm = sym_by_va.get(ta)
                    if nm: annot = f'  ;; -> {nm}'
                    else:
                        nv, nn = near(ta)
                        if nn: annot = f'  ;; near {nn}+0x{(t.value.imm-nv)&~1:x}'
            except: pass
        annot += resolve_pc_rel(ins)
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic} {ins.op_str}{annot}')
