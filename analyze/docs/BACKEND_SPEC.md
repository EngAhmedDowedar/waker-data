# Waker — Backend Specification

Strategic specification of `com.anansimobile.city_ar`'s HTTP backend. The goal is to replace per-crash patching with a complete map of the territory so any remaining work is informed by the whole picture.

Companion files:
- **`BACKEND_SPEC_machine.md`** — auto-generated raw index (774 commands, 29 missions, 10,347 strings, every CXxxScreen parser method). Re-run `python analyze/tools/build_backend_spec.py` to refresh.
- `SCHEMAS.md` — the reversed JSON schemas for parsers we've handled.
- `STATUS.md` — current per-feature state.
- `RUN_SERVER.md` — operational guide.

---

## 1. Architecture (verified)

```
┌─ phone ──────────────────────────────────────┐         ┌─ local-server/python/server.py ──┐
│                                              │         │                                  │
│  libcity_ar.so (32-bit ARM/Thumb)            │         │  Flask app, bound 0.0.0.0:       │
│    ├─ NGHttpSession    ─────PUT body─────►   │         │    8080  /checkversion + /api/*  │
│    │     cipher: base64(XOR(json, KEY))      │         │    9090  /city/*  (same Flask)   │
│    │     XOR_KEY = LOTR verse @.rodata       │         │    8992  analytics (ignored)     │
│    │                                         │         │                                  │
│    ├─ ngHttpClient::HandleUpdate    ◄───base64(XOR)────┤  Required response root keys:    │
│    │     (response dispatcher, 0x5cfac8)     │         │    error="0", timestamp,         │
│    │                                         │         │    errorMessage, data            │
│    └─ CXxxScreen::OnReceiveResponse(cmd,obj) │         │    (injected by after_request)   │
│         /CXxxScreen::ParseXxx(obj)           │         │                                  │
│                                              │         │  Routes: 19 explicit + catch-all │
│  assets/                                     │         └──────────────────────────────────┘
│    *.city  (93 BE-binary catalogs)           │
│    ar | en | de | ...  (localization tables) │
│    (CLIENT-SIDE — server has no influence)   │
└──────────────────────────────────────────────┘
```

Wire protocol, envelope injection, and method-normalizer (PUT→POST) are all in `server.py`'s commented sections. Full provenance in [`reference-server-layout`](../../../.claude/projects/.../reference_server_layout.md) memory.

---

## 2. Command inventory — by status

774 unique command/field strings live in `.rodata` cluster `0x6fd000-0x6ff400`. Some are URL path segments (`/city/<cmd>`); the rest are JSON field names. The auto-generated `BACKEND_SPEC_machine.md` indexes them all and marks each with one of:

| Mark | Meaning                                                            | Count* |
|------|--------------------------------------------------------------------|-------:|
| `[OK]` | Explicitly handled by a server.py route with a verified-safe shape | 19    |
| `[CA]` | Falls through to a catch-all (`/city/<path:cmd>` → `data:{}`)      | ~750  |
| `[?]`  | Not even a catch-all match (some `/api/*`, `/<root>/*`)            | <10   |

\* approximate; many `[CA]` strings are field names, not commands.

The `[CA]` bucket is dangerously broad: each entry could be either (a) a safe no-op (the client never requests it during normal play, or the client tolerates `data:{}`), or (b) a route the client DOES hit and which crashes when handed `data:{}` because its parser expects a typed array/object. We've found ~6 of (b) so far: `getplayerlist` (needs `[]`), `getcitygoods` (needs `{goodsList:[]}`), `randomfighters` (array of CCitier), `estate/buy` (one CHouse), `introplayers` (`[]`), `gettopmsgs` (array of msg objects). The remaining `[CA]` commands have not been individually verified.

### Mapping each command to its parser

`libcity_ar.so` ships the **full unstripped C++ symbol table** (35,707 mangled names). For any command we want to support correctly, the parser address is one demangle away. The machine spec's "Parser classes" section lists every `CXxxScreen` / `CXxxMnger` / `CXxxManager` / `CXxxClient` and its `ParseXxx` / `OnReceiveResponse` methods — that's the call graph.

To recover a single endpoint's response shape from the binary:
1. Find the relevant parser method via `c++filt`-demangled symbol table.
2. Disassemble that method (capstone, Thumb-2 dominant).
3. Identify `add ip, pc, #X` PIC string loads — each loaded string is a JSON field name the parser reads (the PIC base is `0x75ab20`).
4. Identify the vtable slot used per field: `bl <offset>(vtable)` → vtable+0x14 = `begin()` (iterator) → array, vtable+0x4 = `GetNode(name)` → object key lookup, then sub-vtable+0xC = `GetInt`, +0x10 = `GetString`, +0x14 = `GetObject` (object ref!), +0x18 = `GetArray`.
5. The combination of (3) + (4) gives the JSON shape.

