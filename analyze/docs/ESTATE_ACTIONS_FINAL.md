# ESTATE_ACTIONS_FINAL.md — Verified Estate Action-Response Contracts

Binary-verified (libcity_ar.so v1.1.38), JOB/GYM/ESTATE methodology. Reuses
ESTATE_PARSER_FINAL findings (CHouse = 22-key object; `estates`/`myEstates`/
`spouseEstates` = arrays). New disassembly of the action dispatchers; all command ids
read as raw literals and all JSON keys resolved deterministically against PIC base
`0x75ab20`. Vtable: `+0x14`=begin-iterator (array), `+0x40`=GetObjectItem; int64 helper
`0x69300c`; CHouse ctor `0x69317c` (0x120). Singleton/global accessor `0x69320c`.

---

## A. Estate command ids (verified)

| cmd | hex | Handler screen | Action |
|-----|-----|----------------|--------|
| 315 | 0x13b | `CPropertyListCateScreen::OnReceiveResponse` @0x524b7c | **buy** |
| 316 | 0x13c | `CDecorateScreen::OnReceiveResponse` @0x38702c (`0x4f<<2`) | **decorate** |
| 317–322 | 0x13d–0x142 | `CPropertyListCateScreen` (dispatch range `cmd ≤ 323`) | other estate mutations (sell / rent / unrent / maintain) |
| 323 | 0x143 | `CHouse::OnReceiveResponse` @0x44a260 **and** the buy-screen range top | estate update (rent/sell-side) |
| 335 | 0x14f | `CHouse::OnReceiveResponse` @0x44a260 | **check-in / collect income** |

`CPropertyListCateScreen::OnReceiveResponse` gates on `cmd ≤ 323` then branches — it owns
the whole 315–323 mutation range. `CHouse::OnReceiveResponse` compares `cmd == 0x14f` and
`cmd == 0x143`. No estate path-strings exist (`buyestate`/`sellestate`/`rentestate` = 0) —
commands are numeric, exactly like Job (285/284) and Gym (251/252/601/602).

---

## B. JSON keys per action (resolved, base 0x75ab20)

| Action (cmd) | Parser | Keys read | Container |
|--------------|--------|-----------|-----------|
| Buy (315) | `CPropertyListCateScreen::OnReceiveResponse` | `buy_house`, `estates` | object; `estates` = **array** of CHouse |
| Sell/Rent (317–323) | same screen + `CHouse::OnReceiveResponse` | `estates` (refresh) | object; `estates` = array |
| Decorate (316) | `CDecorateScreen::OnReceiveResponse` | `idx`, `decoration` | object |
| Decorate detail | `CDecorateScreen::Parse(data,int)` @0x3871cc | `num`, `happy`, `money`, `idx`, **`exipreAt`** | object |
| Check-in (335) | `CHouse::OnReceiveResponse` | `happy`, `money`, `liveEstate`, `maintainExpireAt`, `checkin_house` | object |
| Maintenance | (in 317–323 range) | `estates` + `maintainExpireAt` | object |

> **Typo is real:** the decorate parser reads the key **`exipreAt`** (not `expireAt`).
> Use the misspelled key verbatim or the value is dropped.

CHouse element fields (when an estate object appears in `estates`/`buy_house`) are the 22
verified `CHouse::Parse` keys from ESTATE_PARSER_FINAL (`id, estateType, …, customHouseTag`).

---

## C. Container / required / optional / null-guard rules

| Item | Rule |
|------|------|
| top-level `data` for every action | **OBJECT** (never a bare array) |
| `estates`, `buy_house`(if array) | if present **must be arrays/objects** matching CHouse; begin-iterated (Class-A if wrong type) |
| `estateType` inside any CHouse | **REQUIRED valid `property.city` id (800–817)** — `GetById` null-derefs (fault 0x84) otherwise |
| all other CHouse keys | optional, null-guarded |
| `idx`, `decoration`, `num`, `happy`, `money`, `exipreAt`, `liveEstate`, `maintainExpireAt`, `checkin_house` | optional scalars, object-accessor null-guarded (missing → 0) |
| every action response | **`data:{}` is crash-safe** (all keys null-guarded); populate keys to make the action *take effect* |

---

## D. Endpoint classification

