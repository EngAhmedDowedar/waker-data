# STATUS.md — Current state of the Waker revival

_Last updated: 2026-06-10._ Reproduce with **RUN_SERVER.md** (clean state + `SERVER_HOST=<your-host>`).

---

## ✅ Fully working

- **Wire protocol**: base64( XOR(json, key) ) cipher (symmetric, key embedded in code); response
  envelope auto-injection (`error="0"`, `timestamp`, `errorMessage`, `data`). On 8080 and 9090.
- **Cold boot → main city screen** via the direct-login path, reliably, from a cleared state.
- **Player HUD** populated from a complete `CPlayer`: name, level (20), gold (100000),
  money (5,000,000), cheque, merits; **resource bars show current/max** (the `*Up` fields are the
  max — energy/blood/happy/brave 100/100); base stats (str/end/spd/agi).
- **gettopmsgs flood** that crash-looped the game at world-load — eliminated (native 1-byte patch).
- **Firebase/GCM bypass** (2026-06-10): disabled all legacy notification services and stubbed
  `FirebaseInitProvider.onCreate()`, `FCMInstanceIDService.onTokenRefresh()`, and
  `FCMMessagingService.onMessageReceived()` in smali. Fixes ANR: "executing service
  FCMInstanceIDService" that blocked startup trying to reach dead Firebase servers.
- **New-player tutorial tour** (job→gym→market, which crashed those screens) — disabled via
  `newPlayer:0`, so the game lands on the city view instead.
- **Networking**: binds `0.0.0.0`, reachable across the LAN; avatar photo-picker dialog suppressed
  (`avatarAt>0`).

## 🟡 Partially working

- **Main city screen** is stable and rendered **only with NO active mission** (missionId kept past
  the 29 `mission.city` entries). The city, HUD, building labels, and bottom nav render.
- **Estate**: `CHouse` parses from a valid object (`estateType:800` = a real `property.city` id);
  `listestates`/`buy` no longer crash. Deeper estate-screen interaction not exercised.
- **Random fighters**: schema reversed (`/city/fight/randomfighters` = array of `CCitier`
  players); a valid sample is served — but the full fight-mission flow isn't reachable (below).
- **missionId=1 flow** (2026-06-10): mission-chain endpoints added (see below). Needs on-device
  verification — `missionId` is set to 1 in `_make_player()`, the mascot bubble should show
  "اوجد وظيفة مناسبة" ("Find a suitable job"). **Untested on device.**

## 🔌 Mission-chain endpoints added (2026-06-10)

The following dedicated routes were added to `server.py` to replace catch-all `data:{}` responses
that crash array-iterating parsers when a mission is active:

| Endpoint | Fix | Reason |
|----------|-----|--------|
| `/city/gang/randomgangs` | `data:[{gang obj}]` (array) | Iterator null-deref on `{}` — same pattern as `randomfighters` |
| `/city/mission/updatemission` | `data: CPlayer` | Mission progress update returns full player |
| `/city/mission/getmission` | `data: {missionId, ...}` | Mission state fetch |
| `/city/player/updatelevel` | `data: CPlayer` | Level-up — was crashing on catch-all |
| `/city/player/pause` | `data: {}` | Pause/resume ack |
| `/city/heartbeat` | `data: {time}` | Periodic keepalive |
| `/game/maintenance/check` | `data: {maintenance:false}` | Maintenance-mode gate |
| `/city/job/getjobs` | `data: [{job}, ...]` (array) | Mission 1 = "find a job" — job screen |
| `/city/job/work` | `data: CPlayer` | Start working |
| `/city/gym/getgym` | `data: {gymTypes:[], ...}` | Gym screen data |
| `/city/gym/train` | `data: CPlayer` | Gym training |
| `/city/crime/docrime` | `data: CPlayer` | Crime action |
| `/city/player/getplayerinfo` | `data: CPlayer` | Player info fetch |
| `/city/friend/getfriends` | `data: []` (array) | Friends list |
| `/city/player/getranking` | `data: []` (array) | Rankings |
| `/city/goods/playerbags` | `data: {bags:[], goods:[]}` | Inventory |
| `/city/goods/playergoods` | `data: {goods:[]}` | Goods list |

