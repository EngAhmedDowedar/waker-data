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
def cstr(va,m=40):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    return s.decode('ascii','replace') if s and 2<=len(s)<=34 and all(48<=b<123 or b in(45,95) for b in s) and any(97<=b<123 or 65<=b<91 for b in s) else None
mT=Cs(CS_ARCH_ARM,CS_MODE_THUMB); mT.detail=True
def disfn(name,L=None):
    if name not in sbn: print(f"[{name} MISSING]"); return
    v,szz=sbn[name]; base=v&~1; o=va2off(base); ln=L or szz
    print(f"\n=== {name} 0x{base:08x} (sz 0x{ln:x}) ===")
    for ins in mT.disasm(data[o:o+ln],base):
        an=''; op=ins.op_str
        if ins.mnemonic.startswith('ldr') and '[pc' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; V=struct.unpack_from('<I',data,va2off(lit))[0]
                s=cstr((0x75ab20+(V-0x100000000 if V&0x80000000 else V))&0xFFFFFFFF) or cstr(V)
                if s: an+=f' STR="{s}"'
            except: pass
        if ins.mnemonic in('bl','blx') and ins.operands and ins.operands[-1].type==2:
            an+=' -> '+near(ins.operands[-1].value.imm&~1)
        if 'cmp' in ins.mnemonic: an+=' <cmp>'
        print(f"  +0x{ins.address-base:03x} {ins.mnemonic:<6} {op}{an}")
disfn('_ZN11CGameScreen12InitTutorialEih')
disfn('_ZN15CMissionManager11IsNeedGuideEii')
disfn('_ZN15CMissionManager9needGuideEi')
