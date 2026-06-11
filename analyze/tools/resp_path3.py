"""
HTTP request-encode / response-decode path:
  - CHttpClient::CheckVersion (request builder) -> recover encode + key string
  - CHttpClient::ParseResponseEx / ngHttpClient::ParseResponseEx (response decode)
  - ngHttpHandler::OnReceiveResponse (base handler)
Call resolution follows linker veneers (b.w / ldr pc,[pc]) and PLT->import.
Also lists base64/json/decompress/decode symbols.
"""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
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
# PLT/GOT
got_to_name={}; relplt=sec.get('.rel.plt')
if relplt:
    for i in range(relplt['size']//8):
        r_off,r_info=struct.unpack_from('<II',data,relplt['off']+i*8); si=r_info>>8
        st_name=struct.unpack_from('<I',data,dsym['off']+si*16)[0]
        got_to_name[r_off]=data[dstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
def read_cstr(va,m=96):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\x00',o,o+m+1); e=e if e>=0 else o+m; s=data[o:e]
    return s.decode('ascii','replace') if (len(s)>=1 and all(9<=b<127 for b in s)) else None
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
mda=Cs(CS_ARCH_ARM,CS_MODE_ARM); mda.detail=True
def follow(t):
    """resolve call target through dynsym / veneer / PLT-GOT"""
    if (t&~1) in sym_by_va: return sym_by_va[t&~1]
    o=va2off(t&~1)
    if o is None: return f'0x{t:08x}'
    # try thumb veneer: b.w X  OR  ldr.w pc,[pc,#x]; .word
    try:
        ins=next(md.disasm(data[o:o+8], t&~1))
        if ins.mnemonic in('b','b.w') and ins.operands and ins.operands[-1].type==2:
            x=ins.operands[-1].value.imm
            if (x&~1) in sym_by_va: return sym_by_va[x&~1]+' [veneer]'
        if ins.mnemonic in('ldr.w','ldr') and 'pc' in ins.op_str and 'pc' in ins.op_str.split(',')[0]:
            pass
    except: pass
    # arm veneer / plt: ldr pc,[pc,#x] or add ip,pc.. ; check GOT
    if (t&~1) in got_to_name: return got_to_name[t&~1]+' [PLT]'
    nv=None
    for s in sorted(sym_by_va):
        if s>(t&~1): break
        nv=s
    if nv is not None and (t-nv)<0x600: return f'{sym_by_va[nv]}+0x{(t-nv)&~1:x}'
    return f'0x{t:08x}'
def disfn(name,length=None,va=None):
    if va is None:
        va,sz=symbols.get(name,(0,0))
    else:
        sz=length or 0
    if not va: print(f"[{name} missing]"); return
    start=va&~1; ln=length or sz or 0x100; o=va2off(start); code=data[o:o+ln]
    print(f"\n===== {name} va=0x{start:08x} len=0x{ln:x} =====")
    regc={}; movacc={}
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
                if lo:
                    val=struct.unpack_from('<I',data,lo)[0]; rt=op.split(',')[0].strip(); regc[rt]=val
                    an+=f'  ; lit=0x{val:08x}'; s=read_cstr(val)
                    if s: an+=f' "{s}"'
            except: pass
        if mn in('add','adds','add.w') and op.replace(' ','').endswith(',pc'):
            rt=op.split(',')[0].strip()
            if rt in regc:
                tgt=(ins.address+4+regc[rt])&0xFFFFFFFF; s=read_cstr(tgt)
                an+=f'  ; =0x{tgt:08x}'
                if s: an+=f' "{s}"'
        if mn=='movw': rt=op.split(',')[0].strip(); movacc[rt]=int(op.split('#')[-1],0)
        elif mn=='movt':
            rt=op.split(',')[0].strip()
            if rt in movacc:
                movacc[rt]|=int(op.split('#')[-1],0)<<16; s=read_cstr(movacc[rt]); an+=f'  ; {rt}=0x{movacc[rt]:08x}'
                if s: an+=f' "{s}"'
        if mn in('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2: an+=f'  ; -> {follow(t.value.imm)}'
            except: pass
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')

print("=== base64 / json / decompress / decode symbols ===")
for nm,(va,sz) in sorted(symbols.items(),key=lambda x:x[1][0]):
    if any(k in nm for k in ['ase64','Base64','B64','b64',' json','Json','JSON','cJSON',
            'Uncompress','uncompress','Decompress','GZip','Gzip','gzip','Zip','Decode','decode','XOR','Xor']):
        print(f"  0x{va&~1:08x} {nm}")

disfn('_ZN11CHttpClient12CheckVersionEv')
disfn('_ZN11CHttpClient14ParseResponseExEPv')
disfn('_ZN12ngHttpClient14ParseResponseExEPv')
disfn('_ZN13ngHttpHandler17OnReceiveResponseEiPv')
