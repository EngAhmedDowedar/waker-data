"""Reverse CTopScreen::ParseSysMsg (+24 crash) + chat parsers; determine
data shape (array begin-iterator vs object GetNode) for /city/chat/* endpoints."""
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
e_shoff=struct.unpack_from('<I',data,0x20)[0]; e_shnum=struct.unpack_from('<H',data,0x30)[0]; e_shes=struct.unpack_from('<H',data,0x2e)[0]; e_shstrndx=struct.unpack_from('<H',data,0x32)[0]
shstr=struct.unpack_from('<I',data,e_shoff+e_shstrndx*e_shes+0x10)[0]
sec={}
for i in range(e_shnum):
    nm,ty,fl,ad,of,sz,*_=struct.unpack_from('<10I',data,e_shoff+i*e_shes)
    name=data[shstr+nm:].split(b'\x00',1)[0].decode('ascii','replace'); sec[name]=dict(addr=ad,off=of,size=sz)
dsym=sec['.dynsym']; dstr=sec['.dynstr']; symbols={}; sym_by_va={}
for i in range(dsym['size']//16):
    so=dsym['off']+i*16; st_name,st_value,st_size,*_=struct.unpack_from('<IIIBBH',data,so)
    nm=data[dstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm: symbols[nm]=(st_value,st_size)
    if nm and st_value: sym_by_va[st_value&~1]=nm
def read_cstr(va,m=48):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\x00',o,o+m+1); e=e if e>=0 else o+m; s=data[o:e]
    return s.decode('ascii','replace') if (len(s)>=1 and all(9<=b<127 for b in s)) else None
def near(va):
    nv=None
    for s in sorted(sym_by_va):
        if s>va: break
        nv=s
    return (sym_by_va[nv],va-nv) if nv is not None and va-nv<0x1500 else (None,0)
PIC=0x75ab20
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def disfn(name=None,va=None,L=None,label=''):
    if va is None: va,sz=symbols.get(name,(0,0))
    else: sz=L or 0
    if not va: print(f"[{name} MISSING]"); return
    start=va&~1; ln=L or sz or 0x90; o=va2off(start); code=data[o:o+ln]
    print(f"\n===== {label or name}  va=0x{start:08x} len=0x{ln:x} =====")
    litreg={}
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
                if lo: litreg[rd]=struct.unpack_from('<I',data,lo)[0]
            except: pass
        if mn in('adds','add') and len(parts)==3 and parts[1] in litreg:
            sv=litreg[parts[1]]; sv=sv-0x100000000 if sv&0x80000000 else sv
            s=read_cstr((PIC+sv)&0xFFFFFFFF)
            if s: an+=f' KEY="{s}"'
        if '#0x14]' in op: an+=' <ARRAY begin-iter(vtbl+0x14)>'
        if '#0x40]' in op: an+=' <OBJECT GetNode(vtbl+0x40)>'
        if mn in('bl','blx') and ins.operands and ins.operands[-1].type==2:
            tv=ins.operands[-1].value.imm&~1; nn,do=near(tv)
            an+=f' -> {sym_by_va.get(tv) or (nn+("+0x%x"%do) if nn else hex(tv))}'
        print(f'  +0x{ins.address-start:02x} {ins.bytes.hex():<8} {mn:<6} {op}{an}')

print("=== ParseSysMsg / chat parser symbols ===")
for nm,(va,sz) in symbols.items():
    if any(k in nm for k in ['ParseSysMsg','ParseTopMsg','ParsePulledMsg','ParseMsg','TopScreen']):
        print(f"  0x{va&~1:08x} sz=0x{sz:x} {nm}")
for c in ['_ZN10CTopScreen11ParseSysMsgEPv','_ZN11CChatScreen11ParseSysMsgEPv']:
    if c in symbols: disfn(c, label=c)
