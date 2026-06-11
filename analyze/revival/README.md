# Waker local-play revival guide (ready-to-test)

This repo is a decompiled APK project. The local-play workflow here gives you a reproducible setup to boot the client and route game traffic to localhost.

---

## 1) Extract API/domain inventory

```bash
cd /home/runner/work/waker/waker
python3 /home/runner/work/waker/waker/tools/extract_endpoints.py \
  --root /home/runner/work/waker/waker \
  --output /home/runner/work/waker/waker/revival/endpoint_inventory.json
```

Output:
- `/home/runner/work/waker/waker/revival/endpoint_inventory.json`
- includes URLs/hosts from smali/resources/native strings (`lib/armeabi/libcity_ar.so` included).

---

## 2) Run local backend (step by step)

1. Open terminal:
   ```bash
   cd /home/runner/work/waker/waker
   ```
2. Start backend:
   ```bash
   python3 /home/runner/work/waker/waker/tools/local_backend.py --host 0.0.0.0 --ports 8080,8992,2095
   ```
3. Confirm it is alive:
   ```bash
   curl -s http://127.0.0.1:8080/health
   ```
4. Test login flow:
   ```bash
   curl -s -X POST http://127.0.0.1:8080/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"player_local"}'
   ```
5. Use returned token:
   ```bash
   curl -s http://127.0.0.1:8080/player/profile \
     -H 'Authorization: Bearer <TOKEN>'
   ```

### Local backend API + request data shape

- `GET /health` -> no body
- `GET /ping` -> no body
- `POST /auth/login`
  - accepted fields: `username` or `user` or `deviceId`
- `GET /config/bootstrap` -> no auth
- `GET /player/profile`
  - auth: `Authorization: Bearer <token>` or `?token=...`
- `GET /player/state`
  - auth: `Authorization: Bearer <token>` or `?token=...`
- `POST /player/state`
  - auth required
  - body fields:
    - `deltaCoins` (int, max absolute `1000000`)
    - `deltaLevel` (int, max absolute `10000`)
- `POST /logevent/weightevent`
  - accepts any JSON and returns `{ok:true}` to avoid analytics hard-fail
- `GET /page/pwdreset`
  - returns placeholder HTML page
- unknown `GET/POST` endpoints now return safe fallback `{ok:true, fallback:true, ...}` for resilience

Verbose request/response logs are enabled in backend output.

---

## 3) Use `revival/hosts.override` on Windows and Android

### Generate override file

```bash
python3 /home/runner/work/waker/waker/tools/generate_hosts_override.py \
  --inventory /home/runner/work/waker/waker/revival/endpoint_inventory.json \
  --ip 127.0.0.1 \
  --output /home/runner/work/waker/waker/revival/hosts.override
```

### Windows host (`C:\Windows\System32\drivers\etc\hosts`)

1. Open Notepad as Administrator.
2. Open:
   - `C:\Windows\System32\drivers\etc\hosts`
3. Append content from:
   - `/home/runner/work/waker/waker/revival/hosts.override`
4. Flush DNS:
   ```powershell
   ipconfig /flushdns
   ```

### Android emulator/device

- **USB device / emulator recommended path**: keep hosts IP as `127.0.0.1` and use adb reverse:
  ```bash
  adb reverse tcp:8080 tcp:8080
  adb reverse tcp:8992 tcp:8992
  adb reverse tcp:2095 tcp:2095
  ```
- **Physical Android device to your PC backend**: regenerate with your PC LAN IP:
  ```bash
  python3 /home/runner/work/waker/waker/tools/generate_hosts_override.py \
    --inventory /home/runner/work/waker/waker/revival/endpoint_inventory.json \
    --ip <PC_LAN_IP> \
    --output /home/runner/work/waker/waker/revival/hosts.override
  ```

Then apply on rooted Android:
```bash
adb root
adb remount
adb push /home/runner/work/waker/waker/revival/hosts.override /sdcard/hosts.override
adb shell su -c 'cat /sdcard/hosts.override >> /etc/hosts'
adb shell su -c 'chmod 644 /etc/hosts'
adb reboot
```

---

## 4) OBB / expansion files required

Detected by app logic (`Main.expansionFilesDelivered`):
- package: `com.anansimobile.city_ar`
- versionCode: `2090800068`
- expected main OBB name:
  - `main.2090800068.com.anansimobile.city_ar.obb`
