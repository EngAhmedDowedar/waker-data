"""
Extend the prior pass:
  (A) full disasm of opcode 0x80 handler from 0x48ff20 through 0x49036c
      (the function's bail-end and the success path 0x48ff28+)
  (B) Thumb-2 32-bit encodings reading/writing this+0x2AC inside
      CLoadingScreen, to confirm (or refute) the "state byte is always 0"
      observation
  (C) resolve the pc-relative literals at 0x48fef6 / 0x48fefa
      (the global object the success path touches)
"""
import os, struct
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
    for t, off, vb, _, msz in segs:
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
    sh_name, sh_type, _, sh_addr, sh_off, sh_size, *_ = \
        struct.unpack_from('<10I', data, base)
    name = data[sh_offset_str + sh_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    sections.append(dict(name=name, addr=sh_addr, off=sh_off, size=sh_size))
def sec(n):
    for s in sections:
        if s['name'] == n: return s
dynsym = sec('.dynsym'); dynstr = sec('.dynstr')
sym_by_va = {}; symbols = {}
for i in range(dynsym['size']//16):
    so = dynsym['off']+i*16
    st_name, st_value, st_size, *_ = struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm:
        symbols[nm] = (st_value, st_size)
        sym_by_va[st_value & ~1] = nm
def nearest_sym(va):
    best=None
    for s in sorted(sym_by_va):
        if s > va: break
        best=s
    return best, sym_by_va.get(best)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True

# ============================================================
# (A) Disasm 0x48ff20 .. 0x49036c
# ============================================================
print('='*72)
print('(A) opcode-0x80 handler continuation, 0x48ff20 .. 0x49036c')
print('='*72)
start, end = 0x48ff20, 0x49036c + 16
o = va_to_off(start)
code = data[o:o + (end-start)]

for ins in md.disasm(code, start):
    annot = ''
    if ins.mnemonic in ('bl','blx'):
        try:
            t = ins.operands[-1]
            if t.type == 2:
                nm = sym_by_va.get(t.value.imm & ~1)
                if nm: annot = f'  ;; -> {nm}'
                else:
                    nv, nn = nearest_sym(t.value.imm & ~1)
                    if nn: annot = f'  ;; near {nn}+0x{(t.value.imm-nv)&~1:x}'
        except: pass
    op = ins.op_str
    if '#0x2ac' in op.lower() or '#684' in op: annot += '  ;; this+0x2AC'
    if 'pc, #' in op and ins.mnemonic in ('ldr','ldr.w'):
        try:
            ofs_str = op.split('#')[-1].rstrip(']')
            imm = int(ofs_str, 0)
            pc_lit = ((ins.address + 4) & ~3) + imm
            litoff = va_to_off(pc_lit)
            if litoff and litoff + 4 <= len(data):
                val = struct.unpack_from('<I', data, litoff)[0]
                annot += f'  ;; lit @0x{pc_lit:x} = 0x{val:08x}'
        except: pass
    print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic} {op}{annot}')
    if ins.address >= 0x49036c + 8:
        break

# ============================================================
# (B) Thumb-2 32-bit accessors to this+0x2AC inside CLoadingScreen funcs
#     Pattern: F8 D? im im  ldr.w  Rt,[Rn,#imm12]  for ldrw imm12=0x2AC -> 0x2AC = bytes (F8 D? AC 2..)
#     STRB-imm.w T3: F8 8N im im
#     LDRB-imm.w T3: F8 9N im im
#     also alt: F8 0N im im STRB negative... we focus on T3 forms with imm12 directly.
# ============================================================
print()
print('='*72)
print('(B) Thumb-2 32-bit LDR/STR/LDRB/STRB with imm12=0x2AC anywhere in .text')
print('='*72)

text = sec('.text')
text_off = text['off']; text_va = text['addr']; text_size = text['size']

def t2_imm12_match(hw1, hw2):
    # returns (mnemonic, Rt, Rn, imm12) if it is a Thumb-2 STRB/LDRB/STR/LDR with imm12 form, else None
    # encodings:
    #   STRB.w imm12   1111 1000 1000 Rn   Rt imm12       -> hw1=0xF88x, hw2= Rt<<12 | imm12
    #   LDRB.w imm12   1111 1000 1001 Rn
    #   STR.w  imm12   1111 1000 1100 Rn
    #   LDR.w  imm12   1111 1000 1101 Rn
    #   STRH.w imm12   1111 1000 1010 Rn
    #   LDRH.w imm12   1111 1000 1011 Rn
    if (hw1 & 0xFFF0) == 0xF880: mnemonic = 'strb.w'
    elif (hw1 & 0xFFF0) == 0xF890: mnemonic = 'ldrb.w'
    elif (hw1 & 0xFFF0) == 0xF8C0: mnemonic = 'str.w'
    elif (hw1 & 0xFFF0) == 0xF8D0: mnemonic = 'ldr.w'
    elif (hw1 & 0xFFF0) == 0xF8A0: mnemonic = 'strh.w'
    elif (hw1 & 0xFFF0) == 0xF8B0: mnemonic = 'ldrh.w'
    else: return None
    Rn = hw1 & 0xF
    Rt = (hw2 >> 12) & 0xF
    imm12 = hw2 & 0xFFF
    return (mnemonic, Rt, Rn, imm12)

hits_t2 = []
for off in range(0, text_size - 4, 2):
    hw1 = struct.unpack_from('<H', data, text_off + off)[0]
    if (hw1 & 0xF800) != 0xF800: continue  # quick skip
    hw2 = struct.unpack_from('<H', data, text_off + off + 2)[0]
    r = t2_imm12_match(hw1, hw2)
    if not r: continue
    mn, Rt, Rn, imm12 = r
    if imm12 == 0x2AC:
        va = text_va + off
        ov, on = nearest_sym(va)
        hits_t2.append((va, mn, Rt, Rn, imm12, ov, on))

print(f'  found {len(hits_t2)} Thumb-2 imm12==0x2AC accesses:')
for va, mn, Rt, Rn, imm12, ov, on in hits_t2:
    print(f'    va=0x{va:08x}  {mn} r{Rt},[r{Rn},#0x{imm12:x}]  '
          f'in {on} (@0x{ov:08x})')

# Filter to CLoadingScreen-related accessors only
cls_va = symbols.get('_ZN14CLoadingScreenC2Eh', (0,0))[0] & ~1
# range of CLoadingScreen methods: approximate by clustering symbols beginning with _ZN14CLoadingScreen
ls_methods = [(v & ~1, sz, k) for k, (v, sz) in symbols.items() if k.startswith('_ZN14CLoadingScreen')]
ls_ranges = [(start_va, start_va + size, name) for start_va, size, name in ls_methods]
ls_writers = []
for va, mn, Rt, Rn, imm12, ov, on in hits_t2:
    if on and on.startswith('_ZN14CLoadingScreen'):
        if mn.startswith('strb') or mn.startswith('str.'):
            ls_writers.append((va, mn, Rt, Rn, on))

print()
print(f'  -> CLoadingScreen STRB-class writers to this+0x2AC: {len(ls_writers)}')
for va, mn, Rt, Rn, on in ls_writers:
    print(f'    va=0x{va:08x}  {mn} r{Rt},[r{Rn},#0x2AC]  in {on}')

# ============================================================
# (C) PC-relative literal resolution at 0x48fef6 / 0x48fefa
# ============================================================
print()
print('='*72)
print('(C) PC-relative literals in opcode-0x80 success path')
print('='*72)

for ldr_va, label in [(0x48fef6, 'ldr r0,[pc,#0x20]  used by adds r0,pc'),
                       (0x48fefa, 'ldr r1,[pc,#0x20]  used by adds r1,r1,r0')]:
    pc_lit = ((ldr_va + 4) & ~3) + 0x20
    o = va_to_off(pc_lit)
    if o is None: continue
    val = struct.unpack_from('<I', data, o)[0]
    # adds r0,pc style: target = (pc_at_add_pc) + val
    # For first ldr (loaded value used by add r0,pc at 0x48fef8), add_pc instr's PC = 0x48fef8+4 = 0x48fefc
    # Target = 0x48fefc + val (sign-extended).
    add_pc_pc = 0x48fefc
    if val & 0x80000000:
        signed_val = val - 0x100000000
    else:
        signed_val = val
    target = (add_pc_pc + signed_val) & 0xFFFFFFFF
    # nearest dynsym
    nv, nn = nearest_sym(target & ~1)
    print(f'  {label}')
    print(f'    literal @0x{pc_lit:08x} = 0x{val:08x}  (signed {signed_val})')
    print(f'    resolved target = 0x{target:08x}  -> near {nn} (@0x{nv:08x})')
