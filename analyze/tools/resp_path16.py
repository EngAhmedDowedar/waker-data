"""Resolve ARM 'bx pc' veneers to real targets (0x693ecc role-entry parser,
0x6a8cac ParseRoleList, etc.) and search for role-list root key strings."""
import os, struct
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
dsym=sec['.dynsym']; dstr=sec['.dynstr']; sym_by_va={}
for i in range(dsym['size']//16):
    so=dsym['off']+i*16; st_name,st_value,st_size,*_=struct.unpack_from('<IIIBBH',data,so)
    nm=data[dstr['off']+st_name:].split(b'\x00',1)[0].decode('ascii','replace')
    if nm and st_value: sym_by_va[st_value&~1]=nm
def near(va):
    nv=None
    for s in sorted(sym_by_va):
        if s>va: break
        nv=s
    return (sym_by_va[nv],va-nv) if nv is not None and va-nv<0x2000 else (None,0)
mda=Cs(CS_ARCH_ARM,CS_MODE_ARM); mda.detail=True
def resolve_veneer(va):
    # va: thumb 'bx pc' (2b) + pad(2b); ARM code at (va&~3)+4
    base=(va&~3)+4; o=va2off(base)
    insns=list(mda.disasm(data[o:o+16], base))
    tgt=None
    for ins in insns:
        if ins.mnemonic=='ldr' and 'pc,' in ins.op_str and '[pc' in ins.op_str:
            # ldr pc,[pc,#imm] : target = .word at (ins.addr+8+imm)
            try:
                imm=int(ins.op_str.split('#')[-1].rstrip(']'),0)
                wo=va2off(ins.address+8+imm); tgt=struct.unpack_from('<I',data,wo)[0]
            except: pass
        if ins.mnemonic in('b','bx') and ins.operands and ins.operands[-1].type==2:
            tgt=ins.operands[-1].value.imm
    dis='; '.join(f'{i.mnemonic} {i.op_str}' for i in insns[:3])
    return tgt, dis

for v in [0x693ecc,0x6a8cac,0x693ebc,0x6a8c8c,0x6a8c9c,0x6a8cbc,0x6a8ccc,0x69532c,0x6950fc,0x69313c]:
    tgt,dis=resolve_veneer(v)
    if tgt is not None:
        nn,do=near(tgt&~1); tn=sym_by_va.get(tgt&~1) or (f'{nn}+0x{do:x}' if nn else hex(tgt))
        print(f"  veneer 0x{v:08x} -> 0x{tgt:08x}  {tn}    [{dis}]")
    else:
        print(f"  veneer 0x{v:08x} -> ? [{dis}]")

print("\n=== role-list / getplayerlist key strings ===")
for kw in [b'roleList',b'roles',b'playerList',b'players',b'roleInfo',b'getplayerlist',
           b'playerlist',b'roleData',b'characterList',b'roleNum']:
    start=0;n=0
    while n<3:
        i=data.find(kw,start)
        if i<0:break
        va=None
        for t,off,vb,msz in segs:
            if t==1 and off<=i<off+msz: va=vb+(i-off);break
        e=data.find(b'\x00',i,i+40); s=data[i:e] if e>=0 else data[i:i+40]
        if all(9<=b<127 for b in s) and 3<=len(s)<=30:
            print(f"  {kw.decode():14} va={'0x%08x'%va if va else '?'} {s.decode()!r}")
        n+=1; start=i+1
