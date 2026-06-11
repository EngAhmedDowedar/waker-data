"""
Targeted static analysis pass for the next decision point.

Inputs: libcity_ar.so
Output: structured report covering
  (7) every launchUrl / LaunchURL / update / url / version / intent string
      in .rodata (with offset and ±64-byte cluster context)
  (8) callers of CLoadingScreen::CheckUpdate (0x48f8b1) and every branch
      site whose target lies inside the CheckUpdate region [0x48f8b0, 0x48f960)
  (9) the opcode dispatch tree in CLoadingScreen::OnReceiveResponse and
      the full disasm of the opcode=0x80 (CheckVersion) success path,
      including the next vtable-dispatched method whose return value
      becomes the next state gate.

Goal: identify the minimal native condition blocking progression after
/checkversion is delivered, so we can pick between
  - minimal valid response schema, or
  - minimal safe native patch.
"""
import os, struct, re, sys
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

SO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', 'lib', 'armeabi', 'libcity_ar.so')
data = open(SO, 'rb').read()

# --- ELF parsing ---
e_phoff = struct.unpack_from('<I', data, 0x1c)[0]
e_phentsize = struct.unpack_from('<H', data, 0x2a)[0]
e_phnum = struct.unpack_from('<H', data, 0x2c)[0]
e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize = struct.unpack_from('<H', data, 0x2e)[0]
e_shnum = struct.unpack_from('<H', data, 0x30)[0]
e_shstrndx = struct.unpack_from('<H', data, 0x32)[0]

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

shstrtab_hdr_off = e_shoff + e_shstrndx * e_shentsize
sh_offset_str = struct.unpack_from('<I', data, shstrtab_hdr_off + 0x10)[0]
sections = []
for i in range(e_shnum):
    base = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_off, sh_size, *_ = \
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
# (7) String dump: launch / launchurl / update / url / version / intent / scheme
# ============================================================
print('='*72)
print('(7) launchUrl / LaunchURL / update / url-related strings in binary')
print('='*72)

rodata = sec('.rodata')
data_sec = sec('.data')
search_regions = [(rodata['off'], rodata['off']+rodata['size'], '.rodata')]
if data_sec:
    search_regions.append((data_sec['off'], data_sec['off']+data_sec['size'], '.data'))

# Scan for null-terminated ASCII strings of length 3..256 then filter
def scan_strings(b, lo, hi):
    out = []
    i = lo
    while i < hi:
        if 0x20 <= b[i] < 0x7f:
            j = i
            while j < hi and 0x20 <= b[j] < 0x7f:
                j += 1
            # require null terminator and min length
            if j < hi and b[j] == 0 and (j - i) >= 3:
                out.append((i, b[i:j].decode('ascii','replace')))
            i = j + 1
        else:
            i += 1
    return out

keywords = re.compile(r'launch|update|url|intent|scheme|version|review|major|isReview|needUpdate|forceUpdate|description|apkUrl|downloadUrl|patchUrl|redirect|policy|server|host|ActivityNotFound|ACTION_VIEW|wakr|anansigame', re.I)

hits = []
for lo, hi, name in search_regions:
    for off, s in scan_strings(data, lo, hi):
        if keywords.search(s):
            hits.append((off, name, s))

# Cluster by proximity: print +/-2 strings as context
hits_sorted = sorted(hits, key=lambda x: x[0])
already = set()
for i, (off, sec_name, s) in enumerate(hits_sorted):
    if i in already: continue
    cluster = [hits_sorted[i]]
    j = i + 1
    while j < len(hits_sorted) and hits_sorted[j][0] - hits_sorted[j-1][0] < 256:
        cluster.append(hits_sorted[j]); already.add(j); j += 1
    if len(cluster) >= 1:
        print(f'  cluster @ {sec_name} 0x{cluster[0][0]:08x}:')
        for o, sn, st in cluster:
            print(f'    0x{o:08x}  {st!r}')

