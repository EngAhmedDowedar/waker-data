# ESTATE_PARSER_FINAL.md — Verified Estate Subsystem Contract

Binary-verified (libcity_ar.so v1.1.38), JOB/GYM methodology. Reused the existing symbol
DB (targeted greps) + fresh disassembly of the estate parsers; all PIC string keys
resolved deterministically against base `0x75ab20`. Vtable byte-offsets: `+0x08`=iter
hasNext, `+0x0c`=iter next/getElement, `+0x14`=begin-iterator (ARRAY), `+0x40`=
GetObjectItem(key). Int64 read helper `0x69300c`; CHouse ctor `0x69317c` (size 0x120).

---

## A. Headline — estate IS server-driven (catalog is merged client-side)

Unlike Job/Gym, estate endpoints **are required**. The split is:

- **`property.city` (18 rows, ids 800–817) is client-local** (`CGameData::LoadProperties`),
  parsed by `CProperty::Read`/`CProperty::Parse` → the *type* config
  (`proxyPrice, basicHappy, maintainCost, canDeal, canSell, canRent`).
- **The server sends the player's estate INSTANCES** (`CHouse` objects) over the network.
- **The client MERGES them**: `CHouse.estateType` → `GetById(estateType)` into the local
  `property.city` catalog (inside `CHouse::GetPrice`) to compute price/happy/maintenance.

So estate is genuinely **MIXED**: server state (CHouse instances) + client catalog
(CProperty by `estateType`).

---

## B. Symbols (verified)

| Symbol | Addr | Role |
|--------|------|------|
| `CHouse::Parse` | 0x4498d8 | per-estate instance parser (22 keys) |
| `CHouse::OnReceiveResponse` | — | (exists; estate-object response) |
| `CProperty::Read` / `CProperty::Parse` | — | **local** `property.city` catalog reader |
| `CPlayer::ParseHouses` | 0x516c3e | `estates` array in player payload |
| `CPlayer::ParseLiveHouse` | 0x516cb0 | `liveEstateObj` single estate |
| `CPropertyCateScreen::Parse` | 0x52034c | array sub-parser (myEstates/spouseEstates) |
| `CPropertyCateScreen::OnReceiveResponse` | 0x520a2c | estate-screen dispatcher |
| `CPropertyListScreen::ParseNumberData` | — | buy-list availability |
| `CDecorateScreen::Parse` | — | decorate action |
| `CGameData::LoadProperties / LoadDecorations / LoadSpecialGoodsHouse` | — | local catalog loaders |

Endpoint strings present: `listestates`=1, `decorate`=1; CHouse keys `sellPrice`,
`rentPrice`(×2), `rentExpireAt`, `estateType`(×2), `liveEstate`(×2), `estates`(×2).
Absent: `listbytype`, `listbycate`, `estate/buy` (paths built dynamically).

---

## C. Response trace — every JSON key

### `CHouse::Parse(data)` @0x4498d8 — the estate instance (OBJECT)
22 `GetObjectItem(+0x40)` keys, each null-guarded (missing → 0/empty), stored to CHouse
struct offsets. Verified in order:
```
id  estateType  systemEstate  decoration1  decoration2  decoration3
maid1  maid1ExpireAt  maid2  maid2ExpireAt  ownerId  renterId
renterName  ownerName  status  sellPrice  rentPrice  rentExpireAt
rentDays  maintainExpireAt  customHouseAt  customHouseTag
```
Container: **object**. **Exactly matches `_make_house()`** in server.py.

### `CPlayer::ParseHouses(data)` @0x516c3e — `estates` (ARRAY)
Null-guards, then `vtable+0x14` **begin-iterator** → loops `hasNext(+0x08)`/
`getElement(+0x0c)`, builds a CHouse (0x69317c, 0x120 bytes) per element. `estates` **must
be an array** or `begin()` returns NULL → Class-A SIGSEGV. (`_make_player` sends `[]` ✓.)

