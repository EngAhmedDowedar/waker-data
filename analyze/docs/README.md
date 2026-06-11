# Waker (وكر الاوغاد) - Private Server Revival Project

## About

**Waker** (وكر الاوغاد / Den of Scoundrels / Wild City) was an Arabic-region
online city-building/crime game developed by **Anansi Mobile**. The game was
published on Google Play and ran until approximately 2019-2020 when the servers
were permanently shut down.

This project provides tools to **revive the game** by emulating the original
backend servers locally, allowing the game to boot and function again.

## Quick Start

### 1. Patch the Client

```bash
# Patch native library (redirect server URLs to localhost)
python tools/patch_so.py

# Patch smali code (disable dead analytics)
python tools/patch_smali.py

# Rebuild the APK
apktool b . -o waker-patched.apk

# Sign and install
keytool -genkey -v -keystore waker.jks -keyalg RSA -keysize 2048 -validity 10000 -alias waker
jarsigner -keystore waker.jks waker-patched.apk waker
adb install waker-patched.apk
```

### 2. Start the Local Server

**Node.js:**
```bash
cd local-server/node && npm install && npm start
```

**Python Flask:**
```bash
cd local-server/python && pip install -r requirements.txt && python server.py
```

### 3. Play!

Launch the game on your device/emulator. It will connect to the local server.

## Documentation

| Document | Description |
|----------|-------------|
| [REVERSE_ENGINEERING_ANALYSIS.md](REVERSE_ENGINEERING_ANALYSIS.md) | Complete technical analysis |
| [NETWORKING_MAP.md](NETWORKING_MAP.md) | Network architecture, endpoints, protocols |
| [SETUP_GUIDE.md](SETUP_GUIDE.md) | Detailed step-by-step instructions |

## Project Structure

```
waker/
├── tools/                    # Patching tools
│   ├── patch_so.py          # Binary patcher for libcity_ar.so
│   └── patch_smali.py       # Smali patcher for analytics
├── local-server/             # Server emulators
│   ├── node/                # Node.js version
│   │   ├── package.json
│   │   └── server.js
│   └── python/              # Python Flask version
│       ├── requirements.txt
│       └── server.py
├── lib/armeabi/             # Native library
│   └── libcity_ar.so       # Game engine (to be patched)
├── smali/                   # Decompiled Java bytecode
├── assets/                  # Game data files
├── res/                     # Android resources
├── AndroidManifest.xml      # App manifest
└── apktool.yml             # APK metadata
```

## Technical Summary

| Component | Details |
|-----------|---------|
| **Package** | `com.anansimobile.city_ar` |
| **Version** | 1.1.38 |
| **Engine** | NextGenEngine (NGE) - C++/OpenGL ES 2.0 |
| **Protocol** | HTTP POST + JSON on port 8080 |
| **TCP** | Keep-alive on port 9090 (RC4 encrypted) |
| **API Methods** | ~636 identified in CHttpClient |
| **Server Emulation** | 60+ endpoints implemented |

## License

This project is for educational and preservation purposes only.
All game assets belong to Anansi Mobile.