# Look up cross-references: who loads these string addresses via PC-relative ldr?
print()
print('--- LDR pc-relative xrefs to selected high-signal strings ---')
text = sec('.text')
text_va = text['addr']; text_off = text['off']; text_size = text['size']

key_strings = [s for off, _, s in hits if any(k in s for k in (
    'launchUrl','LaunchURL','updateUrl','launch','apkUrl','downloadUrl',
    'patchUrl','redirectUrl','needUpdate','forceUpdate','description'))]
key_str_vas = []
for off, _, s in hits:
    if s in key_strings:
        va = off_to_va(off)
        if va is not None: key_str_vas.append((va, s))

# Scan .text for ARM/Thumb LDR-literal that load any of these addresses
# Thumb LDR (literal): 0x4800..0x4fff encodes "ldr Rd, [pc, #imm8*4]"
# 32-bit Thumb LDR.W literal: 0xF8DF Rd[12:15] imm12 ...
xref_table = {va: [] for va, _ in key_str_vas}

for off in range(0, text_size - 4, 2):
    hw1 = struct.unpack_from('<H', data, text_off + off)[0]
    # 16-bit T1 LDR (literal)
    if 0x4800 <= hw1 <= 0x4FFF:
        Rd = (hw1 >> 8) & 7
        imm8 = hw1 & 0xFF
        cur_va = text_va + off
        pc = (cur_va + 4) & ~3
        litaddr = pc + imm8 * 4
        litoff = va_to_off(litaddr)
        if litoff is None: continue
        if litoff + 4 > len(data): continue
        val = struct.unpack_from('<I', data, litoff)[0]
        # Two cases: literal is a raw VA, OR (very common) the literal is an *offset*
        # added to PC via subsequent "add Rd, pc" pattern.
        if val in xref_table:
            xref_table[val].append((cur_va, 'direct'))
        else:
            # check for offset+pc pattern: next insn might be "add Rd, pc" (4478..447F)
            hw2 = struct.unpack_from('<H', data, text_off + off + 2)[0]
            if 0x4478 <= hw2 <= 0x447F:
                target = (cur_va + 4 + val) & 0xFFFFFFFF
                if target in xref_table:
                    xref_table[target].append((cur_va, 'pc+lit'))

for va, s in key_str_vas:
    refs = xref_table.get(va, [])
    if refs:
        print(f'  "{s}" @ va 0x{va:08x}')
        for ref_va, mode in refs[:8]:
            ov, on = nearest_sym(ref_va)
            print(f'    xref at 0x{ref_va:08x}  ({mode})  in {on} (@0x{ov:08x})')
        if len(refs) > 8:
            print(f'    ...({len(refs)-8} more)')

# ============================================================
# (8) Callers of CheckUpdate + branches into [0x48f8b0, 0x48f960)
# ============================================================
print()
print('='*72)
print('(8) callers of CheckUpdate and branches into the patched region')
print('='*72)

cu_va = symbols['_ZN14CLoadingScreen11CheckUpdateEPKcS1_'][0] & ~1
region_lo = cu_va
region_hi = (cu_va + 168 + 16) & ~1
print(f'  CheckUpdate region: [0x{region_lo:08x}, 0x{region_hi:08x})')

# Scan for Thumb-2 BL/BLX and 16-bit B / Bcc landing in the region.
direct_callers = []
internal_branches = []

# 32-bit BL/BLX
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
    pc = cur_va + 4
    target = pc + imm32
    is_blx = ((hw2 >> 12) & 1) == 0
    if is_blx: target &= ~3
    target_clean = target & ~1
    if region_lo <= target_clean < region_hi:
        ov, on = nearest_sym(cur_va)
        if target_clean == cu_va:
            direct_callers.append((cur_va, ov, on))
        else:
            internal_branches.append((cur_va, target_clean, ov, on))

