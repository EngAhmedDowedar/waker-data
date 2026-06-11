"""
Native patch for CLoadingScreen::CheckUpdate in libcity_ar.so.

Goal: force the "no update / latest version" branch unconditionally
so the launchUrl dialog never appears. State byte at this+0x2AC
is ignored after this patch.

Primary patch (default, Option A — 1-byte branch flip):
   file_off 0x48f911:  D0 -> E0
   beq #0x48f92c   (T1 0xD?xx)   -->   b #0x48f92c  (T2 0xE?xx)

Alternative (Option B — 2-byte force r7=0):
   file_off 0x48f8f0:  2F 5C -> 00 27
   ldrb r7, [r5, r0]  -->  movs r7, #0

Run with --variant B to choose Option B instead of A.
"""
import argparse, os, shutil, sys

SO_DEFAULT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          '..', 'lib', 'armeabi', 'libcity_ar.so')

PATCHES = {
    'A': dict(
        name='flip beq->b at state-byte branch',
        offset=0x48f910,
        original=bytes.fromhex('0cd0'),
        replacement=bytes.fromhex('0ce0'),
        desc='Forces CheckUpdate to always take the "no update" path',
    ),
    'B': dict(
        name='force state-byte read to constant 0',
        offset=0x48f8f0,
        original=bytes.fromhex('2f5c'),
        replacement=bytes.fromhex('0027'),
        desc='Replaces ldrb r7,[r5,r0] with movs r7,#0',
    ),
}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--variant', choices=['A', 'B'], default='A')
    ap.add_argument('--input', default=SO_DEFAULT)
    ap.add_argument('--output', default=None)
    ap.add_argument('--no-backup', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    out = args.output or args.input
    p = PATCHES[args.variant]
    with open(args.input, 'rb') as f:
        data = bytearray(f.read())

    cur = bytes(data[p['offset']:p['offset'] + len(p['original'])])
    print(f"Variant {args.variant}: {p['name']}")
    print(f"  file_off = 0x{p['offset']:08x}")
    print(f"  bytes now = {cur.hex()}")
    print(f"  expected  = {p['original'].hex()}")
    print(f"  patched   = {p['replacement'].hex()}")
    if cur == p['replacement']:
        print("  -> Already patched. Nothing to do.")
        return 0
    if cur != p['original']:
        print("  -> Mismatch. Aborting (binary differs).")
        return 1
    if args.dry_run:
        print("  -> Dry-run; no file written.")
        return 0
    if not args.no_backup and args.input == out:
        bak = args.input + '.preupdate.bak'
        if not os.path.exists(bak):
            shutil.copy2(args.input, bak)
            print(f"  -> backup: {bak}")
    for i, b in enumerate(p['replacement']):
        data[p['offset'] + i] = b
    with open(out, 'wb') as f:
        f.write(bytes(data))
    print(f"  -> wrote {out}")
    print(f"  Description: {p['desc']}")
    return 0

if __name__ == '__main__':
    sys.exit(main())
