import struct,bisect
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
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
ds=sec['.dynsym']; dt=sec['.dynstr']; syms=[]
for i in range(ds['size']//16):
    o=ds['off']+i*16; n,v,szz,*_=struct.unpack_from('<IIIBBH',data,o); nm=data[dt['off']+n:].split(b'\0',1)[0].decode('ascii','replace')
    if nm and v: syms.append((v&~1,szz,nm))
syms.sort(); addrs=[s[0] for s in syms]
def near(va):
    i=bisect.bisect_right(addrs,va)-1
    if i<0: return hex(va)
    a,z,nm=syms[i]; return f"{nm}+0x{va-a:x}" if va-a<0x2500 else hex(va)
mA=Cs(CS_ARCH_ARM,CS_MODE_ARM)
def follow(t):
    base=t&~1; o=va2off(base); raw=data[o:o+16]
    ins=list(mA.disasm(data[va2off(base+4):va2off(base+4)+12],base+4))
    if ins and ins[0].mnemonic=='ldr' and 'ip, [pc' in ins[0].op_str:
        W=struct.unpack_from('<I',data,va2off(base+0xc))[0]; return (W+base+0x10)&0xFFFFFFFE
    return None
tgt=follow(0x693ecc)
print(f"0x693ecc -> {hex(tgt) if tgt else '?'}  ({near(tgt&~1) if tgt else ''})")
def cstr(va,m=34):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    if s and 2<=len(s)<=32 and all(48<=b<123 or b in(45,95) for b in s) and (97<=s[0]<123 or 65<=s[0]<91):
        try: return s.decode('ascii')
        except: return None
def scan(base,L,label):
    o=va2off(base); out=[]; ss=set()
    for k in range(0,L-3,2):
        V=struct.unpack_from('<I',data,o+k)[0]; Vs=V-0x100000000 if V&0x80000000 else V
        if -0x80000<=Vs<=0x80000:
            s=cstr((0x75ab20+Vs)&0xFFFFFFFF)
            if s and s not in ss and len(s)>=2: ss.add(s); out.append(s)
    print(f"\n{label} 0x{base:08x}: {len(out)} fields")
    for i in range(0,len(out),6): print("  "+'  '.join(out[i:i+6]))
if tgt:
    sz=next((z for a,z,nm in syms if (a==(tgt&~1))),0x600)
    scan(tgt&~1, sz or 0x600, "fighter/role parse")
