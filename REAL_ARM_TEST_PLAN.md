# Real ARM Device Test Plan

The next evidence source. Goal: determine on physical ARM hardware whether the post-city
crash is Houdini-only (expected to vanish) and whether the estate/goods render path
produces a **symbolizable `libcity_ar.so`** crash (the one remaining server-fixable
question). Frozen baseline: `freeze-2026-06-11-arm-pivot`.

> Rule: do not add or change server routes based on emulator data. Any endpoint work
> after this must be justified by ARM logs captured below.

---

## 0. Prerequisites

| Item | Requirement |
|------|-------------|
| Device | Physical ARM phone, `armeabi-v7a` or `arm64` (e.g. Samsung RK8W103BVET). **Not** the x86 emulator. |
| Build | `client/waker-patched-signed.apk` (SHA `1bf9af28…`). **No rebuild** — already ARMv7. |
| Network | Phone + PC on same LAN. PC reachable at **`192.168.1.3`** (the IP baked into `libcity_ar.so`). |
| Server | `local-server/python/server.py` running with `SERVER_HOST=192.168.1.3`, ports 8080/9090/8992 open in the PC firewall. |
| Device hygiene | Do-Not-Disturb ON, remove chat/notification apps if possible (Samsung auto-backgrounds the game ~30s otherwise — `STATUS.md:102`). |

---

## 1. Deployment Steps

```bash
# 1.1 Confirm a real ARM device is attached (ABI must NOT be x86)
adb devices -l
adb -s <serial> shell getprop ro.product.cpu.abi      # expect armeabi-v7a / arm64-v8a

# 1.2 Verify the artifact matches the freeze
sha256sum client/waker-patched-signed.apk             # expect 1bf9af28...

# 1.3 Start the server on the PC (separate terminal)
#     Ensure SERVER_HOST=192.168.1.3 in server.py / env
python local-server/python/server.py
#     From the phone, confirm reachability (browser or curl):
#       http://192.168.1.3:8080/debug/probe  -> {"next_variant":6}

# 1.4 Clean install (fresh data avoids the stale-bulletin popup)
adb -s <serial> uninstall com.anansimobile.city_ar 2>/dev/null
adb -s <serial> install -r client/waker-patched-signed.apk
```

---

## 2. Capture Steps

```bash
# 2.1 Clear + start logcat capture BEFORE launch
adb -s <serial> logcat -c
adb -s <serial> logcat -v threadtime > analyze/logs/arm_logcat_20260611.log &

# 2.2 (Optional, if rooted) live tombstone watch
adb -s <serial> shell "ls -t /data/tombstones" > /dev/null

# 2.3 Launch
adb -s <serial> shell am start -n com.anansimobile.city_ar/.Main

# 2.4 Drive the UI manually (see §4 estate/goods path), ~2–3 min

# 2.5 On any crash OR after the run, pull artifacts
adb -s <serial> pull /data/tombstones analyze/logs/arm_tombstones/   # needs root; else use logcat F DEBUG block
#     Keep the PC-side server log:
cp <server stdout/stderr> analyze/logs/arm_server_20260611.log

# 2.6 If a native crash appears, symbolize it (ARM unwinds properly):
#     ndk-stack -sym <dir with libcity_ar.so + symbols> -dump analyze/logs/arm_logcat_20260611.log
#     or: addr2line -f -e analyze/installed_libcity_ar.so <pc-offset>
```

### Artifacts to collect (the three required)
1. `analyze/logs/arm_logcat_20260611.log` — full threadtime logcat
2. `analyze/logs/arm_server_20260611.log` — server request log (which endpoints fired)
3. `analyze/logs/arm_tombstones/` — any `/data/tombstones/tombstone_*` (or the inline `F DEBUG` block from logcat if unrooted)

---

## 3. Expected Success Criteria

| Level | Criterion | Meaning |
|-------|-----------|---------|
| **Boot** | Reaches city screen (step 13), buildings render | Matches emulator baseline |
| **Stability (primary)** | Stays foreground **>60s** past city load with no SIGSEGV | **Houdini hypothesis confirmed** — C1/C2/C4/C5 were emulator-only |
| **Endpoint parity** | Server log shows the same post-step-13 sequence (`getsysmsgs → monthCard → matchconfig → … → airline/airlines`) served 200 | Confirms ARM exercises the same paths the emulator crashed on |
| **Estate/goods (decisive)** | Navigates into Estate and Goods screens without crash | **C3/layout was a Houdini artifact** — nothing more to fix for a demo |
| **Estate/goods crash w/ symbols** | If it crashes, tombstone has a `libcity_ar.so` frame | **Real, server-fixable bug isolated** — now actionable with an offset |

### Decision matrix from results

| Boot? | Stays up >60s? | Estate/goods? | Verdict |
|-------|----------------|---------------|---------|
| ✅ | ✅ | ✅ | **Stable demo achieved.** Freeze scope; no endpoint work needed. |
| ✅ | ✅ | ❌ w/ `libcity_ar.so` frame | One real bug. Disassemble that offset, fix the response shape, retest. |
| ✅ | ❌ w/ `libhoudini` frame | — | Crash is ARM-side too → escalate (different device/OS), not server. |
| ✅ | ❌ w/ `libcity_ar.so` frame | — | Genuine game-data fault survived; symbolize and fix. |
| ❌ | — | — | Network/host issue → re-check `SERVER_HOST=192.168.1.3` reachability. |

---

## 4. Estate / Goods Validation Path

This is the **decisive navigation** — the only post-city path with an unresolved
(C3 / `ngView::LayoutNode`) signature. The emulator crashed here; ARM must exercise it.

```
City screen (step 13)
  └─ Tap GOODS / inventory building
       → fires /city/goods/getcitygoods  ({goodsList:[]})
       → fires /city/goods/playerbags    ({bags:[],goods:[]})
       → CGoodsModel::GetRowCount (0x420F30) renders the list
       ► WATCH FOR: fault 0x657a697b / 0x756f707b (ASCII addr) in GLThread
  └─ Back to city, tap ESTATE / property building
       → fires /city/estate/listestates  (data:[])
       → CPropertyCateScreen::Parse renders categories
       ► WATCH FOR: same ASCII-addr layout fault
```

### What each outcome means
- **Renders fine on ARM** → C3 was Houdini mistranslation; the empty `[]`/`{}` shapes are
  adequate for a demo. Stop here.
- **Crashes with a `libcity_ar.so` frame** → the layout reads a field the empty response
  omits (price/name/icon id used as a pointer). Fix = return **one fully-populated**
  estate + goods element with every field the layout path reads (verify each field in
  `.rodata` first — do not guess). This is the single justified server change, and only
  after ARM logs prove it.

### Minimal data to try IF (and only if) ARM proves a real estate/goods bug
Hold until ARM logs justify it. Candidate (to be field-verified against the disassembly):
```
/city/goods/getcitygoods → {goodsList:[{id:<valid .city id>, name:"", price:1, num:1, icon:0}]}
/city/estate/listestates → [{id:<valid .city id>, type:1, price:1000, name:"", level:1}]
```

---

## 5. Post-Test

- Commit ARM logs to a new branch off the freeze tag (do not reopen emulator work).
- If stable: write `ARM_BASELINE.md`, declare the demo milestone.
- If a real bug: open exactly one targeted fix, justified by the ARM tombstone offset.
