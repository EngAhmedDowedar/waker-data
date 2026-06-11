"""
Codec + key recovery: CMsgCodec::EnCode / GetJsonData (request encode / response
decode) and ngStringHelper::encryptXOR/decryptXOR. Resolves the GCC PIC
two-literal string pattern (picbase set by add rX,pc; string = picbase + signed(lit)).
"""
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
    if nm: symbols[nm]=(st_value,st_size); sym_by_va[st_value&~1]=nm
def read_cstr(va,m=120):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\x00',o,o+m+1); e=e if e>=0 else o+m; s=data[o:e]
    return s.decode('ascii','replace') if (len(s)>=1 and all(9<=b<127 for b in s)) else None
def near(va):
    nv=None
    for s in sorted(sym_by_va):
        if s>va: break
        nv=s
    return (sym_by_va[nv],va-nv) if (nv is not None and va-nv<0x800) else (None,0)
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def disfn(name):
    va,sz=symbols.get(name,(0,0))
    if not va: print(f"[{name} MISSING]"); return
    start=va&~1; ln=sz or 0x200; o=va2off(start); code=data[o:o+ln]
    print(f"\n===== {name}\n      va=0x{start:08x} len=0x{ln:x} =====")
    litreg={}   # reg -> immediate literal value (from ldr pc-rel or movs/mov)
    picreg={}   # reg -> resolved value from add rX,pc
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic
        parts=[p.strip() for p in op.split(',')]
        rd=parts[0] if parts else ''
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
                if lo:
                    val=struct.unpack_from('<I',data,lo)[0]; litreg[rd]=val
                    an+=f'  ; lit=0x{val:08x}'; s=read_cstr(val)
                    if s: an+=f' "{s}"'
            except: pass
        elif mn in('movs','mov') and op.endswith(tuple('0123456789')) and '#' in op:
            try: litreg[rd]=int(op.split('#')[-1],0)
            except: pass
        if mn in('add','adds','add.w') and parts[-1]=='pc':
            if rd in litreg:
                picreg[rd]=(ins.address+4+litreg[rd])&0xFFFFFFFF
                an+=f'  ; picbase=0x{picreg[rd]:08x}'
        # adds rD, rA, rB  where one is picreg and other is litreg(signed) -> string
        if mn in('adds','add','add.w') and len(parts)==3:
            a,b=parts[1],parts[2]
            pic=picreg.get(a) or picreg.get(b)
            litr=None
            if a in litreg and b in picreg: litr=litreg[a]
            elif b in litreg and a in picreg: litr=litreg[b]
            if pic is not None and litr is not None:
                sv=litr-0x100000000 if litr&0x80000000 else litr
                tgt=(pic+sv)&0xFFFFFFFF; s=read_cstr(tgt)
                an+=f'  ; ->0x{tgt:08x}'
                if s: an+=f' "{s}"'
                else:
                    nn,do=near(tgt)
                    if nn: an+=f' {nn}+0x{do:x}'
                picreg[rd]=tgt
        if mn in('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2:
                    tv=t.value.imm; nm2=sym_by_va.get(tv&~1)
                    if nm2: an+=f'  ; -> {nm2}'
                    else:
                        nn,do=near(tv&~1)
                        an+=f'  ; -> {nn}+0x{do:x}' if nn else f'  ; -> 0x{tv:08x}'
            except: pass
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')

for fn in ['_ZN9CMsgCodec6EnCodeE11ENCODE_TYPEP10ngJsonHashP12ngByteBuffer',
           '_ZN9CMsgCodec11GetJsonDataEP12ngByteBufferiPP10ngJsonHash',
           '_ZN9CMsgCodec17GetJsonDataSingleEP12ngByteBufferPP10ngJsonHash',
           '_ZN14ngStringHelper10encryptXOREPKcS1_',
           '_ZN14ngStringHelper10decryptXOREPKcS1_',
           '_ZN12ngHttpClient13CreateReqBodyEP10ngJsonHash']:
    disfn(fn)
