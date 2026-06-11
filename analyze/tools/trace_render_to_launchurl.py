"""
Find the C++ path from nativeRender to NGDevice.launchUrl.

Plan:
  (1) Locate JNI-bound symbol  Java_com_anansimobile_nge_NDKRenderer_nativeRender
      (or equivalent; also dump every Java_* symbol in the .so so we
      know the naming scheme).
  (2) Find the vtable(s) that contain &ngDeviceAndroid::LaunchURL as a
      function pointer — by scanning data sections for 32-bit values
      equal to the function VA (with Thumb bit). Adjacent function
      pointers give us the slot index and the class name (via a
      typeinfo pointer at vtable-2 / vtable-1 in Itanium ABI).
  (3) Scan .text for every Thumb call sequence that targets that slot
      index:  ldr Rt,[Rb]; ldr Rm,[Rt,#slot*4]; blx Rm
      Bucket the callers by owner function.
  (4) Report all callers — these are the candidate sites in render code
      that pass an empty URL into LaunchURL. Owner functions whose names
      include "Render", "DrawFrame", "Step", "Update", or live within
      nativeRender's address range are the primary suspects.
"""
import os, struct
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

SO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', 'lib', 'armeabi', 'libcity_ar.so')
data = open(SO, 'rb').read()

e_phoff = struct.unpack_from('<I', data, 0x1c)[0]
e_phentsize = struct.unpack_from('<H', data, 0x2a)[0]
e_phnum = struct.unpack_from('<H', data, 0x2c)[0]
segs = []
for i in range(e_phnum):
    o = e_phoff + i * e_phentsize
    t, off, va, _, fsz, msz, *_ = struct.unpack_from('<8I', data, o)
    segs.append((t, off, va, fsz, msz))
def va_to_off(va):
    for t, off, vb, _, msz in segs:
        if t == 1 and vb <= va < vb + msz:
            return off + (va - vb)
def off_to_va(off):
    for t, foff, vb, fsz, msz in segs:
        if t == 1 and foff <= off < foff + msz:
            return vb + (off - foff)

