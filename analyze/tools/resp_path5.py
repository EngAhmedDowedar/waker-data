"""
Trace the HTTP send/encode chain + analyze captured request ciphertext.
Part A: disasm CHttpClient::PutURL, ngHttpClient::PutURL, ngStringV2::Base64Encode,
        CheckVersion send-target, with dynsym + veneer call resolution & strings.
Part B: pull captured /checkversion request body, base64-decode, characterize
        (magic, entropy, autocorrelation/IoC, known-plaintext XOR probe).
"""
import os, struct, base64, math
from collections import Counter
from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB, CS_MODE_ARM
HERE=os.path.dirname(os.path.abspath(__file__))
data=open(os.path.join(HERE,'..','lib','armeabi','libcity_ar.so'),'rb').read()
e_phoff=struct.unpack_from('<I',data,0x1c)[0]; e_phnum=struct.unpack_from('<H',data,0x2c)[0]; e_phes=struct.unpack_from('<H',data,0x2a)[0]
segs=[]
for i in range(e_phnum):
    t,off,va,_,fsz,msz,*_=struct.unpack_from('<8I',data,e_phoff+i*e_phes); segs.append((t,off,va,msz))
def va2off(va):
    for t,off,vb,msz in segs:
        if t==1 and vb<=va<vb+msz:
            o=off+(va-vb); return o if o<len(data) else None
e_shoff=struct.unpack_from('<I',data,0x20)[0]; e_shnum=struct.unpack_from('<H',data,0x30)[0]; e_shes=struct.unpack_from('<H',data,0x2e)[0]; e_shstrndx=struct.unpack_from('<H',data,0x32)[0]
shstr=struct.unpack_from('<I',data,e_shoff+e_shstrndx*e_shes+0x10)[0]
sec={}
for i in range(e_shnum):
    nm,ty,fl,ad,of,sz,*_=struct.unpack_from('<10I',data,e_shoff+i*e_shes)
    name=data[shstr+nm:].split(b'\x00',1)[0].decode('ascii','replace'); sec[name]=dict(addr=ad,off=of,size=sz)
