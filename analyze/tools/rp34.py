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
    if s and 2<=len(s)<=36 and all(32<=b<127 for b in s) and any(chr(b).isalpha() for b in s) and ' ' not in s.decode('latin1'):
        return s.decode('ascii','replace')
    return None
mT=Cs(CS_ARCH_ARM,CS_MODE_THUMB); mT.detail=True
def extract(base,L,label):
    o=va2off(base); reg={}; out=[]; ss=set()
    for ins in mT.disasm(data[o:o+L],base):
        mn=ins.mnemonic; op=ins.op_str; parts=[p.strip() for p in op.split(',')]
        if mn.startswith('ldr') and '[pc' in op:
            try:
                imm=int(parts[1].split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm
                reg[parts[0]]=('off',struct.unpack_from('<I',data,va2off(lit))[0])
            except: reg.pop(parts[0],None)
        elif mn in('add','add.w') and len(parts)==2 and parts[1]=='pc':
            r=parts[0]
            if reg.get(r,('',0))[0]=='off':
                reg[r]=('abs',(ins.address+4)+reg[r][1])
            else: reg.pop(r,None)
        elif mn in('adds','add','add.w') and len(parts)==3:
            a,b=reg.get(parts[1]),reg.get(parts[2])
            res=None
            if a and a[0]=='off' and b and b[0]=='abs': res=b[1]+a[1]
            elif a and a[0]=='abs' and b and b[0]=='off': res=a[1]+b[1]
            if res is not None:
                s=cstr(res&0xFFFFFFFF)
                reg[parts[0]]=('str',res)
                if s and s not in ss: ss.add(s); out.append(s)
            else: reg.pop(parts[0],None)
        else:
            # clobber dst reg of other ops
            if parts and parts[0] in reg and mn not in('cmp','cmn','tst','str','strb','strh','push','pop','b','bl','blx','bne','beq','bgt','blt','cbz','cbnz'):
                reg.pop(parts[0],None)
    print(f"{label}: {len(out)} fields")
    for i in range(0,len(out),6): print("  "+'  '.join(out[i:i+6]))
extract(0x5140bc,0x2018,"CPlayer::Parse")
