import struct,bisect,sys
data=open('../lib/armeabi/libcity_ar.so','rb').read()
sh=struct.unpack_from('<I',data,0x20)[0]; sn=struct.unpack_from('<H',data,0x30)[0]; se=struct.unpack_from('<H',data,0x2e)[0]; sx=struct.unpack_from('<H',data,0x32)[0]
shstr=struct.unpack_from('<I',data,sh+sx*se+0x10)[0]; sec={}
for i in range(sn):
    nm,ty,fl,ad,of,szz,*_=struct.unpack_from('<10I',data,sh+i*se); sec[data[shstr+nm:].split(b'\0',1)[0].decode()]=dict(addr=ad,off=of,size=szz)
ds=sec['.dynsym']; dt=sec['.dynstr']; syms=[]
for i in range(ds['size']//16):
    o=ds['off']+i*16; n,v,szz,*_=struct.unpack_from('<IIIBBH',data,o); nm=data[dt['off']+n:].split(b'\0',1)[0].decode('ascii','replace')
    if nm and v: syms.append((v&~1,szz,nm))
syms.sort(); addrs=[s[0] for s in syms]
def near(va):
    i=bisect.bisect_right(addrs,va)-1; return syms[i]
with open('sym_out.txt','w') as f:
    for key in ['PropertyListCate','GetPrice','House']:
        f.write(f"--- '{key}' ---\n")
        c=0
        for a,z,nm in syms:
            if key in nm: f.write(f"  0x{a:08x} sz=0x{z:x} {nm}\n"); c+=1
            if c>=12: break
    for tgt in [0x449da2,0x524b7c,0x524bd3-86]:
        a,z,nm=near(tgt); f.write(f"near 0x{tgt:x}: {nm} +0x{tgt-a:x} (sz=0x{z:x})\n")
print("done",len(syms))
