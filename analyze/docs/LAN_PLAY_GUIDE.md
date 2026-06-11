# Waker – LAN Play Guide (Real Phone + Laptop)

Run the game on a **real Android phone** while the server runs on your **Windows laptop**,
both connected to the same Wi-Fi network.

---

## Step 1: Find Your Laptop's LAN IP

Open a terminal (cmd/PowerShell/Git Bash) on your laptop:

```bash
ipconfig | findstr "IPv4"
```

Look for the address on your **Wi-Fi adapter** (not VPN/Ethernet if you're on Wi-Fi).
Example output:

```
IPv4 Address. . . . . . . . . . . : 192.168.1.5
```

Your laptop IP is **`192.168.1.5`** (use YOUR actual value from now on).

---

## Step 2: Patch the APK to Use Your Laptop IP

```bash
cd "C:/Users/Admin/Videos/New folder/waker"
python tools/patch_so.py --server-ip 192.168.1.5
python tools/patch_smali.py
```

This rewrites every hardcoded server URL inside `libcity_ar.so`:
- `http://city-arab.anansigame.org:8080/` → `http://192.168.1.5:8080/`
- `http://appstat.anansicorp.org:8992/…` → `http://192.168.1.5:8992/…`
- All other dead domains → `http://192.168.1.5:8080/…`

> **If your IP changes later**, you must re-run `patch_so.py` and rebuild the APK.
> Consider assigning a static IP to your laptop in your router settings.

---

## Step 3: Rebuild and Sign the APK

```bash
# Rebuild
apktool b "C:/Users/Admin/Videos/New folder/waker" -o waker-lan.apk

# Generate signing key (one time only)
keytool -genkey -v -keystore waker-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias waker -storepass waker123 -keypass waker123 -dname "CN=Waker"

# Sign the APK
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 -keystore waker-key.jks -storepass waker123 waker-lan.apk waker
```

The signed APK is now ready: **`waker-lan.apk`**

---

## Step 4: Install the APK on Your Phone

Connect your phone via USB with **USB debugging enabled**.

```bash
# Uninstall any previous version first
adb uninstall com.anansimobile.city_ar

# Install the patched APK
adb install waker-lan.apk
```

If `adb` doesn't see the device:
```bash
adb devices
# Should show your device serial. If empty:
# - Check USB cable
# - Enable Developer Options → USB Debugging on phone
# - Accept the "Allow USB debugging" prompt on the phone
```

---

## Step 5: Start the Local Server on Your Laptop

**Set the `SERVER_IP` environment variable** so the server returns the correct
IP in its JSON responses (for the TCP keepalive connection):

### Option A – Node.js:
```bash
cd "C:/Users/Admin/Videos/New folder/waker/local-server/node"
npm install

# Windows CMD:
set SERVER_IP=192.168.1.5 && node server.js

# Windows PowerShell:
$env:SERVER_IP="192.168.1.5"; node server.js

# Git Bash / WSL:
SERVER_IP=192.168.1.5 node server.js
```

### Option B – Python Flask:
```bash
cd "C:/Users/Admin/Videos/New folder/waker/local-server/python"
pip install -r requirements.txt

# Windows CMD:
set SERVER_IP=192.168.1.5 && python server.py

# Windows PowerShell:
$env:SERVER_IP="192.168.1.5"; python server.py

# Git Bash / WSL:
SERVER_IP=192.168.1.5 python server.py
```

You should see:
```
============================================
  Waker Local Server - وكر الاوغاد
============================================
[HTTP] Game API server running on port 8080
       URL: http://192.168.1.5:8080/
[TCP]  KeepAlive server running on port 9090
[STAT] Analytics server running on port 8992
============================================
Ready! Configure your device to point to this server.
============================================
```

Both servers bind to `0.0.0.0` (all network interfaces) so they already
accept connections from the LAN.

---

## Step 6: Open Windows Firewall for Ports 8080, 9090, 8992

Windows Firewall **blocks incoming connections by default**. You must allow
the three ports.

### Quick method (run as Administrator):
```bash
netsh advfirewall firewall add rule name="Waker Game Server 8080" dir=in action=allow protocol=tcp localport=8080
netsh advfirewall firewall add rule name="Waker TCP KeepAlive 9090" dir=in action=allow protocol=tcp localport=9090
netsh advfirewall firewall add rule name="Waker Stats 8992" dir=in action=allow protocol=tcp localport=8992
```

### Or via GUI:
1. Open **Windows Defender Firewall** → **Advanced Settings**
2. **Inbound Rules** → **New Rule**
3. Rule type: **Port**
4. Protocol: **TCP**, Specific ports: **8080, 9090, 8992**
5. Action: **Allow the connection**
6. Profile: check **Private** (your Wi-Fi)
7. Name: `Waker Game Server`

---

## Step 7: Test Connectivity from Your Phone

Before launching the game, verify the phone can reach the laptop.

Open **Chrome on your phone** and visit:

```
http://192.168.1.5:8080/check_version
```

You should see a JSON response:
```json
{"result":0,"code":200,"data":{"version":"1.1.38","versionCode":2090800068,"forceUpdate":false,"updateUrl":"","description":"","needUpdate":false},"errorMsg":""}
```

Also test:
```
http://192.168.1.5:8080/server_list
```

**If you get "connection refused" or timeout:**
- Phone and laptop must be on the **same Wi-Fi network**
- Firewall rules must be active (Step 6)
- Server must be running (check terminal output)
- Some routers have "AP isolation" enabled — disable it in router settings

---

## Step 8: Launch the Game

Open the game on your phone. It will:

1. Call `http://192.168.1.5:8080/check_version` — pass ✅
2. Call `http://192.168.1.5:8080/server_list` — get server list ✅
3. Call `http://192.168.1.5:8080/guest/register` — create account ✅
4. Call `http://192.168.1.5:8080/connect` — enter game ✅
5. Open TCP to `192.168.1.5:9090` — keepalive ✅

Watch the server terminal for live request logs.

---

## Step 9: Debug Connection Failures with Logcat

If the game hangs or crashes, use `adb logcat` to see native logs:

```bash
# Filter for game-related output
adb logcat | grep -i "city_ar\|nge\|NGE\|http\|connect\|socket\|error"

# Or broader:
adb logcat -s "city_ar:*" "NGE:*" "System.err:*"

# Full unfiltered (very verbose):
adb logcat > game_log.txt
```

**What to look for:**
- `Connection refused` → firewall blocking, or server not running
- `UnknownHostException` → domain not patched properly, re-run `patch_so.py`
- `SocketTimeout` → server reachable but not responding fast enough
- `JSON parse error` → server returning wrong format
- Any HTTP URL still showing `anansigame.org` → patch didn't apply

---

## Required Ports Summary

| Port | Protocol | Purpose | Required? |
|------|----------|---------|-----------|
| **8080** | TCP/HTTP | Main game API (all gameplay) | **YES – critical** |
| **9090** | TCP | Real-time keepalive (heartbeat, chat, poker) | **YES – game expects it** |
| **8992** | TCP/HTTP | Analytics event logging | Optional (game works without, but will log errors) |

**Yes, all three ports are needed.** The game will:
- Make HTTP requests to port 8080 for every game action
- Open a persistent TCP socket to port 9090 for real-time features
- POST analytics events to port 8992

The TCP keepalive server on port 9090 **must also be LAN-accessible**. Both
the Node.js and Python servers already bind it to `0.0.0.0`, so it works
on LAN as long as the firewall rule is in place.

---

## Quick Reference: All Commands in Order

```bash
# === ON YOUR LAPTOP ===

# 1. Find your IP
ipconfig | findstr "IPv4"
# Note: 192.168.1.5 (example - use YOUR IP)

# 2. Patch the APK
cd "C:/Users/Admin/Videos/New folder/waker"
python tools/patch_so.py --server-ip 192.168.1.5
python tools/patch_smali.py

# 3. Rebuild
apktool b . -o waker-lan.apk

# 4. Sign (first time: generate key)
keytool -genkey -v -keystore waker-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias waker -storepass waker123 -keypass waker123 -dname "CN=Waker"
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 -keystore waker-key.jks -storepass waker123 waker-lan.apk waker

# 5. Open firewall (Admin terminal)
netsh advfirewall firewall add rule name="Waker 8080" dir=in action=allow protocol=tcp localport=8080
netsh advfirewall firewall add rule name="Waker 9090" dir=in action=allow protocol=tcp localport=9090
netsh advfirewall firewall add rule name="Waker 8992" dir=in action=allow protocol=tcp localport=8992

# 6. Install on phone (USB connected)
adb uninstall com.anansimobile.city_ar
adb install waker-lan.apk

# 7. Start server
cd "C:/Users/Admin/Videos/New folder/waker/local-server/node"
npm install
set SERVER_IP=192.168.1.5 && node server.js

# 8. Test from phone browser: http://192.168.1.5:8080/check_version

# 9. Launch the game on phone

# 10. Debug if needed
adb logcat | grep -i "city_ar\|nge\|http\|error"
```

---

## Cleanup: Remove Firewall Rules Later

```bash
netsh advfirewall firewall delete rule name="Waker 8080"
netsh advfirewall firewall delete rule name="Waker 9090"
netsh advfirewall firewall delete rule name="Waker 8992"
```
