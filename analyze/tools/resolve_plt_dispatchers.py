"""Resolve each Thumb veneer -> ARM PLT entry -> imported JNI symbol.

Layout:
  Thumb veneer @ rva ->
  ARM PLT entry @ rva' (computes GOT slot via add ip,pc,#K + add ip,ip,#H + ldr pc,[ip,#L]!) ->
  GOT slot holds runtime-resolved address of imported symbol named in .rel.plt
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
# Parse dynsym fully (we want imported names too)
def dynsym_at(idx):
    o = do + idx*16
    st_name,st_value,st_size,st_info,st_other,st_shndx = struct.unpack_from('<IIIBBH',data,o)
    nm = data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    return nm, st_value, st_size, st_shndx

# Parse .rel.plt: each entry is R_ARM_JUMP_SLOT (type 22)
# r_offset = the GOT slot VA to fill
# r_info = sym_idx<<8 | type
rel_plt = secs.get('.rel.plt')
print(f'.rel.plt @ off=0x{rel_plt[1]:x} size=0x{rel_plt[2]:x}')
got_va_to_sym = {}
n = rel_plt[2] // 8
for i in range(n):
    rb = rel_plt[1] + i*8
    r_offset, r_info = struct.unpack_from('<II', data, rb)
    r_type = r_info & 0xff
    r_sym = r_info >> 8
    if r_type == 22:  # R_ARM_JUMP_SLOT
        nm, _, _, _ = dynsym_at(r_sym)
        got_va_to_sym[r_offset] = nm
print(f'parsed {len(got_va_to_sym)} JUMP_SLOT entries')

# For each veneer, decode the ARM PLT it jumps to, then decode the PLT entry
# arithmetic to get the GOT slot VA, then look up symbol.
VENEERS = [
    (0x693c4c, "S_str_conv"),
    (0x6bce9c, "D0"),
    (0x6bcaac, "D1"),
    (0x6bcabc, "D2"),
    (0x6bcacc, "D3 (jstring args in nativeRender)"),
    (0x6bcadc, "D4"),
    (0x6bcb9c, "D5"),
    (0x6bcecc, "D6"),
    (0x6bf62c, "D7"),
]

def decode_plt(arm_va):
    """ARM PLT entry:
       add ip, pc, #imm_a, rot=12   ; ip = pc + (imm_a << 20)
       add ip, ip, #imm_b           ; ip += imm_b
       ldr pc, [ip, #imm_c]!        ; ip += imm_c, jump to *ip
    """
    o = va_to_off(arm_va)
    if o is None: return None
    w0 = struct.unpack_from('<I', data, o)[0]
    w1 = struct.unpack_from('<I', data, o+4)[0]
    w2 = struct.unpack_from('<I', data, o+8)[0]
    # ARM add immediate: <cond> 0010100 S Rn Rd rotate imm8
    # We parse out the immediate values; use ARM's modified-immediate encoding
    def arm_modimm(w):
        imm12 = w & 0xFFF
        rot = (imm12 >> 8) & 0xF
        v = imm12 & 0xFF
        return ((v >> (2*rot)) | (v << (32 - 2*rot))) & 0xFFFFFFFF
    imm_a = arm_modimm(w0)
    imm_b = arm_modimm(w1)
    # ldr pc, [ip, #imm_c]!  : imm12 is bits[11:0], U bit is bit[23]
    imm_c = w2 & 0xFFF
    U = (w2 >> 23) & 1
    if U == 0: imm_c = -imm_c
    # pc-at-execution of `add ip, pc, #...` is arm_va + 8
    pc1 = arm_va + 8
    ip_after_first = pc1 + imm_a
    ip_after_second = ip_after_first + imm_b
    got_slot_va = ip_after_second + imm_c
    return dict(arm_va=arm_va, w=(w0,w1,w2),
                imm_a=imm_a, imm_b=imm_b, imm_c=imm_c,
                got_slot_va=got_slot_va)

_out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plt_resolution.txt'), 'w', encoding='utf-8')
def emit(s=''):
    print(s)
    _out.write(s + '\n')
    _out.flush()

emit('PLT resolution of nativeRender dispatcher helpers')
emit('='*72)
for vva, label in VENEERS:
    vo = va_to_off(vva)
    if vo is None:
        emit(f'\n{label} (va=0x{vva:08x}): NOT MAPPED')
        continue
    # Veneer ARM offset is at vva+4..+15
    const = struct.unpack_from('<I', data, vo+12)[0]
    if const & 0x80000000: signed = const - 0x100000000
    else: signed = const
    arm_target = (vva + 4 + 8 + signed) & 0xFFFFFFFF
    plt = decode_plt(arm_target)
    if not plt:
        emit(f'\n{label} veneer=0x{vva:08x}  arm_target=0x{arm_target:08x} (no map)')
        continue
    got = plt['got_slot_va']
    sym = got_va_to_sym.get(got)
    emit('')
    emit(f'{label}  thumb_veneer=0x{vva:08x}  arm_plt=0x{arm_target:08x}  got_slot=0x{got:08x}')
    emit(f'  PLT raw: 0x{plt["w"][0]:08x} 0x{plt["w"][1]:08x} 0x{plt["w"][2]:08x}')
    emit(f'  PLT decoded: ip = pc(+8) + 0x{plt["imm_a"]:x} + 0x{plt["imm_b"]:x} + 0x{plt["imm_c"]:x} = 0x{got:08x}')
    emit(f'  IMPORTED SYMBOL: {sym}')
_out.close()
print('---DONE---')
