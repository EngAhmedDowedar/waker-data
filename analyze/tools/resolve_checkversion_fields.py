"""
Resolve every PC-relative string that the opcode-0x80 handler hands to
vtable[16] (the JSON-field lookup) so we can name each field. Output the
mapping field-name -> where its parsed value is stored.

Pattern in the .text:
    ldr  r0, [pc, #imm_a]      ; literal A = offset
    add  r0, pc                ; r0 = A + (pc_of_add+4)
    ldr  r1, [pc, #imm_b]      ; literal B = offset
    adds r1, r1, r0            ; r1 = B + r0  (field-name string addr)
    ldr  r0, [r5]              ; vtable
    ldr  r2, [r0, #0x40]       ; vtable[16]
    mov  r0, r5
    blx  r2                    ; lookup
    cmp  r0, #0
    beq  <skip>
    adds r0, #4
    bl   <parser>              ; parse value
    ... uses result ...

The field name string lives at A + B + (pc of add r0,pc + 4).
"""
import os, struct, re
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

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True

def read_cstr(addr):
    o = va_to_off(addr)
    if o is None or o >= len(data): return None
    end = data.find(b'\x00', o, o + 256)
    if end < 0: return None
    try:
        return data[o:end].decode('ascii', 'replace')
    except: return None

start, end = 0x48fec8, 0x49036c
o = va_to_off(start)
code = data[o:o+(end-start)]

# Stream of instructions; track the most recent (ldr r0,[pc,#imm], add r0,pc) target r0_pc_offset,
# then the next (ldr r1,[pc,#imm]) literal value, then `adds r1, r1, r0`. The first arg to vtable[16]
# computes to r1 = lit_value + r0_target where r0_target = literal0 + (pc-bias of add r0,pc + 4).

instrs = list(md.disasm(code, start))
# Index by VA for backtracking
by_va = {ins.address: ins for ins in instrs}

# Find every `blx r2` preceded by `ldr r2,[r0,#0x40]` -> these are vtable[16] dispatches
# Then walk backwards from each to recover the string-pointer construction.

def lit_value(va, imm):
    pc = (va + 4) & ~3
    addr = pc + imm
    off = va_to_off(addr)
    if off is None or off + 4 > len(data): return None
    return struct.unpack_from('<I', data, off)[0]

results = []

for idx, ins in enumerate(instrs):
    if ins.mnemonic != 'blx': continue
    if ins.op_str != 'r2': continue
    # walk back to find the most recent ldr r2,[r0,#0x40]
    found_vtable = False
    for j in range(idx-1, max(0, idx-6), -1):
        p = instrs[j]
        if p.mnemonic == 'ldr' and p.op_str in ('r2, [r0, #0x40]', 'r2,[r0,#0x40]'):
            found_vtable = True
            break
    if not found_vtable: continue

    # walk further back to find: adds r1, r1, r0  preceded by  ldr r1,[pc,#X]
    # and ldr r0,[pc,#Y]; add r0, pc
    r1_lit = None
    r0_lit = None
    r0_pc_va = None
    for j in range(idx-2, max(0, idx-14), -1):
        p = instrs[j]
        if p.mnemonic == 'adds' and p.op_str == 'r1, r1, r0':
            # the previous instructions set r1 and r0
            # r1 from a ldr r1,[pc,#imm]
            for k in range(j-1, max(0,j-4), -1):
                q = instrs[k]
                if q.mnemonic == 'ldr' and q.op_str.startswith('r1, [pc, #'):
                    m = re.search(r'#([0-9a-fx]+)', q.op_str)
                    if m: r1_lit = lit_value(q.address, int(m.group(1), 0))
                    break
            # r0 from "ldr r0,[pc,#imm]; add r0, pc"
            for k in range(j-1, max(0,j-6), -1):
                q = instrs[k]
                if q.mnemonic == 'add' and q.op_str == 'r0, pc':
                    add_pc_va = q.address
                    # the ldr r0,[pc,#imm] just before
                    for kk in range(k-1, max(0,k-3), -1):
                        r = instrs[kk]
                        if r.mnemonic == 'ldr' and r.op_str.startswith('r0, [pc, #'):
                            m = re.search(r'#([0-9a-fx]+)', r.op_str)
                            if m:
                                r0_lit = lit_value(r.address, int(m.group(1), 0))
                                r0_pc_va = add_pc_va + 4  # pc value at execution of add r0,pc
                            break
                    break
            break
    if r0_lit is None or r1_lit is None or r0_pc_va is None: continue

    # Field-name string address = r1_lit + r0_lit + r0_pc_va (signed wrap to 32-bit)
    field_va = (r1_lit + r0_lit + r0_pc_va) & 0xFFFFFFFF
    s = read_cstr(field_va)
    # Inspect what happens right after blx r2 for "what is done with the parsed value"
    sink = []
    for j in range(idx+1, min(len(instrs), idx+10)):
        q = instrs[j]
        sink.append(f'{q.mnemonic} {q.op_str}')
        if q.mnemonic in ('strb','str') and ('[r4,' in q.op_str or '[r5,' in q.op_str):
            break
        if q.mnemonic == 'bl' and '0x694fbc' not in q.op_str and '0x692fcc' not in q.op_str and '0x692fdc' not in q.op_str:
            break
    results.append({
        'vtable16_va': ins.address,
        'r0_lit': r0_lit, 'r1_lit': r1_lit, 'r0_pc_va': r0_pc_va,
        'field_va': field_va, 'field': s,
        'sink_preview': sink,
    })

print(f'opcode-0x80 handler vtable[16] field lookups: {len(results)}')
for r in results:
    print()
    print(f'  blx r2 @ va=0x{r["vtable16_va"]:08x}')
    print(f'    field-name string @ va=0x{r["field_va"]:08x}  =  {r["field"]!r}')
    print(f'    next ops: {" ; ".join(r["sink_preview"])}')
