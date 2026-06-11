import struct, bisect, os
data=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','lib','armeabi','libcity_ar.so'),'rb').read()
e_shoff=struct.unpack_from('<I',data,0x20)[0]; e_she=struct.unpack_from('<H',data,0x2e)[0]
e_shn=struct.unpack_from('<H',data,0x30)[0]; e_shstr=struct.unpack_from('<H',data,0x32)[0]
shdr=e_shoff+e_shstr*e_she; shstr=struct.unpack_from('<I',data,shdr+0x10)[0]
secs={}
for i in range(e_shn):
    b=e_shoff+i*e_she
    sn,st,_,sa,so,sz,*_=struct.unpack_from('<10I',data,b)
    secs[data[shstr+sn:].split(b'\x00',1)[0].decode('ascii','replace')]=(sa,so,sz)
e_phoff=struct.unpack_from('<I',data,0x1c)[0]; e_phe=struct.unpack_from('<H',data,0x2a)[0]; e_phn=struct.unpack_from('<H',data,0x2c)[0]
segs=[]
for i in range(e_phn):
    o=e_phoff+i*e_phe; t,off,va,_,fsz,msz,*_=struct.unpack_from('<8I',data,o); segs.append((t,off,va,msz))
def v2o(va):
    for t,off,vb,msz in segs:
        if t==1 and vb<=va<vb+msz: return off+(va-vb)
    return None
da,do,dz=secs['.dynsym']; dso=secs['.dynstr'][1]
sym_by_va={}
for i in range(dz//16):
    o=do+i*16; st_name,st_value,*_=struct.unpack_from('<IIIBBH',data,o)
    nm=data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm and st_value: sym_by_va[st_value&~1]=nm
ssv=sorted(sym_by_va)
def near(va):
    idx=bisect.bisect_right(ssv,va)-1
    return (ssv[idx],sym_by_va[ssv[idx]]) if idx>=0 else (0,None)
relmap={}
for sname in ('.rel.dyn','.rel.plt'):
    if sname not in secs: continue
    ra,ro,rsz=secs[sname]
    for i in range(rsz//8):
        r_off,r_info=struct.unpack_from('<II',data,ro+i*8)
        rt=r_info&0xff; rs=r_info>>8
        if rt==23:
            to=v2o(r_off)
            if to is not None: relmap[r_off]=('REL',struct.unpack_from('<I',data,to)[0])
        elif rt==2:
            so2=do+rs*16; sv=struct.unpack_from('<IIIBBH',data,so2)[1]
            relmap[r_off]=('ABS32',sv)

out=[]
for VT,label in [(0x00752b70,'ngDeviceAndroid'),(0x0074edf0,'ngDevice')]:
    out.append('=== %s vtable @ 0x%08x ==='%(label,VT))
    for slot in range(40):
        sa=VT+slot*4
        o=v2o(sa)
        if o is None: break
        raw=struct.unpack_from('<I',data,o)[0]
        rel=relmap.get(sa)
        resolved=rel[1] if rel else raw
        nv,nn=near(resolved&~1) if resolved else (0,None)
        mark=''
        if (resolved&~1)==0x5efb9c: mark='   <<<< ngDeviceAndroid::LaunchURL'
        if (resolved&~1)==0x5bb8bc: mark='   <<<< ngDevice::LaunchURL(stub)'
        out.append('  [%2d] +0x%03x raw=0x%08x %-7s resolved=0x%08x %s%s'%(
            slot, slot*4, raw, (rel[0] if rel else 'noreloc'), resolved, nn, mark))
    out.append('')
open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'vtable_dump.txt'),'w',encoding='utf-8').write('\n'.join(out)+'\n')
print('done')
