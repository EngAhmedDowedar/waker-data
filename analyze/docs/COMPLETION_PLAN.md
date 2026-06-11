# Waker — Full Project Completion Plan

Analysis-only report. No game runs, rebuilds, or patches were performed.
Generated 2026-06-11 from: `.dynsym` (36,881 sym), tombstones, crash reports,
endpoint/parser maps, FULL_GAME_ANALYSIS, ENDPOINT_DEPENDENCY_GRAPH,
IMPLEMENTATION_PRIORITY, server logs (`server_stderr_phase1.log`,
`session_requests_20260611.txt`), and `tombstone_phase1_classB.txt`.

---

## 0. Executive Summary

- The game **reliably boots to the city screen (step 13)** on the emulator with the
  current build + server, and processes all ~16 post-step-13 automatic requests.
- **Every known Class A crash (null array-iterator) is eliminated.** 32 endpoints that
  call `vtbl+0x14 begin()` on the response now receive `data:[]`.
- **One crash class remains live**, and the captured evidence shows it is **not** a
  game-parser bug. The faulting thread is 100% inside `libhoudini.so` (the x86→ARM
  translation layer) executing unmapped JIT code. This is an **emulator/translation
  fault (Class B-houdini)**, not a server-data fault.
- A **second, distinct rendering fault** (`ngView::LayoutNode`, fault addr `0x756f707b`)
  was seen earlier and is the only remaining candidate that is plausibly server-fixable
  (Class B-layout). It has **not** been captured in a tombstone with a game-symbol stack,
  so it is currently unproven.
- Net: the project is at the boundary between "boots reliably" and "stays up reliably."
  The shortest path to a stable demo is **not** more endpoints — it is **isolating which
  of the two Class B faults actually kills the session**, because they have opposite fixes
  (one is server-side data, one is emulator-side and may be unfixable without a real
  ARM device).

---

## 1. Complete Inventory of Unresolved Crashes

There are **two crash signatures still observed after Phase 1**, plus residual
*latent* risk. Class A is closed; the items below are everything not closed.

### Crash #1 — Houdini JIT translation fault (PRIMARY, captured)

| Field | Value |
|-------|-------|
| Tombstone | `analyze/logs/tombstone_phase1_classB.txt` |
| Signal | SIGSEGV, SEGV_MAPERR, fault addr `0x891c2454` |
| Thread | `GLThread 593` (tid 23307) |
| `eip` | `0x891c2454` — unmapped anon region (`[anon:Mem_0x10002002]` JIT code cache) |
| Backtrace | `#00 pc 891c2454 <unknown>`; stack frames are `libhoudini.so` + `linker (__dl_dl_iterate_phdr)` only |
| Game frames present? | **None.** No `libcity_ar.so`, no `Parse*`, no `LayoutNode` in the crashing stack |
| Class | **B-houdini** (translation/runtime, not game logic) |

