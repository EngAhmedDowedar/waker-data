"""
RC4 crypto path + key recovery for libcity_ar.so.
- xref all ngRC4 / RC4Mnger / IsUseRC4Encrypt / inflate call sites in .text
- for each caller, show a pre-call window with string/PIC literals (key candidates)
- fully disassemble IsUseRC4Encrypt, ngRC4::OperateKey, EncryptWithKey(bytebuf),
  DecryptWithKey(bytebuf), and CHttpClient::CheckVersion
"""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

HERE = os.path.dirname(os.path.abspath(__file__))
data = open(os.path.join(HERE,'..','lib','armeabi','libcity_ar.so'),'rb').read()

e_phoff=struct.unpack_from('<I',data,0x1c)[0]; e_phnum=struct.unpack_from('<H',data,0x2c)[0]
e_phes=struct.unpack_from('<H',data,0x2a)[0]
segs=[]
for i in range(e_phnum):
    t,off,va,_,fsz,msz,*_=struct.unpack_from('<8I',data,e_phoff+i*e_phes); segs.append((t,off,va,msz))
def va2off(va):
    for t,off,vb,msz in segs:
        if t==1 and vb<=va<vb+msz:
            o=off+(va-vb); return o if o<len(data) else None
e_shoff=struct.unpack_from('<I',data,0x20)[0]; e_shnum=struct.unpack_from('<H',data,0x30)[0]
e_shes=struct.unpack_from('<H',data,0x2e)[0]; e_shstrndx=struct.unpack_from('<H',data,0x32)[0]
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

def read_cstr(va,maxlen=96):
    o=va2off(va)
    if o is None: return None
    end=data.find(b'\x00',o,o+maxlen+1)
    if end<0: end=o+maxlen
    s=data[o:end]
    if len(s)>=1 and all(9<=b<127 for b in s): return s.decode('ascii','replace')
    return None

# target set: ngRC4*, RC4Mnger*, IsUseRC4Encrypt, SetUseRc4
TARGS={}
for nm,(va,sz) in symbols.items():
    if ('ngRC4' in nm or 'RC4Mnger' in nm or 'UseRC4' in nm or 'UseRc4' in nm
        or nm in ('inflate','inflateInit2_')):
        TARGS[va&~1]=nm
print("=== RC4/inflate target symbols ===")
for va,nm in sorted(TARGS.items()):
    print(f"  0x{va:08x} {nm}")

# BL/BLX decoder
def bl_target(addr,hw1,hw2):
    if (hw1&0xF800)!=0xF000: return None
    if (hw2&0xC000)!=0xC000: return None
    S=(hw1>>10)&1; imm10=hw1&0x3FF
    J1=(hw2>>13)&1; J2=(hw2>>11)&1; imm11=hw2&0x7FF
    I1=(~(J1^S))&1; I2=(~(J2^S))&1
    imm=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if imm&(1<<24): imm-=(1<<25)
    is_bl=(hw2&0x1000)!=0
    tgt=(addr+4+imm)&0xFFFFFFFF
    if not is_bl: tgt&=~3
    return tgt

text=sec['.text']; toff=text['off']; tva=text['addr']; tsz=text['size']
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True

# scan for callers
callers={}  # target -> [caller_va]
for off in range(0,tsz-4,2):
    hw1=struct.unpack_from('<H',data,toff+off)[0]
    if (hw1&0xF800)!=0xF000: continue
    hw2=struct.unpack_from('<H',data,toff+off+2)[0]
    t=bl_target(tva+off,hw1,hw2)
    if t is not None and (t&~1) in TARGS:
        callers.setdefault(t&~1,[]).append(tva+off)

def window(va_call, back=0x2c):
    start=(va_call-back)&~1; o=va2off(start); code=data[o:o+back+4]
    out=[]; regc={}; movacc={}
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm
                lo=va2off(lit)
                if lo:
                    val=struct.unpack_from('<I',data,lo)[0]; rt=op.split(',')[0].strip(); regc[rt]=val
                    an+=f'  ; lit=0x{val:08x}'; s=read_cstr(val)
                    if s: an+=f' "{s}"'
            except: pass
        if mn in('add','adds','add.w') and op.replace(' ','').endswith(',pc'):
            rt=op.split(',')[0].strip()
            if rt in regc:
                tgt=(ins.address+4+regc[rt])&0xFFFFFFFF; s=read_cstr(tgt)
                an+=f'  ; ={"0x%08x"%tgt}'
                if s: an+=f' "{s}"'
        if mn=='movw': rt=op.split(',')[0].strip(); movacc[rt]=int(op.split('#')[-1],0)
        elif mn=='movt':
            rt=op.split(',')[0].strip()
            if rt in movacc:
                movacc[rt]|=int(op.split('#')[-1],0)<<16; s=read_cstr(movacc[rt])
                an+=f'  ; {rt}=0x{movacc[rt]:08x}'
                if s: an+=f' "{s}"'
        if mn in('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2:
                    nm=sym_by_va.get(t.value.imm&~1)
                    if nm: an+=f'  ; -> {nm}'
                    else: an+=f'  ; -> 0x{t.value.imm:08x}'
            except: pass
        out.append(f'    0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')
    return '\n'.join(out)

print("\n=== RC4/inflate CALL SITES (with pre-call window) ===")
for tgt in sorted(callers):
    nm=TARGS[tgt]
    print(f"\n-- callers of {nm} (0x{tgt:08x}): {len(callers[tgt])} --")
    for cva in callers[tgt][:8]:
        ov=cva; near=None
        for s in sorted(sym_by_va):
            if s>cva: break
            near=s
        nn=sym_by_va.get(near)
        print(f"  caller 0x{cva:08x}  (in {nn} +0x{(cva-near)&~1:x})")
        print(window(cva))

# Full disasm of a few key funcs
def disfn(name, length=None):
    va,sz=symbols.get(name,(0,0))
    if not va: print(f"[{name} missing]"); return
    start=va&~1; ln=length or sz or 0x80; o=va2off(start); code=data[o:o+ln]
    print(f"\n===== {name} va=0x{start:08x} len=0x{ln:x} =====")
    print(window(start+ln, back=ln))  # reuse annotator over whole range

for fn in ['_ZN8CFunGame15IsUseRC4EncryptEv','_ZN5ngRC410OperateKeyEPKcPh',
           '_ZN5ngRC414EncryptWithKeyEP12ngByteBufferS1_PKc',
           '_ZN5ngRC414DecryptWithKeyEP12ngByteBufferS1_PKc',
           '_ZN10ngRC4Mnger7InitKeyEv']:
    disfn(fn)
