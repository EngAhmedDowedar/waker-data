# Final Inventory — Frozen at `freeze-2026-06-11-arm-pivot`

Snapshot of server state before the ARM-hardware pivot. No further server changes
until justified by physical-device logs. Source of truth: `local-server/python/server.py`
(SHA `4e3651d1…`).

---

## 1. Implemented Routes (specific handlers)

~60 specific routes across 3 Flask apps (game API 8080, city 9090 = same app, analytics 8992).

### 1a. Real / typed-data routes (drive the boot path)

| Route | Shape | Notes |
|-------|-------|-------|
| `/checkversion` | `{...}` full v6 | version, servers[], upgrade flags, lastLoginPlayer |
| `/api/connect` | `{login}` | `_login_success_payload()` — keepLiveServerHost |
| `/api/authplayerkey` | `{login}` | resume login, mirrors connect |
| `/api/getallserver` | `[server]` | **array directly** (ParseServerList iterates) |
| `/city/impart` | `{}` | config singleton; boot lookups fall back to bundled `.city` |
| `/city/connect/getplayerlist` | `[]` | empty = character-creation path |
| `/city/connect/connect` | `{CPlayer}` | `_make_player()` — drives HUD |
| `/city/connect/create` | `{CPlayer}` | same CPlayer shape |
| `/city/goods/getcitygoods` | `{goodsList:[]}` | typed empty array |
| `/city/goods/playerbags` | `{bags:[],goods:[]}` | |
| `/city/goods/playergoods` | `{goods:[]}` | |
| `/city/gym/getgym` | `{gymTypes:[],gymServiceDetails:[]}` | |

### 1b. Array-stub routes — `data:[]` (Class-A crash prevention, 27 routes)

These exist solely because their parser calls `begin()` (vtbl+0x14) and crashes on `{}`:

```
/city/connect/getplayerlist   /city/player/introplayers     /city/friend/getfriends
/city/player/getranking       /city/airline/airlines        /city/chat/getsysmsgs
/city/chat/gettopmsgs         /city/chat/getmsg             /race/car/getcars
/race/car/getstoreitems       /city/hospital/patients       /city/gang/randomgangs
/city/jail/prisonerlist       /city/event/list              /city/player/logingifts
/city/marital/candidates      /city/fight/randomfighters    /city/job/getjobs
/city/store/catelist          /city/showwindow/list         /city/skyscraper/list
/city/lottery/info            /city/lottery/prizes          /city/lottery/records
/city/mercenary/helpandbattle /city/mercenary/rank          /city/mercenary/ybclass
/city/hunt/store/list         /city/crossserverwar/joinlist /race/match/maplist
/race/match/dungeon/info      /race/match/record            /race/match/recorddesc
/city/deal/taobao             /city/chat/<path:cmd>
```

### 1c. Object-stub routes — `data:{}` (safe, null-guarded parsers)

```
/city/estate/buy        /city/mission/updatemission  /city/mission/getmission
/city/player/updatelevel /city/player/pause          /city/heartbeat
/game/maintenance/check  /city/job/work              /city/gym/train
/city/crime/docrime      /city/player/getplayerinfo
```

### 1d. Debug (plaintext, not ciphered): `/debug/history`, `/debug/probe`

---

## 2. Remaining Catch-All Routes (everything not above falls here)

| Catch-all | Returns | Risk |
|-----------|---------|------|
| `/city/chat/<path:cmd>` | `data:[]` | safe (chat parsers iterate arrays) |
| `/city/<path:cmd>` | `data:{}` | safe for null-guarded; **latent Class-A** for any unguarded array sub-parser (the `/city/deal/taobao` failure mode) |
| `/<path:path>` (root) | `data:{}` | logs `[API] UNHANDLED`; auth/misc |
| stat_app `/<path:path>` (8992) | `{result:0}` | analytics, ignored |

