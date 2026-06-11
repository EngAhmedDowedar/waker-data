"""
Trace where this+0x2AC is written in CLoadingScreen::OnReceiveResponse
to confirm the state-byte semantics ('1 = update available').
Also identify the helper 0x693b7c that CheckUpdate calls — what singleton
does it return?
"""
import struct, os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

SO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', 'lib', 'armeabi', 'libcity_ar.so')
data = open(SO, 'rb').read()

e_phoff = struct.unpack_from('<I', data, 0x1c)[0]
e_phentsize = struct.unpack_from('<H', data, 0x2a)[0]
e_phnum = struct.unpack_from('<H', data, 0x2c)[0]
segs = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    t, off, va, _, fsz, msz, *_ = struct.unpack_from('<8I', data, o)
    segs.append((t, off, va, fsz, msz))
def va_to_off(va):
    for t, off, vb, fsz, msz in segs:
        if t == 1 and vb <= va < vb + msz:
            return off + (va - vb)

e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize = struct.unpack_from('<H', data, 0x2e)[0]
e_shnum = struct.unpack_from('<H', data, 0x30)[0]
e_shstrndx = struct.unpack_from('<H', data, 0x32)[0]
shstrtab_hdr_off = e_shoff + e_shstrndx * e_shentsize
sh_offset_str = struct.unpack_from('<I', data, shstrtab_hdr_off + 0x10)[0]
sections = []
for i in range(e_shnum):
    base = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, *_ = \
        struct.unpack_from('<10I', data, base)
    name = data[sh_offset_str + sh_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    sections.append(dict(name=name, addr=sh_addr, off=sh_offset, size=sh_size, type=sh_type))
def sec(n):
    for s in sections:
        if s['name'] == n: return s
dynsym = sec('.dynsym'); dynstr = sec('.dynstr')
symbols = {}
sym_by_va = {}
for i in range(dynsym['size'] // 16):
    so = dynsym['off'] + i * 16
    st_name, st_value, st_size, *_ = struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off'] + st_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    if nm:
        symbols[nm] = (st_value, st_size)
        sym_by_va[st_value & ~1] = nm

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True

def disasm_func(va, n):
    o = va_to_off(va & ~1)
    code = data[o:o+n]
    for ins in md.disasm(code, va & ~1):
        # annotate this+0x2AC stores / loads
        op = ins.op_str
        annot = ''
        if ins.mnemonic in ('strb', 'ldrb') and ('#0x2ac' in op or '#684' in op):
            annot = '  ;; this+0x2AC'
        if ins.mnemonic in ('bl', 'blx'):
            try:
                tgt = ins.operands[-1]
                if tgt.type == 2:
                    nm = sym_by_va.get(tgt.value.imm & ~1)
                    if nm: annot = f'  ;; -> {nm}'
            except: pass
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic} {op}{annot}')

# OnReceiveResponse for CLoadingScreen
key = '_ZN14CLoadingScreen17OnReceiveResponseEiPv'
va, sz = symbols.get(key, (None, None))
print(f'=== CLoadingScreen::OnReceiveResponse va=0x{va:08x} size={sz} ===')
if va:
    disasm_func(va, sz or 0x400)

# Show what 0x693b7c is by looking at nearest preceding sym
def near(va):
    best=None
    for s in sorted(sym_by_va):
        if s > va: break
        best=s
    return best, sym_by_va.get(best)
print('\n0x693b7c context:')
v, n = near(0x693b7c)
print(f'  nearest preceding sym: 0x{v:08x} {n}')
# Disasm a bit of 0x693b7c
print('  disasm 0x693b7c (24 bytes):')
disasm_func(0x693b7c, 24)
