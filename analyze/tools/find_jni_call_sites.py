"""Find all libcity_ar.so call sites that invoke JNI runtime functions
(NewStringUTF, CallStaticVoidMethod[V|A], GetStaticMethodID, FindClass)
via PLT trampolines.

Strategy:
  1. Walk .rel.plt to find GOT slots for imported JNI symbols
  2. Find the PLT entry that targets each such GOT slot
  3. Find the Thumb veneer that targets each PLT entry
  4. Scan .text for Thumb-2 BL targeting each veneer
  5. Group callers by owner function
"""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM

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

# JNI symbols of interest. These are mangled C++ names in libart.so for the
# JNI member functions. We match by demangled-name substring on the imported
# symbol name in libcity_ar.so's .dynsym.
JNI_NAME_HINTS = [
    "NewStringUTF",
    "CallStaticVoidMethod",   # catches V/A variants too
    "CallStaticBooleanMethod",
    "CallStaticIntMethod",
    "CallStaticObjectMethod",
    "GetStaticMethodID",
    "FindClass",
    "GetMethodID",
    "GetStringUTFChars",
]

# Find JUMP_SLOT entries for matching symbol names
rel_plt = secs['.rel.plt']
got_to_sym = {}     # got_va -> sym name (str)
n = rel_plt[2] // 8
for i in range(n):
    rb = rel_plt[1] + i*8
    r_offset, r_info = struct.unpack_from('<II', data, rb)
    if (r_info & 0xff) != 22: continue
    sym = dynsym_at(r_info >> 8)
    if any(h in sym for h in JNI_NAME_HINTS):
        got_to_sym[r_offset] = sym

print('Imported JNI symbols matched in .rel.plt: {}'.format(len(got_to_sym)))
for got, sym in list(got_to_sym.items())[:30]:
    print('  GOT 0x{:08x}  {}'.format(got, sym))
if len(got_to_sym) > 30: print('  ... ({} total)'.format(len(got_to_sym)))

# Walk .plt section: each entry's third instruction `ldr pc, [ip, #imm_c]!`
# computes the GOT slot as we calculated before.
plt = secs.get('.plt')
print()
print('.plt @ 0x{:x} size 0x{:x}'.format(plt[1], plt[2]))
plt_base_va = plt[0]; plt_base_off = plt[1]; plt_size = plt[2]

def arm_modimm(w):
    imm12 = w & 0xFFF
    rot = (imm12 >> 8) & 0xF
    v   = imm12 & 0xFF
    n   = 2 * rot
    if n == 0: return v
    return ((v >> n) | (v << (32 - n))) & 0xFFFFFFFF

# PLT layout: 12 bytes per entry after a 20-byte header in standard ARM ELF.
# Skip the header, then enumerate entries.
PLT_ENTRY_SIZE = 12
PLT_HEADER_SIZE = 20

plt_va_to_got = {}
i = PLT_HEADER_SIZE
while i + 12 <= plt_size:
    entry_va = plt_base_va + i
    entry_off = plt_base_off + i
    w0 = struct.unpack_from('<I', data, entry_off)[0]
    w1 = struct.unpack_from('<I', data, entry_off+4)[0]
    w2 = struct.unpack_from('<I', data, entry_off+8)[0]
    # sanity check: must be add ip,pc; add ip,ip; ldr pc,[ip,...]!
    if (w0 & 0xfffff000) != 0xe28fc000 or (w1 & 0xfffff000) != 0xe28cc000 or (w2 & 0xfff00fff)>>12 != 0xe5bcf:
        # try misaligned layout
        i += 4
        continue
    imm_a = arm_modimm(w0)
    imm_b = arm_modimm(w1)
    imm_c_raw = w2 & 0xFFF
    U = (w2 >> 23) & 1
    imm_c = imm_c_raw if U else -imm_c_raw
    pc = entry_va + 8
    got_slot = (pc + imm_a + imm_b + imm_c) & 0xFFFFFFFF
    plt_va_to_got[entry_va] = got_slot
    i += 12

print('PLT entries decoded: {}'.format(len(plt_va_to_got)))

