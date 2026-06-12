#!/usr/bin/env python3
"""Verify the /city/job/getjobs response parser from libcity_ar.so (binary only).

Finds job-related symbols, disassembles the OnReceiveResponse / Parse functions in
Thumb, and resolves string literals (JSON key names) reached via PC-relative loads.
"""
import os, struct, sys
import capstone

SO = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                  '..', 'baseline-apk-src', 'lib', 'armeabi', 'libcity_ar.so')
data = open(SO, 'rb').read()

# --- program headers: va<->file off ---
e_phoff = struct.unpack_from('<I', data, 0x1c)[0]
e_phentsize = struct.unpack_from('<H', data, 0x2a)[0]
e_phnum = struct.unpack_from('<H', data, 0x2c)[0]
segs = []
for i in range(e_phnum):
    t, off, va, _, fsz, msz, *_ = struct.unpack_from('<8I', data, e_phoff + i*e_phentsize)
    if t == 1:
        segs.append((off, va, fsz, msz))

def va2off(va):
    for off, vb, fsz, msz in segs:
        if vb <= va < vb + fsz:
            return off + (va - vb)
    return None

# --- sections / dynsym ---
e_shoff = struct.unpack_from('<I', data, 0x20)[0]
e_shentsize = struct.unpack_from('<H', data, 0x2e)[0]
e_shnum = struct.unpack_from('<H', data, 0x30)[0]
e_shstrndx = struct.unpack_from('<H', data, 0x32)[0]
shstr = struct.unpack_from('<I', data, e_shoff + e_shstrndx*e_shentsize + 0x10)[0]
sec = {}
for i in range(e_shnum):
    nm, ty, fl, ad, of, sz, *_ = struct.unpack_from('<10I', data, e_shoff + i*e_shentsize)
    sec[data[shstr+nm:].split(b'\0', 1)[0].decode('latin1')] = dict(addr=ad, off=of, size=sz)

