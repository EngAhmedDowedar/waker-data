# Emulator (Houdini/x86) vs Real ARM — Risk Assessment

Analysis-only. Decides whether the session-ending post-city crash is an x86/Houdini
translation artifact or a genuine game-data fault, and what to expect on real ARM hardware.
Generated 2026-06-11 from on-disk tombstone/logcat evidence + prior real-device notes.

---

## 0. Answer to the gating question

**Can we test on a real ARM Android device? — YES, and it has already been done once.**

- A physical ARM phone is referenced throughout the repo: **Samsung RK8W103BVET**
  (also an `SM-A805N`-class device), `armeabi-v7a`, non-rooted.
- Real-device screenshots exist: `analyze/screenshots/screen_realdevice{,2,3}.png` (May 29).
- **No new build is required.** `client/waker-patched-signed.apk` already contains the
  `lib/armeabi/` ARMv7 `libcity_ar.so` with all three native patches baked in. The same
  APK that runs under Houdini on the emulator installs **natively** on an ARM phone.
- **Current blocker is purely physical:** no ARM device is attached to this PC right now.
  `adb devices` shows only `emulator-5554` (x86/Houdini). The Samsung must be connected
  via USB (or `adb connect` over Wi-Fi) before deployment.

---

## 1. Evidence for Houdini (translation-layer) faults

| Evidence | Detail | Source |
|----------|--------|--------|
| Recurring identical fault | `#00 pc 000bf750 /system/lib/libhoudini.so`, fault addr `0x0` | logcat_fix1 08:53, logcat_fix2 09:13, logcat_fix3 10:45 (tombstone_03) |
| Same offset across unrelated builds | The **identical** `libhoudini.so +0xbf750` also crashed the May-27 frida-era build (fault `0x10`, 8+ times) | full_live_log.txt |
| Pure-Houdini stack | tombstone_phase1_classB: `eip 0x891c2454` unmapped; entire stack is `libhoudini.so` + `linker (__dl_dl_iterate_phdr)` — zero game frames | tombstone_phase1_classB.txt |
| Translated-code fault region | C3 fault in `[anon:Mem_0x20000000]` — Houdini's JIT code cache, not any `.so` mapping | logcat_fix3 10:28 (tombstone_02) |
| Persisted after data fixes | C4 (`+0xbf750`) occurred **after** all Phase-1 `data:[]` routes were added — adding correct JSON did not stop it | server_stderr_phase1.log + logcat_fix3 |
| Structural unwind failure | No captured crash unwinds into `libcity_ar.so`; under Houdini, ARM game code never executes from its file mapping, so debuggerd cannot symbolize it | all tombstones single-frame `#00` only |

**Confidence that Houdini is involved in the session-ending crash: HIGH.**
The same translator offset kills three different builds across three weeks. This is a
property of the x86+Houdini environment, not of any one server response.

---

## 2. Evidence for game-data (server-fixable) faults

| Evidence | Detail | Source | Strength |
|----------|--------|--------|----------|
| ASCII fault addresses | C3 `0x657a697b` ("{ize"), earlier `0x756f707b` ("{pou"), `0x0` patterns — printable bytes used as a pointer = a string/JSON field dereferenced as a pointer | logcat_fix3, POST_STEP13 | Medium — but occurs inside translated code, so could be Houdini mistranslation rather than a real bad pointer |
| Class A theory | Parsers calling `begin()` (vtbl+0x14) on `data:{}` → null-iterator → SIGSEGV `0x0` | CRASH_CORRELATION_REPORT, POST_STEP13 | **Weak as evidence** — the attributions (`ParsePatient`/`GetRowCount`/`ParseAirlines`) appear in **no on-disk stack**; they are inferred from fault-pattern, and the actual captured fault-`0x0` stack is Houdini, not a parser |
| `/city/deal/taobao` discovery | A MEDIUM-classified parser did reach an array sub-parser and crash until given `data:[]` | PHASE1_COMPLETION_REPORT | Medium — proves data-shape faults are real, but this one was *fixed*; doesn't prove a remaining data fault |
| Estate/goods correlation | Crashes follow `/city/estate/listestates` + `/city/goods/*` in the request log | server_stderr_phase1.log | Weak — correlation only; no symbolized estate/goods frame captured |

