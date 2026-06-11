"""Use Capstone to disasm each ARM PLT entry properly, extract the absolute
GOT slot from its operands, then map to imported symbol via .rel.plt.
"""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM

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
    st_name,st_value,st_size,st_info,st_other,st_shndx = struct.unpack_from('<IIIBBH',data,o)
    return data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')

# Parse .rel.plt
rel_plt = secs['.rel.plt']
got_va_to_sym = {}
n = rel_plt[2] // 8
for i in range(n):
    rb = rel_plt[1] + i*8
    r_offset, r_info = struct.unpack_from('<II', data, rb)
    if (r_info & 0xff) == 22:
        got_va_to_sym[r_offset] = dynsym_at(r_info >> 8)

# Dump first few entries to debug
print('First 10 .rel.plt entries:')
for i in range(min(10, n)):
    rb = rel_plt[1] + i*8
    r_offset, r_info = struct.unpack_from('<II', data, rb)
    print('  r_offset=0x{:08x}  r_info=0x{:08x}  type={}  sym={}'.format(
        r_offset, r_info, r_info & 0xff, dynsym_at(r_info >> 8)))
print('total .rel.plt entries: {}'.format(n))
print()

md = Cs(CS_ARCH_ARM, CS_MODE_ARM); md.detail = True

VENEERS = [
    (0x693c4c, "S_str_conv"),
    (0x6bce9c, "D0"),
    (0x6bcaac, "D1"),
    (0x6bcabc, "D2"),
    (0x6bcacc, "D3"),
    (0x6bcadc, "D4"),
    (0x6bcb9c, "D5"),
    (0x6bcecc, "D6"),
    (0x6bf62c, "D7"),
]

_out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'plt_resolution_v2.txt'), 'w', encoding='utf-8')
def emit(s=''):
    print(s)
    _out.write(s + '\n'); _out.flush()

# Tracking: for each veneer, find the actual ARM target, then trust Capstone's
# decoded immediates to compute the GOT slot.
for vva, label in VENEERS:
    vo = va_to_off(vva)
    if vo is None: continue
    const = struct.unpack_from('<I', data, vo+12)[0]
    signed = const - 0x100000000 if (const & 0x80000000) else const
    # corrected ARM target: add_pc instruction is at vva+8, its PC is vva+16
    arm_target = (vva + 16 + signed) & 0xFFFFFFFF
    emit('')
    emit('='*72)
    emit('{}  thumb_veneer=0x{:08x}  ARM target=0x{:08x}'.format(label, vva, arm_target))
    emit('='*72)
    to = va_to_off(arm_target)
    if to is None:
        emit('  TARGET NOT MAPPED')
        continue
    # Disasm 3 instructions of the PLT entry
    code = data[to:to+12]
    insns = list(md.disasm(code, arm_target))
    if len(insns) < 3:
        emit('  partial disasm: {}'.format(insns))
        continue
    ip_val = arm_target + 8  # pc at execution of first add
    for ins in insns:
        emit('  0x{:08x}: {} {}'.format(ins.address, ins.mnemonic, ins.op_str))
    # Manually compute GOT slot from operands
    try:
        # ins[0]: add ip, pc, #imm_a   -> ip = arm_target + 8 + imm_a
        # ins[1]: add ip, ip, #imm_b   -> ip += imm_b
        # ins[2]: ldr pc, [ip, #imm_c]! -> ip += imm_c (writeback); pc = *ip
        def imm_of(ins):
            for op in ins.operands:
                if op.type == 2:  # ARM_OP_IMM
                    return op.value.imm
            return None
        imm_a = imm_of(insns[0])
        imm_b = imm_of(insns[1])
        imm_c = imm_of(insns[2])
        # The third instruction is ldr with possibly a negative imm; treat sign via U bit
        # but Capstone usually returns signed value
        emit('  imm_a={} imm_b={} imm_c={}'.format(imm_a, imm_b, imm_c))
        got_slot = (arm_target + 8 + imm_a + imm_b + imm_c) & 0xFFFFFFFF
        sym = got_va_to_sym.get(got_slot)
        emit('  GOT slot = 0x{:08x}    IMPORTED SYMBOL: {}'.format(got_slot, sym))
        # If sym is None, try +/- the imm_c
        if sym is None:
            for delta in (-imm_c*2, imm_c*2, -4, 4):
                cand = (got_slot + delta) & 0xFFFFFFFF
                if cand in got_va_to_sym:
                    emit('    (delta {:+}: 0x{:08x} -> {})'.format(delta, cand, got_va_to_sym[cand]))
    except Exception as e:
        emit('  decode err: {}'.format(e))

_out.close()
print('---DONE---')