### `CPlayer::ParseLiveHouse(data)` @0x516cb0 — `liveEstateObj` (OBJECT)
Null-guards, constructs ONE CHouse at player+0x268 from `data`. Single **object**, no
iteration. (`_make_player` sends `_make_house(9001)` ✓ — proves a full 22-field CHouse
object is safe at boot.)

### `CPropertyCateScreen::Parse(data)` @0x52034c — array sub-parser (ARRAY)
`vtable+0x14` begin-iterator over `data`; per element builds a CHouse, filters by
`status`(struct+0xb0 ∈ {1,2,3}) and `ownerId`(struct+0x7c vs player id), adds to the
screen list. Requires an **array**.

### `CPropertyCateScreen::OnReceiveResponse(cmd,data)` @0x520a2c — dispatcher (OBJECT)
Reads `data` as an **object**; resolved keys:
```
money  happy  liveEstate  maintainExpireAt  spouseLiveEstate
myEstates  spouseEstates  checkin_house
```
`myEstates` and `spouseEstates` are passed to `Parse` (begin-iterated) ⇒ **arrays of
CHouse**. `money`/`happy` refresh player resources; `liveEstate`/`maintainExpireAt`/
`spouseLiveEstate` are scalars; `checkin_house` is a separate command branch. All
object-accessor null-guarded.

---

## D. Field provenance (task 4)

| Field group | Source | Mechanism |
|-------------|--------|-----------|
| `proxyPrice, basicHappy, maintainCost, canDeal, canSell, canRent` | **property.city** (client) | `CProperty::Read`; looked up by `GetById(estateType)` |
| 22 `CHouse` fields (id, estateType, decorations, maids, owner/renter, status, sell/rentPrice, rent*, maintain*, customHouse*) | **server state** | `CHouse::Parse` from network `data` |
| display price / happy / maintenance | **merged client-side** | `CHouse::GetPrice` = f(CProperty catalog, CHouse instance) |

`estateType` is the join key: server sends the id, client resolves the catalog row.

---

## E. Endpoint classification (task 6)

| Endpoint | Parser | Class | Container |
|----------|--------|-------|-----------|
| property catalog (types) | `CProperty` / `LoadProperties` | **ASSET_ONLY** (client-local; no endpoint) | n/a |
| `/city/estate/listestates` | `CPropertyCateScreen::OnReceiveResponse` → `Parse` | **PLAYER_STATE** (MIXED: refs catalog by estateType) | **object** `{…, myEstates:[CHouse], spouseEstates:[CHouse]}` |
| `/city/estate/buy` | `CPropertyListCateScreen` builds CHouse + GetPrice | **ACTION_RESPONSE** | object (one CHouse) |
| `/city/estate/decorate` | `CDecorateScreen::Parse` | **ACTION_RESPONSE** | object |
| buy-list (listbytype/cate) | `CPropertyListScreen::ParseNumberData` | PLAYER_STATE (availability) refs catalog | object (counts) |
| player payload `estates[]` / `liveEstateObj` | `CPlayer::ParseHouses` / `ParseLiveHouse` | PLAYER_STATE | array / object |

---

## F. Required vs optional / null-guards / containers (task 3)

| Item | Rule |
|------|------|
| `estateType` | **REQUIRED to be a valid `property.city` id (800–817)** — `GetById(estateType)` in `CHouse::GetPrice` null-derefs (fault `0x84`) on an unknown id. Every other CHouse field optional. |
| all other 21 CHouse keys | optional, null-guarded (`GetObjectItem`→NULL→0/empty) |
| `myEstates`, `spouseEstates`, `estates` | if present **MUST be arrays** (begin-iterator); omitting is safe |
| `liveEstateObj` | object (single CHouse) or omit |
| `money, happy, liveEstate, maintainExpireAt, spouseLiveEstate` | optional scalars (object-accessor) |
| top-level `data` for listestates | **OBJECT** (not a bare array — see §H) |