**Confidence that a *remaining* game-data fault is the session-ending blocker: LOW–MEDIUM.**
The strongest data-side candidate (C3, ASCII fault on estate/goods render) is real but
seen once, and it manifests inside JIT-translated code, so it cannot be cleanly separated
from a Houdini mistranslation without an ARM control test.

### Counter-evidence (data is probably fine)

`PLAYER_DATA_PUSH.md:32` records that on the **real ARM Samsung**, the full boot sequence
(`/checkversion → /api/connect → /city/impart → connect/{getplayerlist,create,connect}
→ /city/chat/getsysmsgs → /city/monthCard/enterMatchCard → /race/match/matchconfig`) ran
**crash-free for 25s+ with the game foreground** — the same sequence that reliably crashes
the emulator post-city. That is the single strongest data point in the project, and it
points at Houdini, not the JSON.

---

## 3. Confidence Summary

| Hypothesis | Confidence it explains the session-ending crash | Server-fixable? |
|-----------|--------------------------------------------------|-----------------|
| **Houdini translation fault** (`+0xbf750` / JIT) | **HIGH** (~75%) — recurring, build-independent, survived data fixes, real-ARM run was clean | No |
| **Remaining game-data / layout fault** (C3 estate/goods) | **LOW–MEDIUM** (~25%) — real signature but single capture, intertwined with JIT | Yes, if isolated |
| Missing assets (Class C) | Very low — no crash evidence; impart-empty is benign | n/a |
| Network/protocol (Class D) | None — resolved | n/a |

---

## 4. Expected Outcome on Real ARM Hardware

| Crash | Expected on ARM | Confidence | Reasoning |
|-------|-----------------|-----------|-----------|
| C1/C2/C4 `libhoudini+0xbf750` (fault 0x0) | **Disappears** | High | No Houdini layer exists on ARM; prior ARM run was crash-free through the same sequence |
| C5 `0x891c2454` (pure Houdini/linker) | **Disappears** | High | Stack is entirely translation-layer code that ARM does not use |
| C3 `0x657a697b` / layout `0x756f707b` (estate/goods render) | **Uncertain — may persist** | Medium | If it is a genuine field-shape bug it will reproduce; if it was JIT mistranslation it vanishes. The prior ARM run only reached ~`matchconfig` (25s) and likely did **not** navigate to estate/goods, so this is *not yet settled* and is the key thing the ARM test must exercise |

### Net prediction

- **Most likely:** the game boots to the city screen on ARM and **stays up** past the point
  where the emulator dies — because the dominant signature is Houdini-side.
- **Residual risk on ARM:** the estate/goods render path (C3) is unproven on ARM and must be
  explicitly visited to confirm. If it crashes there with a `libcity_ar.so` frame, that is a
  real, symbolizable, server-fixable bug — and ARM is the platform where it can finally be
  symbolized (debuggerd unwinds native ARM properly).
- **Device-side nuisance (not a game bug):** `STATUS.md:102` notes the Samsung
  auto-backgrounds the game ~every 30s via notifications. Mitigate with Do-Not-Disturb /
  a dedicated quiet device, or it will masquerade as instability.

---

## 5. Decision

Per the standing instruction ("the current evidence suggests Houdini may be the dominant
failure source… only continue symbolized tombstone work if ARM hardware is unavailable"):

- **ARM hardware is available in principle → halt emulator crash analysis.**
- The symbolized-tombstone-on-emulator effort is **deprioritized**; it cannot succeed
  anyway (Houdini stacks don't unwind into game code).
- Proceed to the ARM deployment path (§6 of the response). The only gate is physically
  connecting the device — no rebuild, the signed APK is ARM-ready.

### What the ARM test settles in one boot

1. Does the post-city Houdini crash vanish? (Expected: yes.)
2. Does estate/goods render cleanly, or produce a *symbolizable* `libcity_ar.so` crash?
   (This is the one remaining genuinely-server-fixable question, and ARM is the only place
   it can be answered with real symbols.)
