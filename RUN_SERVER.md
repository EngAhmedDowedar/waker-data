# RUN_SERVER.md — Start the Waker server & connect the device

Follow this top to bottom on a clean machine to reproduce the current working state
(boot → main city screen). No reverse-engineering knowledge required.

---

## ⚠️ IF THE SERVER "DID NOT START" — READ THIS FIRST

On **Windows**, `python server.py` crashes **immediately** with a `UnicodeEncodeError`
because the startup banner contains Arabic text the default `cp1252` console can't encode.
**You must force UTF-8 output.** The single command that works from a clean clone:

```powershell
cd local-server\python
$env:SERVER_HOST="192.168.1.3"; $env:PYTHONUTF8="1"; python -X utf8 server.py
```
```bash
# git-bash / WSL / Linux / macOS
cd local-server/python
SERVER_HOST=192.168.1.3 PYTHONUTF8=1 python -X utf8 server.py
```

If you see three `Running on http://...:8080/9090/8992` lines, it started. Full details,
ports, verification, and other failure modes are below.

---

## 0. Networking overview (read first)

The game client needs to reach this server by hostname or IP. There are three
deployment options — pick whichever fits your setup:

| Setup | APK patched to | SERVER_HOST= | Name resolution |
|-------|---------------|-------------|-----------------|
| **A. Hostname (recommended)** | `waker.local` | your LAN IP (e.g. `192.168.1.3`) | phone's `/etc/hosts`, router DNS, or mDNS |
| **B. Direct IP** | your LAN IP (e.g. `192.168.1.3`) | same IP | none needed |
| **C. Remote / VPS** | `my-vps.example.com` | the domain | public DNS |

**Option A** is recommended because the APK doesn't need to be re-patched when
your IP changes — just update the DNS/hosts entry. The shipped APK uses
`waker.local` by default.

The `SERVER_HOST` env var tells the server what address to *advertise back* to
the client in keepalive and server-list responses. If it doesn't match what the
client connects to, the game stalls after login.

---

## 1. Requirements

- **Python 3.8+** (tested on 3.12). `python --version`
- Python packages: **flask==3.0.0**, **werkzeug==3.0.1**
- **adb** (Android platform-tools) on PATH — to install/launch the client.
- An Android device **reachable from the PC** (arm/arm64; a real device is most
  reliable — x86 emulators need ARM translation/Houdini and are flaky here).
  - **One device at a time.** If `adb devices` lists more than one, target one
    explicitly with `adb -s <serial> …`.
- Firewall must allow inbound TCP **8080, 9090, 8992**.

Install deps:
```bash
cd local-server/python
python -m pip install -r requirements.txt
```

---

## 2. Required ports

| Port | Role | Bind |
|------|------|------|
| **8080** | Game HTTP API (`/checkversion`, `/api/*`, `/city/*`) | `0.0.0.0` |
| **9090** | "keepLiveServerPort" keepalive channel (same cipher) | `0.0.0.0` |
| **8992** | Analytics/stat server | `0.0.0.0` |

## 3. Required files (must be present next to server.py)

`server.py` imports two sibling modules and one data directory — all are committed, so a
clean clone has them, but the server **must be launched from `local-server/python/`** so the
imports resolve:

| Path | Role | Required? |
|------|------|-----------|
| `local-server/python/server.py` | the server | yes |
| `local-server/python/city_loader.py` | loads the `.city` catalogs | yes (imported) |
| `local-server/python/player_state.py` | Phase 1 mutable player state | yes (imported) |
| `local-server/python/gamedata/*.json` | 93 decoded catalog tables | yes — `city_loader` reads these at startup |
| `local-server/python/player_state.json` | runtime save file | **auto-created** on first run (gitignored) |

No external network assets are fetched. If `gamedata/` is missing, the server still starts
but logs `0 catalogs` and asset-backed endpoints serve empty data.

---

## 4. Exact commands to launch

### 4a. Start the server

git-bash / WSL / Linux / macOS:
```bash
cd local-server/python
SERVER_HOST=192.168.1.3 PYTHONUTF8=1 python -X utf8 server.py
```

Windows PowerShell:
```powershell
cd local-server\python
$env:SERVER_HOST="192.168.1.3"; $env:PYTHONUTF8="1"; python -X utf8 server.py
```