---

## G. Minimal safe payloads (task 7)

**listestates — guaranteed-safe minimal** (object, empty arrays; begin-iterator on `[]`
returns the end-sentinel → zero iterations, no crash):
```json
{ "myEstates": [], "spouseEstates": [] }
```

**listestates — real data** (one owned estate; same CHouse shape proven safe as
`liveEstateObj` at boot):
```json
{ "money": <int>, "happy": <int>, "liveEstate": <houseId>,
  "maintainExpireAt": 0, "spouseLiveEstate": 0,
  "myEstates": [ { "id": 1, "estateType": 800, "systemEstate": 0,
     "decoration1":0,"decoration2":0,"decoration3":0,
     "maid1":0,"maid1ExpireAt":0,"maid2":0,"maid2ExpireAt":0,
     "ownerId": <playerId>, "renterId":0, "renterName":"",
     "ownerName":"Player", "status":1, "sellPrice":1000, "rentPrice":100,
     "rentExpireAt":0, "rentDays":0, "maintainExpireAt":0,
     "customHouseAt":0, "customHouseTag":"" } ],
  "spouseEstates": [] }
```
`estateType:800` (CaoPeng) is mandatory-valid. `ownerId` should equal the player id so
`CPropertyCateScreen::Parse`'s owner filter keeps it.

**estate/buy / decorate** — one CHouse object with a valid `estateType` (as `_make_house()`).

These avoid: **CHouse crash** (valid `estateType`), **estate-array Class-A crash** (arrays
are arrays), and the **layout/JSON-cleanup crash** (correct object container — see §H).

---

## H. The `0x756f707b` correlation (task 8)

Verified facts that reframe the crash:
1. The estate-screen parser expects `data` = **OBJECT** `{myEstates:[…], spouseEstates:[…]}`.
   The current/previous server returned `/city/estate/listestates` as a **bare array**
   (`data: []`, and the crashing attempt `data: [ _make_house() ]`) — the **wrong
   container**. `OnReceiveResponse` probes object keys; on a bare array those return NULL.
2. A **single full 22-field CHouse object is provably safe** — `liveEstateObj` carries
   exactly that at every boot with no crash. So the 22 fields / object size are **not**
   the trigger.
3. The `0x756f707b` fault is ASCII ("{pou") in the native JSON tree-cleanup
   (`ngHashMap`→`ngLinkedList`) — a string value walked as a pointer during destruction of
   the parsed `data` tree. The trigger correlated with the **bare-array-of-large-object**
   response, not with CHouse itself.

**Conclusion:** the previous crash was a **container-shape error** (bare array where an
object is required), not a CHouse field problem. Serving the **correct object shape**
(§G) — empty arrays for the guaranteed-safe baseline, or arrays of valid CHouse objects
for real data — uses exactly the structure the game itself parses (`myEstates` is natively
an array of CHouse) and the proven-safe CHouse object (`liveEstateObj`). Per the
emulator-vs-ARM risk assessment, the populated path should still be confirmed on ARM
(the JSON-cleanup fault lived in the Houdini-translated allocator), but the **shape** is
now binary-verified, not guessed.

---

## I. Recommendation (no changes made)

- `/city/estate/listestates` should return an **object** `{myEstates:[], spouseEstates:[]}`,
  not a bare `[]` — the current bare array is both the wrong contract and the shape that
  triggered `0x756f707b`. Minimal-safe = empty arrays; real data = arrays of CHouse with
  valid `estateType`.
- No `property.city` rows should be sent — the catalog is client-local; only the
  `estateType` id crosses the network (merge happens client-side via `GetById`).
- Estate is the first audited subsystem that genuinely needs **PLAYER_STATE shaping** on a
  real endpoint; the verified contract above is sufficient to implement it without
  guesswork (pending ARM validation of the populated path).