e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize = struct.unpack_from('<H', data, 0x2e)[0]
e_shnum = struct.unpack_from('<H', data, 0x30)[0]
e_shstrndx = struct.unpack_from('<H', data, 0x32)[0]
shstrtab_hdr_off = e_shoff + e_shstrndx * e_shentsize
sh_offset_str = struct.unpack_from('<I', data, shstrtab_hdr_off + 0x10)[0]
sections = []
for i in range(e_shnum):
    base = e_shoff + i * e_shentsize
    sh_name, sh_type, _, sh_addr, sh_off, sh_size, *_ = \
        struct.unpack_from('<10I', data, base)
    name = data[sh_offset_str + sh_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    sections.append(dict(name=name, type=sh_type, addr=sh_addr, off=sh_off, size=sh_size))
def sec(n):
    for s in sections:
        if s['name'] == n: return s

dynsym = sec('.dynsym'); dynstr = sec('.dynstr')
symbols = {}; sym_by_va = {}
for i in range(dynsym['size'] // 16):
    so = dynsym['off'] + i * 16
    st_name, st_value, st_size, *_ = struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off'] + st_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    if nm:
        symbols[nm] = (st_value, st_size)
        sym_by_va[st_value & ~1] = nm
def nearest_sym(va):
    best=None
    for s in sorted(sym_by_va):
        if s > va: break
        best=s
    return best, sym_by_va.get(best)

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True

# ============================================================
# (1) JNI-bound symbols: Java_*
# ============================================================
print('='*72)
print('(1) JNI-bound symbols in libcity_ar.so')
print('='*72)
jni_syms = [(v[0], v[1], k) for k, v in symbols.items() if k.startswith('Java_')]
jni_syms.sort()
print(f'  total Java_* symbols: {len(jni_syms)}')
for va, sz, n in jni_syms:
    if 'NDKRender' in n or 'NGDevice' in n or 'launchUrl' in n.lower() or 'native' in n.lower():
        print(f'    va=0x{va:08x}  size={sz:>6}  {n}')
print('  -- only render/device related shown; others omitted.')

# Pick out the nativeRender symbol
nrender_va = None; nrender_sz = None
for va, sz, n in jni_syms:
    if 'NDKRenderer' in n and 'nativeRender' in n:
        nrender_va = va & ~1; nrender_sz = sz
        print(f'\n  nativeRender entry: {n}\n    va=0x{nrender_va:08x}  size={nrender_sz}')
        break
if nrender_va is None:
    for va, sz, n in jni_syms:
        if 'nativeRender' in n:
            nrender_va = va & ~1; nrender_sz = sz
            print(f'\n  (fallback) nativeRender entry: {n}\n    va=0x{nrender_va:08x}  size={nrender_sz}')
            break

# ============================================================
# (2) Find vtables containing &ngDeviceAndroid::LaunchURL
# ============================================================
print()
print('='*72)
print('(2) vtables containing &ngDeviceAndroid::LaunchURL (0x5efb9c)')
print('='*72)
launch_va_thumb = 0x005efb9d   # Thumb bit set
launch_va_raw   = 0x005efb9c
needle1 = struct.pack('<I', launch_va_thumb)
needle2 = struct.pack('<I', launch_va_raw)

vtable_hits = []
for nm in ('.data.rel.ro', '.data.rel.ro.local', '.data', '.rodata'):
    s = sec(nm)
    if not s: continue
    blob = data[s['off']:s['off']+s['size']]
    base_va = s['addr']
    for needle, tag in ((needle1, 'thumb'), (needle2, 'raw')):
        i = 0
        while True:
            p = blob.find(needle, i)
            if p < 0: break
            if p % 4 == 0:
                vtable_hits.append((s['off']+p, base_va+p, nm, tag))
            i = p + 4

if not vtable_hits:
    print('  (no occurrences of LaunchURL VA found in data sections)')
else:
    for foff, va, secname, tag in vtable_hits:
        print(f'  {tag:5s} hit  {secname}  file_off=0x{foff:08x}  va=0x{va:08x}')

# For each hit, reconstruct the surrounding vtable: scan backwards for
# Itanium-style typeinfo header (offset_to_top + typeinfo_ptr) and
# enumerate function pointer slots until a NULL or non-text address.
def is_text_va(v):
    if v == 0: return False
    text = sec('.text')
    return text['addr'] <= (v & ~1) < text['addr'] + text['size']

print()
print('  Reconstructed vtable around each hit (slot index of LaunchURL):')
for foff, va, secname, tag in vtable_hits:
    # walk back until we find two consecutive non-text values (typeinfo header)
    start_off = foff
    while start_off >= 8:
        v0 = struct.unpack_from('<I', data, start_off - 8)[0]
        v1 = struct.unpack_from('<I', data, start_off - 4)[0]
        # typeinfo ptr should be non-text (data area), offset_to_top often 0 or small
        if not is_text_va(v0) and not is_text_va(v1):
            # also require the very next slot is a text VA (start of vtable)
            v2 = struct.unpack_from('<I', data, start_off)[0]
            if is_text_va(v2):
                break
        start_off -= 4
    # walk forward enumerating function pointers
    print(f'\n  vtable starting near file_off=0x{start_off:08x}  va=0x{off_to_va(start_off):08x} (in {secname})')
    # try to resolve typeinfo string
    ti_ptr = struct.unpack_from('<I', data, start_off - 4)[0]
    if ti_ptr:
        ti_off = va_to_off(ti_ptr)
        if ti_off:
            # typeinfo: vptr; name_ptr; ...   name_ptr at +4
            try:
                name_ptr = struct.unpack_from('<I', data, ti_off + 4)[0]
                if name_ptr:
                    no = va_to_off(name_ptr)
                    if no:
                        end = data.find(b'\x00', no, no + 128)
                        if end > 0:
                            print(f'    typeinfo name @0x{name_ptr:08x}: {data[no:end].decode("ascii","replace")!r}')
            except: pass

    slot = 0; cur = start_off
    while cur + 4 <= len(data) and slot < 64:
        v = struct.unpack_from('<I', data, cur)[0]
        if not is_text_va(v):
            break
        nm = sym_by_va.get(v & ~1)
        mark = '   <-- LaunchURL' if v in (launch_va_thumb, launch_va_raw) else ''
        if nm or mark:
            print(f'    slot[{slot:2d}]  off=0x{cur:08x}  va=0x{v:08x}  ({nm}){mark}')
        elif slot < 24:
            print(f'    slot[{slot:2d}]  off=0x{cur:08x}  va=0x{v:08x}')
        cur += 4; slot += 1

# Determine the slot index (use first thumb hit if any)
launch_slot_byte = None
if vtable_hits:
    foff, va, secname, tag = vtable_hits[0]
    # find the start of this vtable
    start_off = foff
    while start_off >= 8:
        v0 = struct.unpack_from('<I', data, start_off - 8)[0]
        v1 = struct.unpack_from('<I', data, start_off - 4)[0]
        if not is_text_va(v0) and not is_text_va(v1):
            v2 = struct.unpack_from('<I', data, start_off)[0]
            if is_text_va(v2):
                break
        start_off -= 4
    launch_slot_byte = foff - start_off  # byte offset within vtable from slot 0
    print(f'\n  -> LaunchURL slot byte-offset within vtable = 0x{launch_slot_byte:x}')

# ============================================================
# (3) Scan .text for vtable calls with offset == launch_slot_byte
# ============================================================
if launch_slot_byte is not None:
    print()
    print('='*72)
    print(f'(3) all .text sites doing  ldr Rt,[Rb,#0x{launch_slot_byte:x}] ; blx Rt')
    print('='*72)
    text = sec('.text')
    text_off = text['off']; text_va = text['addr']; text_size = text['size']
    callers = []
    # Encodings for Thumb LDR (immediate offset):
    #   T1 LDR (imm, small): 01101 imm5 Rn Rt  hw = 0x6800..0x6FFF
    #     offset = imm5 * 4  (max 124)
    #   T3 (32-bit LDR.W imm12): F8DF / F8Dx ...
    for off in range(0, text_size - 6, 2):
        # Look for small Thumb LDR  ldr Rt,[Rb,#imm] where imm == launch_slot_byte
        hw = struct.unpack_from('<H', data, text_off + off)[0]
        match_offset = None; rb=None; rt=None
        if 0x6800 <= hw <= 0x6FFF:
            imm5 = (hw >> 6) & 0x1F
            ofs = imm5 * 4
            if ofs == launch_slot_byte:
                rb = (hw >> 3) & 7
                rt = hw & 7
                match_offset = ofs
        # also try Thumb-2 LDR.W imm12
        elif (hw & 0xFFF0) == 0xF8D0:
            hw2 = struct.unpack_from('<H', data, text_off + off + 2)[0]
            imm12 = hw2 & 0xFFF
            if imm12 == launch_slot_byte:
                rb = hw & 0xF
                rt = (hw2 >> 12) & 0xF
                match_offset = imm12
        if match_offset is None: continue
        # the next or following instruction should be blx Rt (4xxx)
        # Scan a few instructions ahead.
        for k in range(2, 12, 2):
            hwn = struct.unpack_from('<H', data, text_off + off + k)[0]
            # blx Rm encoding: 0100 0111 1 Rm[3:0] 000 -> 0x4780..0x47F8 stride 8
            if 0x4780 <= hwn <= 0x47FF and ((hwn >> 3) & 0xF) == rt:
                cur_va = text_va + off
                ov, on = nearest_sym(cur_va)
                callers.append((cur_va, on, ov))
                break
    print(f'  total candidate call sites: {len(callers)}')
    grouped = {}
    for cur, on, ov in callers:
        grouped.setdefault((on, ov), []).append(cur)
    for (on, ov), sites in sorted(grouped.items(), key=lambda x: x[1][0]):
        in_render = (nrender_va is not None
                     and nrender_va <= sites[0] < nrender_va + (nrender_sz or 0))
        mark = '  *** INSIDE nativeRender ***' if in_render else ''
        print(f'  {on} (@0x{ov:08x}) — {len(sites)} site(s){mark}')
        for s in sites[:6]:
            print(f'    0x{s:08x}')
        if len(sites) > 6:
            print(f'    ... and {len(sites)-6} more')
