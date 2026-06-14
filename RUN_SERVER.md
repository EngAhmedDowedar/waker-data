# RUN_SERVER.md — Start the Waker server & connect the device

Follow this top to bottom on a clean machine to reproduce the current working state
(boot → main city screen). No reverse-engineering knowledge required.

---

## ✅ VERIFIED WORKING METHOD (USB / ADB Reverse)

The most reliable setup — works even when the device is on a different subnet than the PC:

```powershell
# 1. Start the server (Windows PowerShell, from repo root)
cd local-server\python
$env:PYTHONUTF8="1"; python -X utf8 server.py

# 2. Set up ADB reverse port forwarding (device → PC, over USB)
adb reverse tcp:8080 tcp:8080
adb reverse tcp:9090 tcp:9090
adb reverse tcp:8992 tcp:8992

# 3. Clear game state (forces direct-login path; avoids resume-path stall)
adb shell pm clear com.anansimobile.city_ar

# 4. Install and launch the USB-patched APK
adb install -r client/waker-usb-signed.apk
adb shell am start -n com.anansimobile.city_ar/.Main
```

The game will auto-proceed past the login screen in ~3–5 minutes.
Watch for `[LoadingMnger] do step:13` in logcat to confirm city boot.

**Why ADB reverse?** The device may be on a different IP subnet (172.16.x vs 192.168.x).
ADB reverse tunnels all three game ports through the USB connection so the device reaches
the server at `127.0.0.1` regardless of network topology.

**Why `pm clear`?** The resume path (used after any crash/restart) tries a binary keepalive
on port 9090 that our HTTP-only server cannot respond to. Clearing state forces the fresh
direct-login path which uses standard HTTP throughout. Always `pm clear` before launch.

---

## ⚠️ IF THE SERVER "DID NOT START" — READ THIS FIRST

On **Windows**, `python server.py` crashes **immediately** with a `UnicodeEncodeError`
because the startup banner contains Arabic text the default `cp1252` console can't encode.
**You must force UTF-8 output.** The single command that works from a clean clone:

```powershell
cd local-server\python
$env:PYTHONUTF8="1"; python -X utf8 server.py
```
```bash
# git-bash / WSL / Linux / macOS
cd local-server/python
PYTHONUTF8=1 python -X utf8 server.py
```

If you see three `Running on http://...:8080/9090/8992` lines, it started. Full details,
ports, verification, and other failure modes are below.

> **Note:** `SERVER_HOST` is no longer needed for the USB/ADB-reverse setup — the APK
> connects to `127.0.0.1` directly and ADB reverse handles the forwarding. Set it only
> if you also want the `/debug/probe` banner to show the right IP.

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
# Recommended: USB/ADB-reverse APK (server at 127.0.0.1, works on any device)
adb install -r client/waker-usb-signed.apk
# if signature mismatch: adb uninstall com.anansimobile.city_ar  then install again

# Legacy: Wi-Fi APK (server at 192.168.1.3, requires same subnet)
# adb install -r client/waker-patched-signed.apk
```

### 4c. Set up ADB reverse and launch with CLEAN state

```bash
# Forward all three game ports through USB (MUST be done after every adb reconnect)
adb reverse tcp:8080 tcp:8080
adb reverse tcp:9090 tcp:9090
adb reverse tcp:8992 tcp:8992

# Clear state (forces direct-login path; avoids resume-path binary-keepalive stall)
adb shell pm clear com.anansimobile.city_ar
adb shell am start -n com.anansimobile.city_ar/.Main
```

> **Why the clears:** leftover state makes the client take the **resume / authplayerkey**
> path which tries a binary keepalive on port 9090 that this HTTP server cannot handle.
> Clearing forces the proven direct path:
> `checkversion → api/connect → impart → getplayerlist → create → connect → city`
>
> **After `pm clear`, the game auto-proceeds through the login screen** in ~3–5 minutes
> without requiring any manual taps. No interaction needed — just wait for
> `[LoadingMnger] do step:13` in logcat.

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
| 7 | **Step 10 stall** — game loops after login | Clear device state (`pm clear`) and re-run adb reverse (section 4c) |
| 8 | **ADB reverse required** — device on different subnet (172.16.x vs 192.168.x) | `adb reverse tcp:8080 tcp:8080; adb reverse tcp:9090 tcp:9090; adb reverse tcp:8992 tcp:8992` |

## 9. Common failures

| Symptom | Cause | Fix |
|---|---|---|
| `UnicodeEncodeError` on startup | Windows cp1252 console | Use `PYTHONUTF8=1 python -X utf8 server.py` |
| `OSError: address already in use` | Previous server still running | Kill it: find PID with `netstat`, then kill |
| Banner shows `127.0.0.1` | `SERVER_HOST` not set | Restart with `SERVER_HOST=<your-host>` |
| Game stuck on title | Phone can't reach the server | Check name resolution + firewall |
| Game reaches step 10, retries | Cached resume path binary keepalive — HTTP server can't respond | `adb shell pm clear com.anansimobile.city_ar` then relaunch |
| Game stuck on loading screen (no city) | ADB reverse not set up or expired | Run `adb reverse tcp:8080/9090/8992 tcp:8080/9090/8992` again |
| Server gets no requests after `authplayerkey` | Resume path — binary keepalive stall | `pm clear` to force direct-login path |
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
[ ] 1. python --version                        → 3.8+ (verified on 3.12.3)
[ ] 2. pip install -r local-server/python/requirements.txt   (flask 3.0.0, werkzeug 3.0.1)
[ ] 3. confirm local-server/python/gamedata/ has ~93 *.json
[ ] 4. cd local-server/python                  (MUST cd here — imports are relative siblings)
[ ] 5. PYTHONUTF8=1 python -X utf8 server.py   → see three "Running on ...8080/9090/8992"
[ ] 6. curl http://127.0.0.1:8080/debug/probe  → {"next_variant":6}
[ ] 7. adb reverse tcp:8080 tcp:8080 && adb reverse tcp:9090 tcp:9090 && adb reverse tcp:8992 tcp:8992
[ ] 8. adb install -r client/waker-usb-signed.apk
[ ] 9. adb shell pm clear com.anansimobile.city_ar
[ ] 10. adb shell am start -n com.anansimobile.city_ar/.Main
[ ] 11. wait ~3-5 min → logcat shows [LoadingMnger] do step:13 → CITY SCREEN
```

Minimal one-liner once deps are installed:
```bash
cd local-server/python && PYTHONUTF8=1 python -X utf8 server.py
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