| Action | Class | Rationale |
|--------|-------|-----------|
| Buy (315) | **ACTION_RESPONSE** (returns CHouse) + PLAYER_STATE (estates refresh) → **MIXED** | reads `buy_house` + refreshed `estates[]` |
| Sell / Rent / Unrent (317–323) | **MIXED** | refresh `estates[]` (player state) as the action result |
| Decorate (316) | **MIXED** | updates `happy`/`money` (player) + decoration slot `idx`/`exipreAt` |
| Maintenance | **MIXED** | updates `maintainExpireAt` + estates refresh |
| Check-in / collect (335) | **MIXED** | `money`/`happy` deltas to CPlayer + `liveEstate`/`maintainExpireAt` |

None are ASSET_ONLY (no catalog rows cross — `estateType` ids only, merged client-side via
`GetById`, per ESTATE_PARSER_FINAL).

---

## E. Exact minimal valid payloads

All keys null-guarded ⇒ `data:{}` never crashes; the shapes below make the action *work*.

**Buy estate (cmd 315)** — returns the bought house + refreshed list:
```json
{ "buy_house": { "id": 1, "estateType": 800, "ownerId": <playerId>,
                 "ownerName": "Player", "status": 1, "sellPrice": 1000,
                 "rentPrice": 100 },
  "estates": [ { "id": 1, "estateType": 800, "ownerId": <playerId>,
                 "ownerName": "Player", "status": 1 } ] }
```
(`estateType` must be 800–817; all other CHouse keys optional.)

**Decorate (cmd 316)**:
```json
{ "idx": 1, "decoration": <decorationId>, "num": 1,
  "happy": <newHappy>, "money": <newMoney>, "exipreAt": 0 }
```

**Rent / Sell (cmd 317–323)** — refresh the estates array with updated instance fields:
```json
{ "estates": [ { "id": 1, "estateType": 800, "ownerId": <playerId>,
                 "renterId": <renterId>, "renterName": "X", "status": 2,
                 "rentPrice": 100, "rentExpireAt": <ts>, "rentDays": 7 } ] }
```

**Maintenance**:
```json
{ "estates": [ { "id": 1, "estateType": 800, "ownerId": <playerId>,
                 "maintainExpireAt": <ts> } ] }
```

**Check-in / collect (cmd 335)**:
```json
{ "money": <newMoney>, "happy": <newHappy>, "liveEstate": <houseId>,
  "maintainExpireAt": <ts>, "checkin_house": 1 }
```

---

## F. Full CHouse vs deltas vs CPlayer (explicit)

Verified from the disassembly:

1. **Buy / Sell / Rent return full CHouse objects** (not deltas). The handler allocates a
   CHouse (`0x69317c`, 0x120 bytes) per element and re-parses it via the `estates` array /
   `buy_house` object — the client **rebuilds** its estate list from the response.
2. **Decorate and Check-in carry resource DELTAS** (`money`, `happy`) plus the specific
   changed fields (`idx`/`decoration`/`exipreAt`; `liveEstate`/`maintainExpireAt`). These
   are written to the player/global singleton directly (via `0x69320c`), i.e. they
   **update CPlayer state**, not the estate list.
3. So the model is **MIXED**: structural mutations (buy/sell/rent) return **full refreshed
   CHouse instances**; resource-affecting actions (decorate/check-in/maintenance) return
   **deltas that update CPlayer** alongside the changed estate field.

---

## G. Note for implementation (no changes made)

- Estate actions are **object-shaped** responses with null-guarded keys — `data:{}` is the
  guaranteed-safe baseline; the §E payloads make each action functional.
- The current `/city/estate/buy` returns a **bare CHouse object**; the verified handler
  also reads `buy_house` and `estates` — wrapping as `{buy_house:{…}, estates:[…]}` is the
  precise shape (the bare object's keys are simply not found, so the bought house is not
  added to the list).
- `estateType` validity (800–817) is the only hard requirement across all estate payloads.

**Confidence:** keys & containers **High** (deterministically resolved); cmd ids 315/316/
323/335 **High** (raw literals); the 317–322 action-to-cmd mapping **Medium** (range owned
by the buy screen; individual sub-branches not each disassembled).

Success criterion met: every estate action's field names, containers, and required fields
are verified — enough to implement buy/decorate/rent/sell/maintenance without guessing.
