"""Find the full XOR key string in the .so and validate the scheme against the
captured /checkversion request: base64-decode -> XOR(key) -> expect clean JSON."""
import os, re, base64, json
HERE=os.path.dirname(os.path.abspath(__file__))
so=open(os.path.join(HERE,'..','lib','armeabi','libcity_ar.so'),'rb').read()

print("=== key-string search in libcity_ar.so ===")
keys_found=[]
for needle in [b'One ring', b'ring to rule', b'rule them', b'One Ring']:
    start=0
    while True:
        i=so.find(needle,start)
        if i<0: break
        end=so.find(b'\x00', i, i+200); end=end if end>=0 else i+200
        s=so[i:end]
        if all(9<=b<127 for b in s):
            print(f"  @0x{i:06x}: {s!r}")
            keys_found.append(s)
        start=i+1

# candidate keys to try
cands=list(dict.fromkeys(keys_found+[b'One ring to rule them all',
        b'One ring to rule them all, one ring to find them']))

def xor(data,key):
    return bytes(data[i]^key[i%len(key)] for i in range(len(data)))

dump=open(os.path.join(HERE,'..','local-server','python','protocol_dump.log'),encoding='utf-8',errors='replace').read()
bodies=re.findall(r'REQUEST PUT /checkversion.*?Body:\s*([A-Za-z0-9+/=]+)', dump, re.S)
raw=base64.b64decode(bodies[-1].strip())
print(f"\n=== decrypt captured request ({len(raw)} bytes) ===")
for k in cands:
    pt=xor(raw,k)
    ok=False
    try: json.loads(pt.decode('utf-8','strict')); ok=True
    except Exception as e: err=str(e)[:60]
    print(f"\n-- key={k!r} (len {len(k)}) jsonOK={ok} --")
    print("  plaintext:", pt[:300].decode('utf-8','replace'))
    if not ok: print("  (json err:", err, ")")
