# PHASE 1 — In-Game Validation Attempt (2026-06-12)

Ran the game against the Phase 1 server on the **x86/Houdini emulator** (the only device
attached; no physical ARM device present). Honest outcome below.

## Setup
- Server: `SERVER_HOST=192.168.1.3 PYTHONIOENCODING=utf-8 python server.py` — all 3 ports
  serving (8080/9090/8992 verified via `/debug/probe`).
  - Note: the Arabic startup banner crashes the server under Windows `cp1252` console;
    **`PYTHONIOENCODING=utf-8` is required** to start it. (Code unchanged; runtime env only.)
- Device: `emulator-5554`, ABI **x86**, app installed, host reachable at `192.168.1.3`
  (matches the IP baked into `libcity_ar.so`).
- Fresh boot: `pm clear` + `logcat -c` + `am start`.

## What worked ✅
- **Server + Phase 1 code boots cleanly**; no 500s, no tracebacks.
- Game reached **LoadingMnger step 7** (title / server-select screen) and issued
  `PUT /checkversion → 200`. **No crash** (logcat clean).
- The boot path is **intact** with the Phase 1 changes (estate object-shape, player_state
  wiring did not break `/checkversion` or the load sequence).
- Input injection reaches **native UI**: a BACK key popped the "Quit Game?" dialog and a
  display-coord tap dismissed it — proving `adb` input works for system windows.

## Blocker ❌ (why full validation did not complete)
- The **GL game surface ignores synthetic `adb input tap`** on this emulator. Exhaustive
  attempts on the "ابدا" (Start) button failed to trigger `/api/connect`:
  - display coords (full vertical sweep x=270, y=380–520),
  - swapped/landscape coords (touch panel is 959×539; tried (440/480/515,270), (445,250/290)),
  - bottom-right login button.
  All produced **zero** `/api/connect`. Native dialogs respond in display coords; the GL
  view does not respond to injected taps at any coordinate.
- Consequence: the game **cannot be driven past server-select via automation** on this x86
  emulator, so the city / estate / inventory / job / crime screens could not be reached to
  capture their live requests.

This matches the project's established history: boot was previously validated by **manual
taps** in the emulator GUI, and the **ARM pivot** (`EMULATOR_VS_ARM_RISK_ASSESSMENT.md`,
`REAL_ARM_TEST_PLAN.md`) exists precisely because this x86/Houdini path is unreliable.

## Validation status by goal
| Goal | Status |
|------|--------|
| City loads | **Not reached** — stalled at server-select (Start tap not injectable) |
| Estate screen opens | Not reached (blocked by above) |
| Inventory screen opens | Not reached |
| Job screen works | Not reached |
| Crime screen works | Not reached |
| New endpoint requests captured | Only `/checkversion` (pre-login) — nothing new |
| Crashes captured | **None** (logcat clean through step 7) |

**Server-side Phase 1 remains fully validated** by `test_phase1.py` (24/24 against the real
request/response contract) — only the *in-game visual* pass is incomplete.

## To complete the validation (two paths)
1. **Manual taps (fastest):** the server is running at `192.168.1.3`. In the LDPlayer GUI,
   click "ابدا" (Start) → select Waker → let it boot to the city, then open Estate /
   Inventory / Job / Crime. Watch `analyze/logs/phase1_server_*.log` for the requests
   (`estate/listestates`, `goods/playerbags`, `job/work`, `crime/docrime`) and confirm no
   `0x756f707b` crash on the estate screen.
2. **Real ARM device (authoritative):** per `REAL_ARM_TEST_PLAN.md` — deploy the same APK,
   which both removes the Houdini variable and accepts normal input.

## Decision
Per the instruction ("only after a full gameplay validation pass should Phase 2 begin"),
**Phase 2 is NOT started** — the in-game validation did not complete. Phase 1 server code
is correct and tested; it needs a human tap (or ARM device) to confirm on-device.
