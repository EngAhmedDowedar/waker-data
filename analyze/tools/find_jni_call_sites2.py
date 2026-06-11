"""Find libcity_ar.so JNI call sites — corrected PLT decoding.

PLT layout (confirmed): 20-byte header, then 12-byte entries:
  add ip, pc, #imm_a   (0xe28fc???)
  add ip, ip, #imm_b   (0xe28cc???)
  ldr pc, [ip, #imm_c]! (0xe5bcf??? for U=1, 0xe53cf??? for U=0)
"""
import os, struct

data=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','lib','armeabi','libcity_ar.so'),'rb').read()
e_phoff=struct.unpack_from('<I',data,0x1c)[0]
e_phentsize=struct.unpack_from('<H',data,0x2a)[0]
e_phnum=struct.unpack_from('<H',data,0x2c)[0]
segs=[]
for i in range(e_phnum):
    o=e_phoff+i*e_phentsize
    t,off,va,_,fsz,msz,*_=struct.unpack_from('<8I',data,o)
    segs.append((t,off,va,fsz,msz))
def va_to_off(va):
    for t,off,vb,_,msz in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)

e_shoff=struct.unpack_from('<I',data,0x20)[0]
e_shentsize=struct.unpack_from('<H',data,0x2e)[0]
e_shnum=struct.unpack_from('<H',data,0x30)[0]
e_shstrndx=struct.unpack_from('<H',data,0x32)[0]
shdr=e_shoff+e_shstrndx*e_shentsize
shstr=struct.unpack_from('<I',data,shdr+0x10)[0]
secs={}
for i in range(e_shnum):
    b=e_shoff+i*e_shentsize
    sn,st,_,sa,so,sz,*_=struct.unpack_from('<10I',data,b)
    nm=data[shstr+sn:].split(b'\x00',1)[0].decode('ascii','replace')
    secs[nm]=(sa,so,sz)
da,do,dz=secs['.dynsym']; dsa,dso,dsz=secs['.dynstr']
def dynsym_at(idx):
    o = do + idx*16
    st_name,st_value,*_=struct.unpack_from('<IIIBBH',data,o)
    return data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