ds, dt = sec['.dynsym'], sec['.dynstr']
syms = []
for i in range(ds['size'] // 16):
    o = ds['off'] + i*16
    n, v, sz, info, other, shndx = struct.unpack_from('<IIIBBH', data, o)
    nm = data[dt['off']+n:].split(b'\0', 1)[0].decode('latin1', 'replace')
    if nm and v:
        syms.append((v & ~1, sz, nm))
syms.sort()
import bisect
addrs = [s[0] for s in syms]
def sym_at(va):
    i = bisect.bisect_right(addrs, va) - 1
    if i >= 0:
        a, sz, nm = syms[i]
        return nm, va - a
    return '?', 0

def find(*keys):
    out = []
    for a, sz, nm in syms:
        if all(k in nm for k in keys):
            out.append((a, sz, nm))
    return out

md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
md.detail = False

def read_cstr(va, maxlen=64):
    o = va2off(va)
    if o is None:
        return None
    end = data.find(b'\0', o, o+maxlen)
    if end < 0:
        return None
    s = data[o:end]
    try:
        return s.decode('utf-8')
    except UnicodeDecodeError:
        return None

def disasm(va, size, label=''):
    """Disassemble a Thumb function, annotating PC-relative literal loads with the
    string they point to (JSON keys) and BL/BLX targets with the callee symbol."""
    off = va2off(va)
    if off is None:
        print(f'  (no file offset for 0x{va:x})'); return []
    code = data[off:off+size]
    lits = []
    print(f'\n===== {label} @ 0x{va:x} (size 0x{size:x}) =====', flush=True)
    cnt = 0
    for ins in md.disasm(code, va):
        cnt += 1
        if cnt > 400:
            break
        line = f'  0x{ins.address:08x}  {ins.mnemonic:7} {ins.op_str}'
        ann = ''
        # literal pool loads: ldr rX, [pc, #imm]
        if ins.mnemonic.startswith('ldr') and 'pc' in ins.op_str:
            # compute literal address: (PC&~3)+imm ; PC = addr+4
            try:
                imm = int(ins.op_str.split('#')[-1].rstrip(']'), 0)
                lit_addr = ((ins.address + 4) & ~3) + imm
                lo = va2off(lit_addr)
                if lo is not None:
                    val = struct.unpack_from('<I', data, lo)[0]
                    s = read_cstr(val)
                    tgt, d = sym_at(val & ~1)
                    if s and all(32 <= ord(c) < 127 for c in s):
                        ann = f'   ; -> "{s}"'
                        lits.append((ins.address, s))
                    else:
                        ann = f'   ; = 0x{val:x}' + (f' ({tgt}+0x{d:x})' if tgt!='?' and d<0x400 else '')
            except Exception:
                pass
        if ins.mnemonic in ('bl', 'blx') and ins.op_str.startswith('#'):
            try:
                t = int(ins.op_str[1:], 0)
                nm, d = sym_at(t)
                ann = f'   ; -> {nm}+0x{d:x}' if d else f'   ; -> {nm}'
            except Exception:
                pass
        print(line + ann)
    return lits

def find_string_va(s):
    """Return list of VAs where the C-string `s` (NUL-terminated) lives in the image."""
    needle = s.encode() + b'\0'
    out, start = [], 0
    while True:
        i = data.find(needle, start)
        if i < 0:
            break
        # map file offset back to a VA
        for off, vb, fsz, msz in segs:
            if off <= i < off + fsz:
                out.append(vb + (i - off)); break
        start = i + 1
    return out

def xrefs_to_va(target_va, scan_lo=0x320000, scan_hi=0x600000):
    """Find code sites that PC-rel load a literal whose value == target_va."""
    hits = []
    o0 = va2off(scan_lo); o1 = va2off(scan_hi)
    if o0 is None or o1 is None:
        return hits
    # scan the literal pools: any 4-byte word == target_va, then find who loads it
    pos = o0
    while pos < o1 - 4:
        w = struct.unpack_from('<I', data, pos)[0]
        if w == target_va or w == (target_va | 1):
            # this file offset is a literal; compute its VA
            litva = None
            for off, vb, fsz, msz in segs:
                if off <= pos < off + fsz:
                    litva = vb + (pos - off); break
            hits.append(litva)
        pos += 4
    return hits

if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else 'syms'
    if what == 'syms':
        print('### job-related symbols ###')
        for key in ('HrMarketCateScreen', 'JobCategory', 'OnReceiveResponse'):
            res = find(key)
            if res:
                print(f'-- match "{key}" ({len(res)}) --')
                for a, sz, nm in res[:30]:
                    print(f'  0x{a:08x} sz=0x{sz:<5x} {nm}')
    elif what == 'str':
        for s in ('getjobs', 'job/getjobs', 'jobs', 'highestJobs', 'job', 'category',
                  'salary', 'jobId', 'jobs', 'level'):
            vas = find_string_va(s)
            print(f'"{s}": ' + (', '.join(f'0x{v:x}' for v in vas) if vas else '(none)'))
    elif what == 'dis':
        # disassemble a symbol by name substring
        key = sys.argv[2]
        for a, sz, nm in find(key):
            disasm(a, max(sz, 4), nm)
    elif what == 'full':
        print('## job strings present in binary ##')
        for s in ('getjobs', 'jobs', 'highestJobs', 'job', 'category', 'salary',
                  'level', 'jobNum', 'jobCategory', 'highestJob'):
            vas = find_string_va(s)
            print(f'  "{s}": ' + (', '.join(f'0x{v:x}' for v in vas) if vas else '(none)'))
        # exact OnReceiveResponse for the job screen
        print('\n## CHrMarketCateScreen members of interest ##')
        for a, sz, nm in find('HrMarketCateScreen'):
            if any(k in nm for k in ('OnReceiveResponse', 'GetJobList', 'ParseDoJob',
                                     'ViewDidLoad', 'OnEnter', 'Refresh', 'Send',
                                     'Request', 'GetJob')):
                print(f'  0x{a:08x} sz=0x{sz:<5x} {nm}')
        for want in ('_ZN19CHrMarketCateScreen17OnReceiveResponseEiPv',
                     '_ZN19CHrMarketCateScreen18ParseDoJobResponseEPv',
                     '_ZN19CHrMarketCateScreen22ParseGetSaleryResponseEPv'):
            hit = [s for s in syms if s[2] == want]
            if hit:
                a, sz, nm = hit[0]
                disasm(a, max(sz, 4), nm)