# Also scan for 16-bit B and Bcc that land in the region (only useful for
# branches from within the same function, but we'll keep them).
for off in range(0, text_size - 2, 2):
    hw1 = struct.unpack_from('<H', data, text_off + off)[0]
    cur_va = text_va + off
    target = None
    if (hw1 & 0xF000) == 0xD000 and ((hw1 >> 8) & 0xF) != 0xE and ((hw1 >> 8) & 0xF) != 0xF:
        # Bcc T1
        imm8 = hw1 & 0xFF
        if imm8 & 0x80: imm8 -= 0x100
        target = cur_va + 4 + imm8 * 2
    elif (hw1 & 0xF800) == 0xE000:
        # B T2
        imm11 = hw1 & 0x7FF
        if imm11 & 0x400: imm11 -= 0x800
        target = cur_va + 4 + imm11 * 2
    if target is not None and region_lo <= (target & ~1) < region_hi:
        ov, on = nearest_sym(cur_va)
        # ignore internal CheckUpdate self-branches
        if region_lo <= cur_va < region_hi:
            continue
        internal_branches.append((cur_va, target & ~1, ov, on))

print(f'\n  direct BL/BLX -> CheckUpdate ({len(direct_callers)}):')
for cur, ov, on in direct_callers:
    print(f'    0x{cur:08x}  in {on} (@0x{ov:08x})')

print(f'\n  other branches landing inside CheckUpdate region ({len(internal_branches)}):')
for cur, tgt, ov, on in internal_branches:
    print(f'    0x{cur:08x} -> 0x{tgt:08x}  in {on} (@0x{ov:08x})')

# Also: every STRB / LDRB referencing this+0x2AC.
# Pattern 1 (small Thumb): movs r0,#0xAB ; lsls r0,r0,#2 ; (ldrb|strb) Rt,[Rn,r0]
# Pattern 2 (32-bit Thumb-2 LDRB/STRB immediate with imm12=0x2AC): less common, scan loosely.
print()
print('  this+0x2AC accessors (state byte writers/readers):')
patA = bytes.fromhex('ab208000')
i = 0
hits_2ac = []
while True:
    p = data.find(patA, i)
    if p < 0: break
    # next 2 bytes are the ldrb/strb
    if p + 6 > len(data): i = p+2; continue
    nxt = struct.unpack_from('<H', data, p + 4)[0]
    # Thumb LDRB/STRB register: 5C/54 family bits (opc=01110_L_Rm_Rn_Rt where L=load/store)
    # We already see in CheckUpdate: 2f5c = ldrb r7,[r5,r0]  and  2e54 = strb r6,[r5,r0]
    mnemonic = None
    op = nxt & 0xFE00
    if op == 0x5C00: mnemonic = 'ldrb'
    elif op == 0x5400: mnemonic = 'strb'
    elif op == 0x5800: mnemonic = 'ldr'
    elif op == 0x5000: mnemonic = 'str'
    if mnemonic:
        va = off_to_va(p)
        ov, on = nearest_sym(va) if va else (None, None)
        hits_2ac.append((p, va, mnemonic, nxt, ov, on))
    i = p + 2

for off, va, mn, raw, ov, on in hits_2ac:
    Rt = raw & 7; Rn = (raw >> 3) & 7; Rm = (raw >> 6) & 7
    print(f'    off=0x{off:08x} va=0x{va:08x}  {mn} r{Rt},[r{Rn},r{Rm}]  '
          f'in {on} (@0x{ov:08x})')

# ============================================================
# (9) Opcode dispatch tree + opcode 0x80 success path
# ============================================================
print()
print('='*72)
print('(9) opcode dispatch in OnReceiveResponse + 0x80 (CheckVersion) handler')
print('='*72)

orr_va, orr_sz = symbols['_ZN14CLoadingScreen17OnReceiveResponseEiPv']
orr_va &= ~1
print(f'  OnReceiveResponse va=0x{orr_va:08x} size={orr_sz}')
o = va_to_off(orr_va)
code = data[o:o+orr_sz]

