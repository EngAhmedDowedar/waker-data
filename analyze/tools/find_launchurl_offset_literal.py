"""Find every occurrence of the literal value (launchUrl_va - global_base) in .text."""
import struct, os
data=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','lib','armeabi','libcity_ar.so'),'rb').read()
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
da,do,dz=secs['.dynsym']; dsa,dso,dsz=secs['.dynstr']
sym_by_va={}
for i in range(dz//16):
    o=do+i*16
    st_name,st_value,*_=struct.unpack_from('<IIIBBH',data,o)
    nm=data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm: sym_by_va[st_value & ~1]=nm
def near(va):
    best=None
    for s in sorted(sym_by_va):
        if s>va: break
        best=s
    return best, sym_by_va.get(best)

tva,toff,tsize=secs['.text']
# The known global_base for ngDeviceAndroid::LaunchURL was 0x75AB20.
# The offset stored in its literal pool was 0xfffaa9d4 (= 0x7054f4 - 0x75AB20 mod 2^32).
needle = struct.pack('<I', (0x7054f4 - 0x75AB20) & 0xFFFFFFFF)
print('Searching .text for offset-literal ' + needle.hex() + ' (= 0x7054f4 - 0x75AB20):')
i=0; hits=0
end = toff+tsize
while True:
    p = data.find(needle, toff+i, end)
    if p<0: break
    if (p-toff) % 2 == 0:
        cur_va = tva + (p-toff)
        nv, nn = near(cur_va)
        print('  off=0x{:08x}  va=0x{:08x}  in {} (@0x{:08x})'.format(
            p, cur_va, nn, nv or 0))
        hits += 1
    i = p - toff + 1
print('total:', hits)
