import struct,bisect
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
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
ds=sec['.dynsym']; dt=sec['.dynstr']; syms=[]; exact={}
for i in range(ds['size']//16):
    o=ds['off']+i*16; n,v,szz,*_=struct.unpack_from('<IIIBBH',data,o); nm=data[dt['off']+n:].split(b'\0',1)[0].decode('ascii','replace')
    if nm and v: syms.append((v&~1,szz,nm,v&1)); exact[v&~1]=(nm,v&1,szz)
syms.sort(); addrs=[s[0] for s in syms]
def near(va):
    i=bisect.bisect_right(addrs,va)-1
    if i<0: return hex(va)
    a,z,nm,th=syms[i]; return f"{nm}+0x{va-a:x}" if va-a<0x4000 else hex(va)
def cstr(va,m=48):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    return s.decode('ascii','replace') if s and all(9<=b<127 for b in s) else None
PIC=0x75ab20
mT=Cs(CS_ARCH_ARM,CS_MODE_THUMB); mT.detail=True
mA=Cs(CS_ARCH_ARM,CS_MODE_ARM); mA.detail=True
out=open('rp29_out.txt','w')
def disfn(va,ln,label):
    base=va&~1; info=exact.get(base); thumb=True
    sym=near(base)
    if info: thumb=(info[1]==1)
    md=mT if thumb else mA
    o=va2off(base)
    out.write(f"\n===== {label} 0x{base:08x} [{'T' if thumb else 'A'}] {sym} =====\n")
    litreg={}
    for ins in md.disasm(data[o:o+ln],base):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]
        if mn.startswith('ldr') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm if thumb else ins.address+8+imm; litreg[parts[0]]=struct.unpack_from('<I',data,va2off(lit))[0]
            except: pass
        if mn in('add','adds','add.w') and len(parts)==3 and parts[1] in litreg:
            sv=litreg[parts[1]]; sv=sv-0x100000000 if sv&0x80000000 else sv; s=cstr((PIC+sv)&0xFFFFFFFF)
            if s: an+=f' KEY="{s}"'
        if '#0x40]' in op: an+=' <GetNode>'
        if '#0x44]' in op: an+=' <GetByName?>'
        if mn in('bl','blx') and ins.operands and ins.operands[-1].type==2:
            an+=' -> '+near(ins.operands[-1].value.imm&~1)
        out.write(f"  +0x{ins.address-base:03x} {ins.bytes.hex():<8} {mn:<6} {op}{an}\n")
        if (mn=='pop' and 'pc' in op) or mn=='bx': break
disfn(0x2c6e24,0x180,"CHouse-parse(house,data)")
disfn(0x2c5fa4,0x80,"GetPrice-lookup(house)")
out.close(); print("OK")
