"""Follow each Thumb->ARM veneer and disasm the actual ARM target.
Veneer layout (each 16 bytes):
  Thumb @ va:
    0x4778 / 0x7847  bx pc
    0xbf00 / 0xc046  nop / mov r8,r8
  ARM @ va+4:
    0xe59fc000  ldr r12, [pc, #0]
    0xe08cf00f  add pc, r12, pc
    .word <offset>      (signed 32-bit)
  ARM target VA = va + 4 + 8 + offset    (8 = ARM pipeline bias for `add pc, r12, pc`)
"""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_ARM, CS_MODE_THUMB

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

md_arm = Cs(CS_ARCH_ARM, CS_MODE_ARM); md_arm.detail = True
md_thumb = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md_thumb.detail = True

VENEERS = [
    (0x693c4c, "S_str_conv (C-string -> jstring)"),
    (0x6bce9c, "D0 @ 0x6bce9c"),
    (0x6bcaac, "D1 @ 0x6bcaac"),
    (0x6bcabc, "D2 @ 0x6bcabc"),
    (0x6bcacc, "D3 @ 0x6bcacc"),
    (0x6bcadc, "D4 @ 0x6bcadc"),
    (0x6bcb9c, "D5 @ 0x6bcb9c"),
    (0x6bcecc, "D6 @ 0x6bcecc"),
    (0x6bf62c, "D7 @ 0x6bf62c"),
]

_out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dispatchers_arm_out.txt'), 'w', encoding='utf-8')
def emit(s=''):
    print(s)
    _out.write(s + '\n')
    _out.flush()

for vva, label in VENEERS:
    vo = va_to_off(vva)
    if vo is None:
        emit(f'\n=== {label} (VA NOT IN PT_LOAD) ===')
        continue
    bx = struct.unpack_from('<H', data, vo)[0]
    nop = struct.unpack_from('<H', data, vo+2)[0]
    ldr = struct.unpack_from('<I', data, vo+4)[0]
    addp = struct.unpack_from('<I', data, vo+8)[0]
    const = struct.unpack_from('<I', data, vo+12)[0]
    if bx != 0x4778 or (ldr & 0xfffff000) != 0xe59fc000 or addp != 0xe08cf00f:
        emit(f'\n=== {label}  va=0x{vva:08x}  UNEXPECTED VENEER ENCODING ===')
        emit(f'  raw: bx=0x{bx:04x} nop=0x{nop:04x} ldr=0x{ldr:08x} addp=0x{addp:08x} const=0x{const:08x}')
        continue
    arm_at = vva + 4
    if const & 0x80000000: signed_const = const - 0x100000000
    else: signed_const = const
    target_arm = (arm_at + 8 + signed_const) & 0xFFFFFFFF
    nv, nn = near(target_arm)

    emit('')
    emit('='*72)
    emit(f'  {label}')
    emit(f'  veneer va=0x{vva:08x}  ARM target=0x{target_arm:08x}  (offset 0x{const:08x})')
    if nn: emit(f'  nearest preceding symbol: {nn} (@0x{nv:08x}, +0x{target_arm-nv:x})')
    emit('='*72)
    to = va_to_off(target_arm)
    if to is None:
        emit('  TARGET NOT MAPPED')
        continue
    code = data[to:to+0x100]
    for ins in md_arm.disasm(code, target_arm):
        annot = ''
        if ins.mnemonic in ('bl','blx','b'):
            try:
                t = ins.operands[-1]
                if t.type == 2:
                    ta = t.value.imm
                    nm = sym_by_va.get(ta & ~1)
                    if nm: annot = f'  ;; -> {nm}'
                    else:
                        nv2, nn2 = near(ta & ~1)
                        if nn2: annot = f'  ;; near {nn2}+0x{(ta-nv2)&~1:x}'
            except: pass
        if ins.mnemonic == 'ldr' and 'pc' in ins.op_str:
            # try pc-relative literal
            try:
                imm = int(ins.op_str.split('#')[-1].rstrip(']'), 0)
                pc = ins.address + 8
                la = pc + imm
                lo = va_to_off(la)
                if lo and lo + 4 <= len(data):
                    val = struct.unpack_from('<I', data, lo)[0]
                    annot += f'  ;; lit @0x{la:x} = 0x{val:08x}'
            except: pass
        emit(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic} {ins.op_str}{annot}')
        # stop at a return-like instruction (bx lr, mov pc,lr, pop {...,pc})
        if (ins.mnemonic == 'bx' and 'lr' in ins.op_str) or \
           (ins.mnemonic in ('mov',) and 'pc, lr' in ins.op_str) or \
           ('pc}' in ins.op_str and ins.mnemonic in ('pop','ldm','ldmia','ldmfd','ldmdb','ldmib','ldmda')):
            break
_out.close()
print('---DONE---')
