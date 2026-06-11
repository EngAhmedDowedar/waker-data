"""Find the gettopmsgs request GATE in CTopScreen::HandleUpdate @0x5918c8:
where RequestMsg (0x592238) / its veneer is called and the timer/flag condition
that should throttle it. Annotate [this+off] field access, cmp, and call targets."""
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
def near(va):
    nv=None
    for s in sorted(sym_by_va):
        if s>va: break
        nv=s
    return (sym_by_va[nv],va-nv) if nv is not None and va-nv<0x2000 else (None,0)
# resolve PC-relative veneer target
mda=Cs(CS_ARCH_ARM,CS_MODE_THUMB)
mdarm=Cs(CS_ARCH_ARM,CS_MODE_ARM)
def follow(t):
    if (t&~1) in sym_by_va: return sym_by_va[t&~1]
    base=(t&~3)+4; o=va2off(base)
    try:
        insns=list(mdarm.disasm(data[o:o+12], base))
        word=None
        for ins in insns:
            if ins.mnemonic=='ldr' and 'ip, [pc]' in ins.op_str:
                word=struct.unpack_from('<I',data,va2off(base+8))[0]
        if word is not None:
            # add pc,ip,pc : target = word + (base+4) + 8
            tgt=(word+base+12)&0xFFFFFFFF
            nn,do=near(tgt&~1); return (sym_by_va.get(tgt&~1) or (nn+("+0x%x"%do) if nn else hex(tgt)))+'[ven]'
    except: pass
    nn,do=near(t&~1); return (nn+("+0x%x"%do)) if nn else hex(t)
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
va=0x5918c8; ln=0x66c; o=va2off(va); code=data[o:o+ln]
print(f"=== CTopScreen::HandleUpdate 0x{va:08x} len=0x{ln:x} (calls + field/cmp gates) ===")
for ins in md.disasm(code,va):
    op=ins.op_str; mn=ins.mnemonic; show=False; an=''
    if mn in('bl','blx') and ins.operands and ins.operands[-1].type==2:
        tv=ins.operands[-1].value.imm&~1; r=follow(tv)
        if any(k in r for k in ['RequestMsg','RequestSysMsg','0x592238','0x59313c','0x6ba0dc','0x6ba04c','HttpClient','PutURL','0x6a8bcc']):
            an=f' -> {r}'; show=True
    if ('[r' in op and ('#0x' in op)) and mn.startswith(('ldr','str')) and any(o2 in op for o2 in ['0x440','0x444','0x448','0x7d','0x1f0','0x1f4','0x4','#0x']):
        pass
    if mn in('cmp','cmp.w') and ('#' in op): an=an or ' <cmp>';
    if show:
        print(f'  0x{ins.address:08x}: {mn:<6} {op}{an}')
# also: who calls RequestMsg 0x592238 ?
def bl_t(addr,h1,h2):
    if (h1&0xF800)!=0xF000 or (h2&0xC000)!=0xC000: return None
    S=(h1>>10)&1;i10=h1&0x3FF;J1=(h2>>13)&1;J2=(h2>>11)&1;i11=h2&0x7FF
    I1=(~(J1^S))&1;I2=(~(J2^S))&1;imm=(S<<24)|(I1<<23)|(I2<<22)|(i10<<12)|(i11<<1)
    if imm&(1<<24): imm-=(1<<25)
    t=(addr+4+imm)&0xFFFFFFFF
    return t if (h2&0x1000) else (t&~3)
text=sec['.text']; toff=text['off']; tva=text['addr']; tsz=text['size']
for target,tn in [(0x592238,'RequestMsg'),(0x591160,'RequestSysMsg')]:
    print(f"\n=== callers of {tn} (0x{target:08x}) ===")
    for off in range(0,tsz-4,2):
        h1=struct.unpack_from('<H',data,toff+off)[0]
        if (h1&0xF800)!=0xF000: continue
        h2=struct.unpack_from('<H',data,toff+off+2)[0]
        t=bl_t(tva+off,h1,h2)
        if t is not None and (t&~1)==target:
            nn,do=near(tva+off); print(f"  @0x{tva+off:08x} ({nn}+0x{do:x})")
