import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
data=open('../lib/armeabi/libcity_ar.so','rb').read()
ph=struct.unpack_from('<I',data,0x1c)[0]; pn=struct.unpack_from('<H',data,0x2c)[0]; pe=struct.unpack_from('<H',data,0x2a)[0]
segs=[struct.unpack_from('<8I',data,ph+i*pe) for i in range(pn)]
def va2off(va):
    for t,off,vb,_,fsz,msz,*_ in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)
def cstr(va,m=48):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    return s.decode('ascii','replace') if s and 2<=len(s)<=40 and all(32<=b<127 for b in s) else None
PIC=0x75ab20; mT=Cs(CS_ARCH_ARM,CS_MODE_THUMB); mT.detail=True
base=0x5140bc; L=0x2018; o=va2off(base); litreg={}; seen=[]
for ins in mT.disasm(data[o:o+L],base):
    op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]
    if mn.startswith('ldr') and 'pc' in op and '[' in op:
        try:
            imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; litreg[parts[0]]=struct.unpack_from('<I',data,va2off(lit))[0]
        except: pass
    if mn in('add','adds','add.w') and len(parts)==3 and parts[1] in litreg:
        sv=litreg[parts[1]]; sv=sv-0x100000000 if sv&0x80000000 else sv; s=cstr((PIC+sv)&0xFFFFFFFF)
        if s and any(c.isalpha() for c in s) and ' ' not in s:
            seen.append(s)
# dedup preserving order
out=[]; ss=set()
for s in seen:
    if s not in ss: ss.add(s); out.append(s)
print(f"CPlayer::Parse field strings: {len(out)} unique")
for i in range(0,len(out),6):
    print("  "+'  '.join(out[i:i+6]))
