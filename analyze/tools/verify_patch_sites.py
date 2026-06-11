"""
Verify the exact bytes at every candidate patch site within
CLoadingScreen::CheckUpdate, and dump:
  - what's at 0x6a8c9c (the bl from the arg2==NULL branch)
  - what's at 0x48ed6e in CLoadingScreen ctor (where this+0x2AC also appears)
  - ngDeviceAndroid::LaunchURL disasm (for the JNI bridge confirmation)
"""
import struct, os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

SO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', 'lib', 'armeabi', 'libcity_ar.so')
data = open(SO, 'rb').read()

# minimal PT_LOAD map
e_phoff = struct.unpack_from('<I', data, 0x1c)[0]
e_phentsize = struct.unpack_from('<H', data, 0x2a)[0]
e_phnum = struct.unpack_from('<H', data, 0x2c)[0]
segs = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    t, off, va, _, fsz, msz, *_ = struct.unpack_from('<8I', data, o)
    segs.append((t, off, va, fsz, msz))
def va_to_off(va):
    for t, off, vb, fsz, msz in segs:
        if t == 1 and vb <= va < vb + msz:
            return off + (va - vb)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)

def disasm_at(va, n_bytes, label):
    print(f'\n--- {label}  va=0x{va:08x}  off=0x{va_to_off(va):08x} ---')
    o = va_to_off(va)
    code = data[o:o+n_bytes]
    print(f'    raw bytes: {code.hex()}')
    for ins in md.disasm(code, va):
        print(f'    0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic} {ins.op_str}')

# 1. patch sites in CheckUpdate
disasm_at(0x48f8ba, 4, 'patch site A: cmp r4,#0 + beq desc-NULL')
disasm_at(0x48f8ec, 8, 'patch site B: state-byte read (this+0x2AC)')
disasm_at(0x48f90e, 4, 'patch site C: cmp r7,#0 + beq state==0')
disasm_at(0x48f918, 4, 'patch site D: blx r4 (state!=0 dispatch)')

# 2. helper at 0x6a8c9c (called from desc-NULL branch)
disasm_at(0x6a8c9c, 64, '0x6a8c9c (suspect helper called when arg2==NULL)')

# 3. CLoadingScreen ctor read of this+0x2AC
disasm_at(0x48ed6e - 6, 28, 'CLoadingScreen ctor near this+0x2AC')

# 4. ngDeviceAndroid::LaunchURL
disasm_at(0x5efb9c, 172, 'ngDeviceAndroid::LaunchURL (JNI bridge)')

# 5. show the PC-relative constant loaded at 0x48f920 (ldr r1, [pc, #0x30])
# Thumb PC = (pc & ~3) + 4 at decode time, so:
# pc_for_decode = (0x48f920 & ~3) + 4 = 0x48f924
# offset = 0x30 -> address = 0x48f924 + 0x30 = 0x48f954
off = va_to_off(0x48f954)
val = struct.unpack_from('<I', data, off)[0]
print(f'\nPC-rel constant @0x48f954 (used by ldr r1,[pc,#0x30] at 0x48f920) = 0x{val:08x}')
# helper-B (0x69320c) returns base, plus this constant -> what is base+const?
# (Without disassembling helper-B fully we cannot resolve to a name, but record raw value.)

# 6. show the PC-relative at end (ldr r1, [pc, #8] at 0x48f944)
# pc_for_decode = (0x48f944 & ~3) + 4 = 0x48f948 ;  + 8 = 0x48f950
off = va_to_off(0x48f950)
val = struct.unpack_from('<I', data, off)[0]
print(f'PC-rel constant @0x48f950 (used by ldr r1,[pc,#8] at 0x48f944) = 0x{val:08x}')