This is the workflow that produced the verified CPlayer / CHouse / CCitier / CGoods / CMission shapes. Anything else can be added to that list with the same process.

---

## 3. Client-side-only data paths (no server involvement)

These three big systems are populated by **bundled assets**, not server responses. The server can do *nothing* directly to fill them:

### 3a. Mascot bubble / mission text — VERIFIED 2026-05-30
```
CPlayer.missionId   →   assets/mission.city[id]   →   missionTip (u32 string id)
                                                       │
                                                       └──→  assets/ar[string id]   →   Arabic UTF-8
```
- `mission.city`: 29 entries (ids 1..23, 26-28, 30, 31, 35). Each = 14 BE32 fields. Field order: `id, tutorialId, missionName_strid, missionTip_strid, missionDesc_strid, missionType, tarProgress, rewardExp, rewardCheck, rewardGoodIdx, rewardGoodCate, rewardGoodAmount, branchOrMainCity, missionFinishText_strid`.
- `assets/ar`: 10,347-string localization table. Format: u16 BE count, then `[u16 BE len][utf-8 bytes]` × N. ID = ordinal index.
- Empirically: `missionId=1` → bubble shows "اوجد وظيفة مناسبة" ("Find a suitable job"). `missionId=100` → no entry → empty bubble.

### 3b. City catalogs (property/product/job/crime/etc.)
- 93 `*.city` files in `assets/`. Same big-endian format as `mission.city`. Looked up by `GetById(0x69341c)`.
- The server has NO copy of these. When CPlayer references `estateType:800` we know it's a valid id because we found 800 in `property.city` directly — not because the server "sent" it.

### 3c. UI strings (Arabic locale)
- `assets/ar` (full strings) + `assets/rlString-ar.bin` (a 27-string UI subset).
- The current Arabic name `'أهلاً بك في الوكر'` we put in CPlayer.signature is just a string — it overrides nothing in `ar`.

**Consequence**: to "populate world state" we change what the SERVER sends (the IDs and quantities), but the actual TEXT/sprites/icons come from these assets. A wrong id = null UI element. A right id = whatever the bundled asset says.

---

## 4. Where the gaps actually are

Three categories of unresolved unknowns, ranked by leverage:

### 4a. Untested catch-all commands (~750 entries)
For each `[CA]`-marked command, we don't know if it's hit during normal play or only on specific user actions, and whether `data:{}` is accepted. Resolution doesn't need Frida — the **server-side `protocol_dump.log` already records every request the client makes**. The remaining work is:

1. Boot the game into the main screen with several different CPlayer states (`missionId`=1, =23, =100; `playerStatus.status`=0/1/2; `vip`=0/1).
2. Drive each feature screen (job, gym, market, estate, gang…) by tapping in the UI.
3. Compare new requests in `protocol_dump.log` against the catch-all list; each new path is a previously-unobserved endpoint to add.

No new tooling needed — the runtime instrumentation is already in `server.py`.

### 4b. Confirmed-needed shapes that catch-all currently breaks
`getmsg`, `getoldmsg`, `getsysmsgs`, `randomgangs`, `playergoods`, `playerbags`, `playerequip`, `updatelevel`, `avatarinfo`, `airline/airlines`, `bank/checkbalance`, `monthCard/enterMatchCard`, `race/match/matchconfig`. The missionId=1 test (2026-05-30 17:17) confirmed each of these is requested during a mission-active boot and they currently get `data:{}` from the catch-all. **Static-only resolution path**:

1. For each name, locate the parser via the symbol table search above (`grep _Z.*<cmd>` or look at the demangled CXxxScreen list in the machine spec).
2. Read the field-name strings the parser loads.
3. Add an explicit server.py route that returns the right container shape with empty contents.

This is the workflow that already produced the verified-safe shapes for the 19 explicit routes. No Frida needed — but a Frida hook (4c) would short-circuit the disasm step.

### 4c. Unresolvable from static alone
True unknowns where we'd need runtime instrumentation:

