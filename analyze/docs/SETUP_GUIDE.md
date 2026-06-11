# Waker (وكر الاوغاد) - Setup Guide

## How to Make the Game Work Again with a Local Server

This guide explains how to patch the game client and run a local server to make
the offline game (وكر الاوغاد / Wild City / Den of Scoundrels) boot and function
again after its original servers were shut down.

---

## Prerequisites

- **Python 3.8+** (for patching tools and Flask server)
- **Node.js 16+** (for Node.js server, optional if using Python)
- **Android device** or **emulator** (Android 4.0+)
- **apktool** v2.5+ (for rebuilding the APK)
- **Java JDK 8+** (for apktool and signing)
- **ADB** (Android Debug Bridge)
- **keytool/jarsigner** or **apksigner** (for signing the APK)

---

## Method A: Hosts File Redirect (Simplest - No Binary Patching)

This method redirects the game's DNS requests to your local server without
modifying the APK binary. Requires root on Android device.

### Step 1: Start the Local Server

**Option 1 - Node.js:**
```bash
cd local-server/node
npm install
npm start
```

**Option 2 - Python Flask:**
```bash
cd local-server/python
pip install -r requirements.txt
python server.py
```

Both servers listen on:
- **Port 8080** - Main game API
- **Port 9090** - TCP keepalive
- **Port 8992** - Analytics (stub)

### Step 2: Edit Android Hosts File (requires root)

```bash
adb root
adb shell "echo '10.0.2.2 city-arab.anansigame.org' >> /etc/hosts"
adb shell "echo '10.0.2.2 appstat.anansicorp.org' >> /etc/hosts"
adb shell "echo '10.0.2.2 city.wiyun.com' >> /etc/hosts"
adb shell "echo '10.0.2.2 s3.amazonaws.com' >> /etc/hosts"
adb shell "echo '10.0.2.2 www.sakhabgame.com' >> /etc/hosts"
adb shell "echo '10.0.2.2 alog.umeng.com' >> /etc/hosts"
```

> **Note:** `10.0.2.2` is the host machine's IP from the Android emulator.
> If using a physical device on the same WiFi, use your computer's LAN IP instead.

### Step 3: Install and Run the Game

Install the original (unmodified) APK and launch it.

---

## Method B: Binary Patching (Recommended - No Root Required)

This method patches the APK to redirect all server URLs to localhost/your IP.

### Step 1: Run the Binary Patcher (patch .so file)

```bash
cd tools
python patch_so.py
```

This patches `lib/armeabi/libcity_ar.so` to redirect:
- `city-arab.anansigame.org:8080` → `127.0.0.1:8080`
- `city-arab.anansigame.org:2095` → `127.0.0.1:8080`
- `appstat.anansicorp.org:8992` → `127.0.0.1:8992`
- S3/resource URLs → `127.0.0.1:8080`

**For a custom IP** (e.g., LAN server):
```bash
python patch_so.py --server-ip 192.168.1.100
```

### Step 2: Run the Smali Patcher (disable analytics)

```bash
python patch_smali.py
```

This disables:
- Umeng analytics
- TalkingData tracking
- AppsFlyer attribution
- Expansion file checks

### Step 3: Rebuild the APK

```bash
cd ..
apktool b . -o waker-patched.apk
```

### Step 4: Sign the APK

Create a keystore (one time):
```bash
keytool -genkey -v -keystore waker-key.jks -keyalg RSA -keysize 2048 -validity 10000 -alias waker
```

Sign:
```bash
jarsigner -verbose -sigalg SHA256withRSA -digestalg SHA-256 -keystore waker-key.jks waker-patched.apk waker
```

Or with apksigner:
```bash
apksigner sign --ks waker-key.jks --out waker-signed.apk waker-patched.apk
```

### Step 5: Install on Device

```bash
adb install waker-signed.apk
```

### Step 6: Start the Local Server

On your PC (same machine or accessible via network):

**Node.js:**
```bash
cd local-server/node
npm install
npm start
```