Replace `192.168.1.3` with your actual LAN IP, hostname, or domain:
```bash
SERVER_HOST=192.168.1.3       # LAN IP
SERVER_HOST=waker.local       # mDNS / hosts-file hostname
SERVER_HOST=my-vps.example.com  # remote VPS
```

> `PYTHONUTF8=1 -X utf8` is required on Windows — the banner has Arabic text
> that crashes the default cp1252 console without it.

Leave it running. You should see `[HTTP] Game API server running on port 8080`
and `URL: http://<your-host>:8080/`.

> **Legacy note:** `SERVER_IP` still works as a fallback if `SERVER_HOST` is not set.

### 4b. Install the client (first time / after re-patch)

```bash
adb install -r client/waker-patched-signed.apk
# if signature mismatch: adb uninstall com.anansimobile.city_ar  then install again
```

### 4c. Launch the game (use a CLEAN state so it takes the direct-login path)

```bash
adb shell rm -rf /sdcard/Android/data/com.anansimobile.city_ar
adb shell pm clear com.anansimobile.city_ar
adb shell am start -n com.anansimobile.city_ar/.Main
```

> Why the clears: leftover state makes the client take a cached **resume /
> server-selection** path that stalls at step 10. Clearing forces the proven
> direct path: `checkversion → api/connect → getplayerlist → connect → main`.

---

## 5. Verify the server

```bash
# Ports listening?
netstat -ano | grep -E ":8080|:9090|:8992"

# HTTP responds locally?
curl -s "http://127.0.0.1:8080/debug/probe"       # -> {"next_variant":6}

# Reachable from the phone's perspective?
# (open this URL in the phone's browser — should return JSON)
curl -s "http://<your-host>:8080/debug/probe"

# Watch live traffic:
tail -f local-server/python/protocol_dump.log
```

---

## 6. Name resolution (Option A — hostname setup)

If the APK is patched to a hostname (e.g. `waker.local`), the phone needs to
resolve it to your server's IP. Pick one method:

**Method 1 — Router DNS / DHCP reservation:**
Add a DNS entry in your router mapping `waker.local` → your PC's LAN IP.

**Method 2 — Phone hosts file (rooted):**
```bash
adb shell "echo '192.168.1.3 waker.local' >> /etc/hosts"
```

**Method 3 — mDNS (Bonjour/Avahi):**
If your PC advertises itself as `<hostname>.local` via mDNS and the phone
supports it, use that hostname directly in the APK patch.

**Method 4 — DNS override app (no root):**
Apps like "DNS66" or "personalDNSfilter" can override DNS on unrooted devices.

---

## 7. Changing the APK's target host

The hostname/IP is stored as a string in `libcity_ar.so`. To change it:

```bash
cd analyze/tools
python patch_so.py --server-host 192.168.1.3     # direct IP
python patch_so.py --server-host waker.local      # hostname (default)
python patch_so.py --server-host my-vps.com       # remote server
```

Max hostname length: **24 characters** (limited by the tightest .rodata slot).

After patching, rebuild and re-sign the APK:
```bash
cd analyze/client-apk-src
apktool b .
java -jar uber-apk-signer.jar -a dist/*.apk
# then adb install the new APK
```

---

## 8. Connectivity diagnostic checklist

| # | Check | Fix |
|---|-------|-----|
| 1 | **Ports listening** — `netstat` shows 8080/9090/8992 on `0.0.0.0` | Server didn't start — check console |
| 2 | **SERVER_HOST matches** — banner shows the expected host/IP | Restart with correct `SERVER_HOST` |
| 3 | **Name resolves** — phone can resolve the hostname to the PC's IP | Set up DNS (section 6) |
| 4 | **Same network** — phone and PC can reach each other | Same Wi-Fi/subnet |
| 5 | **Firewall** — inbound TCP 8080/9090/8992 allowed | Add firewall rules or test with firewall off |
| 6 | **Phone browser test** — `http://<host>:8080/debug/probe` returns JSON | Confirms end-to-end connectivity |
| 7 | **Step 10 stall** — game loops after login | Clear device state (section 4c) |
| 8 | **ADB reverse (USB fallback)** — if APK targets `127.0.0.1` | `adb reverse tcp:8080 tcp:8080; adb reverse tcp:9090 tcp:9090; adb reverse tcp:8992 tcp:8992` |

