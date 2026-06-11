# Player-data push — round notes (2026-05-30)

Goal: move from "game launches" to "game state is correctly reconstructed."

## What was reversed

Pulled the full **/city/\*** command-name table from `libcity_ar.so` (.rodata cluster `0x6fd000-0x6ff800`, 847 strings). That gives the authoritative endpoint inventory — the binary's literal list of every backend command the client can invoke.

Confirmed that:

- **All currently-handled endpoints are real**: `connect`, `create`, `impart`, `getplayerlist`, `gettopmsgs`, `getsysmsgs`, `getmsg`, `randomfighters`, `randomgangs`, `introplayers`, `listestates`, `buy`, `getcitygoods`, `heartbeat`, `enterMatchCard`, `matchconfig`, `getallserver`, `authplayerkey` — every one is in the table.
- **The agent-claimed offsets** (`@0x000b01ae` etc.) for mascot/NPC dialog **were wrong** — that addressing range doesn't match this .so. Discarded.
- **Mascot/NPC dialog text source — not statically determinable.** The chat-msg fields cluster at `0x6fd3e5..0x6fd441` (`messageKey`, `messageType`, `senderName`, `threadId`, `receiverKey`/`receiverUid`) which is the most likely candidate, but the exact route that powers the bottom-of-screen mascot bubble can't be pinned without dynamic analysis (Frida log of HTTP requests while the bubble is on screen). The "introUid" string at `0x6fd205` sits in the auth cluster — it's a parameter the client SENDS at completeinfo, not a server-returned field, so populating `/city/player/introplayers` won't surface the mascot.
- **World-state walkers / building owners** beyond what's served today: not in the table as a single endpoint. The map's walking NPCs are most likely rendered from `randomfighters`+`introplayers` combined with mission/quest data, not a separate `/city/npc/*` call (no such string in the table).

## What was diffed

`_make_player()` previously returned **68 of 168** CPlayer fields. Bucketed gap:

| Bucket | Missing count | Boot-critical? |
|---|---:|---|
| identity/profile (maritalRegistered, spouse, liveEstate, htPlayer, …) | 9 | ⚠ types unverified |
| tutorial/mission/dialog (messages, playerEvent\*Flag, dailyTask, …) | 20 | ⚠ types unverified |
| world/social (gang, gangMember, force, titleList, cityOccupy, …) | 23 | ⚠ types unverified |
| counters/stats (jailHalved, flightTimes, drugAddictionTreatMoney, …) | 7 | safe scalars |
| connectivity (holdem\*, keepLiveServer\*) | 9 | already in login payload |
| feature-specific (auctions, gym, dungeon, mercenary, …) | 32 | not boot-critical |
| other (liveEstateObj — already present as object) | 1 | — |

## What was patched and verified

**Stable diff applied to `_make_player()`** (verified on Samsung RK8W103BVET — full boot sequence `/checkversion → /api/connect → /city/impart → /city/connect/{getplayerlist, create, connect} → /city/chat/getsysmsgs → /city/monthCard/enterMatchCard → /race/match/matchconfig`, no crashes for 25s+, game's `.Main` activity foreground):

- `name`: `'Player'` → `'Abu Hassan'` (Arabic-locale matches game's locale; surfaces in HUD, friend lists, NPC dialog templates).
- `signature`: `'Welcome to Waker'` → `'أهلاً بك في الوكر'` (Arabic).
- `/city/chat/gettopmsgs` roster: 3 generic English messages → 5 in-character Arabic messages (mix of النظام / الزعيم), giving the ticker texture.

That's all that landed. The bigger additive patch (48 more "safe-scalar" CPlayer fields + bumped level/exp/currencies) crashed the GLThread at the very next request `/city/player/updatelevel` after `/city/connect/connect`. Reverted.

## Regression note — why the wider patch crashed

SCHEMAS.md lists the 168 CPlayer field NAMES but not their parser TYPES. CPlayer::Parse @0x5140bc accepts the JSON, but several name-list entries are actually **object references** read by `GetObject` (e.g. `liveEstate` is almost certainly a CHouse ref mirroring `liveEstateObj`), and the downstream render thread null-derefs when handed an `int` where it expects an object pointer. Same risk applies to `spouse`, `force`/`forceType`, `playerEventFlag`/`playerEventValue`/`playerPendingFlag`, `hasGangBattle`, `gangBossFlag`, `tradeFlag` — any of these could be the killer; no single-variable bisect was done because the test device is unreliable (WhatsApp interrupts ~every 3 min). Recorded as memory entry `feedback-cplayer-field-types-unverified`.

The cheap correctness rule: **before adding any new CPlayer field, find its read in CPlayer::Parse (0x5140bc onward) and check the vtable slot used** (`GetInt`/`GetString`/`GetObject`/`GetArray`). Schema NAMES verify the field exists; they do NOT verify its container type.

## Next missing endpoints — ranked

1. **`/city/chat/getmsg`** with `{msgs:[...]}` shape (per STATUS.md suspicion). Strong candidate to be the mascot bubble's actual source. Currently falls through to `/city/chat/<cmd>` catch-all returning `data:[]`. Verify by Frida-hooking `CChatScreen::ParseSysMsg`/`ParseMsg` and watching what's read out of the response on the mascot bubble's frame.
2. **`/city/player/updatelevel`** — handler today is the root catch-all. Triggered when CPlayer level/exp implies a level-up vs. cached state. Needs a proper response (the level-up cascade) before any level/exp values can move from the baseline.
3. **`/city/player/atHome`** (string at `0x6fd2dc`) — currently catch-all. Plausibly a server-side "player is home" tick that gates some HUD widgets.
4. **`/city/player/avatarinfo`** (string at `0x6fd843`) — avatar metadata. Catch-all today; avatar render currently uses `avatarAt > 0` to suppress the photo-picker but the actual avatar texture comes from this call.
5. **The mission chain** when `missionId != 100` — `/city/chat/getmsg` + `/city/fight/randomfighters` + `/city/gang/randomgangs` + likely `/city/player/inMission` (string at `0x6fd9f3`). Cluster all together for active-mission rendering. STATUS.md blocker #1.

## What dynamic analysis would unblock

Static analysis alone cannot answer: which endpoint feeds the mascot bubble, what the active-mission cascade actually crashes on, what shape `/city/player/updatelevel` needs. A Frida script that hooks `ngHttpClient::HandleUpdate` and prints `(method, path, response body)` plus the active screen at the time would close these gaps in one boot. Per memory, native ARM Frida is unreliable under Houdini on this stack; but the real Samsung is ARM, so a normal Frida-server attach should work — the open task.
