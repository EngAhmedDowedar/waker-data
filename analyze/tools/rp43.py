import struct
data=open('../lib/armeabi/libcity_ar.so','rb').read()
ph=struct.unpack_from('<I',data,0x1c)[0]; pn=struct.unpack_from('<H',data,0x2c)[0]; pe=struct.unpack_from('<H',data,0x2a)[0]
segs=[struct.unpack_from('<8I',data,ph+i*pe) for i in range(pn)]
def va2off(va):
    for t,off,vb,_,fsz,msz,*_ in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)
def cstr(va,m=34):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    if s and 2<=len(s)<=32 and all(48<=b<123 or b in(45,95) for b in s) and (97<=s[0]<123 or 65<=s[0]<91):
        try: return s.decode('ascii')
        except: return None
    return None
BASE=0x75ab20
def scan(base,L,label):
    o=va2off(base); out=[]; ss=set()
    for k in range(0,L-3,2):
        V=struct.unpack_from('<I',data,o+k)[0]; Vs=V-0x100000000 if V&0x80000000 else V
        if -0x80000<=Vs<=0x80000:
            s=cstr((BASE+Vs)&0xFFFFFFFF)
            if s and s not in ss and len(s)>=2: ss.add(s); out.append(s)
    print(f"\n{label}: {len(out)} fields")
    for i in range(0,len(out),6): print("  "+'  '.join(out[i:i+6]))
scan(0x3ee774,0xc8,"CFightingScreen::ParseFighters (randomfighters)")
scan(0x3ed040,0x680,"CFightSimulate::ParseFighterInfo")
scan(0x3ed6f4,0x5d0,"CFightSimulate::ParseFighterInfoNew")
