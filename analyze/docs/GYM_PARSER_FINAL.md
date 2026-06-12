# GYM_PARSER_FINAL.md — Verified Gym Subsystem Contract

Binary-verified (libcity_ar.so v1.1.38), same targeted workflow as `JOB_PARSER_FINAL.md`.
No rescans: used the captured disassembly of the gym functions and resolved PIC string
keys deterministically against base `0x75ab20`. Vtable byte-offsets: `+0x08`=iter hasNext,
`+0x0c`=iter next/count, `+0x10`=IntValue, `+0x14`=begin-iterator (array), `+0x40`=
GetObjectItem(key). Int64 read helper: `0x6933ec`/`0x69300c`.

---

## A. Headline answer (for the "enable SERVE_ASSET_DATA for gym_service" question)

**Do NOT enable asset serving for `gym_service`.** No gym endpoint returns the
`gym_service` / `gym_type` / `gym_service_cost` / `gym_item` catalog. Those tables are
**client-local** (loaded by `CGameData::LoadGymService/LoadGymType/LoadGymServiceCost/
LoadGymItem`) and optionally mirrored by the impart config (`gymTypes`,
`gymServiceDetails` are `CImpart` keys). The gym **response parsers read PLAYER STATE
only** (attributes, opened gyms, services-in-use) — never catalog rows. Pushing
`gym_service.city` rows through `getgym` would be wrong-shaped (the parser would ignore
every key — see §D).

---

## B. Symbols (verified, targeted lookup — not a rescan)

| Symbol | Addr | Role |
|--------|------|------|
| `CGymScreen::OnReceiveResponse(int,void*)` | 0x42d664 | command dispatcher |
| `CGymScreen::ParseResponse(void*)` | 0x42d340 | gym-info / exercise result parser |
| `CGymScreen::ParseEnterGymInfo(void*)` | 0x42bbc8 | enter-gym state parser |
| `CGameData::LoadGymType/Service/ServiceCost/Item` | — | **local** `.city` catalog loaders |
| `CImpart::ParseGymType/ParseGymService/ParseGymServiceCost` | — | gym catalog from impart config (not a gym endpoint) |

No `CPlayer` gym-specific parser exists (the attribute fields are parsed by the generic
`CPlayer::Parse`). Binary strings: `getgym`, `gym/getgym`, `enterGym` = **absent**;
`gymTypes`, `gymServiceDetails`, `gymType`, `serviceId`, `gymId`, `curUseGym` = present.

---

## C. Response trace — every JSON key accessed

### `OnReceiveResponse(cmd, data)` @0x42d664
Dispatches on `cmd`; the debug strings name the actions:
| cmd | branch | label string |
|-----|--------|--------------|
| 251 (0xfb) | exercise result | `"Excercise"` / `"recv excercise response"` |
| 252 (0xfc) | exercise (variant) | — |
| 601 (0x259) | open gym | `"open_gym"` |
| 602 (0x25a) | join gym | `"join_gym"` |
All are **actions**. Data parsing is delegated to the registered parsers below.

### `CGymScreen::ParseResponse(data)` @0x42d340  (gym-info / exercise result)
Reads `data` as an **OBJECT**; 9 `GetObjectItem(+0x40)` calls, each → GetInt64 if present
(null-guarded: missing key leaves 0). **No array iteration.** Verified keys (all scalar):

```
basicStrength  basicAgile  basicEndurance  basicSpeed
strength       agile       endurance       speed
gymLevel
```

These are **CPlayer attribute fields** — i.e. the response returns the player's updated
attributes after training. Container: **object**. Every field optional/null-guarded.

### `CGymScreen::ParseEnterGymInfo(data)` @0x42bbc8  (enter-gym state)
Null-guards `data`, then reads an **OBJECT**:
| key | container | access |
|-----|-----------|--------|
| `curUseGymIdx` | scalar int | GetObjectItem → GetInt64 (null-guarded) |
| `openedGyms` | **array** of int | GetObjectItem → begin-iter (+0x14), per-elem GetInt64; each looked up via `GetById` in the local gym catalog |
| `services` | **array** of object | GetObjectItem → begin-iter; each element has key `gymIdx` (GetObjectItem → GetInt64) |

