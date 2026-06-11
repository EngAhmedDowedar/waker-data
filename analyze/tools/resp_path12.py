"""Discovery for step-10 stage: /api/getallserver + /api/connect.
- find endpoint/command strings + their .rodata neighbors
- list symbols for AllServer/Connect/ServerInfo/Login/Tcp
- disasm CServerMnger::ParseServerList (server-list parser)
- find callers of CTcpLongConnectCreate::CreatLongConnect (TCP init trigger)"""
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
    return (sym_by_va[nv],va-nv) if nv is not None and va-nv<0x1000 else (None,0)
THUNK={0x69300c:'IntValue[INT]',0x692fcc:'str_dup[STR]',0x692fdc:'Str.assign'}
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def disfn(name=None,va=None,L=None,label=''):
    if va is None: va,sz=symbols.get(name,(0,0))
    else: sz=L or 0
    if not va: print(f"[{name} MISSING]"); return
    start=va&~1; ln=L or sz or 0x140; o=va2off(start); code=data[o:o+ln]
    print(f"\n===== {label or name}  va=0x{start:08x} len=0x{ln:x} =====")
    litreg={}; picreg={}
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
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
                an+=f' KEY="{s}"' if s else f' ->0x{tgt:08x}'; picreg[rd]=tgt
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
        if '#0x40]' in op: an+=' (GetNode)'
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')

print("=== endpoint / command strings ===")
import re
for kw in [b'getallserver',b'allserver',b'api/connect',b'/connect',b'getserverinfo',b'serverinfo',b'api/',b'connect',b'getServerList']:
    start=0;hits=0
    while hits<3:
        i=data.find(kw,start)
        if i<0:break
        s=read_cstr(0)  # placeholder
        # compute va
        va=None
        for t,off,vb,msz in segs:
            if t==1 and off<=i<off+msz: va=vb+(i-off);break
        full=read_cstr(va) if va else None
        if full and 3<=len(full)<=40:
            print(f"  {kw.decode():14} foff=0x{i:06x} va={'0x%08x'%va if va else '?'} str={full!r}")
        hits+=1; start=i+1

print("\n=== relevant symbols ===")
for nm,(va,sz) in sorted(symbols.items(),key=lambda x:x[1][0]):
    if any(k in nm for k in ['AllServer','GetAllServer','ParseServerList','DoGetServerInfo','DoConnect',
            'CreatLongConnect','OnConnectSuccess','ParseConnect','ConnectServer','GetServerInfo',
            'OnReceiveResponse','ParseRoleList','DoLogin','Login']):
        print(f"  0x{va&~1:08x} sz=0x{sz:<4x} {nm}")

disfn('_ZN12CServerMnger15ParseServerListEPv', label='CServerMnger::ParseServerList')
disfn('_ZN7CServer5ParseEPv', label='CServer::Parse (recap)', L=0x40)
