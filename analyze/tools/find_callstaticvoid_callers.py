"""Optimized: find callers of _JNIEnv::CallStaticVoidMethod (GOT 0x0076f974).
Uses array-based halfword iteration for speed."""
import os, struct, array

data=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','lib','armeabi','libcity_ar.so'),'rb').read()
e_shoff=struct.unpack_from('<I',data,0x20)[0]
e_she=struct.unpack_from('<H',data,0x2e)[0]
e_shn=struct.unpack_from('<H',data,0x30)[0]
e_shstr=struct.unpack_from('<H',data,0x32)[0]
shdr=e_shoff+e_shstr*e_she; shstr=struct.unpack_from('<I',data,shdr+0x10)[0]
secs={}
for i in range(e_shn):
    b=e_shoff+i*e_she
    sn,st,_,sa,so,sz,*_=struct.unpack_from('<10I',data,b)
    nm=data[shstr+sn:].split(b'\x00',1)[0].decode('ascii','replace')
    secs[nm]=(sa,so,sz)
da,do,dz=secs['.dynsym']; dsa,dso,dsz=secs['.dynstr']
sym_by_va={}
for i in range(dz//16):
    o=do+i*16
    st_name,st_value,*_=struct.unpack_from('<IIIBBH',data,o)
    nm=data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm and st_value: sym_by_va[st_value & ~1]=nm
sorted_syms = sorted(sym_by_va)
import bisect
def near(va):
    idx = bisect.bisect_right(sorted_syms, va) - 1
    if idx < 0: return None, None
    s = sorted_syms[idx]
    return s, sym_by_va[s]

def arm_modimm(w):
    imm12=w&0xFFF; rot=(imm12>>8)&0xF; v=imm12&0xFF; nn=2*rot
    return v if nn==0 else (((v>>nn)|(v<<(32-nn)))&0xFFFFFFFF)

# GOT slots of interest
TARGETS = {
    0x0076f974: "CallStaticVoidMethod",
    0x0076f7f4: "CallStaticIntMethod",
    0x0075fd78: "CallStaticObjectMethod",
    0x0076f9a4: "CallStaticBooleanMethod",
}

plt=secs['.plt']; plt_va=plt[0]; plt_off=plt[1]; plt_sz=plt[2]
plt_for_got={}
i=0x14
while i+12<=plt_sz:
    eo=plt_off+i
    w0=struct.unpack_from('<I',data,eo)[0]
    w1=struct.unpack_from('<I',data,eo+4)[0]
    w2=struct.unpack_from('<I',data,eo+8)[0]
    if (w0&0xfffff000)==0xe28fc000 and (w1&0xfffff000)==0xe28cc000 and \
       ((w2&0xfffff000)==0xe5bcf000 or (w2&0xfffff000)==0xe53cf000):
        imm_a=arm_modimm(w0); imm_b=arm_modimm(w1)
        ic=w2&0xFFF; U=(w2>>23)&1; imm_c=ic if U else -ic
        got=(plt_va+i+8+imm_a+imm_b+imm_c)&0xFFFFFFFF
        if got in TARGETS:
            plt_for_got[plt_va+i]=TARGETS[got]
    i+=12
print('PLT entries for targets:')
for p,s in plt_for_got.items(): print('  PLT 0x%08x -> %s'%(p,s))

# veneers
text=secs['.text']; tva=text[0]; toff=text[1]; tsz=text[2]
veneer_sym={}
i=0
while i+16<=tsz:
    if data[toff+i]==0x78 and data[toff+i+1]==0x47 and data[toff+i+2]==0xc0 and data[toff+i+3]==0x46:
        ldrw=struct.unpack_from('<I',data,toff+i+4)[0]
        addp=struct.unpack_from('<I',data,toff+i+8)[0]
        if (ldrw&0xfffff000)==0xe59fc000 and addp==0xe08cf00f:
            const=struct.unpack_from('<I',data,toff+i+12)[0]
            sc=const-0x100000000 if (const&0x80000000) else const
            vva=tva+i; arm_t=(vva+16+sc)&0xFFFFFFFF
            if arm_t in plt_for_got: veneer_sym[vva]=plt_for_got[arm_t]
            i+=16; continue
    i+=2
print('veneers:')
for v,s in veneer_sym.items(): print('  veneer 0x%08x -> %s'%(v,s))

# Fast BL scan: load text as halfword array
hw = array.array('H')
hw.frombytes(data[toff:toff+ (tsz & ~1)])
veneer_set = set(veneer_sym.keys())

callers = {v: [] for v in veneer_sym}
nhw = len(hw)
for k in range(nhw - 1):
    h1 = hw[k]
    if (h1 & 0xF800) != 0xF000: continue
    h2 = hw[k+1]
    if (h2 & 0xC000) != 0xC000: continue
    S=(h1>>10)&1; imm10=h1&0x3FF
    J1=(h2>>13)&1; J2=(h2>>11)&1; imm11=h2&0x7FF
    I1=1^(J1^S); I2=1^(J2^S)
    imm32=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if S: imm32-=(1<<25)
    cur=tva+k*2
    tgt=(cur+4+imm32)&0xFFFFFFFE
    if tgt in veneer_set:
        callers[tgt].append(cur)

out=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'callstaticvoid_callers.txt'),'w',encoding='utf-8')
def emit(s=''):
    print(s); out.write(s+'\n'); out.flush()

emit('Callers of CallStatic*Method veneers')
emit('='*72)
for v,sites in callers.items():
    sym=veneer_sym[v]
    emit('')
    emit('=== %s  (%d sites) veneer 0x%08x ==='%(sym,len(sites),v))
    byo={}
    for cv in sites:
        ov,on=near(cv); byo.setdefault((on,ov),[]).append(cv)
    for (on,ov),lst in sorted(byo.items(), key=lambda kv: kv[1][0]):
        emit('  %s (@0x%08x) -- %d'%(on, ov or 0, len(lst)))
        for s in lst[:4]: emit('    0x%08x'%s)
        if len(lst)>4: emit('    ...%d more'%(len(lst)-4))
out.close()
print('---DONE---')