All player state (which gyms are open, current gym, per-gym service). Container: object
with two optional arrays; everything null-guarded.

---

## D. Comparison vs catalogs and `_make_player()`

| Verified key | Source | In `gym_service/type/cost/item.city`? | In `_make_player()`? |
|--------------|--------|----------------------------------------|----------------------|
| basicStrength/Agile/Endurance/Speed | player | No | **Yes** |
| strength/agile/endurance/speed | player | No | **Yes** |
| gymLevel | player | No | No (optional) |
| curUseGymIdx | player | No | No (optional) |
| openedGyms[] | player | No | No (optional) |
| services[{gymIdx}] | player | No | No (optional) |

**None** of the parser keys match any column of `gym_service.city` (`id,f1,name,f3..f7`),
`gym_type.city`, `gym_service_cost.city`, or `gym_item.city`. The catalogs feed the
client-side `GetGymByType`/`SetGymList` rendering via `CGameData`, **not** the network
parsers. `_make_player()` already supplies the 8 attribute fields ParseResponse reads;
the 4 gym-state fields are absent but **safely omitted** (null-guarded).

---

## E. Endpoint classification

| Endpoint (server.py route) | Verified parser | Class | Container |
|----------------------------|-----------------|-------|-----------|
| gym catalog (types/services/costs/items) | client `LoadGym*` / impart | **ASSET_ONLY** (client-local; no endpoint) | n/a |
| `/city/gym/getgym` | `ParseResponse` | **PLAYER_STATE** (attributes) | object of scalars |
| `/city/gym/train` (exercise, cmd 251/252) | `ParseResponse` | **ACTION_RESPONSE** (updated attributes) | object of scalars |
| enter-gym (cmd via `GetEnterGymInfo`) | `ParseEnterGymInfo` | **PLAYER_STATE** | object + arrays |
| open gym (601) / join gym (602) | OnReceiveResponse | **ACTION_RESPONSE** | — |

No gym endpoint is **ASSET_ONLY at the network layer**. Nothing is **UNKNOWN** — all
gym response paths resolved.

---

## F. Verified payload shapes (safe to serve)

Because gym responses are player-state, the *values* come from the player, not assets.
All keys are null-guarded, so any subset is safe. Exact verified shapes:

**getgym / exercise result** (`ParseResponse`):
```json
{ "basicStrength": <int>, "basicAgile": <int>, "basicEndurance": <int>,
  "basicSpeed": <int>, "strength": <int>, "agile": <int>,
  "endurance": <int>, "speed": <int>, "gymLevel": <int> }
```
(Returning `_make_player()` already satisfies this — those keys exist at top level.)

**enter-gym** (`ParseEnterGymInfo`):
```json
{ "curUseGymIdx": <int>,
  "openedGyms": [ <gymTypeId>, ... ],
  "services": [ { "gymIdx": <gymServiceId> }, ... ] }
```
where `gymTypeId` ∈ `gym_type.city` ids (1–3) and `gymServiceId` ∈ `gym_service.city`
ids (1–15) — i.e. the arrays carry **references** into the client catalogs, not the rows.

---

## G. Recommendation

1. **Leave `SERVE_ASSET_DATA` off for gym.** `gym_service`/`gym_type`/etc. are not served
   by any endpoint; enabling would inject ignored, wrong-shaped data.
2. The current `/city/gym/getgym` stub returns `{gymTypes:[], gymServiceDetails:[]}` —
   those are **impart** keys, not getgym keys; harmless (null-guarded) but not real data.
   If real gym info is wanted, return the player attribute object above (player-state),
   not asset rows.
3. `ASSET_ENDPOINT_MAPPING.md`: reclassify gym from "ASSET-READY" to **player-state /
   action / client-local catalog** — analogous to the `/city/job/getjobs` resolution.
