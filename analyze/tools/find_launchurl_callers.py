"""
Find ngDevice::LaunchURL native symbol, then locate every caller
inside libcity_ar.so. Also dump the disasm of caller-functions whose
chain leads into CheckUpdate or its sibling CLoadingScreen methods.
"""
import struct, os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

SO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', 'lib', 'armeabi', 'libcity_ar.so')
data = open(SO, 'rb').read()

e_phoff = struct.unpack_from('<I', data, 0x1c)[0]
e_phentsize = struct.unpack_from('<H', data, 0x2a)[0]
e_phnum = struct.unpack_from('<H', data, 0x2c)[0]
e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize = struct.unpack_from('<H', data, 0x2e)[0]
e_shnum = struct.unpack_from('<H', data, 0x30)[0]
e_shstrndx = struct.unpack_from('<H', data, 0x32)[0]

segments = []
for i in range(e_phnum):
    base = e_phoff + i * e_phentsize
    p_type, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, p_align = \
        struct.unpack_from('<8I', data, base)
    segments.append(dict(type=p_type, off=p_offset, vaddr=p_vaddr,
                         filesz=p_filesz, memsz=p_memsz, flags=p_flags))
def va_to_off(va):
    for s in segments:
        if s['type'] == 1 and s['vaddr'] <= va < s['vaddr'] + s['memsz']:
            return s['off'] + (va - s['vaddr'])
    return None