dsym=sec['.dynsym']; dstr=sec['.dynstr']; symbols={}; sym_by_va={}
for i in range(dsym['size']//16):
    so=dsym['off']+i*16; st_name,st_value,st_size,*_=struct.unpack_from('<IIIBBH',data,so)
    nm=data[dstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm: symbols[nm]=(st_value,st_size); sym_by_va[st_value&~1]=nm
def read_cstr(va,m=120):
    o=va2off(va)
    if o is None: return None
    e=data.find(b'\x00',o,o+m+1); e=e if e>=0 else o+m; s=data[o:e]
    return s.decode('ascii','replace') if (len(s)>=1 and all(9<=b<127 for b in s)) else None
md=Cs(CS_ARCH_ARM,CS_MODE_THUMB); md.detail=True
def follow(t):
    if (t&~1) in sym_by_va: return sym_by_va[t&~1]
    o=va2off(t&~1)
    if o is not None:
        try:
            ins=next(md.disasm(data[o:o+8], t&~1))
            if ins.mnemonic in('b','b.w') and ins.operands and ins.operands[-1].type==2:
                x=ins.operands[-1].value.imm
                if (x&~1) in sym_by_va: return sym_by_va[x&~1]+' [veneer]'
        except: pass
    nv=None
    for s in sorted(sym_by_va):
        if s>(t&~1): break
        nv=s
    if nv is not None and (t-nv)<0x300: return f'{sym_by_va[nv]}+0x{(t-nv)&~1:x}'
    return f'0x{t:08x}'
def disfn(name=None, va=None, ln=None, label=''):
    if va is None: va,sz=symbols.get(name,(0,0))
    else: sz=ln or 0
    if not va: print(f"[{name} MISSING]"); return []
    start=va&~1; L=ln or sz or 0x120; o=va2off(start); code=data[o:o+L]
    print(f"\n===== {label or name}  va=0x{start:08x} len=0x{L:x} =====")
    litreg={}; picreg={}; named=[]
    for ins in md.disasm(code,start):
        an=''; op=ins.op_str; mn=ins.mnemonic; parts=[p.strip() for p in op.split(',')]; rd=parts[0] if parts else ''
        if mn in('ldr','ldr.w') and 'pc' in op and '[' in op:
            try:
                imm=int(op.split('#')[-1].rstrip(']'),0); lit=((ins.address+4)&~3)+imm; lo=va2off(lit)
                if lo:
                    val=struct.unpack_from('<I',data,lo)[0]; litreg[rd]=val; an+=f'  ; lit=0x{val:08x}'; s=read_cstr(val)
                    if s: an+=f' "{s}"'
            except: pass
        if mn in('add','adds','add.w') and parts[-1]=='pc' and rd in litreg:
            picreg[rd]=(ins.address+4+litreg[rd])&0xFFFFFFFF; an+=f'  ; picbase=0x{picreg[rd]:08x}'
        if mn in('adds','add','add.w') and len(parts)==3:
            a,b=parts[1],parts[2]; pic=picreg.get(a) or picreg.get(b)
            litr=litreg.get(a) if (a in litreg and b in picreg) else (litreg.get(b) if (b in litreg and a in picreg) else None)
            if pic is not None and litr is not None:
                sv=litr-0x100000000 if litr&0x80000000 else litr; tgt=(pic+sv)&0xFFFFFFFF; s=read_cstr(tgt)
                an+=f'  ; ->0x{tgt:08x}'+(f' "{s}"' if s else ''); picreg[rd]=tgt
        if mn in('bl','blx'):
            try:
                t=ins.operands[-1]
                if t.type==2:
                    r=follow(t.value.imm); an+=f'  ; -> {r}'
                    if not r.startswith('0x'): named.append(r)
            except: pass
        print(f'  0x{ins.address:08x}: {ins.bytes.hex():<8} {mn:<7} {op}{an}')
    return named

print("="*70); print("PART A: encode-path disassembly"); print("="*70)
allnamed={}
for nm in ['_ZN11CHttpClient6PutURLER10ngStringV2P10ngJsonHash',
           '_ZN12ngHttpClient6PutURLER10ngStringV2P10ngJsonHash',
           '_ZN10ngStringV212Base64EncodeEP12ngByteBuffer']:
    allnamed[nm]=disfn(nm)
print("\n--- CheckVersion send target 0x6a8bcc (veneer?) ---")
disfn(va=0x6a8bcc, ln=0x30, label='send_target_0x6a8bcc')

# ============ PART B: ciphertext analysis ============
print("\n"+"="*70); print("PART B: captured /checkversion request ciphertext"); print("="*70)
dump=open(os.path.join(HERE,'..','local-server','python','protocol_dump.log'),'r',encoding='utf-8',errors='replace').read()
import re
bodies=re.findall(r'REQUEST PUT /checkversion.*?Body:\s*([A-Za-z0-9+/=]+)', dump, re.S)
print(f"found {len(bodies)} checkversion request bodies; analyzing last one")
if bodies:
    b64=bodies[-1].strip()
    print("b64 len:",len(b64))
    raw=base64.b64decode(b64)
    print("decoded len:",len(raw))
    print("first 48 bytes hex:",raw[:48].hex())
    print("first 48 bytes repr:",bytes(raw[:48]))
    print("magic check: zlib(78..)?",raw[:1]==b'\x78',"gzip(1f8b)?",raw[:2]==b'\x1f\x8b')
    # entropy
    cnt=Counter(raw); ent=-sum((c/len(raw))*math.log2(c/len(raw)) for c in cnt.values())
    print(f"byte entropy: {ent:.3f} bits/byte over {len(set(raw))} distinct values")
    # IoC
    N=len(raw); freqs=Counter(raw)
    ioc=sum(v*(v-1) for v in freqs.values())/(N*(N-1)/256) if N>1 else 0
    print(f"index of coincidence (norm, ~1.0=random, >1.7=text): {ioc:.3f}")
    # autocorrelation for periods 1..40 (count equal byte pairs at lag)
    print("autocorrelation (lag: matches) lags 1..40:")
    acs=[]
    for lag in range(1,41):
        m=sum(1 for i in range(N-lag) if raw[i]==raw[i+lag]); acs.append((lag,m))
    avg=sum(m for _,m in acs)/len(acs)
    spikes=[ (l,m) for l,m in acs if m>avg*1.6]
    print("  avg matches:",f"{avg:.1f}","; spikes(>1.6x avg):",spikes if spikes else "none (no short repeating-XOR period)")
    # known-plaintext XOR probe: assume plaintext begins with several candidate prefixes
    for pt in [b'{"header"', b'{"command"', b'header=', b'command=', b'{"head', b'\x00\x00', b'{"']:
        key=bytes(raw[i]^pt[i] for i in range(min(len(pt),len(raw))))
        printable=all(32<=k<127 for k in key)
        print(f"  KP-XOR pt={pt!r:18} -> key_bytes={key.hex()} {'ascii=%r'%key if printable else ''}")