# Find every cmp r1,#K / beq pair => opcode dispatch
print('\n  opcode dispatch table (cmp r1,#K  -> destination):')
prev = None
for ins in md.disasm(code, orr_va):
    if ins.mnemonic == 'cmp':
        try:
            ops = ins.operands
            if len(ops) >= 2 and ops[0].type == 1 and ops[0].reg and ops[1].type == 2:
                # capstone reg index: r1 is reg=66 in ARM, but easier to compare op_str
                if ins.op_str.startswith('r1,'):
                    prev = (ins.address, ins.op_str.split('#')[-1].strip())
        except Exception:
            pass
    elif ins.mnemonic in ('beq','bne','bgt','blt','bge','ble','bhi','bls'):
        if prev:
            tgt = None
            try:
                if ins.operands and ins.operands[-1].type == 2:
                    tgt = ins.operands[-1].value.imm
            except: pass
            if tgt is not None:
                print(f'    {prev[0]:#x}: cmp r1,#{prev[1]}  -> {ins.mnemonic} 0x{tgt:08x}')
        prev = None

# Now disassemble the opcode=0x80 handler in detail.
# From earlier pass: cmp r1,#0x80 is at 0x48fec8, success path starts at 0x48fece.
print('\n  full disasm: opcode 0x80 (/checkversion) handler  [0x48fec8..]')
start = 0x48fec8
end = 0x48ff80  # show a generous window past the vtable call that gates next state
o2 = va_to_off(start)
code2 = data[o2:o2 + (end - start)]
for ins in md.disasm(code2, start):
    annot = ''
    if ins.mnemonic in ('bl','blx'):
        try:
            t = ins.operands[-1]
            if t.type == 2:
                nm = sym_by_va.get(t.value.imm & ~1)
                if nm: annot = f'  ;; -> {nm}'
                else:
                    nv, nn = nearest_sym(t.value.imm & ~1)
                    if nn: annot = f'  ;; near {nn}+0x{(t.value.imm-nv)&~1:x}'
        except: pass
    op = ins.op_str
    # mark state-byte and vtable-related hints
    if '#0x2ac' in op or '#684' in op: annot += '  ;; this+0x2AC'
    if 'pc, #' in op and ins.mnemonic == 'ldr':
        # try to resolve the pc-relative literal
        try:
            ofs_str = op.split('#')[-1].rstrip(']')
            imm = int(ofs_str, 0)
            pc_lit = ((ins.address + 4) & ~3) + imm
            litoff = va_to_off(pc_lit)
            if litoff and litoff + 4 <= len(data):
                val = struct.unpack_from('<I', data, litoff)[0]
                annot += f'  ;; lit @0x{pc_lit:x} = 0x{val:08x}'
        except: pass
    print(f'    0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic} {op}{annot}')
    if ins.mnemonic in ('pop','bx') and 'pc' in op:
        # function-ish return — keep going a bit but at least mark it
        pass
    if ins.address - start >= (end - start) - 4:
        break

print()
print('='*72)
print('Summary / decision points:')
print('='*72)
print("""
Next steps depend on what the opcode-0x80 handler does with the response:
  - If it calls a vtable parser and only checks "result == 0" or "code == 200":
        the gate is response-shape, not version — fix by widening the server
        schema (add fields the parser may need beyond version/* keys).
  - If it explicitly reads .version/.majorVersion and compares against a
        hard-coded constant ("39", "1.1.38", or version code embedded in
        the .so):
        the gate is version comparison; either match it server-side or
        patch the comparison branch.
  - If the next vtable call's return value (cmp r0,#0 at 0x48ff08) drives
        a beq to a "bail-to-end" basic block:
        that beq is the *next* candidate gate. Note its file offset and
        we have the minimal patch site, structurally identical to the
        Option A patch you already applied at 0x48f910.
""")