# Now find Thumb veneers that target PLT entries we care about
# Veneer: (Thumb) bx pc; mov r8,r8; (ARM) ldr r12,[pc,#0]; add pc,r12,pc; .word offset
text = secs['.text']
text_va = text[0]; text_off = text[1]; text_size = text[2]
veneer_to_plt = {}  # veneer_va_thumb -> plt_va
i = 0
while i + 16 <= text_size:
    # Thumb bx pc + mov r8,r8 pattern
    if data[text_off + i] == 0x78 and data[text_off + i + 1] == 0x47 and \
       data[text_off + i + 2] == 0xc0 and data[text_off + i + 3] == 0x46:
        ldrw = struct.unpack_from('<I', data, text_off + i + 4)[0]
        addp = struct.unpack_from('<I', data, text_off + i + 8)[0]
        if (ldrw & 0xfffff000) == 0xe59fc000 and addp == 0xe08cf00f:
            const = struct.unpack_from('<I', data, text_off + i + 12)[0]
            signed_c = const - 0x100000000 if (const & 0x80000000) else const
            veneer_va = text_va + i
            arm_target = (veneer_va + 16 + signed_c) & 0xFFFFFFFF
            if arm_target in plt_va_to_got:
                veneer_to_plt[veneer_va] = arm_target
            i += 16
            continue
    i += 2

print('Veneers->PLT mappings: {}'.format(len(veneer_to_plt)))

# Filter veneers whose PLT target's GOT slot is a JNI symbol of interest
jni_veneers = {}   # veneer_va -> (plt_va, sym_name)
for veneer_va, plt_va in veneer_to_plt.items():
    got = plt_va_to_got[plt_va]
    sym = got_to_sym.get(got)
    if sym:
        jni_veneers[veneer_va] = (plt_va, sym)
print()
print('JNI-interesting veneers: {}'.format(len(jni_veneers)))
for v, (p, s) in sorted(jni_veneers.items()):
    print('  veneer 0x{:08x} -> PLT 0x{:08x} -> {}'.format(v, p, s))

# Scan .text for Thumb-2 BL targeting any of these veneers
print()
print('Callers of JNI veneers:')
caller_count = {}
caller_list = {}
for v in jni_veneers:
    caller_list[v] = []
for off in range(0, text_size - 4, 2):
    hw1 = struct.unpack_from('<H', data, text_off + off)[0]
    hw2 = struct.unpack_from('<H', data, text_off + off + 2)[0]
    if (hw1 & 0xF800) != 0xF000: continue
    if (hw2 & 0xC000) != 0xC000: continue
    S=(hw1>>10)&1; imm10=hw1&0x3FF
    J1=(hw2>>13)&1; J2=(hw2>>11)&1; imm11=hw2&0x7FF
    I1=1^(J1^S); I2=1^(J2^S)
    imm32=(S<<24)|(I1<<23)|(I2<<22)|(imm10<<12)|(imm11<<1)
    if S: imm32 -= (1<<25)
    cur_va = text_va + off
    target = (cur_va + 4 + imm32) & ~1
    if target in jni_veneers:
        caller_list[target].append(cur_va)

_out = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'jni_call_sites.txt'), 'w', encoding='utf-8')
def emit(s=''):
    print(s); _out.write(s + '\n'); _out.flush()

emit('JNI call-site report (libcity_ar.so)')
emit('='*72)
emit('JNI veneers found:')
for v, (p, s) in sorted(jni_veneers.items()):
    emit('  veneer 0x{:08x} -> PLT 0x{:08x} -> {}'.format(v, p, s))
emit('')
for veneer_va, callers in sorted(caller_list.items(), key=lambda kv: jni_veneers[kv[0]][1]):
    _, sym = jni_veneers[veneer_va]
    emit('')
    emit('=== {} ({} callers)  veneer @ 0x{:08x} ==='.format(sym, len(callers), veneer_va))
    by_owner = {}
    for cv in callers:
        ov, on = near(cv)
        by_owner.setdefault((on, ov), []).append(cv)
    for (on, ov), sites in sorted(by_owner.items(), key=lambda kv: kv[1][0]):
        emit('  {} (@0x{:08x})  -- {} call(s)'.format(on, ov or 0, len(sites)))
        for s in sites[:4]:
            emit('    site 0x{:08x}'.format(s))
        if len(sites) > 4:
            emit('    ...{} more'.format(len(sites)-4))

_out.close()
print('---DONE---')
