import struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
data=open('../lib/armeabi/libcity_ar.so','rb').read()
print("size",len(data))
print("CheckUpdate byte @0x48f911 =",hex(data[0x48f911]),"(e0=patched, d0=orig)")
print("gettopmsgs gate byte @0x59190d =",hex(data[0x59190d]),"(dc=bgt orig, e0=patched/always-skip)")
i=data.find(b"192.168.1.4"); print("'192.168.1.4' at file off:",hex(i) if i>=0 else "NOT FOUND")
i2=data.find(b"city_ar"); 
# resolve veneer 0x69320c
ph=struct.unpack_from('<I',data,0x1c)[0]; pn=struct.unpack_from('<H',data,0x2c)[0]; pe=struct.unpack_from('<H',data,0x2a)[0]
segs=[struct.unpack_from('<8I',data,ph+i*pe) for i in range(pn)]
def va2off(va):
    for t,off,vb,_,fsz,msz,*_ in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)
sh=struct.unpack_from('<I',data,0x20)[0]; sn=struct.unpack_from('<H',data,0x30)[0]; se=struct.unpack_from('<H',data,0x2e)[0]; sx=struct.unpack_from('<H',data,0x32)[0]
shstr=struct.unpack_from('<I',data,sh+sx*se+0x10)[0]; sec={}
for i in range(sn):
    nm,ty,fl,ad,of,szz,*_=struct.unpack_from('<10I',data,sh+i*se); sec[data[shstr+nm:].split(b'\0',1)[0].decode()]=dict(addr=ad,off=of,size=szz)
ds=sec['.dynsym']; dt=sec['.dynstr']; symv={}
for i in range(ds['size']//16):
    o=ds['off']+i*16; n,v,*_=struct.unpack_from('<III',data,o); nm=data[dt['off']+n:].split(b'\0',1)[0].decode('ascii','replace')
    if nm and v: symv[v&~1]=nm
def near(va):
    nv=None
    for s in sorted(symv):
        if s>va: break
        nv=s
    return f"{symv[nv]}+0x{va-nv:x}" if nv is not None and va-nv<0x3000 else hex(va)
mdA=Cs(CS_ARCH_ARM,CS_MODE_ARM)
def follow(t):
    if (t&~1) in symv: return symv[t&~1],(t&~1)
    base=(t&~3); o=va2off(base)
    try:
        ins=list(mdA.disasm(data[o:o+12],base))
        if ins and ins[0].mnemonic=='ldr' and 'ip, [pc' in ins[0].op_str:
            word=struct.unpack_from('<I',data,va2off(base+8))[0]; tg=(word+base+12)&0xFFFFFFFE; return near(tg)+'[ven]',tg
    except: pass
    return near(t&~1),(t&~1)
nm,tg=follow(0x69320c); print("\n0x69320c ->",nm,"(va 0x%x)"%tg)
# disasm the resolved target (the interval getter)
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
o=va2off(tg)
print("--- interval getter @0x%x ---"%tg)
for ins in md.disasm(data[o:o+0x40],tg):
    an=''
    if ins.mnemonic in('bl','blx') and ins.operands and ins.operands[-1].type==2:
        an=' -> '+follow(ins.operands[-1].value.imm&~1)[0]
    print("  +0x%03x %-8s %-7s %s%s"%(ins.address-tg,ins.bytes.hex(),ins.mnemonic,ins.op_str,an))
    if ins.mnemonic in('bx','pop') and 'pc' in ins.op_str: break
