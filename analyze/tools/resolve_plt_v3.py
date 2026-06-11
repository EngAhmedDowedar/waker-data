"""Manual decode of ARM modimm operand to resolve PLT entries.
Each PLT entry's three instructions encode:
  add ip, pc, #imm12_a (modimm)
  add ip, ip, #imm12_b (modimm)
  ldr pc, [ip, #imm12_c]!  (U bit -> sign of imm12_c)
GOT slot = (plt_va + 8) + value(imm12_a) + value(imm12_b) + signed(imm12_c)
"""
import os, struct

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
def dynsym_at(idx):
    o = do + idx*16
    st_name,st_value,*_ = struct.unpack_from('<IIIBBH',data,o)
    return data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')

rel_plt = secs['.rel.plt']
got_va_to_sym = {}
n = rel_plt[2] // 8
for i in range(n):
    rb = rel_plt[1] + i*8
    r_offset, r_info = struct.unpack_from('<II', data, rb)
    if (r_info & 0xff) == 22:
        got_va_to_sym[r_offset] = dynsym_at(r_info >> 8)

def arm_modimm(w):
    """Decode ARM modified immediate from a 32-bit instruction word's bits[11:0]."""
    imm12 = w & 0xFFF
    rot = (imm12 >> 8) & 0xF
    v   = imm12 & 0xFF
    n   = 2 * rot
    if n == 0:
        return v
    return ((v >> n) | (v << (32 - n))) & 0xFFFFFFFF

VENEERS = [
    (0x693c4c, "S_str_conv"),
    (0x6bce9c, "D0_block_A_first"),
    (0x6bcaac, "D1"),
    (0x6bcabc, "D2"),
    (0x6bcacc, "D3_jstring_args"),
    (0x6bcadc, "D4"),
    (0x6bcb9c, "D5"),
    (0x6bcecc, "D6_block_A_last"),
    (0x6bf62c, "D7_alt"),
]

_out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plt_resolution_v3.txt'), 'w', encoding='utf-8')
def emit(s=''):
    print(s); _out.write(s + '\n'); _out.flush()

emit('Resolution: thumb veneer -> ARM PLT -> GOT slot -> imported symbol')
emit('='*72)
for vva, label in VENEERS:
    vo = va_to_off(vva)
    if vo is None: continue
    veneer_const = struct.unpack_from('<I', data, vo+12)[0]
    signed_v = veneer_const - 0x100000000 if (veneer_const & 0x80000000) else veneer_const
    arm_target = (vva + 16 + signed_v) & 0xFFFFFFFF

    to = va_to_off(arm_target)
    if to is None:
        emit('\n{}  veneer=0x{:08x}  -> 0x{:08x} (UNMAPPED)'.format(label, vva, arm_target))
        continue
    w0 = struct.unpack_from('<I', data, to)[0]
    w1 = struct.unpack_from('<I', data, to+4)[0]
    w2 = struct.unpack_from('<I', data, to+8)[0]
    imm_a = arm_modimm(w0)
    imm_b = arm_modimm(w1)
    # For LDR with writeback, imm12 in bits[11:0], U bit = bit[23]
    imm_c_raw = w2 & 0xFFF
    U_bit = (w2 >> 23) & 1
    imm_c = imm_c_raw if U_bit else -imm_c_raw

    pc1 = arm_target + 8   # PC for the first `add ip, pc, ...`
    got_slot = (pc1 + imm_a + imm_b + imm_c) & 0xFFFFFFFF
    sym = got_va_to_sym.get(got_slot)

    emit('')
    emit('{:30s} veneer=0x{:08x}  ARM PLT=0x{:08x}'.format(label, vva, arm_target))
    emit('  raw words: 0x{:08x}  0x{:08x}  0x{:08x}'.format(w0, w1, w2))
    emit('  imm_a=0x{:x}  imm_b=0x{:x}  imm_c={}'.format(imm_a, imm_b, imm_c))
    emit('  GOT slot = pc(=0x{:x}) + 0x{:x} + 0x{:x} + ({}) = 0x{:08x}'.format(
        pc1, imm_a, imm_b, imm_c, got_slot))
    emit('  -> IMPORTED SYMBOL: {}'.format(sym))
_out.close()
print('---DONE---')
