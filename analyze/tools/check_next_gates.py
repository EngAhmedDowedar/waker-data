"""
Quick static answers for the post-CheckUpdate triage:
  - Does ngDeviceAndroid::LaunchURL validate / reject an empty url?
  - What does DoGetServerInfo do? Is there a similar state-byte gate?
  - Any other static BL site whose target is, or trampolines to, LaunchURL?
"""
import struct, os
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
    sh_name, sh_type, _, sh_addr, sh_off, sh_size, *_ = \
        struct.unpack_from('<10I', data, base)
    name = data[sh_offset_str + sh_name:].split(b'\x00', 1)[0].decode('ascii', 'replace')
    sections.append(dict(name=name, type=sh_type, addr=sh_addr, off=sh_off, size=sh_size))
def sec(n):
    for s in sections:
        if s['name'] == n: return s
dynsym = sec('.dynsym'); dynstr = sec('.dynstr')
symbols = {}; sym_by_va = {}
for i in range(dynsym['size']//16):
    so = dynsym['off']+i*16
    st_name, st_value, st_size, *_ = struct.unpack_from('<IIIBBH', data, so)
    nm = data[dynstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm:
        symbols[nm]=(st_value, st_size); sym_by_va[st_value & ~1]=nm

md = Cs(CS_ARCH_ARM, CS_MODE_THUMB); md.detail = True

def near(va):
    best=None
    for s in sorted(sym_by_va):
        if s > va: break
        best=s
    return best, sym_by_va.get(best)

def disasm(va, n, label):
    print(f'\n=== {label}  va=0x{va:08x}  off=0x{va_to_off(va):08x}  size={n} ===')
    o = va_to_off(va); code = data[o:o+n]
    for ins in md.disasm(code, va):
        annot=''
        if ins.mnemonic in ('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2:
                    nm = sym_by_va.get(t.value.imm & ~1)
                    if nm: annot = f'  ;; -> {nm}'
                    else:
                        nv, nn = near(t.value.imm & ~1)
                        if nn: annot = f'  ;; -> near {nn}+0x{(t.value.imm-nv)&~1:x}'
            except: pass
        op = ins.op_str
        if '#0x2ac' in op or '#684' in op: annot += '  ;; this+0x2AC'
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {ins.mnemonic} {op}{annot}')

# Q1: LaunchURL empty/null check — full disasm
v,sz = symbols['_ZN15ngDeviceAndroid9LaunchURLEPKc']
disasm(v & ~1, sz, 'ngDeviceAndroid::LaunchURL')

# Q4: DoGetServerInfo full disasm
v,sz = symbols['_ZN14CLoadingScreen15DoGetServerInfoEh']
disasm(v & ~1, sz, 'CLoadingScreen::DoGetServerInfo (next step after CheckVersion)')

# Q: any other static BL whose chain leads to LaunchURL — count via Thumb-2 BL scan, but
# with an indirection step: scan for any BL whose target is a 2-instruction veneer that
# trampolines to LaunchURL's VA range.
text = sec('.text')
text_va = text['addr']; text_off = text['off']; text_size = text['size']
launchurl_va = symbols['_ZN15ngDeviceAndroid9LaunchURLEPKc'][0] & ~1
# 1) find veneers (bx pc; mov r8,r8) whose ARM target is within ±0x100 of LaunchURL
veneer_pat = b'\x78\x47\xc0\x46'
veneer_targets_to_launchurl = []
i = 0
while True:
    p = data.find(veneer_pat, i)
    if p < 0: break
    # ARM instructions follow (4 bytes aligned). Decode: ldr r12,[pc,#0]; add pc,r12,pc; CONST
    arm_off = p + 4
    if arm_off + 12 > len(data): i = p+4; continue
    ldr  = struct.unpack_from('<I', data, arm_off)[0]
    addp = struct.unpack_from('<I', data, arm_off+4)[0]
    const= struct.unpack_from('<I', data, arm_off+8)[0]
    # PC bias = arm_off VA + 8 + 4 (pipeline) — but ldr offset is +0, so r12 = const at arm_off+8
    if ldr == 0xe59fc000 and addp == 0xe08cf00f:
        # target = arm_off(va) + 4 (next ARM instr) + 8 (pc bias) + const (signed)
        # In Thumb→ARM veneer: actual sequence:
        #   ARM @ arm_off: ldr r12, [pc, #0]   ; loads CONST (at arm_off+8)
        #   ARM @ arm_off+4: add pc, r12, pc   ; pc at this insn is arm_off+4+8
        # So target = arm_off + 4 + 8 + const = arm_off + 12 + const
        va_arm = None
        for t,off,vb,_,msz in segs:
            if t==1 and off <= arm_off < off+msz:
                va_arm = vb + (arm_off-off); break
        if va_arm is None: i = p+4; continue
        target = (va_arm + 12 + const) & 0xFFFFFFFF
        if abs(target - launchurl_va) < 0x80:
            # find the Thumb BL site that calls this veneer
            veneer_va = va_arm - 4  # the bx pc is 4 bytes before
            veneer_targets_to_launchurl.append((p, veneer_va, target))
    i = p+4

print(f'\n=== Veneers that trampoline into LaunchURL region ({launchurl_va:#x}) ===')
for p, vva, t in veneer_targets_to_launchurl:
    print(f'  veneer at file 0x{p-4:x}, va 0x{vva:08x}  --ARM--> 0x{t:08x}')

# Then scan .text for BL targeting any of those veneers
veneer_vas = {v for _,v,_ in veneer_targets_to_launchurl}
print(f'\n=== BL sites that call into LaunchURL via veneer ===')
callers = []
for off in range(0, text_size-4, 2):
    hw1 = struct.unpack_from('<H', data, text_off+off)[0]
    hw2 = struct.unpack_from('<H', data, text_off+off+2)[0]
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
    is_blx = ((hw2>>12)&1)==0
    if is_blx: target &= ~3
    target &= ~1
    if target in veneer_vas:
        owner_va=None
        for s in sorted(sym_by_va):
            if s > cur_va: break
            owner_va = s
        owner = sym_by_va.get(owner_va)
        callers.append((cur_va, target, owner_va, owner))

for cur, tgt, ov, on in callers:
    print(f'  call_at 0x{cur:08x} -> veneer 0x{tgt:08x}   in {on} (@0x{ov:08x})')
print(f'  total: {len(callers)}')