**~100 of the 161 mapped endpoints are served only by `/city/<path:cmd>` `data:{}`.**
Up to 88 of those touch MEDIUM-classified parsers (null-guarded, but the taobao case
proved guards don't cover every dispatch path).

---

## 3. Known Parser Mappings (verified, binary-grounded)

Full map: `ENDPOINT_DEPENDENCY_GRAPH.md` (161 endpoints) + `CRASH_CORRELATION_REPORT.md`.
Highest-confidence (disassembled) parser→shape facts:

| Parser | Addr | Pattern | Shape | Endpoint |
|--------|------|---------|-------|----------|
| `CServerMnger::ParseServerList` | 0x56eb4c | begin-iter | `[]` | `/api/getallserver` |
| `CServerMnger::ParseRoleList` | 0x56f19a | begin-iter | `[]` | `/city/connect/getplayerlist` |
| `CAirportScreen::ParseAirlines` | 0x324B04 | `42 69` +4 | `[]` | `/city/airline/airlines` |
| `CTopScreen::ParseSysMsg` | 0x59318C | `42 69` +4 | `[]` | `/city/chat/getsysmsgs` |
| `CRG_CarWarehouseScreen::ParseCarList` | 0x53084C | `42 69` +10 | `[]` | `/race/car/getcars` |
| `CRG_StoreScreen::ParseStoreRandomList` | 0x549DB8 | `4A 69` +22 | `[]` | `/race/car/getstoreitems` |
| `CFeedbackScreen::ParseChilds` | 0x3ea612 | begin-iter | `[]` | `/city/player/introplayers` |
| `CMarketCateScreen::ParseGoodsAmount` | 0x4c2fe8 | named field | `{goodsList}` | `/city/goods/getcitygoods` |
| `CEventBuyMonthCard::ParseEvent` | 0x3AC530 | `02 6C` (guarded) | `{}` | `/city/monthCard/enterMatchCard` |
| `CRaceCoreMnger::ParseAthleticsData` | 0x543AB4 | `03 6C` (guarded) | `{}` | `/race/match/matchconfig` |
| `CNewspaperScreen::ParseNews` | 0x503B6C | `02 6C` ×3 (guarded) | `{}` | `/city/news/frontpage` |
| `CDealMarketDetailScreen::ParseDetailTaobao` | 0x3837FE | begin-iter (unguarded path) | `[]` | `/city/deal/taobao` |

Classification totals (from FULL_GAME_ANALYSIS §3): 15 CRITICAL (all routed), 7 HIGH
(unverified), 88 MEDIUM (guarded), 57 LOW, 110 SAFE.

---

## 4. Unresolved Crashes (frozen state)

Detail: `COMPLETION_PLAN.md` §1, `EMULATOR_VS_ARM_RISK_ASSESSMENT.md`.

| # | Signature | Top frame | Class | Confidence | Server-fixable? |
|---|-----------|-----------|-------|-----------|-----------------|
| C1/C2/C4 | `libhoudini.so +0xbf750`, fault `0x0` | Houdini runtime | B-houdini | HIGH — recurs across 3 boots + frida-era | No |
| C3 | anon JIT, fault `0x657a697b` ("{ize") | translated game code | B-layout | MEDIUM — 1 capture, estate/goods | Maybe (field shape) |
| C5 | `0x891c2454`, stack all libhoudini/linker | Houdini/linker | B-houdini | MEDIUM — 1 capture | No |
| D1–D3 | `ParsePatient`/`GetRowCount`/`ParseAirlines` fault `0x0` | *inferred* | A (mitigated) | LOW — no on-disk stack; contradicted | n/a (already `data:[]`) |
| D-layout | `ngView::LayoutNode` `0x756f707b` | *inferred* | B-layout | LOW — likely same as C3 | Maybe |

**Class A: closed (all 32 known array endpoints routed).** **Class D (network): closed.**
**Class C (assets): no crash evidence.** Remaining live = two Class-B signatures, both
dominated by Houdini per the risk assessment.

**No crash in this inventory has a symbolized `libcity_ar.so` stack** — a structural
consequence of Houdini, and the reason the next evidence must come from ARM hardware.