## 9. Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `UnicodeEncodeError` on startup | Windows cp1252 console | Use `PYTHONUTF8=1 python -X utf8 server.py` |
| `OSError: address already in use` | Previous server still running | Kill it: find PID with `netstat`, then kill |
| Banner shows `127.0.0.1` | `SERVER_HOST` not set | Restart with `SERVER_HOST=<your-host>` |
| Game stuck on title | Phone can't reach the server | Check name resolution + firewall |
| Game reaches step 10, retries | Cached resume path (unimplemented) | Clear device state and relaunch |
| `adb install` signature error | Different signer than installed | `adb uninstall com.anansimobile.city_ar`, reinstall |

---

## 10. USB-only setup (no Wi-Fi needed)

If you can't use Wi-Fi, patch the APK to `127.0.0.1` and use ADB port forwarding:

```bash
# Patch APK to localhost
python analyze/tools/patch_so.py --server-host 127.0.0.1
# (rebuild + sign + install the APK)

# Forward device ports to PC
adb reverse tcp:8080 tcp:8080
adb reverse tcp:9090 tcp:9090
adb reverse tcp:8992 tcp:8992

# Start server (no SERVER_HOST needed — default 127.0.0.1 is correct)
cd local-server/python
PYTHONUTF8=1 python -X utf8 server.py
```

---

## 11. Fresh-clone checklist (zero → running)

```
[ ] 1. python --version            → 3.8+ (verified on 3.12.3)
[ ] 2. pip install -r local-server/python/requirements.txt   (flask 3.0.0, werkzeug 3.0.1)
[ ] 3. confirm local-server/python/gamedata/ has ~93 *.json   (ls | wc -l)
[ ] 4. cd local-server/python      (MUST cd here — imports are relative siblings)
[ ] 5. set SERVER_HOST to the IP/host the device reaches      (e.g. 192.168.1.3)
[ ] 6. set PYTHONUTF8=1  /  -X utf8 (Windows: mandatory)
[ ] 7. python -X utf8 server.py    → see three "Running on ...8080/9090/8992"
[ ] 8. curl http://127.0.0.1:8080/debug/probe   → {"next_variant":6}
[ ] 9. (device) browser http://<SERVER_HOST>:8080/debug/probe → JSON
[ ] 10. install + launch APK (§4b/§4c)
```

Minimal one-liner once deps are installed:
```bash
cd local-server/python && SERVER_HOST=192.168.1.3 PYTHONUTF8=1 python -X utf8 server.py
```

---

## 12. Startup Verification Report (repo state as of this commit)

Verified by importing every module from a clean checkout — **nothing is missing**.

### Environment
| Item | Value |
|------|-------|
| Python | 3.12.3 (requirement: 3.8+) |
| Third-party packages | **flask 3.0.0**, **werkzeug 3.0.1** (flask's dep) — both in `requirements.txt`, both installed |
| Working dir | `local-server/python/` (required for sibling imports) |
| Catalogs loaded | **93** from `gamedata/*.json` (94 files incl. `_summary.json`) |
| Ports | HTTP **8080**, keepalive **9090**, analytics **8992** |
| `SERVER_HOST` default | `127.0.0.1` (override per network) |

### Full dependency inventory (every import)
| Module | Imports | Type | Present? |
|--------|---------|------|----------|
| `server.py` | `base64, json, os, random, threading, time, collections.deque, datetime.datetime` | stdlib | ✅ |
| `server.py` | `flask (Flask, jsonify, make_response, request)` | pip | ✅ flask 3.0.0 |
| `server.py` | `city_loader`, `player_state` | local sibling | ✅ |
| `player_state.py` | `json, os, time, threading` | stdlib | ✅ |
| `city_loader.py` | `os, json, glob, struct` | stdlib | ✅ |

**No optional/missing imports.** The only non-stdlib dependency in the entire server is
`flask` (+ its bundled `werkzeug`). Everything else is the Python standard library.

### Boot confirmation
`python -c "import server"` (from `local-server/python/`, with `PYTHONUTF8=1`) returns:
```
city_loader, player_state, server: import OK
GAMEDATA catalogs: 93
ports HTTP/TCP/STAT: 8080 9090 8992
```
i.e. the repository **imports and initializes cleanly**. The *only* thing that stops a
launch on Windows is the cp1252 banner (§ top + §9) — solved by `PYTHONUTF8=1 -X utf8`.

> Note (no code change here): the banner crash could be removed permanently with a
> one-line guard on the print, but per instruction the code is left unmodified — use the
> UTF-8 env var.
