"""
Compound-PIC xref scan for the 'launchUrl' string at va 0x7054f4.

The compound pattern used by this binary is:
    ldr Rb, [pc, #A]    ; Rb = literal_A
    add Rb, pc          ; Rb = literal_A + pc_at_add+4  -> global base
    ldr Rt, [pc, #B]    ; Rt = literal_B  (string offset)
    adds Rd, Rt, Rb     ; Rd = literal_B + global_base  -> string VA
We scan all (ldr+add) pairs first, then for each, look ahead within a small
window for any subsequent (ldr Rt,[pc,#B]; adds Rdest, Rt, Rbase) whose
final value equals the launchUrl string VA. Each hit's owner function is
where C++ is calling GetStaticMethodID("launchUrl",...).
"""
import os, struct

_here = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
data = open(os.path.join(_here, '..','lib','armeabi','libcity_ar.so'),'rb').read()

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

dsa,dso,dsz=secs['.dynstr']
da,do,dz=secs['.dynsym']
sym_by_va={}
for i in range(dz//16):
    o=do+i*16
    st_name,st_value,st_size,*_=struct.unpack_from('<IIIBBH',data,o)
    nm=data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm: sym_by_va[st_value & ~1]=nm
def near(va):
    best=None
    for s in sorted(sym_by_va):
        if s>va: break
        best=s
    return best, sym_by_va.get(best)

LAUNCH_URL_VA = 0x007054f4
tva,toff,tsize=secs['.text']

def read_imm_lit(va, imm8):
    pc = (va + 4) & ~3
    addr = pc + imm8 * 4
    off = va_to_off(addr)
    if off is None or off + 4 > len(data): return None
    return struct.unpack_from('<I', data, off)[0]

# Build a list of (ldr_va, Rd, lit_val_of_ldr) for every Thumb T1 LDR-PC.
ldrs = []
i = 0
while i < tsize - 2:
    hw = struct.unpack_from('<H', data, toff + i)[0]
    if 0x4800 <= hw <= 0x4FFF:
        Rd = (hw >> 8) & 7
        imm8 = hw & 0xFF
        lit = read_imm_lit(tva + i, imm8)
        if lit is not None:
            ldrs.append((tva + i, Rd, lit))
    i += 2

# Index ldrs by VA for fast lookup
ldr_by_va = {v: (Rd, lit) for v, Rd, lit in ldrs}

# Now scan for "add Rd, pc" instructions. T1 form: 0x4478..0x447F, where bits[2:0] = Rd_low3.
# When found, look backwards within ~8 bytes for the matching `ldr Rd, [pc, #...]` whose Rd matches.
xrefs = []
i = 0
while i < tsize - 2:
    hw = struct.unpack_from('<H', data, toff + i)[0]
    if 0x4478 <= hw <= 0x447F:
        Rd_add = hw & 7
        add_va = tva + i
        # find matching ldr before it
        ldr_va_match = None; lit_A = None
        for back in (2, 4, 6, 8):
            cand_va = add_va - back
            ent = ldr_by_va.get(cand_va)
            if ent and ent[0] == Rd_add:
                ldr_va_match = cand_va; lit_A = ent[1]
                break
        if ldr_va_match is None:
            i += 2; continue

        # base address established at the `add Rd, pc` instruction
        global_base = (lit_A + (add_va + 4)) & 0xFFFFFFFF

        # Look ahead in a 12-byte window for `ldr Rt, [pc, #B]; adds Rdest, Rt, Rd_add`
        for fwd in range(2, 20, 2):
            la = add_va + fwd
            ent2 = ldr_by_va.get(la)
            if not ent2: continue
            Rt, lit_B = ent2
            # Next instruction(s) — look for `adds Rdest, Rt, Rb` (T1 ADDS Rd, Rn, Rm encoding 0x1800..0x19FF)
            # bits[15:9]=0001100, bits[8:6]=Rm, bits[5:3]=Rn, bits[2:0]=Rd
            for fwd2 in range(2, 8, 2):
                aa = la + fwd2
                if aa - tva >= tsize: break
                hwn = struct.unpack_from('<H', data, toff + (aa - tva))[0]
                if (hwn & 0xFE00) == 0x1800:
                    Rm = (hwn >> 6) & 7; Rn = (hwn >> 3) & 7
                    # operands are (Rt + Rd_add) -> either order
                    if (Rm == Rt and Rn == Rd_add) or (Rm == Rd_add and Rn == Rt):
                        string_va = (lit_B + global_base) & 0xFFFFFFFF
                        if string_va == LAUNCH_URL_VA:
                            xrefs.append({
                                'add_va': add_va, 'global_base': global_base,
                                'ldr_lit_B_va': la, 'lit_B': lit_B,
                                'adds_va': aa, 'string_va': string_va,
                            })
                    break
    i += 2

print(f'Compound-PIC xrefs to "launchUrl" string (va 0x{LAUNCH_URL_VA:x}): {len(xrefs)}')
for r in xrefs:
    nv, nn = near(r['add_va'])
    print()
    print(f'  add r?,pc @ va=0x{r["add_va"]:08x}  (global_base = 0x{r["global_base"]:08x})')
    print(f'    in {nn} (@0x{nv:08x})')
    print(f'    ldr lit B @0x{r["ldr_lit_B_va"]:08x} = 0x{r["lit_B"]:08x}')
    print(f'    adds @0x{r["adds_va"]:08x}  -> string va = 0x{r["string_va"]:08x}')

# Owner grouping
owners = {}
for r in xrefs:
    _, on = near(r['add_va'])
    owners.setdefault(on, []).append(r['add_va'])
print()
print(f'Owners ({len(owners)}):')
for on, sites in owners.items():
    print(f'  {on}  -> {len(sites)} site(s):  ' + ', '.join(f'0x{s:08x}' for s in sites))
