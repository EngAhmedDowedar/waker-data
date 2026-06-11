import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
data=open('../lib/armeabi/libcity_ar.so','rb').read()
ph=struct.unpack_from('<I',data,0x1c)[0]; pn=struct.unpack_from('<H',data,0x2c)[0]; pe=struct.unpack_from('<H',data,0x2a)[0]
segs=[struct.unpack_from('<8I',data,ph+i*pe) for i in range(pn)]
def va2off(va):
    for t,off,vb,_,fsz,msz,*_ in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)
def cstr(va,m=40):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    if s and 2<=len(s)<=34 and all(48<=b<123 or b in (45,95) for b in s) and any(97<=b<123 or 65<=b<91 for b in s):
        try: return s.decode('ascii')
        except: return None
    return None
mT=Cs(CS_ARCH_ARM,CS_MODE_THUMB); mT.detail=True
def scan(base,L,label,BASE=0x75ab20):
    o=va2off(base); out=[]; ss=set()
    for ins in mT.disasm(data[o:o+L],base):
        if ins.mnemonic.startswith('ldr') and '[pc' in ins.op_str:
            try:
                imm=int(ins.op_str.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; V=struct.unpack_from('<I',data,va2off(lit))[0]
            except: continue
            Vs=V-0x100000000 if V&0x80000000 else V
            for cand in (BASE+Vs, V):
                s=cstr(cand&0xFFFFFFFF)
                if s and s not in ss:
                    ss.add(s); out.append((ins.address-base,s)); break
    print(f"{label}: {len(out)} candidate field strings (base=0x{BASE:x})")
    for off,s in out: print(f"  +0x{off:04x} {s}")
scan(0x5140bc,0x2018,"CPlayer::Parse")
print()
scan(0x4498d8,0x37c,"CHouse::Parse")
scan(0x40cc70,0x198,"CGoods::Parse")
scan(0x51f67c,0x10c,"CProperty::Parse")
scan(0x516c3e,0x72,"CPlayer::ParseHouses")
scan(0x516180,0x14,"CPlayer::ParseGoods")
scan(0x4c2fe8,0xd4,"CMarketCateScreen::ParseGoodsAmount")
print()
scan(0x468ef8,0x1e84,"CImpart::ParseImpart")
