/*
 * Runtime native patch for CLoadingScreen::CheckUpdate
 * in libcity_ar.so (com.anansimobile.city_ar / Waker).
 *
 * Forces the state-byte check at va 0x48f910 to fall into the
 * "no update / latest version" branch unconditionally — the
 * launchUrl path is then never taken regardless of what the
 * server returned.
 *
 * Houdini-safe: pure memory write to a module page; no inline
 * Interceptor.attach on ARM code, which is unreliable under
 * x86 emulator + Houdini translation.
 *
 * Usage (after manual app launch, attach to running PID):
 *   frida -U -p <PID> -l frida_patch_checkupdate.js
 */

'use strict';

const LIB = 'libcity_ar.so';
const PATCH_OFFSET = 0x48f910;       // file/RVA offset (PT_LOAD vbase = 0)
const ORIGINAL = [0x0c, 0xd0];       // beq #0x48f92c
const REPLACEMENT = [0x0c, 0xe0];    // b   #0x48f92c

// --- optional alternative (Option B): force ldrb -> movs r7, #0 ---
// const PATCH_OFFSET = 0x48f8f0;
// const ORIGINAL = [0x2f, 0x5c];
// const REPLACEMENT = [0x00, 0x27];

function tryPatch() {
    const m = Process.findModuleByName(LIB);
    if (!m) {
        console.log('[!] ' + LIB + ' not loaded yet, will retry...');
        return false;
    }
    const target = m.base.add(PATCH_OFFSET);
    const cur = Memory.readByteArray(target, ORIGINAL.length);
    const curArr = new Uint8Array(cur);
    const expected = new Uint8Array(ORIGINAL);
    const wantArr = new Uint8Array(REPLACEMENT);

    const hex = (a) => Array.from(a).map(b => b.toString(16).padStart(2,'0')).join(' ');
    console.log('[*] ' + LIB + ' base = ' + m.base);
    console.log('[*] target va = ' + target);
    console.log('[*] bytes now      = ' + hex(curArr));
    console.log('[*] expected before= ' + hex(expected));
    console.log('[*] patched bytes  = ' + hex(wantArr));

    let match = true;
    for (let i = 0; i < ORIGINAL.length; i++) {
        if (curArr[i] !== ORIGINAL[i]) { match = false; break; }
    }
    if (!match) {
        let already = true;
        for (let i = 0; i < REPLACEMENT.length; i++) {
            if (curArr[i] !== REPLACEMENT[i]) { already = false; break; }
        }
        if (already) {
            console.log('[+] Already patched.');
            return true;
        }
        console.log('[!] Bytes do not match expected original. Aborting.');
        return true; // stop retrying
    }

    Memory.protect(target, ORIGINAL.length, 'rwx');
    Memory.writeByteArray(target, REPLACEMENT);

    // Clear i-cache so the patched instruction is fetched fresh.
    // Frida's Memory.writeByteArray + Memory.protect on a code page
    // should be sufficient on most ARM kernels, but flush to be safe.
    try {
        const flush = new NativeFunction(
            Module.findExportByName(null, '__builtin___clear_cache')
              || Module.findExportByName(null, 'cacheflush'),
            'int', ['pointer', 'pointer', 'int']);
        flush(target, target.add(64), 0);
    } catch (e) { /* best-effort */ }

    const verify = new Uint8Array(Memory.readByteArray(target, REPLACEMENT.length));
    console.log('[+] Patched. verify=' + hex(verify));
    return true;
}

if (!tryPatch()) {
    // libcity_ar.so loads in a later thread on Houdini; retry until present.
    const iv = setInterval(() => {
        if (tryPatch()) clearInterval(iv);
    }, 250);
}