- expected configured size:
  - `23516595` bytes (`0x166d5b3`)

For local-play patch in this repo, expansion check is bypassed (always true), so missing OBB will no longer block startup from this gate.

---

## 5) LVL/license blocking status and patch

Google LVL exists in bundled downloader classes. For local-play reliability, startup OBB gate was patched to bypass expansion/LVL-trigger path:
- file:
  - `/home/runner/work/waker/waker/smali/com/anansimobile/city_ar/Main.smali`
- method patched:
  - `expansionFilesDelivered()Z` -> always returns `true`

This avoids local startup being blocked by downloader/LVL path when OBB/license server is unavailable.

---

## 6) Hardcoded endpoints and HTTPS notes

Core game domain candidates found in native library:
- `http://city-arab.anansigame.org:8080/`
- `http://appstat.anansicorp.org:8992/logevent/weightevent`
- `http://city-arab.anansigame.org:2095/page/pwdreset`
- templates also exist in native:
  - `https://%s:%d/`
  - `http://%s:%d/`

Local routing is done via hosts override. If HTTPS endpoints are used at runtime and fail because of TLS/certificate mismatch, you must either:
1) provide valid certs for redirected domains on your local server, or
2) patch TLS/pinning paths in native code.

---

## 7) Exact rebuild/sign/verify/install commands

From repo root:

```bash
cd /home/runner/work/waker/waker
mkdir -p /home/runner/work/waker/waker/dist

# 1) Rebuild APK from decompiled tree
apktool b /home/runner/work/waker/waker -o /home/runner/work/waker/waker/dist/waker-local-unsigned.apk

# 2) Align
zipalign -f 4 \
  /home/runner/work/waker/waker/dist/waker-local-unsigned.apk \
  /home/runner/work/waker/waker/dist/waker-local-aligned.apk

# 3) Generate debug keystore (one-time)
keytool -genkeypair -v \
  -keystore /home/runner/work/waker/waker/dist/debug.keystore \
  -storepass android \
  -keypass android \
  -alias androiddebugkey \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -dname "CN=Android Debug,O=Android,C=US"

# 4) Sign
apksigner sign \
  --ks /home/runner/work/waker/waker/dist/debug.keystore \
  --ks-key-alias androiddebugkey \
  --ks-pass pass:android \
  --key-pass pass:android \
  --out /home/runner/work/waker/waker/dist/waker-local-signed.apk \
  /home/runner/work/waker/waker/dist/waker-local-aligned.apk

# 5) Verify signature
apksigner verify --verbose --print-certs /home/runner/work/waker/waker/dist/waker-local-signed.apk

# 6) Install
adb uninstall com.anansimobile.city_ar || true
adb install -r /home/runner/work/waker/waker/dist/waker-local-signed.apk
```

---

## 8) Boot + localhost connection checklist

1. Start backend (`0.0.0.0` on ports `8080,8992,2095`).
2. If using adb connection, apply reverse:
   ```bash
   adb reverse tcp:8080 tcp:8080
   adb reverse tcp:8992 tcp:8992
   adb reverse tcp:2095 tcp:2095
   ```
3. Apply hosts mapping on target Android (or emulator).
4. Install signed APK.
5. Launch app:
   ```bash
   adb shell monkey -p com.anansimobile.city_ar -c android.intent.category.LAUNCHER 1
   ```
6. Watch app network logs:
   ```bash
   adb logcat | grep -Ei 'anansi|city|http|ssl|connect|downloader|lvl'
   ```
7. Confirm backend receives requests in terminal (verbose logs).

If no backend hits appear, traffic is likely still inside native flow with unsupported protocol/TLS requirements.

---

## Native networking evidence from `libcity_ar.so`

Likely connection/network primitives present:
- `connect`
- `send`
- `recv`
- `getaddrinfo`
- `inet_addr`
- `_Z14socket_connectPiP8sockaddri`
- `_Z14socket_connectPiPKcs`
- `_Z11socket_sendPiPKcjPj`
- `_Z11socket_recvPiPcjPj`
- `curl_easy_setopt`
- `curl_easy_perform`
- `Curl_http*` family

Hardcoded native domains/URLs observed include:
- `city-arab.anansigame.org`
- `appstat.anansicorp.org`
- `s3.amazonaws.com`
- `http://city-arab.anansigame.org:8080/`
- `http://appstat.anansicorp.org:8992/logevent/weightevent`
