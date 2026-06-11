"""Find every PIC xref to the 'launchUrl' method-name string."""
import struct, os
data=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       '..','lib','armeabi','libcity_ar.so'),'rb').read()

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

xrefs = []
i = 0
while i < tsize - 8:
    hw1 = struct.unpack_from('<H', data, toff + i)[0]
    if 0x4800 <= hw1 <= 0x4FFF:
        Rd = (hw1 >> 8) & 7
        imm8 = hw1 & 0xFF
        cur_va = tva + i
        pc = (cur_va + 4) & ~3
        lit_addr = pc + imm8 * 4
        lit_off = va_to_off(lit_addr)
        if lit_off is None or lit_off+4 > len(data):
            i+=2; continue
        lit_val = struct.unpack_from('<I', data, lit_off)[0]
        for k in (2,4,6,8):
            hwn = struct.unpack_from('<H', data, toff + i + k)[0]
            if 0x4478 <= hwn <= 0x447F and (hwn & 7) == Rd:
                add_pc_va = cur_va + k
                target = (lit_val + (add_pc_va + 4)) & 0xFFFFFFFF
                if target == LAUNCH_URL_VA:
                    xrefs.append((cur_va, add_pc_va, lit_addr, lit_val))
                break
    i += 2

print(f'PIC string-load xrefs to "launchUrl" (va 0x{LAUNCH_URL_VA:x}): {len(xrefs)}')
for ldr_va, add_va, lit_va, lit_val in xrefs:
    nv, nn = near(ldr_va)
    print(f'  ldr_va=0x{ldr_va:08x}  add_pc_va=0x{add_va:08x}')
    print(f'    in {nn} (@0x{nv:08x})')

# also: scan for direct LDR-imm references where literal value == LAUNCH_URL_VA (non-PIC absolute)
print()
print('Direct absolute-VA references (LDR Rd,[pc,#imm] with literal == launchUrl VA):')
direct = []
i = 0
while i < tsize - 4:
    hw = struct.unpack_from('<H', data, toff + i)[0]
    if 0x4800 <= hw <= 0x4FFF:
        imm8 = hw & 0xFF
        cur_va = tva + i
        pc = (cur_va + 4) & ~3
        la = pc + imm8 * 4
        lo = va_to_off(la)
        if lo is not None and lo+4 <= len(data):
            v = struct.unpack_from('<I', data, lo)[0]
            if v == LAUNCH_URL_VA:
                direct.append((cur_va, la, v))
    i += 2
print(f'  total: {len(direct)}')
for cv, la, v in direct:
    nv, nn = near(cv)
    print(f'  0x{cv:08x}  -> abs lit @0x{la:08x} = 0x{v:08x}  in {nn} (@0x{nv:08x})')

# Also: scan .data/.data.rel.ro for any 32-bit value equal to LAUNCH_URL_VA (static binding table)
print()
print('Static-data refs to launchUrl string (e.g. JNINativeMethod arrays):')
needle = struct.pack('<I', LAUNCH_URL_VA)
for sname,(sa,so2,sz2) in secs.items():
    if not sname.startswith('.data'): continue
    chunk = data[so2:so2+sz2]
    i=0
    while True:
        p = chunk.find(needle, i)
        if p<0: break
        if p%4==0:
            ref_va = sa + p
            print(f'  in {sname}: off=0x{so2+p:08x} va=0x{ref_va:08x}')
            # nearby: JNINativeMethod is {const char* name; const char* sig; void* fnPtr;}
            # so check +4 and +8
            try:
                sig_va = struct.unpack_from('<I', data, so2+p+4)[0]
                fn_va  = struct.unpack_from('<I', data, so2+p+8)[0]
                # try resolve sig as a string
                sig_off = va_to_off(sig_va) if sig_va else None
                if sig_off:
                    e = data.find(b'\x00', sig_off, sig_off+128)
                    sig_str = data[sig_off:e].decode('ascii','replace') if e>0 else '?'
                else:
                    sig_str = '?'
                nv, nn = near(fn_va & ~1)
                print(f'    +0: name -> "launchUrl"')
                print(f'    +4: sig  -> va=0x{sig_va:08x}  "{sig_str}"')
                print(f'    +8: fn   -> va=0x{fn_va:08x}  in {nn} (@0x{nv:08x})')
            except Exception as e:
                print(f'    (decode error: {e})')
        i = p + 4