sections = []
shstrtab_hdr_off = e_shoff + e_shstrndx * e_shentsize
sh_offset_str = struct.unpack_from('<I', data, shstrtab_hdr_off + 0x10)[0]
for i in range(e_shnum):
    base = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, *_ = \
        struct.unpack_from('<10I', data, base)
    name = data[sh_offset_str + sh_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    sections.append(dict(name=name, type=sh_type, addr=sh_addr, off=sh_offset, size=sh_size))
def sec(n):
    for s in sections:
        if s['name'] == n: return s
def sec_by_addr(va):
    for s in sections:
        if s['addr'] and s['addr'] <= va < s['addr'] + s['size']: return s

dynsym = sec('.dynsym')
dynstr = sec('.dynstr')
symbols = {}
sym_by_va = {}
for i in range(dynsym['size'] // 16):
    so = dynsym['off'] + i * 16
    st_name, st_value, st_size, st_info, st_other, st_shndx = \
        struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off'] + st_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    if nm:
        symbols[nm] = (st_value, st_size)
        sym_by_va[st_value & ~1] = nm

def find_sym_va(name):
    return symbols.get(name, (None, None))[0]

candidates = ['_ZN8ngDevice9LaunchURLEPKc',
              '_ZN15ngDeviceAndroid9LaunchURLEPKc']
print('=== LaunchURL symbol addresses ===')
launchurl_targets = []
for n in candidates:
    v, sz = symbols.get(n, (None, None))
    if v:
        print(f'  {n}\n    va=0x{v:08x} (off=0x{va_to_off(v & ~1):x}) size={sz}')
        launchurl_targets.append((n, v & ~1, sz))

# Scan whole .text for Thumb BL/BLX with target == any of these
text = sec('.text')
print(f'\n.text @ va=0x{text["addr"]:08x} off=0x{text["off"]:x} size=0x{text["size"]:x}')

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True

# Build interesting target set
target_set = {t for _, t, _ in launchurl_targets}

# To find callers we need to disassemble linearly — Thumb BL is 4 bytes.
# We'll scan in 2-byte step, attempt 4-byte BL decode by checking bits.
print('\n=== Callers of LaunchURL ===')
i = 0
text_va = text['addr']
text_off = text['off']
text_size = text['size']
callers = []
# Pre-scan: find BL/BLX-to-target by Thumb-2 encoding.
# Thumb-2 BL/BLX is 32-bit:
#   first half 0b11110_S_imm10  -> 0xF000..0xF7FF
#   second   : BL: 0b11_1_1_imm11 = 0xD000..0xDFFF (bit 0 of [-1 of byte] = 1 for BL)
#   actually decoding properly using capstone is easier — we just need to bulk-disasm and search for 'launchurl' targets.
# That's slow but workable for 7MB binary. Let's restrict to Thumb-2 prefixed offsets.
for off in range(0, text_size - 4, 2):
    hw1 = struct.unpack_from('<H', data, text_off + off)[0]
    hw2 = struct.unpack_from('<H', data, text_off + off + 2)[0]
    if (hw1 & 0xF800) != 0xF000:
        continue
    if (hw2 & 0xC000) != 0xC000:  # BL/BLX
        continue
    # Decode BL/BLX offset
    S = (hw1 >> 10) & 1
    imm10 = hw1 & 0x3FF
    J1 = (hw2 >> 13) & 1
    J2 = (hw2 >> 11) & 1
    imm11 = hw2 & 0x7FF
    I1 = 1 ^ (J1 ^ S)
    I2 = 1 ^ (J2 ^ S)
    imm32 = (S << 24) | (I1 << 23) | (I2 << 22) | (imm10 << 12) | (imm11 << 1)
    if S:
        imm32 -= (1 << 25)
    cur_va = text_va + off
    pc = cur_va + 4  # Thumb PC
    target = pc + imm32
    is_blx = ((hw2 >> 12) & 1) == 0  # BLX has H=0
    if is_blx:
        target &= ~3
    target &= ~1
    if target in target_set:
        # Determine which function this call is inside
        # Find nearest preceding symbol that is a function
        owner = None
        for sym_va in sorted(sym_by_va):
            if sym_va > cur_va: break
            owner = sym_va
        callers.append((cur_va, target, owner))

for cur, tgt, owner in callers:
    own = sym_by_va.get(owner) if owner else '?'
    print(f'  call_at=0x{cur:08x} -> 0x{tgt:08x}   in {own} (sym_va=0x{owner:08x})')

print(f'\nTotal callers: {len(callers)}')

# Output the symbol address of CheckUpdate
cu = find_sym_va('_ZN14CLoadingScreen11CheckUpdateEPKcS1_')
print(f'\nCheckUpdate va=0x{cu:08x}')

# Check the bl target 0x6a8c9c from CheckUpdate (the arg2==NULL branch) — what symbol is at 0x6a8c9c?
def nearest_sym(va):
    best = None
    for sym_va in sorted(sym_by_va):
        if sym_va > va: break
        best = sym_va
    return best, sym_by_va.get(best)

print(f'\nbl 0x6a8c9c from CheckUpdate (arg2==NULL branch):')
nv, nn = nearest_sym(0x6a8c9c)
print(f'   nearest sym: 0x{nv:08x} -> {nn}')

print(f'\nbl 0x693b7c (vtable getter helper):')
nv, nn = nearest_sym(0x693b7c)
print(f'   nearest sym: 0x{nv:08x} -> {nn}')

print(f'\nbl 0x693a3c (string-load helper?):')
nv, nn = nearest_sym(0x693a3c)
print(f'   nearest sym: 0x{nv:08x} -> {nn}')

print(f'\nbl 0x69320c (call from arg2==NULL and at end):')
nv, nn = nearest_sym(0x69320c)
print(f'   nearest sym: 0x{nv:08x} -> {nn}')

# Now, for each unique caller-owner that we found of LaunchURL, dump symbol name + look for the
# state byte pattern (`#0xab; lsls #2`) or hard-coded #684 ldrb anywhere.
print('\n=== Searching for any function that reads/writes this+0x2AC (this+684) ===')
# Look for the exact instruction pair we already see:
# 0xab20 = movs r0, #0xab
# 0x8000 = lsls r0, r0, #2
pat = b'\xab\x20\x80\x00'
i = 0
while True:
    p = data.find(pat, i)
    if p < 0: break
    va = None
    for s in segments:
        if s['type'] == 1 and s['off'] <= p < s['off'] + s['filesz']:
            va = s['vaddr'] + (p - s['off'])
            break
    nv, nn = (None, None)
    if va is not None:
        # Find nearest preceding symbol
        for sym_va in sorted(sym_by_va):
            if sym_va > va: break
            nv = sym_va; nn = sym_by_va[sym_va]
    print(f'  off=0x{p:08x} va=0x{va:08x}  in {nn} (@0x{nv:08x})' if va else f'  off=0x{p:x} (no PT_LOAD)')
    i = p + 2
