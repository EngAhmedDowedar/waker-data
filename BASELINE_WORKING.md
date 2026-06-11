# Baseline Working Build — 2026-06-11

First confirmed full boot to city screen on emulator.

## Build Artifacts

| Artifact | SHA256 |
|----------|--------|
| `client/waker-patched-signed.apk` (89.3 MB) | `1BF9AF2810C3BE13BCE73EEE5F1901F4B4DF5EB484DE5ADD4EDE72E1A05370B5` |
| `lib/armeabi/libcity_ar.so` (7.45 MB) | `18D15117194C360D3C097D61D61F18B37CE7457CD12B6ABC37E59A8020AB03EE` |

### Native patches applied (vs original APK)

| Offset | Original | Patched | Purpose |
|--------|----------|---------|---------|
| `0x48F911` | `D0` | `E0` | CheckUpdate bypass — skips launchUrl update dialog |
| `0x59190D` | `DC` | `E0` | gettopmsgs gate — stops CTopScreen news-ticker flood |
| 7 bytes | `0x34` | `0x33` | IP: 192.168.1.4 → 192.168.1.3 (all occurrences) |

### Smali changes (vs baseline APK)

- `Main.smali`: Removed `System.loadLibrary("frida-gadget")` from `<clinit>`
- `FirebaseInitProvider.smali`: `onCreate` stubbed (no-op + log)
- `FCMInstanceIDService.smali`: `onTokenRefresh` stubbed
- `FCMMessagingService.smali`: `onMessageReceived` stubbed
- `AndroidManifest.xml`: 6 Firebase/GCM components set `enabled="false"`

## Required Server Configuration

```
SERVER_HOST=192.168.1.3   # MUST match the IP in libcity_ar.so
```

Without this, the server returns `keepLiveServerHost: "127.0.0.1"` in `/api/connect`
and `url: "127.0.0.1"` in `/checkversion`. From the emulator, 127.0.0.1 is the
emulator itself (nothing listening), causing the step-10 keepalive to timeout-loop.

### Server ports

| Port | Purpose | Endpoints |
|------|---------|-----------|
| 8080 | Game API (cipher'd) | `/checkversion`, `/api/*` |
| 9090 | Keepalive / city (cipher'd) | `/city/*` |
| 8992 | Analytics (plaintext) | `/logevent/*` |

### Current missionId

`missionId: 1` — "Find a suitable job" (first mission in mission.city table).
Set in `_make_player()` at server.py line 376.

### Current route count

**38 routes** across 3 Flask apps (app, keepalive_app, analytics_app).

## Known Working Boot Sequence

```
Step  1  — Engine init
Step  4  — Asset decompression
Step  5  — Asset loading
Step  6  — Init subsystems
Step  7  — /checkversion (port 8080) → server selection screen
         — User taps "ابدا" (Start), selects "Waker" server
Step  8  — (transitional)
Step  9  — /api/connect (port 8080) → login, receives keepLiveServerHost:9090
Step 10  — /city/impart (port 9090) → config fetch (empty data OK)
         — Keepalive connection established
Step 11  — /city/connect/getplayerlist → [] (no existing character)
Step 12  — /city/connect/create or /city/connect/connect → full CPlayer object
Step 13  — City loaded, buildings rendered, missions active
```

### Emulator details

- Device: emulator-5554 (Android x86, Houdini ARM translation)
- Screen: 540×960, density 240
- Touch axes swapped: X max=959, Y max=539 (device landscape, display portrait)
- Game launched via: `am start -n com.anansimobile.city_ar/.Main`
- Fresh boot requires: `pm clear com.anansimobile.city_ar` (stale data shows empty bulletin popup)

## Warnings and Errors During Boot

### Non-fatal (boot continues)

| Source | Message | Impact |
|--------|---------|--------|
| `engine` | `[ERROR][Impart]parseImpart,but there has no data!!!!` | Empty impart config; falls back to bundled .city asset defaults. **Also occurred in May 29 known-good boot.** |
| `System.err` | `show AlertDialog! title=` | Empty-title alert briefly shown, dismissed automatically |
| `AppsFlyer` | `WARNING:READ_PHONE_STATE is missing` | Analytics permission; harmless |
| `System.err` | `UnknownHostException: data.flurry.com` | Flurry analytics unreachable; harmless |
| `IabHelper` | `In-app billing error: IAB helper is not set up` | Google billing unavailable; expected on emulator |
| `EGL_adreno` | `eglSurfaceAttrib error 0x3009 (EGL_BAD_MATCH)` | Emulator GPU; cosmetic |

### Post-step-13 crash

```
building 5 released
building 1 released
recv list faction response (×3)
→ lowmemorykiller error → "‫وكر الاوغاد‬ has stopped"
```

The game crashes shortly after reaching the city screen. **Root cause identified:**
the catch-all route (`/city/<path:cmd>`, server.py line 814) returns `data:{}`
for unimplemented endpoints, but many screen parsers expect `data:[]`. The array
begin-iterator on a non-array node returns null → SIGSEGV. Not a CPlayer issue.

See `analyze/docs/POST_STEP13_CRASH_ANALYSIS.md` for the full crash investigation.

## Impart Investigation Summary

See `analyze/docs/IMPART_ANALYSIS.md` for the full reverse-engineering report.
