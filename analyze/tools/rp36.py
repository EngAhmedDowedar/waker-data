import struct,bisect
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
data=open('../lib/armeabi/libcity_ar.so','rb').read()
ph=struct.unpack_from('<I',data,0x1c)[0]; pn=struct.unpack_from('<H',data,0x2c)[0]; pe=struct.unpack_from('<H',data,0x2a)[0]
segs=[struct.unpack_from('<8I',data,ph+i*pe) for i in range(pn)]
def va2off(va):
    for t,off,vb,_,fsz,msz,*_ in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)
sh=struct.unpack_from('<I',data,0x20)[0]; sn=struct.unpack_from('<H',data,0x30)[0]; se=struct.unpack_from('<H',data,0x2e)[0]; sx=struct.unpack_from('<H',data,0x32)[0]
shstr=struct.unpack_from('<I',data,sh+sx*se+0x10)[0]; sec={}
for i in range(sn):
    nm,ty,fl,ad,of,szz,*_=struct.unpack_from('<10I',data,sh+i*se); sec[data[shstr+nm:].split(b'\0',1)[0].decode()]=dict(addr=ad,off=of,size=szz)
ds=sec['.dynsym']; dt=sec['.dynstr']; syms=[]; sbn={}
for i in range(ds['size']//16):
    o=ds['off']+i*16; n,v,szz,*_=struct.unpack_from('<IIIBBH',data,o); nm=data[dt['off']+n:].split(b'\0',1)[0].decode('ascii','replace')
    if nm and v: syms.append((v&~1,szz,nm)); sbn[nm]=(v,szz)
syms.sort(); addrs=[s[0] for s in syms]
def near(va):
    i=bisect.bisect_right(addrs,va)-1
    if i<0: return hex(va)
    a,z,nm=syms[i]; return f"{nm}+0x{va-a:x}" if va-a<0x3000 else hex(va)
mT=Cs(CS_ARCH_ARM,CS_MODE_THUMB); mT.detail=True
def disfn(name,L=None):
    if name not in sbn: print(f"[{name} MISSING]"); return
    v,szz=sbn[name]; base=v&~1; o=va2off(base); ln=L or szz
    print(f"\n=== {name} 0x{base:08x} ===")
    for ins in mT.disasm(data[o:o+ln],base):
        an=''
        if ins.mnemonic in('bl','blx') and ins.operands and ins.operands[-1].type==2:
            an=' -> '+near(ins.operands[-1].value.imm&~1)
        print(f"  +0x{ins.address-base:03x} {ins.mnemonic:<6} {ins.op_str}{an}")
disfn('_ZN9CProperty4ReadEP12ngFileReader')