- **Which command-name strings are URL paths vs. JSON field names.** Static analysis can't always tell — both live in the same `.rodata` cluster. Frida hook to disambiguate: log every call site that builds a URL.
- **The exact bytes the cipher emits vs. what the client decoded.** Server-side dump shows what we sent; only Frida can show what `ngHttpClient::ParseResponse` actually decoded (if the wire body got truncated or the cipher key changed, we'd see it here).
- **Which CPlayer fields trigger downstream UI crashes.** The 48-field experiment crashed the GLThread after `/city/player/updatelevel`. Static alone can't tell us which field was the culprit; Frida + a bisect can.
- **The active-mission cascade.** With `missionId=1` no crash occurred AND 4 new requests appeared (`bank/checkbalance`, `airline/airlines`, `monthCard/enterMatchCard`, `player/pause`) — those are the *next* shapes to reverse. Their parsers are in the symbol table; their response field names need extraction.

---

## 5. Frida hook recipes

Hooks should be installed all at once (the binary's symbols make this trivial — see `analyze/tools/frida_mascot_probe.js` for the working template). The blocker for using Frida on this device is operational, not technical:

**Blocker**: `frida-server` currently on the phone is **x86-built** (`ELF ... 386 ... Android 21`) — the phone is `armeabi-v7a`. Plus the device is non-rooted (`adbd cannot run as root in production builds`), so even the correct frida-server binary can't ptrace without root. The supported path is **frida-gadget** injected into the APK:

1. Download `frida-gadget-17.9.11-android-arm.so` (matches host frida 17.9.11).
2. Drop into `analyze/client-apk-src/lib/armeabi/` as `libfrida-gadget.so`.
3. Add `System.loadLibrary("frida-gadget")` to a Smali class run during app startup (e.g., `com.anansimobile.city_ar.Main` constructor or `Application.onCreate`).
4. Repack with `apktool b`, re-sign with `analyze/client-apk-src/uber-apk-signer.jar`.
5. Install → connect with `frida -U Gadget -l <script.js>`.

One-time setup, ~30 min. After that, every hook recipe below runs without root.

### Recipe A — "What URL is being requested?"
Hook the URL-builder symbol (find it via `c++filt`'d list, look for `BuildURL` / `MakeRequest` / a method on `ngHttpClient` that takes a `const char*` first arg). Log each call's URL string. **Resolves**: which `.rodata` strings are URL paths.

### Recipe B — "Which command response just decoded?"
Already drafted in `analyze/tools/frida_mascot_probe.js`. Hook `_ZN12ngHttpClient13ParseResponseExPv` + `_ZN15CMissionManager17OnReceiveResponseEiPv` + every `CXxxScreen::OnReceiveResponse(int, void*)`. Log the command id (first arg, BE32). **Resolves**: which parser handles which command (without disasm).

### Recipe C — "What field is THIS parser reading?"
Once a specific parser is identified by recipe B, hook the json-getter vtable methods (`GetInt`/`GetString`/`GetObject`/`GetArray` on the `ngJsonHash` object). Log the field name on each call from inside the target parser. **Resolves**: the exact response schema per endpoint, no manual disasm.

### Recipe D — "Which CPlayer field crashed the GLThread?"
Bisect: a Frida script that, on each `/city/connect/connect` response, NULLs out groups of fields in the decoded `ngJsonHash` before CPlayer::Parse runs. Run with progressively smaller groups until the crash is gone. **Resolves**: the un-verified-type-of-the-day question.

### Recipe E — "Where does each .rodata string get loaded?"
Static workaround: `analyze/tools/find_jni_call_sites.py` already does similar PC-relative cross-referencing for a different question. Adapt it to take a target `.rodata` offset and emit every `add ip, pc, #X` instruction in the binary that resolves to it. **Resolves**: which code paths use which strings — full xref for free.

---

## 6. Suggested path forward (not a plan — a frame)

Two independent tracks; either is well-defined enough to run without surprise:

**Track 1 — finish the static reversal of the missionId=1 cascade.**
The new endpoints exposed by the 2026-05-30 17:17 test (`bank/checkbalance`, `airline/airlines`, `monthCard/enterMatchCard`, `player/pause`, `chat/getsysmsgs`, `race/match/matchconfig`, `game/maintenance/check`) all have parsers in the symbol table. Reverse 1-2 per session using the workflow in §2. Each completed endpoint is one less crash surface for an active mission.

**Track 2 — set up frida-gadget (recipe at §5), then run Recipe C against every `[CA]` command** to get all 750 shapes in one or two boots. This is the "complete spec in one pass" play; expensive setup, very cheap per-endpoint after.

Track 2 is strictly better if the operational setup works. Track 1 is the fallback that has no new prerequisites.
