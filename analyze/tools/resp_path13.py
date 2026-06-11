"""Connect/login/getallserver senders + TCP-init trigger.
- disasm CHttpClient::GetAllServer/PlayerLogin and CLoadingScreen Do* steps to
  read the opcode each sets ([this+0x34]) -> maps response routing.
- find callers of CTcpLongConnectCreate::CreatLongConnect (TCP 9090 init).
- disasm CLoadingScreen::OnReceiveResponse opcode handlers."""
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
def read_cstr(va,m=64):
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
THUNK={0x69300c:'IntValue[INT]',0x692fcc:'str_dup[STR]'}
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def disfn(name=None,va=None,L=None,label=''):
    if va is None: va,sz=symbols.get(name,(0,0))
    else: sz=L or 0
    if not va: print(f"[{name} MISSING]"); return
    start=va&~1; ln=L or sz or 0x100; o=va2off(start); code=data[o:o+ln]
    print(f"\n===== {label or name}  va=0x{start:08x} len=0x{ln:x} =====")
    litreg={}; picreg={}
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
        if mn in('movs','mov') and '#' in op and rd:
            try: litreg[rd]=int(op.split('#')[-1],0)
            except: pass
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
                if lo:
                    val=struct.unpack_from('<I',data,lo)[0]; litreg[rd]=val; an+=f' lit=0x{val:08x}'; s=read_cstr(val)
                    if s: an+=f' "{s}"'
            except: pass
        if mn in('add','adds','add.w') and parts[-1]=='pc' and rd in litreg:
            picreg[rd]=(ins.address+4+litreg[rd])&0xFFFFFFFF
        if mn in('adds','add','add.w') and len(parts)==3:
            a,b=parts[1],parts[2]; pic=picreg.get(a) or picreg.get(b)
            litr=litreg.get(a) if (a in litreg and b in picreg) else (litreg.get(b) if (b in litreg and a in picreg) else None)
            if pic is not None and litr is not None:
                sv=litr-0x100000000 if litr&0x80000000 else litr; tgt=(pic+sv)&0xFFFFFFFF; s=read_cstr(tgt)
                an+=f' STR="{s}"' if s else f' ->0x{tgt:08x}'; picreg[rd]=tgt
        # opcode store: str rX,[rY,#0x34]
        if mn=='str' and '#0x34]' in op:
            src=parts[0]
            an+=f'  <== OPCODE store [+0x34] = {("0x%x"%litreg[src]) if src in litreg else src}'
        if mn in('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2:
                    tv=t.value.imm&~1
                    if tv in THUNK: an+=f' -> {THUNK[tv]}'
                    elif tv in sym_by_va: an+=f' -> {sym_by_va[tv]}'
                    else:
                        nn,do=near(tv); an+=f' -> {nn}+0x{do:x}' if nn else f' -> 0x{tv:08x}'
            except: pass
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')

for fn in ['_ZN11CHttpClient12GetAllServerEv','_ZN11CHttpClient11PlayerLoginEv',
           '_ZN14CLoadingScreen15DoGetServerInfoEh','_ZN14CLoadingScreen19DoConnectPlayerInfoEv',
           '_ZN14CLoadingScreen7DoLoginEv','_ZN14CLoadingScreen14OnLoginSuccessEPKcS1_']:
    disfn(fn)

# find callers of CreatLongConnect (TCP init)
def bl_t(addr,h1,h2):
    if (h1&0xF800)!=0xF000 or (h2&0xC000)!=0xC000: return None
    S=(h1>>10)&1;i10=h1&0x3FF;J1=(h2>>13)&1;J2=(h2>>11)&1;i11=h2&0x7FF
    I1=(~(J1^S))&1;I2=(~(J2^S))&1;imm=(S<<24)|(I1<<23)|(I2<<22)|(i10<<12)|(i11<<1)
    if imm&(1<<24): imm-=(1<<25)
    t=(addr+4+imm)&0xFFFFFFFF
    return t if (h2&0x1000) else (t&~3)
text=sec['.text']; toff=text['off']; tva=text['addr']; tsz=text['size']
targets={symbols[n][0]&~1:n for n in symbols if 'CreatLongConnect' in n or 'CreatRaceLongConnect' in n or 'DoConnectPlayerInfo' in n}
print("\n=== callers of CreatLongConnect / DoConnectPlayerInfo (TCP init path) ===")
print("targets:", {hex(k):v for k,v in targets.items()})
for off in range(0,tsz-4,2):
    h1=struct.unpack_from('<H',data,toff+off)[0]
    if (h1&0xF800)!=0xF000: continue
    h2=struct.unpack_from('<H',data,toff+off+2)[0]
    t=bl_t(tva+off,h1,h2)
    if t is not None and (t&~1) in targets:
        nn,do=near(tva+off)
        print(f"  call @0x{tva+off:08x} ({nn}+0x{do:x}) -> {targets[t&~1]}")
