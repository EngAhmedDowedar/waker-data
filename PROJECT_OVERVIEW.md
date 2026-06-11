# Waker — Project Overview

Private-server revival of the dead-server Arabic game **com.anansimobile.city_ar**
("وكر الاوغاد" / Waker, v1.1.38). A local Python/Flask server emulates the game's
HTTP backend so a (lightly patched) client APK boots from the title screen to the
playable main city screen.

---

## Folder structure

```
waker/
├── PROJECT_OVERVIEW.md     ← this file
├── RUN_SERVER.md           ← how to start the server + connect the device (READ THIS)
├── STATUS.md               ← what works / is stubbed / remaining blockers
│
├── local-server/           ← *** RUNTIME *** (the only thing you run)
│   └── python/
│       ├── server.py            the Flask backend (HTTP 8080 + keepalive 9090 + stats 8992)
│       └── requirements.txt     flask==3.0.0, werkzeug==3.0.1
│
├── client/                 ← *** RUNTIME *** (the app you install on the phone)
│   ├── waker-patched-signed.apk        final patched + signed client (install this)
│   └── waker-patched-signed.apk.idsig  signature sidecar (ignore)
│
└── analyze/                ← everything else: reverse-engineering & build artifacts
    ├── tools/                  disassembly/extraction scripts (rp*.py, capstone-based)
    ├── client-apk-src/         apktool-decompiled client (smali/, lib/, res/, assets/, …)
    │                           + uber-apk-signer.jar — used only to RE-PATCH the APK
    ├── docs/                   research notes (SCHEMAS.md, NETWORKING_MAP.md, …)
    ├── logs/                   captured logcat / frida / protocol dumps
    ├── screenshots/            on-device captures from the recovery effort
    ├── apk-builds/             older/intermediate APKs (obsolete; safe to delete)
    ├── reference/              the original working-gameplay video + frames
    ├── obsolete-node-server/   an early Node.js server attempt (superseded by Python)
    ├── revival/                early endpoint inventory / hosts override notes
    ├── __handlers__/           stray decompiler output (libc.so)
    ├── frida-server            arm frida-server binary (dynamic-analysis tool)
    └── installed_libcity_ar.so copy of the native lib that was disassembled
```

---

## Required for RUNTIME (to reproduce the working state)

| File | Purpose |
|------|---------|
| `local-server/python/server.py` | The backend. Serves the cipher'd HTTP protocol on **8080** (game API), **9090** (keepalive), **8992** (analytics). Binds `0.0.0.0`. |
| `local-server/python/requirements.txt` | Python deps (`flask`, `werkzeug`). |
| `client/waker-patched-signed.apk` | The client to install on the device. Already contains the 3 native patches (below). |

That's it. The server reads **no** external assets/config — all responses are built in `server.py`.

**Networking**: the server is configured via `SERVER_HOST` env var (hostname or IP).
The APK's target host is set by `analyze/tools/patch_so.py --server-host <host>`.
See `RUN_SERVER.md` for the full setup options (LAN IP, hostname, VPS, USB-only).

## Analysis-only (NOT needed to run)

Everything under `analyze/`. The two that matter if you ever need to re-patch the client:
- `analyze/tools/patch_so.py` — re-patches the native lib to target any hostname/IP (max 24 chars).
- `analyze/client-apk-src/` — the apktool project. Rebuild with `apktool b` then sign with `uber-apk-signer.jar`.
- `analyze/client-apk-src/lib/armeabi/libcity_ar.so` — the patched native lib (the disassembly target).

---

## Files modified during the recovery effort

1. **`local-server/python/server.py`** — written/rewritten extensively: the base64+XOR cipher,
   the response envelope injector (`error`/`timestamp`/`errorMessage`/`data`), and handlers for
   `/checkversion`, `/api/connect`, `/api/authplayerkey`, `/api/getallserver`, `/city/impart`,
   `/city/connect/{getplayerlist,create,connect}`, `/city/goods/getcitygoods`,
   `/city/estate/{listestates,buy}`, `/city/player/introplayers`, `/city/fight/randomfighters`,
   `/city/chat/*`, plus `_make_player` / `_make_house` / `_make_fighter` data builders.

2. **`analyze/client-apk-src/lib/armeabi/libcity_ar.so`** — 3 native patches (baked into `client/waker-patched-signed.apk`):
   - **Host redirect**: backend host set to `192.168.1.3` (configurable via
     `analyze/tools/patch_so.py --server-host <host>`, max 24 chars).
   - **CheckUpdate bypass**: 1-byte flip at file 0x48f911 (`D0`→`E0`) — skips the launchUrl update dialog.
   - **gettopmsgs flood fix**: 1-byte flip at file 0x59190d (`DC`→`E0`) — turns a `bgt` into an
     unconditional branch so the news-ticker stops polling every frame.

3. **`analyze/client-apk-src/AndroidManifest.xml`** + smali — Firebase/GCM notification bypass:
   - All Firebase services (`FCMInstanceIDService`, `FCMMessagingService`,
     `FirebaseInstanceIdService`, `FirebaseMessagingService`) set to `android:enabled="false"`.
   - `FirebaseInstanceIdReceiver` and `FirebaseInstanceIdInternalReceiver` disabled.
   - `FirebaseInitProvider.onCreate()` stubbed to skip `FirebaseApp.initializeApp()`.
   - `FCMInstanceIDService.onTokenRefresh()` and `FCMMessagingService.onMessageReceived()` stubbed.
   - Fixes ANR: "executing service FCMInstanceIDService" blocked startup trying to reach dead
     Firebase/GCM servers.

4. **`client/waker-patched-signed.apk`** — rebuilt from the patched sources and re-signed (debug key).

See **STATUS.md** for what's working and **RUN_SERVER.md** for how to start everything.
