"""Find the role-list ROOT KEY (in CHttpClient::ParseResponseEx near the
ParseRoleList call @+478 = 0x467442) and the role-entry parser (thunk 0x693ecc).
picbase for PIC string loads is the constant GOT anchor 0x75ab20."""
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
PIC=0x75ab20
THUNK={0x69300c:'IntValue[INT]',0x692fcc:'strdup[STR]',0x692fdc:'Str.assign',0x69317c:'op_new'}
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def follow(t):
    if (t&~1) in sym_by_va: return sym_by_va[t&~1]
    o=va2off(t&~1)
    if o:
        try:
            ins=next(md.disasm(data[o:o+8], t&~1))
            if ins.mnemonic in('b','b.w') and ins.operands and ins.operands[-1].type==2:
                x=ins.operands[-1].value.imm
                if (x&~1) in sym_by_va: return sym_by_va[x&~1]+' [veneer]'
            if ins.mnemonic=='bx' and 'pc' in ins.op_str:
                # arm veneer at t&~1 +? ; read next arm insns
                return f'0x{t:08x}[bxpc-veneer]'
        except: pass
    nn,do=near(t&~1); return f'{nn}+0x{do:x}' if nn else f'0x{t:08x}'
def disrange(start,end,label):
    start&=~1; o=va2off(start); code=data[o:o+(end-start)]
    print(f"\n===== {label}  0x{start:08x}..0x{end:08x} =====")
    litreg={}
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
                if lo:
                    val=struct.unpack_from('<I',data,lo)[0]; litreg[rd]=val; an+=f' lit=0x{val:08x}'
            except: pass
        # PIC string: adds rD, rImm, rBase where the negoff literal is in some reg; resolve via PIC const
        if mn in('adds','add') and len(parts)==3 and parts[1] in litreg:
            sv=litreg[parts[1]]; sv=sv-0x100000000 if sv&0x80000000 else sv
            tgt=(PIC+sv)&0xFFFFFFFF; s=read_cstr(tgt)
            if s: an+=f' KEY="{s}"'
        if mn in('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2:
                    tv=t.value.imm&~1
                    an+=f' -> {THUNK.get(tv, follow(tv))}'
            except: pass
        if '#0x40]' in op: an+=' (GetNode)'
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')

# region around the ParseRoleList call (+478 = 0x467442) in ParseResponseEx
disrange(0x4673f0, 0x467470, 'ParseResponseEx around ParseRoleList call (+478)')
# resolve role-entry parser thunk 0x693ecc
print("\n=== resolve 0x693ecc (role-entry parser thunk) ===")
o=va2off(0x693ecc)
for ins in md.disasm(data[o:o+12], 0x693ecc):
    print(f'  0x{ins.address:08x}: {ins.bytes.hex()} {ins.mnemonic} {ins.op_str}')
# also list ParseRoleList callers via bl scan
def bl_t(addr,h1,h2):
    if (h1&0xF800)!=0xF000 or (h2&0xC000)!=0xC000: return None
    S=(h1>>10)&1;i10=h1&0x3FF;J1=(h2>>13)&1;J2=(h2>>11)&1;i11=h2&0x7FF
    I1=(~(J1^S))&1;I2=(~(J2^S))&1;imm=(S<<24)|(I1<<23)|(I2<<22)|(i10<<12)|(i11<<1)
    if imm&(1<<24): imm-=(1<<25)
    t=(addr+4+imm)&0xFFFFFFFF
    return t if (h2&0x1000) else (t&~3)
text=sec['.text']; toff=text['off']; tva=text['addr']; tsz=text['size']
prl=symbols['_ZN12CServerMnger13ParseRoleListEPv'][0]&~1
print(f"\n=== callers of ParseRoleList (0x{prl:08x}) ===")
for off in range(0,tsz-4,2):
    h1=struct.unpack_from('<H',data,toff+off)[0]
    if (h1&0xF800)!=0xF000: continue
    h2=struct.unpack_from('<H',data,toff+off+2)[0]
    t=bl_t(tva+off,h1,h2)
    if t is not None and (t&~1)==prl:
        nn,do=near(tva+off); print(f"  @0x{tva+off:08x} ({nn}+0x{do:x})")
