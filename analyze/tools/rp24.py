import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB
data=open('../lib/armeabi/libcity_ar.so','rb').read()
ph=struct.unpack_from('<I',data,0x1c)[0]; pn=struct.unpack_from('<H',data,0x2c)[0]; pe=struct.unpack_from('<H',data,0x2a)[0]
segs=[struct.unpack_from('<8I',data,ph+i*pe) for i in range(pn)]
def va2off(va):
    for t,off,vb,_,fsz,msz,*_ in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)
sh=struct.unpack_from('<I',data,0x20)[0]; sn=struct.unpack_from('<H',data,0x30)[0]; se=struct.unpack_from('<H',data,0x2e)[0]; sx=struct.unpack_from('<H',data,0x32)[0]
shstr=struct.unpack_from('<I',data,sh+sx*se+0x10)[0]; sec={}
for i in range(sn):
    nm,ty,fl,ad,of,szz,*_=struct.unpack_from('<10I',data,sh+i*se); sec[data[shstr+nm:].split(b'\0',1)[0].decode()]=dict(addr=ad,off=of,size=szz)
ds=sec['.dynsym']; dt=sec['.dynstr']; symv={}; sym_by_name={}
for i in range(ds['size']//16):
    o=ds['off']+i*16; n,v,szz,*_=struct.unpack_from('<IIIBBH',data,o); nm=data[dt['off']+n:].split(b'\0',1)[0].decode('ascii','replace')
    if nm and v: symv[v&~1]=nm; sym_by_name[nm]=(v,szz)
def near(va):
    nv=None
    for s in sorted(symv):
        if s>va: break
        nv=s
    return f"{symv[nv]}+0x{va-nv:x}" if nv is not None and va-nv<0x2500 else hex(va)
def cstr(va,m=48):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    return s.decode('ascii','replace') if s and all(9<=b<127 for b in s) else None
PIC=0x75ab20
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def disfn(name,L=None):
    v,szz=sym_by_name.get(name,(0,0))
    if not v: print(f"[{name} MISSING]"); return
    start=v&~1; ln=L or szz or 0x120; o=va2off(start)
    print(f"\n===== {name}  va=0x{start:08x} len=0x{ln:x} =====")
    litreg={}
    for ins in md.disasm(data[o:o+ln],start):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; litreg[rd]=struct.unpack_from('<I',data,va2off(lit))[0]
            except: pass
        if mn in('add','adds') and len(parts)==3 and parts[1] in litreg:
            sv=litreg[parts[1]]; sv=sv-0x100000000 if sv&0x80000000 else sv; s=cstr((PIC+sv)&0xFFFFFFFF)
            if s: an+=f' KEY="{s}"'
        if '#0x14]' in op: an+=' <arr.begin>'
        if '#0x8]' in op and mn=='ldr': an+=' <hasNext?>'
        if '#0x40]' in op: an+=' <GetNode>'
        if mn in('bl','blx') and ins.operands and ins.operands[-1].type==2:
            an+=' -> '+near(ins.operands[-1].value.imm&~1)
        print(f"  +0x{ins.address-start:03x} {ins.bytes.hex():<8} {mn:<6} {op}{an}")
pass
pass