sym_by_va={}
for i in range(dz//16):
    o = do + i*16
    st_name,st_value,*_=struct.unpack_from('<IIIBBH',data,o)
    nm = data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm and st_value: sym_by_va[st_value & ~1] = nm
def near(va):
    best=None
    for s in sorted(sym_by_va):
        if s>va: break
        best=s
    return best, sym_by_va.get(best)

JNI_HINTS = ["NewStringUTF","CallStaticVoidMethod","CallStaticBooleanMethod",
             "CallStaticIntMethod","CallStaticObjectMethod","GetStaticMethodID",
             "FindClass","GetMethodID"]

rel_plt = secs['.rel.plt']
got_to_sym = {}
n = rel_plt[2] // 8
for i in range(n):
    rb = rel_plt[1] + i*8
    r_offset, r_info = struct.unpack_from('<II', data, rb)
    if (r_info & 0xff) != 22: continue
    sym = dynsym_at(r_info >> 8)
    if any(h in sym for h in JNI_HINTS):
        got_to_sym[r_offset] = sym

print('JNI imports matched: {}'.format(len(got_to_sym)))
for g, s in got_to_sym.items():
    print('  GOT 0x{:08x}  {}'.format(g, s))

def arm_modimm(w):
    imm12 = w & 0xFFF
    rot = (imm12 >> 8) & 0xF
    v   = imm12 & 0xFF
    nn  = 2 * rot
    if nn == 0: return v
    return ((v >> nn) | (v << (32 - nn))) & 0xFFFFFFFF

plt = secs['.plt']
plt_base_va = plt[0]; plt_base_off = plt[1]; plt_size = plt[2]
plt_va_to_got = {}
i = 0x14  # header is 20 bytes
while i + 12 <= plt_size:
    eo = plt_base_off + i
    w0 = struct.unpack_from('<I', data, eo)[0]
    w1 = struct.unpack_from('<I', data, eo+4)[0]
    w2 = struct.unpack_from('<I', data, eo+8)[0]
    ok = (w0 & 0xfffff000) == 0xe28fc000 and \
         (w1 & 0xfffff000) == 0xe28cc000 and \
         ((w2 & 0xfffff000) == 0xe5bcf000 or (w2 & 0xfffff000) == 0xe53cf000)
    if ok:
        imm_a = arm_modimm(w0); imm_b = arm_modimm(w1)
        imm_c_raw = w2 & 0xFFF
        U = (w2 >> 23) & 1
        imm_c = imm_c_raw if U else -imm_c_raw
        pc = plt_base_va + i + 8
        got = (pc + imm_a + imm_b + imm_c) & 0xFFFFFFFF
        plt_va_to_got[plt_base_va + i] = got
    i += 12
print('PLT entries decoded: {}'.format(len(plt_va_to_got)))

# PLT entries for our JNI symbols
jni_plt = {pva: got_to_sym[got] for pva, got in plt_va_to_got.items() if got in got_to_sym}
print('JNI PLT entries: {}'.format(len(jni_plt)))
for pva, sym in sorted(jni_plt.items()):
    print('  PLT 0x{:08x} -> {}'.format(pva, sym))

# Veneers (thumb) -> PLT
text = secs['.text']
text_va = text[0]; text_off = text[1]; text_size = text[2]
veneer_to_sym = {}
i = 0
while i + 16 <= text_size:
    if data[text_off+i]==0x78 and data[text_off+i+1]==0x47 and \
       data[text_off+i+2]==0xc0 and data[text_off+i+3]==0x46:
        ldrw = struct.unpack_from('<I', data, text_off+i+4)[0]
        addp = struct.unpack_from('<I', data, text_off+i+8)[0]
        if (ldrw & 0xfffff000)==0xe59fc000 and addp==0xe08cf00f:
            const = struct.unpack_from('<I', data, text_off+i+12)[0]
            sc = const-0x100000000 if (const & 0x80000000) else const
            vva = text_va + i
            arm_t = (vva + 16 + sc) & 0xFFFFFFFF
            if arm_t in jni_plt:
                veneer_to_sym[vva] = jni_plt[arm_t]
            i += 16; continue
    i += 2
print('JNI veneers: {}'.format(len(veneer_to_sym)))
for v, s in sorted(veneer_to_sym.items()):
    print('  veneer 0x{:08x} -> {}'.format(v, s))

# Scan .text for BL/BLX to these veneers (the slow part) — group by owner
out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'jni_call_sites2.txt'),'w',encoding='utf-8')
def emit(s=''):
    print(s); out.write(s+'\n'); out.flush()

emit('JNI call sites (corrected)')
emit('='*72)
emit('veneers:')
for v,s in sorted(veneer_to_sym.items()):
    emit('  0x{:08x} -> {}'.format(v,s))
emit('')

callers = {v: [] for v in veneer_to_sym}
for off in range(0, text_size-4, 2):
    hw1 = struct.unpack_from('<H', data, text_off+off)[0]
    if (hw1 & 0xF800) != 0xF000: continue
    hw2 = struct.unpack_from('<H', data, text_off+off+2)[0]
    if (hw2 & 0xC000) != 0xC000: continue
    S=(hw1>>10)&1; imm10=hw1&0x3FF
    J1=(hw2>>13)&1; J2=(hw2>>11)&1; imm11=hw2&0x7FF
    I1=1^(J1^S); I2=1^(J2^S)
    imm32=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if S: imm32 -= (1<<25)
    cur=text_va+off
    tgt=(cur+4+imm32)&~1
    if tgt in callers:
        callers[tgt].append(cur)

for v, sites in sorted(callers.items(), key=lambda kv: veneer_to_sym[kv[0]]):
    sym = veneer_to_sym[v]
    emit('')
    emit('=== {}  ({} call sites) veneer 0x{:08x} ==='.format(sym, len(sites), v))
    byo={}
    for cv in sites:
        ov,on=near(cv)
        byo.setdefault((on,ov),[]).append(cv)
    for (on,ov),lst in sorted(byo.items(), key=lambda kv: kv[1][0]):
        emit('  {} (@0x{:08x}) -- {}'.format(on, ov or 0, len(lst)))
        for s in lst[:3]: emit('    0x{:08x}'.format(s))
        if len(lst)>3: emit('    ...{} more'.format(len(lst)-3))
out.close()
print('---DONE---')