Total route count: **34** (was 18).

## 🔌 Still stubbed (return empty/minimal, accepted at boot)

- `/city/impart` → `data:{}` — the 201-key game config is **not** populated (core lookups still
  work because the client loads `*.city` configs from its own assets; server-side config is empty).
- `/city/chat/*` (`getsysmsgs`, `getmsg`, `gettopmsgs`) → minimal data / empty arrays.
- `/city/goods/getcitygoods` → `{goodsList:[]}` (no goods); inventory `goods`/`bags`/`estates` empty.
- `/city/gang/randomgangs` and most other `/city/<cmd>` → catch-all `data:{}`.

## 🟢 Known-good endpoints (verified to advance the boot without crashing)

`/checkversion` (variant 6) · `/api/connect` · `/api/authplayerkey` · `/api/getallserver` ·
`/city/impart` · `/city/connect/getplayerlist` · `/city/connect/create` ·
`/city/connect/connect` (drives the HUD) · `/city/player/introplayers` ·
`/city/estate/listestates` · `/city/estate/buy` · `/city/goods/getcitygoods` ·
`/city/chat/getsysmsgs` · `/city/monthCard/enterMatchCard` · `/race/match/matchconfig` ·
`/game/maintenance/check` · `/city/heartbeat` · `/city/player/pause`

## ❓ Suspected incomplete

- `/city/chat/getmsg` — serves a basic message object; may need mission-specific content.
- `/city/gang/randomgangs` — now serves a gang array; untested on device.
- `/city/job/getjobs` — serves 2 jobs; job field schema is speculative (not verified from binary).
- `/city/impart` — empty config may break feature screens that read server-config (vs bundled .city).
- All catch-all `/city/<cmd>` (auctions, gym detail, goods/playerbags deeper, player/updatelevel…) —
  accepted during boot but their dedicated screens are unverified (likely need real data to render).

## ⛔ Remaining blockers to a fully playable build

1. **Mission flow untested on device.** `missionId=1` is set, 17 mission-chain endpoints added,
   Firebase ANR bypassed — but the actual device boot with an active mission has not been verified.
   The protocol dump from the next boot will reveal which endpoints still crash.
   **This is the next test to run.**
2. **Resume / server-selection path** stalls at "step 10" (keepalive connect — likely the
   binary/RC4 keepalive channel, unimplemented). Worked around by clearing device state to force the
   direct-login path on every launch.
3. **Per-feature data buildout.** Opening individual feature screens (market goods, inventory,
   auctions, gym, jobs, estate detail) needs realistic, config-matching data referencing valid
   `.city` ids, or they null-deref on render — a per-screen effort.
4. **Test-device instability.** The Samsung used for testing auto-backgrounds the game (~every 30s
   via notifications), crashing/reloading it; clean end-to-end verification needs a quiet/dedicated
   device (Do-Not-Disturb, no chat apps).

### Next concrete task

**Boot the game on-device with `missionId=1` and capture `protocol_dump.log`.** Then:
1. Check for any `[API] UNHANDLED` lines in the server console — those are endpoints hitting
   the catch-all that may need dedicated routes.
2. If the game crashes, check logcat for the crash address and correlate with the last request
   in the protocol dump — that's the endpoint whose response shape is wrong.
3. Fix the crashing endpoint (usually: change `data:{}` to `data:[]` or vice versa, or add
   required sub-fields), restart server, re-test.
4. Repeat until the mission-1 tutorial flow ("find a job") completes and the mascot advances
   to mission 2.

### Suggested follow-up after missions work
- Build out `/city/impart` from the extracted 201-key schema (`analyze/docs/SCHEMAS.md`).
- Iterate feature screens one at a time using the parser schemas in `analyze/docs/SCHEMAS.md`.
- Implement the binary/RC4 keepalive on port 9090 to fix the resume path.
