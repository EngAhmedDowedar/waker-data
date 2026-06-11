"""Precise ngDevice->LaunchURL caller finder.

Step 1: disasm ngDevice::CreateInstance to find the global pointer where the
        singleton instance is stored.
Step 2: scan .text for the precise dispatch shape:
            <load singleton global> -> deref -> ldr vt,[inst] -> ldr fn,[vt,#0x60] -> blx fn
        We approximate by finding functions that BOTH (a) reference the
        singleton global and (b) contain a ldr Rt,[Rn,#0x60];blx Rt site.
"""
import os, struct, array, bisect
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

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

md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
out=[]

# Step 1: find singleton global from CreateInstance
ci=name_to_va.get('_ZN8ngDevice14CreateInstanceEv')
singleton_global=None
if ci:
    o=ci&~1; code=data[o:o+0x80]
    out.append('ngDevice::CreateInstance @ 0x%08x disasm:'%(ci&~1))
    base=None
    for ins in md.disasm(code,ci&~1):
        line='  0x%08x: %s %s'%(ins.address,ins.mnemonic,ins.op_str)
        # track PIC: ldr Rd,[pc,#X]; add Rd,pc -> global base; then str inst,[Rd,#imm] or str to computed
        if ins.mnemonic=='ldr' and 'pc, #' in ins.op_str.replace(' ',''):
            try:
                imm=int(ins.op_str.split('#')[-1].rstrip(']'),0)
                pc=(ins.address+4)&~3; la=pc+imm
                val=struct.unpack_from('<I',data,la)[0]
                line+='   ;lit=0x%08x'%val
            except: pass
        out.append(line)
        if ins.mnemonic in ('bx','pop') and ('lr' in ins.op_str or 'pc' in ins.op_str): break

# Step 2: function-level correlation.
# Build function ranges from sorted symbols.
funcs=[]
prev=None
for va in ssv:
    if prev is not None: funcs.append((prev, va, sym_by_va[prev]))
    prev=va
# scan text for offset-0x60 dispatch sites (reuse), map to function
text=secs['.text']; tva=text[0]; toff=text[1]; tsz=text[2]
hw=array.array('H'); hw.frombytes(data[toff:toff+(tsz&~1)])
def fn_of(va):
    idx=bisect.bisect_right(ssv,va)-1
    return sym_by_va[ssv[idx]] if idx>=0 else '?'
disp_sites=[]
for k in range(len(hw)):
    h=hw[k]
    if (h&0xFFC0)!=0x6E00: continue
    Rt=h&7; blx=0x4780|(Rt<<3)
    for j in range(1,7):
        if k+j<len(hw) and hw[k+j]==blx:
            disp_sites.append(tva+k*2); break
disp_fns=set(fn_of(s) for s in disp_sites)

# Among dispatch-site functions, which also reference 'launch'/'url'/'web'/'open'
# in their name or are URL/ad/promo-ish? Heuristic listing:
out.append('')
out.append('vtable[24]/+0x60 dispatch-site functions whose names suggest URL/web/promo/ad/rate:')
kw=('Url','URL','Web','web','Browser','browser','Open','open','Rate','rate','Promo','promo','Ad','ad','Link','link','Store','store','Review','review','Banner','Help','help','Faq','faq','More','Exit','Quit')
hits=sorted(f for f in disp_fns if any(k in f for k in kw))
for f in hits:
    out.append('  '+f)
out.append('')
out.append('TOTAL dispatch-site functions: %d (most are unrelated UI tables)'%len(disp_fns))

open(os.path.join(os.path.dirname(os.path.abspath(__file__)),'ngdevice_launchurl_callers.txt'),'w',encoding='utf-8').write('\n'.join(out)+'\n')
print('done')
