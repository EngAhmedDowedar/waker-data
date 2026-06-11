"""
Find the vtable slot for ngDeviceAndroid::LaunchURL via:
  (A) .rel.dyn relocations of type R_ARM_RELATIVE whose effective
      relocated value (i.e. addend) equals LaunchURL's VA (with Thumb
      bit). The slot's file offset / VA names the vtable slot.
  (B) once the vtable VA is known, dump enclosing vtable backwards
      to find typeinfo / class name and compute the byte-offset of
      the LaunchURL slot from the vtable start.
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

e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize = struct.unpack_from('<H', data, 0x2e)[0]
e_shnum = struct.unpack_from('<H', data, 0x30)[0]
e_shstrndx = struct.unpack_from('<H', data, 0x32)[0]
shstrtab_hdr_off = e_shoff + e_shstrndx * e_shentsize
sh_offset_str = struct.unpack_from('<I', data, shstrtab_hdr_off + 0x10)[0]
sections = []
for i in range(e_shnum):
    base = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_off, sh_size, sh_link, sh_info, *_ = \
        struct.unpack_from('<10I', data, base)
    name = data[sh_offset_str + sh_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    sections.append(dict(name=name, type=sh_type, addr=sh_addr, off=sh_off,
                         size=sh_size, link=sh_link, info=sh_info))
def sec(n):
    for s in sections:
        if s['name'] == n: return s

dynsym = sec('.dynsym'); dynstr = sec('.dynstr')
sym_by_va = {}; symbols = {}
for i in range(dynsym['size'] // 16):
    so = dynsym['off'] + i * 16
    st_name, st_value, st_size, *_ = struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off'] + st_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    if nm:
        symbols[nm] = (st_value, st_size)
        sym_by_va[st_value & ~1] = nm

# --- (A) walk .rel.dyn relocations
rel_dyn = sec('.rel.dyn')
print(f'.rel.dyn @ off=0x{rel_dyn["off"]:x} size=0x{rel_dyn["size"]:x}')
# ELF32 Rel: r_offset (u32), r_info (u32). type=info&0xff, sym=info>>8
launch_va_thumb = 0x005efb9d
launch_va_raw   = 0x005efb9c
matches = []
n = rel_dyn['size'] // 8
for i in range(n):
    rb = rel_dyn['off'] + i * 8
    r_offset, r_info = struct.unpack_from('<II', data, rb)
    r_type = r_info & 0xff
    r_sym  = r_info >> 8
    if r_type != 23:   # R_ARM_RELATIVE = 23
        continue
    # addend is read from the relocation target in-file
    tgt_off = va_to_off(r_offset)
    if tgt_off is None or tgt_off + 4 > len(data): continue
    addend = struct.unpack_from('<I', data, tgt_off)[0]
    if addend in (launch_va_thumb, launch_va_raw):
        matches.append((r_offset, tgt_off, addend))

print(f'\nR_ARM_RELATIVE relocations whose addend is LaunchURL VA: {len(matches)}')
for r_off, t_off, addend in matches:
    # walk back to find the start of the enclosing vtable
    # in .data.rel.ro / .data, vtables: ... offset_to_top, typeinfo_ptr, [fn ptrs ...]
    print(f'\n  slot @ va=0x{r_off:08x} file_off=0x{t_off:08x} addend=0x{addend:08x}')

    # Find vtable start: scan back for [non-text, non-text] header
    text = sec('.text')
    def is_text(v):
        return v != 0 and text['addr'] <= (v & ~1) < text['addr'] + text['size']

    start = t_off
    while start >= 8:
        v0 = struct.unpack_from('<I', data, start - 8)[0]
        v1 = struct.unpack_from('<I', data, start - 4)[0]
        v2 = struct.unpack_from('<I', data, start)[0]
        if not is_text(v0) and not is_text(v1) and is_text(v2):
            break
        start -= 4
    vtable_va = r_off - (t_off - start)
    slot_byte = t_off - start
    print(f'    enclosing vtable: file_off=0x{start:08x}  va=0x{vtable_va:08x}')
    print(f'    LaunchURL slot byte-offset within vtable = 0x{slot_byte:x}  (slot index {slot_byte//4})')

    # typeinfo at start-4 -> name string at typeinfo+4
    ti = struct.unpack_from('<I', data, start - 4)[0]
    if ti:
        tio = va_to_off(ti)
        if tio:
            try:
                np = struct.unpack_from('<I', data, tio + 4)[0]
                if np:
                    no = va_to_off(np)
                    if no:
                        e = data.find(b'\x00', no, no + 200)
                        if e > 0:
                            print(f'    typeinfo name @0x{np:08x}: {data[no:e].decode("ascii","replace")!r}')
            except: pass

    # enumerate slots forward, name those with known dynsyms
    print(f'    vtable slots:')
    cur = start; slot = 0
    while cur + 4 <= len(data) and slot < 40:
        v = struct.unpack_from('<I', data, cur)[0]
        if not is_text(v) and slot > 0:
            break
        nm = sym_by_va.get(v & ~1)
        mark = '   <-- LaunchURL' if v in (launch_va_thumb, launch_va_raw) else ''
        if mark or nm:
            print(f'      slot[{slot:2d}] off=0x{cur-start:>3x}  va=0x{v:08x}  {nm or ""}{mark}')
        cur += 4; slot += 1

# --- store the slot offset for the next stage
if matches:
    slot_byte = matches[0][1] - 0  # we'll recompute below
    # recompute slot_byte by finding the first match's vtable start
    r_off, t_off, addend = matches[0]
    text = sec('.text')
    def is_text2(v): return v != 0 and text['addr'] <= (v & ~1) < text['addr'] + text['size']
    start = t_off
    while start >= 8:
        v0 = struct.unpack_from('<I', data, start - 8)[0]
        v1 = struct.unpack_from('<I', data, start - 4)[0]
        v2 = struct.unpack_from('<I', data, start)[0]
        if not is_text2(v0) and not is_text2(v1) and is_text2(v2):
            break
        start -= 4
    slot_byte = t_off - start

    # --- (C) scan .text for ldr Rt,[Rb,#slot_byte]; blx Rt sites
    print()
    print('='*72)
    print(f'(C) Thumb call sites with offset 0x{slot_byte:x} -> blx (LaunchURL dispatch):')
    print('='*72)
    text_off = text['off']; text_va = text['addr']; text_size = text['size']
    callers = []
    for off in range(0, text_size - 8, 2):
        hw = struct.unpack_from('<H', data, text_off + off)[0]
        rb = rt = None; match = False
        if 0x6800 <= hw <= 0x6FFF:
            imm5 = (hw >> 6) & 0x1F
            if imm5 * 4 == slot_byte:
                rb = (hw >> 3) & 7; rt = hw & 7; match = True
        elif (hw & 0xFFF0) == 0xF8D0:
            hw2 = struct.unpack_from('<H', data, text_off + off + 2)[0]
            if (hw2 & 0xFFF) == slot_byte:
                rb = hw & 0xF; rt = (hw2 >> 12) & 0xF; match = True
        if not match: continue
        # look ahead for blx Rt within 12 bytes
        for k in range(2, 14, 2):
            hwn = struct.unpack_from('<H', data, text_off + off + k)[0]
            if 0x4780 <= hwn <= 0x47FF and ((hwn >> 3) & 0xF) == rt:
                cur_va = text_va + off
                # owner
                best = None
                for sv in sorted(sym_by_va):
                    if sv > cur_va: break
                    best = sv
                owner = sym_by_va.get(best)
                callers.append((cur_va, best, owner))
                break
    print(f'  candidate sites: {len(callers)}')
    grouped = {}
    for cur, ov, on in callers:
        grouped.setdefault((on, ov), []).append(cur)

    # narrow to interesting candidates: anything that looks render-related
    interesting_kw = ('Render','Render','DrawFrame','Update','Step','Run','Tick',
                      'nativeRender','OnReceive')
    print()
    print('  Grouped by owner (render-keyworded shown first):')
    def is_interesting(on):
        return on and any(k in on for k in interesting_kw)
    sorted_groups = sorted(grouped.items(), key=lambda kv: (0 if is_interesting(kv[0][0]) else 1, kv[1][0]))
    for (on, ov), sites in sorted_groups[:40]:
        mark = '  ***' if is_interesting(on) else ''
        print(f'    {on or "?"} (@0x{(ov or 0):08x}){mark}')
        for s in sites[:4]:
            print(f'      site 0x{s:08x}')
        if len(sites) > 4:
            print(f'      ... +{len(sites)-4}')
    if len(sorted_groups) > 40:
        print(f'    ... +{len(sorted_groups)-40} more owner groups')
