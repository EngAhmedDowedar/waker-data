"""
Look for ARM-mode (32-bit instructions, not Thumb) BL/BLX callers of
ngDeviceAndroid::LaunchURL (0x5efb9c).

ARM BL encoding (cond=1110, A=1, L=1):
   31 28 27 25 24 23 ........... 0
   cond  101  L=1   imm24       -> 0xEBxxxxxx (unconditional)
   target = pc + 8 + SignExtend(imm24:'00', 26)

ARM BLX(imm) encoding (always-imm, switches to Thumb):
   31 28 27 25 24 23 ........... 0
   1111  101  H     imm24       -> 0xFAxxxxxx (H=0) or 0xFBxxxxxx (H=1)
   target = pc + 8 + SignExtend(imm24:H:'0', 26), set Thumb bit
"""
import struct, os

data = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         '..','lib','armeabi','libcity_ar.so'),'rb').read()

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
tva,toff,tsize=secs['.text']

da,do,dz=secs['.dynsym']
dsa,dso,dsz=secs['.dynstr']
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

LAUNCH_VA_RAW   = 0x005efb9c
LAUNCH_VA_THUMB = 0x005efb9d

callers = []
# Iterate every 4-byte aligned position in .text — we don't know which addresses are ARM,
# so we'll just check the encoding pattern. False positives are possible but the result set
# is small and we can verify.
for off in range(0, tsize - 4, 4):
    word = struct.unpack_from('<I', data, toff + off)[0]
    cond = (word >> 28) & 0xF
    op   = (word >> 24) & 0xF
    cur_va = tva + off
    target = None; kind = None
    if cond == 0xE and op == 0xB:    # ARM BL (always)
        imm24 = word & 0xFFFFFF
        if imm24 & 0x800000: imm24 -= 0x1000000
        target = (cur_va + 8 + imm24 * 4) & 0xFFFFFFFF
        kind = 'ARM BL'
    elif cond == 0xF and (op == 0xA or op == 0xB):   # ARM BLX (imm)
        H = (word >> 24) & 1
        imm24 = word & 0xFFFFFF
        if imm24 & 0x800000: imm24 -= 0x1000000
        target = (cur_va + 8 + (imm24 * 4) + (H * 2)) & 0xFFFFFFFF
        target |= 1   # switches to Thumb
        kind = 'ARM BLX'
    if target is None: continue
    if (target & ~1) == LAUNCH_VA_RAW:
        nv, nn = near(cur_va)
        callers.append((cur_va, kind, target, nv, nn))

print(f'ARM-mode callers of LaunchURL: {len(callers)}')
for cv, kind, tgt, nv, nn in callers:
    print(f'  {kind} @ va=0x{cv:08x} -> 0x{tgt:08x}  in {nn} (@0x{nv:08x})')

# Also: scan all 32-bit values across the entire file for either 0x005efb9c or 0x005efb9d
# in 4-byte alignment, to find any function-pointer storage we may have missed (not just .data).
print()
print('All 32-bit aligned occurrences of LaunchURL VA across entire .so:')
for needle, tag in ((LAUNCH_VA_THUMB, 'thumb'), (LAUNCH_VA_RAW, 'raw')):
    needle_b = struct.pack('<I', needle)
    i = 0
    while True:
        p = data.find(needle_b, i)
        if p < 0: break
        if p % 4 == 0:
            # which section?
            sec_name = '?'
            sec_va = 0
            for snm, (sa, so2, sz2) in secs.items():
                if so2 <= p < so2 + sz2:
                    sec_name = snm; sec_va = sa + (p - so2); break
            print(f'  {tag:5s} hit  file_off=0x{p:08x}  va=0x{sec_va:08x}  in {sec_name}')
        i = p + 1