Interpretation: the ARM→x86 JIT jumped to / read an address that is not mapped.
The "memory near ebx" dump shows ART/Houdini allocator strings ("object space
allocation", "rect tab", "found for"), i.e. translator internals, not game JSON.
This is the failure mode the project memory already flagged: *"x86 emu + Houdini
means native ARM is unreliable."* This crash is **not addressable from server.py.**

### Crash #2 — Layout/render fault (SECONDARY, uncaptured in this session)

| Field | Value |
|-------|-------|
| Source | `POST_STEP13_CRASH_ANALYSIS.md`, `IMPLEMENTATION_PRIORITY.md` Phase 3 |
| Signal | SIGSEGV, fault addr `0x756f707b` (ASCII "{pou"), also `0x657a697b` ("{ize") |
| Stack (reported) | `ngView::LayoutNode` → rendering/layout code |
| Trigger (reported) | estate / goods screen rendering |
| Game frames present? | Reported yes (`ngView::LayoutNode`) but **no tombstone with a full game stack is on disk** for this signature |
| Class | **B-layout** (render; ASCII fault addr ⇒ a string/JSON value used as a pointer) |

Interpretation: a fault address that is printable ASCII is the classic signature of a
**string field being dereferenced as a pointer** — i.e., a screen parser read a field
it expected to be a struct/array but got a string (or read past a short response). This
*is* plausibly server-fixable by returning correctly-shaped objects (not bare `data:[]`/
`data:{}`) for the estate/goods screens. But it is **unproven** until captured with a
game-symbol stack.

### Latent risk — undiscovered Class A edge cases (not yet a crash)

`/city/deal/taobao` proved that a parser classified MEDIUM ("null-guarded") can still
reach an array sub-parser on some dispatch paths and crash. The same misclassification
can hide in the **88 MEDIUM** classes. These are not *current* crashes (their screens
have not been opened), but each is a latent Class A waiting for navigation.

---

## 2. Crash Classification

| Class | Definition | Status | Count remaining |
|-------|-----------|--------|-----------------|
| **A** — parser/data shape | Parser calls `begin()` (vtbl+0x14) on response `data`; `{}` ⇒ null-iterator ⇒ SIGSEGV `0x0` | **CLOSED** for all 32 known endpoints | 0 confirmed; ~N latent in 88 MEDIUM classes |
| **B-layout** — render/layout | `ngView::LayoutNode` deref of ASCII-looking pointer; field-shape mismatch on estate/goods | **OPEN, unproven** | 1 signature |
| **B-houdini** — translation | JIT jumps to unmapped addr; stack entirely `libhoudini.so`/linker | **OPEN, likely environmental** | 1 signature (captured) |
| **C** — missing assets/resources | Required `.city` catalog or `assets/ar` string absent | **No confirmed crash** | 0 |
| **D** — network/protocol | Wrong host, cipher, loop, missing route | **CLOSED** | 0 |

Notes:
- **Class C** has not produced a crash. The `[ERROR][Impart] no data` message is benign
  (present in the May-29 known-good boot). The 93 `.city` binary catalogs are bundled in
  the APK and load from disk; no server dependency.
- **Class D** issues seen historically (`127.0.0.1` keepalive loop, `/checkversion` loop,
  cipher) are all resolved by `SERVER_HOST=192.168.1.3` and the existing routes. No
  protocol crash is currently open.

---

## 3. Per-Crash Detail

### Crash #1 (B-houdini)

| Attribute | Value |
|-----------|-------|
| Exact function | None in game code — fault is in `libhoudini.so` JIT cache (`<unknown>` @ `0x891c2454`) |
| Exact screen | Indeterminate; occurred on `GLThread` after city screen, post estate/goods activity |
| Endpoint involved | None directly; followed `/city/estate/listestates` + `/city/volunteer/list` in `server_stderr_phase1.log` (19:50:29) |
| Parser involved | None — no `Parse*` frame on the crashing stack |
| Required schema | N/A (not a data fault) |
| Current schema | N/A |
| Estimated fix | **Environment, not code.** Options: (a) test on a real ARMv7/ARM64 device to confirm it disappears; (b) try a different Houdini/emulator build; (c) accept as emulator flakiness. Server changes will not fix it. |

### Crash #2 (B-layout)

| Attribute | Value |
|-----------|-------|
| Exact function | `ngView::LayoutNode` (reported; address not captured on disk) |
| Exact screen | Estate (`CPropertyCateScreen`) and/or Goods (`CGoodsScreen` / `CGoodsModel::GetRowCount`) |
| Endpoint involved | `/city/estate/listestates` (route exists, returns `data:[]`), `/city/goods/getcitygoods` (returns `{goodsList:[]}`), `/city/goods/playerbags` (returns `{bags:[],goods:[]}`) |
| Parser involved | `CPropertyCateScreen::Parse`, `CGoodsModel::GetRowCount` (0x420F30) |
| Required schema | **Unknown — must be derived.** Empty containers parse without a *parser* crash but may leave the layout reading a field (price/name/icon id) that is absent, then using a string as a pointer. Likely needs ≥1 well-formed element with all fields the layout reads. |
| Current schema | `estate/listestates → data:[]`; `goods/getcitygoods → {goodsList:[]}`; `goods/playerbags → {bags:[],goods:[]}` |
| Estimated fix | Medium. Requires (a) capturing a game-symbol tombstone for `0x756f707b`, (b) disassembling `CGoodsModel::GetRowCount` / `CPropertyCateScreen::Parse` to list every field the layout reads, (c) returning one fully-populated element. **Do not guess fields** — verify each in `.rodata` first (per project rule "binary evidence > docs"). |

### Latent Class A (per MEDIUM class)

| Attribute | Value |
|-----------|-------|
| Exact function | `<Class>::OnReceiveResponse` → array sub-parser (e.g. `ParseDetailTaobao` model) |
| Exact screen | Any of the 88 MEDIUM classes when first opened |
| Endpoint | Class-specific, often **not** name-matching the class (taobao lesson) |
| Required schema | `data:[]` on the path that reaches the sub-parser |
| Current schema | Catch-all `data:{}` |
| Estimated fix | 1 route each, 1 min, **but only discoverable by opening the screen** (runtime) or by disassembling each `OnReceiveResponse` dispatch (binary). |

---

## 4. Final Roadmap

### 4a. Fixes applicable immediately (no binary, no runtime) — LOW value now

These are pure server edits, but they address **latent** risk only (no current crash):

- Convert the two catch-alls to a smarter default that inspects nothing but is paired
  with explicit `data:[]` routes as MEDIUM classes are confirmed. (Mechanical, but
  premature — see §6 shortest path.)
- Add `data:[]` stubs for the remaining unimplemented array endpoints from the
  dependency graph that are *not yet* routed but are known array-iterators in §3a of
  FULL_GAME_ANALYSIS (all 15 of those are already added in Phase 1; nothing outstanding).

**Conclusion: there is no immediately-applicable fix that resolves a *current* crash.**
Both open crashes need diagnosis first.

### 4b. Fixes requiring binary analysis

1. **Disassemble `CGoodsModel::GetRowCount` (0x420F30) and `CPropertyCateScreen::Parse`**
   to enumerate exactly which `data` fields the layout path reads. Output: the minimal
   well-formed element schema for estate/goods. (Targets Crash #2.)
2. **Verify the 6 HIGH-risk parsers** (`ParseBattleStatistics`, `ParseChilds`,
   `ParseList`@Helper, `ParseGoodsAmount`, `Parse`@NationalBid, `ParseCircle`) for the
   `42 69 / 4A 69` begin-iterator pattern, to pre-empt their Class A risk before their
   screens are opened. (Targets latent Class A.)
3. **Spot-check the 88 MEDIUM `OnReceiveResponse` dispatchers** for unguarded paths to
   array sub-parsers (the taobao failure mode). Prioritize classes whose screens are
   reachable from the city HUD.

### 4c. Fixes requiring runtime validation

1. **Capture a game-symbol tombstone for the `0x756f707b` layout fault.** Until this
   exists, Crash #2 is unproven and its fix is a guess. (One isolated boot, navigate to
   estate, pull `/data/tombstones`.)
2. **Confirm whether Crash #1 (Houdini) reproduces on a real ARM device.** This is the
   single highest-information test in the project: it tells you whether the remaining
   instability is your data or the emulator.
3. **Per-screen navigation sweep** to surface latent Class A endpoints the way
   `/city/deal/taobao` was found.

---

## 5. Estimates

### Percentage of game currently working

Measured by *reachable-without-crash*, not by feature completeness:

| Layer | State | Weight |
|-------|-------|--------|
| Boot → city screen (steps 1–13) | Works reliably | ✅ |
| Post-step-13 auto requests (~16) | All served, no Class A crash | ✅ |
| City HUD render | Reaches render; intermittently killed by Class B | ⚠️ |
| Navigable sub-screens (~90 systems) | Stubbed; open-without-crash unverified per screen | ❔ |
| Actual gameplay (estate/job/crime/etc.) | Empty stubs, no real data | ❌ |

- **Boot + session-reach: ~95% working** (gets to the city screen essentially every boot).
- **Session stability: ~50%** (one of two Class B faults ends the session post-city).
- **Feature/gameplay completeness: ~10–15%** (43→~60 routes implemented of 161 mapped;
  almost all are empty stubs, not real game logic).
- **Headline figure: the game "works" to the city screen ~95% of boots, but only stays
  alive long enough to be a stable demo ~50% of the time**, gated entirely by the two
  Class B faults.

### Remaining endpoints

| Metric | Count |
|--------|-------|
| Total endpoints mapped | 161 |
| Specific routes implemented (post-Phase 1) | ~60 |
| Array-stub (`data:[]`) routes | 27 |
| Still served only by catch-all | ~100 |
| Of those, **MEDIUM latent-risk** | up to 88 classes |
| Of those, needing **real data** for gameplay | ~15 (estate, goods, job, school, crime, mission…) |

### Remaining crash classes

| Class | Open? |
|-------|-------|
| A (parser/data) | Closed (latent only) |
| B-layout (render) | **Open, unproven** |
| B-houdini (translation) | **Open, likely environmental** |
| C (assets) | Not open |
| D (network) | Closed |

**Two open signatures, both Class B, with opposite fixes.**

### Shortest path to a stable demo build

The bottleneck is **not** route count. It is identifying which Class B fault actually
kills the demo. Minimal critical path:

1. **One isolated boot to capture a real tombstone for the post-city crash** with a
   game-symbol stack (runtime). Decides whether you are fighting Crash #1 or Crash #2.
2. **If the stack is `libhoudini` (Crash #1):** the demo will never be stable on this
   emulator. Pivot the demo to a **real ARM device** — likely the single highest-leverage
   action in the whole project. No server work needed.
3. **If the stack is `ngView::LayoutNode` (Crash #2):** disassemble
   `CGoodsModel::GetRowCount` + `CPropertyCateScreen::Parse`, return one fully-populated
   estate and goods element (binary analysis + one server edit), re-test.
4. **Freeze scope at "boot → city → idle HUD without crash."** Do **not** implement the
   ~100 remaining endpoints for a demo; they are not on the city screen's auto-request
   path and only add latent surface.

Estimated effort to a stable demo:
- If Crash #1 dominates: **~1 device-swap test** (hours), no code.
- If Crash #2 dominates: **~1 day** (capture + 2 function disassembly + 1 schema + retest).
- The two are mutually exclusive on the critical path; step 1 tells you which.

---

## 6. Recommended Next Action (analysis verdict)

Run **exactly one** isolated boot whose only purpose is to pull the post-city tombstone
with symbols (`adb pull /data/tombstones`, then `ndk-stack`/addr2line against
`libcity_ar.so`). That single artifact collapses the decision tree: it tells you whether
the remaining instability is **your JSON** (fixable, ~1 day) or **the emulator's ARM
translation** (not fixable in server code; needs real hardware). Every other task —
implementing the ~100 catch-all endpoints, populating gameplay data, sweeping MEDIUM
classes — is lower priority than resolving that one fork, because all of them are wasted
effort if the session-ending fault is Houdini.
