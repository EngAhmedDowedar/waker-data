"""
Analyze CLoadingScreen::CheckUpdate, locate launchUrl call site
and the gating conditional branch using this+0x2AC state byte.

Outputs:
 - disassembly window around 0x48f8b0
 - candidate patch sites (conditional branches + state-byte stores)
 - file offsets and exact ARM/Thumb patch bytes
"""
import sys, struct, os
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM

SO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', 'lib', 'armeabi', 'libcity_ar.so')

with open(SO, 'rb') as f:
    data = f.read()

# --- Minimal ELF32 LE parsing ---
assert data[:4] == b'\x7fELF'
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

# --- Section headers / strings ---
sections = []
shstrtab_hdr_off = e_shoff + e_shstrndx * e_shentsize
sh_offset_str = struct.unpack_from('<I', data, shstrtab_hdr_off + 0x10)[0]
for i in range(e_shnum):
    base = e_shoff + i * e_shentsize
    sh_name, sh_type, sh_flags, sh_addr, sh_offset, sh_size, sh_link, sh_info, sh_addralign, sh_entsize = \
        struct.unpack_from('<10I', data, base)
    name = data[sh_offset_str + sh_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    sections.append(dict(name=name, type=sh_type, addr=sh_addr, off=sh_offset,
                         size=sh_size, link=sh_link, entsize=sh_entsize))

def sec_by_name(n):
    for s in sections:
        if s['name'] == n: return s
    return None

# --- Dynamic symbol table ---
dynsym = sec_by_name('.dynsym')
dynstr = sec_by_name('.dynstr')
symbols = {}  # name -> (va_thumb_stripped, size)
for i in range(dynsym['size'] // dynsym['entsize']):
    so = dynsym['off'] + i * dynsym['entsize']
    st_name, st_value, st_size, st_info, st_other, st_shndx = \
        struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off'] + st_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    if nm:
        symbols[nm] = (st_value, st_size)

def find_sym(substr):
    out = []
    for k, v in symbols.items():
        if substr in k:
            out.append((k, v[0], v[1]))
    return out

# Locate key symbols
def show(name):
    res = find_sym(name)
    for n, va, sz in res:
        off = va_to_off(va & ~1)
        print(f'  {n}\n      va=0x{va:08x} off=0x{off:08x} size={sz}')

print('=== Key symbols ===')
for q in ['CheckUpdate', 'launchUrl', 'NGDevice', 'DoCheckVersion',
          'OnReceiveResponse', 'CLoadingScreen', 'DoGetServerInfo']:
    print(f'-- match: {q} --')
    show(q)

# Disassemble CheckUpdate
target_va = symbols['_ZN14CLoadingScreen11CheckUpdateEPKcS1_'][0] if \
    '_ZN14CLoadingScreen11CheckUpdateEPKcS1_' in symbols else 0x48f8b1
sz = symbols.get('_ZN14CLoadingScreen11CheckUpdateEPKcS1_', (0,0))[1]
print(f'\n=== CheckUpdate va=0x{target_va:08x} size=0x{sz:x} ===')

start_va = target_va & ~1
start_off = va_to_off(start_va)
length = sz if sz else 0x300
code = data[start_off:start_off + length]

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
md.detail = True
print(f'(file off 0x{start_off:x}, va 0x{start_va:x}, len {length})\n')

# Build symbol lookup at branch targets
sym_by_va = {(v[0] & ~1): k for k, v in symbols.items()}

interesting = []
for ins in md.disasm(code, start_va):
    annot = ''
    # Branch / call annotations
    if ins.mnemonic in ('bl', 'blx', 'b', 'beq', 'bne', 'bgt', 'blt', 'bge',
                         'ble', 'bhi', 'bls', 'bcs', 'bcc', 'bmi', 'bpl',
                         'cbz', 'cbnz'):
        # Last operand of branches is the target address
        try:
            tgt = ins.operands[-1]
            if tgt.type == 2:  # ARM_OP_IMM
                taddr = tgt.value.imm
                nm = sym_by_va.get(taddr & ~1)
                if nm:
                    annot = f' ; -> {nm}'
        except Exception:
            pass
    # Mark state-byte accesses
    op = ins.op_str
    if '#0x2ac' in op.lower() or '#684' in op or 'r0, #0x2ac' in op.lower():
        annot += ' ;; this+684 ?'
    print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic:<6} {ins.op_str}{annot}')

print('\n=== End disasm ===')
