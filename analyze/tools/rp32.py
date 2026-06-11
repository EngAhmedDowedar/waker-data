import struct,bisect
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
ds=sec['.dynsym']; dt=sec['.dynstr']; sbn={}
for i in range(ds['size']//16):
    o=ds['off']+i*16; n,v,szz,*_=struct.unpack_from('<IIIBBH',data,o); nm=data[dt['off']+n:].split(b'\0',1)[0].decode('ascii','replace')
    if nm and v: sbn[nm]=(v,szz)
def cstr(va,m=64):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\0',o,o+m+1); s=data[o:(e if e>=0 else o+m)]
    return s.decode('ascii','replace') if s and len(s)>=2 and all(32<=b<127 for b in s) else None
PIC=0x75ab20; mT=Cs(CS_ARCH_ARM,CS_MODE_THUMB); mT.detail=True
out=open('rp32_out.txt','w')
def strings_in(name):
    if name not in sbn: out.write(f"[{name} MISSING]\n"); return
    v,szz=sbn[name]; base=v&~1; o=va2off(base); L=szz or 0x200
    out.write(f"\n=== PIC strings in {name} 0x{base:08x} (len 0x{L:x}) ===\n")
    litreg={}; found=[]
    for ins in mT.disasm(data[o:o+L],base):
        op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]
        if mn.startswith('ldr') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; litreg[parts[0]]=struct.unpack_from('<I',data,va2off(lit))[0]
            except: pass
        if mn in('add','adds','add.w') and len(parts)==3 and parts[1] in litreg:
            sv=litreg[parts[1]]; sv=sv-0x100000000 if sv&0x80000000 else sv; s=cstr((PIC+sv)&0xFFFFFFFF)
            if s and any(c.isalpha() for c in s): found.append((ins.address-base,s))
    for off,s in found: out.write(f"  +0x{off:03x} \"{s}\"\n")
for n in ['_ZN17CMarketCateScreen14ParseGoodsAmountEPv','_ZN17CMarketCateScreen15SetTableContentEv','_ZN17CMarketCateScreen18RequestGoodsAmountEv','_ZN17CMarketCateScreen13InitCateTableEv']:
    strings_in(n)
out.close(); print("OK")
