"""Dump every PIC key string in CHttpClient::ParseResponse @0x467264 (up to the
ParseRoleList call @+478) to find the role-list key + envelope structure.
PIC pattern: ldr rB,[pc]=picoff; add rB,pc (picbase=0x75ab20); ldr rA,[pc]=negoff; adds rD,rA,rB."""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,'..','lib','armeabi','libcity_ar.so'),'rb').read()
e_phoff=struct.unpack_from('<I',data,0x1c)[0]; e_phnum=struct.unpack_from('<H',data,0x2c)[0]; e_phes=struct.unpack_from('<H',data,0x2a)[0]
segs=[]
for i in range(e_phnum):
    t,off,va,_,fsz,msz,*_=struct.unpack_from('<8I',data,e_phoff+i*e_phes); segs.append((t,off,va,msz))
def va2off(va):
    for t,off,vb,msz in segs:
        if t==1 and vb<=va<vb+msz:
            o=off+(va-vb); return o if o<len(data) else None
def read_cstr(va,m=48):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\x00',o,o+m+1); e=e if e>=0 else o+m; s=data[o:e]
    return s.decode('ascii','replace') if (len(s)>=1 and all(9<=b<127 for b in s)) else None
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
start=0x467264; end=0x4674a0; o=va2off(start); code=data[o:o+(end-start)]
litreg={}; picreg={}
print(f"=== ParseResponse keys 0x{start:08x}..0x{end:08x} ===")
for ins in md.disasm(code,start):
    op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
    if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
        try:
            imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
            if lo: litreg[rd]=struct.unpack_from('<I',data,lo)[0]
        except: pass
    if mn in('add','adds','add.w') and parts[-1]=='pc' and rd in litreg:
        picreg[rd]=(ins.address+4+litreg[rd])&0xFFFFFFFF
    if mn in('adds','add','add.w') and len(parts)==3:
        a,b=parts[1],parts[2]; pic=picreg.get(a) or picreg.get(b)
        litr=litreg.get(a) if (a in litreg and b in picreg) else (litreg.get(b) if (b in litreg and a in picreg) else None)
        if pic is not None and litr is not None:
            sv=litr-0x100000000 if litr&0x80000000 else litr; tgt=(pic+sv)&0xFFFFFFFF; s=read_cstr(tgt)
            if s: print(f"  +0x{ins.address-start:03x} @0x{ins.address:08x}  KEY={s!r}")
            picreg[rd]=tgt