**Python:**
```bash
cd local-server/python
pip install -r requirements.txt
python server.py
```

### Step 7: Launch the Game

The game should now:
1. ✅ Pass version check
2. ✅ Get server list (local)
3. ✅ Register/login as guest
4. ✅ Load player data
5. ✅ Enter the game

---

## Method C: Using an Android Emulator (Easiest for Testing)

### Step 1: Set up Android Emulator

Use Android Studio emulator or any emulator (BlueStacks, LDPlayer, etc.)

### Step 2: Patch for Emulator IP

When running in an emulator, `10.0.2.2` maps to the host machine's localhost:
```bash
python tools/patch_so.py --server-ip 10.0.2.2
```

### Step 3: Rebuild, Sign, Install, Run

Follow Steps 3-7 from Method B above.

---

## Troubleshooting

### Game crashes on startup
- Check that the local server is running and accessible
- Verify the server IP is correct for your setup
- Check server console for incoming requests

### Game hangs on loading screen
- The game may be waiting for a response. Check server console for UNHANDLED requests
- Look for the specific endpoint being called and add it to the server

### "Version update required"
- Make sure `/check_version` returns `needUpdate: false` and `forceUpdate: false`
- The version in response must match: `"1.1.38"`

### TCP connection refused
- Ensure port 9090 is not blocked by firewall
- Server must be running the TCP keepalive listener
- The `keepLiveServerPort` in server list and connect responses must be 9090

### Game shows blank/white screen
- This is usually a GL rendering issue unrelated to networking
- Ensure the emulator supports OpenGL ES 2.0
- Try a different emulator or device

### Server shows UNHANDLED endpoint
- This is expected! The server handles 60+ known endpoints
- Unknown endpoints return generic success `{"result":0}`
- If the game needs specific data from an endpoint, add it to the server

---

## Network Configuration Summary

| Service | Port | Protocol | Purpose |
|---------|------|----------|---------|
| Game API | 8080 | HTTP | All game API calls |
| TCP KeepAlive | 9090 | TCP | Real-time (heartbeat, chat) |
| Analytics | 8992 | HTTP | Event logging (stub) |

---

## File Structure

```
waker/
├── tools/
│   ├── patch_so.py          # Binary patcher for libcity_ar.so
│   └── patch_smali.py       # Smali patcher for analytics/checks
├── local-server/
│   ├── node/
│   │   ├── package.json     # Node.js dependencies
│   │   └── server.js        # Node.js local server
│   └── python/
│       ├── requirements.txt # Python dependencies
│       └── server.py        # Flask local server
├── lib/
│   └── armeabi/
│       └── libcity_ar.so    # Native library (to be patched)
├── smali/                   # Decompiled Java bytecode
├── assets/                  # Game assets
├── res/                     # Android resources
├── AndroidManifest.xml      # App manifest
├── apktool.yml             # APK metadata
├── REVERSE_ENGINEERING_ANALYSIS.md  # Full analysis
├── NETWORKING_MAP.md        # Network documentation
└── SETUP_GUIDE.md           # This file
```

---

## Advanced: Custom Server IP for LAN Play

If running the server on a different machine:

```bash
# Patch with your server's LAN IP
python tools/patch_so.py --server-ip 192.168.1.100

# Rebuild and sign APK
apktool b . -o waker-lan.apk
jarsigner -keystore waker-key.jks waker-lan.apk waker

# Start server on 192.168.1.100
cd local-server/node && npm start
# or
cd local-server/python && python server.py
```

Both server implementations listen on `0.0.0.0` (all interfaces) by default.

---

## Advanced: Adding Game Features

The local server returns minimal data. To add more realistic gameplay:

1. **Edit player stats** in the `createDefaultPlayer()` function
2. **Add items** to market/store responses
3. **Implement missions** by returning mission data in `/mission/list`
4. **Add NPC enemies** for combat
5. **Persist data** by adding a database (SQLite/JSON file)

The server is designed to be easily extensible. Each endpoint handler is
self-contained and can be modified independently.
