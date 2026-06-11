"""Disassemble Java_com_anansimobile_nge_NDKRenderer_nativeRender and resolve every BL/BLX target."""
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

md=Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail=True
start_va = 0x005f4710
end_va = start_va + 476
o = va_to_off(start_va)
code = data[o:o+(end_va-start_va)]
print('Disassembly: Java_com_anansimobile_nge_NDKRenderer_nativeRender')
print('  va=0x{:08x}  size={}'.format(start_va, 476))
print()
for ins in md.disasm(code, start_va):
    annot = ''
    if ins.mnemonic in ('bl','blx'):
        try:
            t = ins.operands[-1]
            if t.type == 2:
                ta = t.value.imm & ~1
                nm = sym_by_va.get(ta)
                if nm: annot = '  ;; -> {}'.format(nm)
                else:
                    nv, nn = near(ta)
                    if nn: annot = '  ;; near {}+0x{:x}'.format(nn, (t.value.imm - nv) & ~1)
        except: pass
    print('  0x{:08x}: {:<8} {} {}{}'.format(ins.address, ins.bytes.hex(), ins.mnemonic, ins.op_str, annot))
