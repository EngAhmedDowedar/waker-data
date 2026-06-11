"""Find virtual-dispatch sites for ngDevice vtable slot [24] (offset 0x60) =
LaunchURL. Pattern (Thumb): ldr Rt,[Rn,#0x60] ; (few insns) ; blx Rt.

Also: count ABS32 relocations referencing the LaunchURL symbol (to confirm
the vtable slot is the only address-taking), and locate the ngDevice
singleton getter so we can correlate callers.
"""
import os, struct, array, bisect
data=open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','lib','armeabi','libcity_ar.so'),'rb').read()
e_shoff=struct.unpack_from('<I',data,0x20)[0]; e_she=struct.unpack_from('<H',data,0x2e)[0]
e_shn=struct.unpack_from('<H',data,0x30)[0]; e_shstr=struct.unpack_from('<H',data,0x32)[0]
shdr=e_shoff+e_shstr*e_she; shstr=struct.unpack_from('<I',data,shdr+0x10)[0]
secs={}
for i in range(e_shn):
    b=e_shoff+i*e_she
    sn,st,_,sa,so,sz,*_=struct.unpack_from('<10I',data,b)
    secs[data[shstr+sn:].split(b'\x00',1)[0].decode('ascii','replace')]=(sa,so,sz)
da,do,dz=secs['.dynsym']; dso=secs['.dynstr'][1]
sym_by_va={}; name_to_va={}
for i in range(dz//16):
    o=do+i*16; st_name,st_value,*_=struct.unpack_from('<IIIBBH',data,o)
    nm=data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm and st_value: sym_by_va[st_value&~1]=nm; name_to_va[nm]=st_value
ssv=sorted(sym_by_va)
def near(va):
    idx=bisect.bisect_right(ssv,va)-1
    return (ssv[idx],sym_by_va[ssv[idx]]) if idx>=0 else (0,None)

out=[]
# 1. Count ABS32 relocs to LaunchURL symbol
launch_sym_idx=None
for i in range(dz//16):
    o=do+i*16; st_name=struct.unpack_from('<I',data,o)[0]
    nm=data[dso+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm=='_ZN15ngDeviceAndroid9LaunchURLEPKc': launch_sym_idx=i; break
abs32=0
ra,ro,rsz=secs['.rel.dyn']
for i in range(rsz//8):
    r_off,r_info=struct.unpack_from('<II',data,ro+i*8)
    if (r_info&0xff)==2 and (r_info>>8)==launch_sym_idx:
        abs32+=1; out.append('  ABS32 reloc -> LaunchURL at GOT/vtable VA 0x%08x'%r_off)
out.insert(0,'LaunchURL symbol idx=%s, ABS32 relocs referencing it: %d'%(launch_sym_idx,abs32))

# 2. ngDevice singleton getter
out.append('')
out.append('ngDevice singleton getters / instance accessors:')
for nm,va in sorted(name_to_va.items()):
    if 'ngDevice' in nm and ('GetInstance' in nm or 'Instance' in nm or 'Shared' in nm or 'Get' in nm and 'Device' in nm[:14]):
        if 'Instance' in nm or 'Shared' in nm:
            out.append('  0x%08x %s'%(va,nm))

# 3. Scan .text for ldr Rt,[Rn,#0x60]; ...; blx Rt
text=secs['.text']; tva=text[0]; toff=text[1]; tsz=text[2]
hw=array.array('H'); hw.frombytes(data[toff:toff+(tsz&~1)])
# Thumb LDR imm T1 with offset 0x60: 0x6800 | (0x18<<6) | (Rn<<3) | Rt = 0x6E00 | (Rn<<3) | Rt
# so high bits == 0x6E00..0x6E3F
sites=[]
nhw=len(hw)
for k in range(nhw):
    h=hw[k]
    if (h & 0xFFC0) != 0x6E00:  # ldr Rt,[Rn,#0x60]
        continue
    Rt=h&7
    # look ahead up to 6 halfwords for blx Rt (0x4780|(Rt<<3))
    blx=0x4780|(Rt<<3)
    for j in range(1,7):
        if k+j>=nhw: break
        if hw[k+j]==blx:
            sites.append(tva+k*2)
            break
out.append('')
out.append('Candidate vtable[24] (offset 0x60) dispatch sites (ldr Rt,[Rn,#0x60];blx Rt): %d'%len(sites))
byo={}
for cv in sites:
    nv,nn=near(cv); byo.setdefault((nn,nv),[]).append(cv)
for (nn,nv),lst in sorted(byo.items(), key=lambda kv: kv[1][0]):
    out.append('  %s (@0x%08x) -- %d'%(nn,nv or 0,len(lst)))
    for s in lst[:3]: out.append('      0x%08x'%s)
    if len(lst)>3: out.append('      ...%d more'%(len(lst)-3))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'vtable24_sites.txt'),'w',encoding='utf-8').write('\n'.join(out)+'\n')
print('done; %d dispatch sites'%len(sites))
