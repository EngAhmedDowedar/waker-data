"""Trace post-checkversion TCP setup: DoGetServerInfo @ 0x490dd0 and the
CTcpLongConnectCreate / server-info path. Find the null+0x10 deref source.
Annotates PIC strings, resolved calls, [reg,#0x10/#0x14] derefs, and port-ish imms."""
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
    if nm: symbols[nm]=(st_value,st_size);
    if nm and st_value: sym_by_va[st_value&~1]=nm
def read_cstr(va,m=90):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\x00',o,o+m+1); e=e if e>=0 else o+m; s=data[o:e]
    return s.decode('ascii','replace') if (len(s)>=1 and all(9<=b<127 for b in s)) else None
def near(va):
    nv=None
    for s in sorted(sym_by_va):
        if s>va: break
        nv=s
    return (sym_by_va[nv],va-nv) if nv is not None and va-nv<0x1200 else (None,0)
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def disrange(start,L,label):
    start&=~1; o=va2off(start); code=data[o:o+L]
    print(f"\n===== {label}  va=0x{start:08x} len=0x{L:x} =====")
    litreg={}; picreg={}
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
                if lo:
                    val=struct.unpack_from('<I',data,lo)[0]; litreg[rd]=val; an+=f'  ; lit=0x{val:08x}'; s=read_cstr(val)
                    if s: an+=f' "{s}"'
            except: pass
        if mn in('add','adds','add.w') and parts[-1]=='pc' and rd in litreg:
            picreg[rd]=(ins.address+4+litreg[rd])&0xFFFFFFFF
        if mn in('adds','add','add.w') and len(parts)==3:
            a,b=parts[1],parts[2]; pic=picreg.get(a) or picreg.get(b)
            litr=litreg.get(a) if (a in litreg and b in picreg) else (litreg.get(b) if (b in litreg and a in picreg) else None)
            if pic is not None and litr is not None:
                sv=litr-0x100000000 if litr&0x80000000 else litr; tgt=(pic+sv)&0xFFFFFFFF; s=read_cstr(tgt)
                an+=f'  ; STR->0x{tgt:08x}'+(f' "{s}"' if s else ''); picreg[rd]=tgt
        if mn in('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2:
                    nm=sym_by_va.get(t.value.imm&~1)
                    if nm: an+=f'  ; -> {nm}'
                    else:
                        nn,do=near(t.value.imm&~1); an+=f'  ; -> {nn}+0x{do:x}' if nn else f'  ; -> 0x{t.value.imm:08x}'
            except: pass
        # flag derefs at +0x10 / +0x14 (fault is null+0x10) and port-ish imms
        if ('#0x10]' in op or '#0x14]' in op) and mn.startswith(('ldr','str')):
            an+='   <== +0x10/14 deref'
        if mn=='blx' and op in('r1','r2','r3','r4','r5','r6','r7'):
            an+='   (vcall)'
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')

print("=== symbols: tcp/connect/server/gateway/keepalive ===")
for nm,(va,sz) in sorted(symbols.items(),key=lambda x:x[1][0]):
    if any(k in nm for k in ['TcpLongConnect','TcpClient','ConnectCreate','GetServerInfo','ServerInfo',
            'ServerList','GetServerList','Gateway','KeepAlive','keepLive','DoConnect','LongConnect',
            'CServer','OnConnect','ParseServer']):
        print(f"  0x{va&~1:08x} sz=0x{sz:<5x} {nm}")

disrange(0x490dd0,0x1c,'CLoadingScreen::DoGetServerInfo')
# CTcpLongConnectCreate methods
for nm,(va,sz) in symbols.items():
    if 'TcpLongConnect' in nm and ('C1' in nm or 'C2' in nm or 'Connect' in nm or 'Init' in nm or 'Create' in nm):
        if sz and sz<0x400:
            disrange(va,sz,nm)
disrange(0x5cbb80,0x2c0,'crash-region full ~0x5cbdc4 (TCP-connect-create)')
