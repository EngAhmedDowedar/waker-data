# PLAYER_STATE_IMPLEMENTATION_PLAN.md

Implementation plan to replace stub responses with real player-state data.
**Source of truth:** `PLAYER_STATE_MASTER_MAP.md` (all contracts already binary-verified).
No new endpoints, no new RE — every shape below is taken from the verified reports.

Two ingredients already exist in the repo:
- **Catalog data** — `city_loader.py` loads all 93 `.city` tables into `GAMEDATA`
  (costs/rewards/prices are readable server-side: `crime.f7`, `property` price, etc.).
- **`_make_player()` / `_make_house()`** — the CPlayer / CHouse builders with verified keys.

What's missing is a **mutable, persisted player record** + a little action logic. This plan
defines both.

---

## 0. Minimum player-state model (the "database")

A single demo player → one persisted JSON file `player_state.json`, loaded at startup,
mutated by action endpoints, serialized (in slices) by state endpoints. No real DB needed.

```python
PlayerState = {
  # identity / currencies (exist in _make_player)
  "id", "name", "level", "exp",
  "money", "cheque", "gold",
  # attributes (exist) — Gym mutates these
  "strength","endurance","speed","agile",
  "basicStrength","basicEndurance","basicSpeed","basicAgile",
  # resources (exist) — actions consume/award
  "energy","energyUp","blood","bloodUp","happy","happyUp","brave","braveUp","moral","moralUp",
  # status / cooldown  — Crime & Gym set this
  "playerStatus": {"status","statusAt","statusDuration"},
  "coolingTime",
  # mission (exist, scalar)
  "missionId","missionProgress",
  # inventory  — Goods
  "goods": [CGoods], "bags": [CGoods],
  # estates  — Estate
  "estates": [CHouse], "liveEstate",
  # job state
  "highestJobs"/"jobCategory": {<jobTypeId>: level}, "salaryAt",
  # gym state
  "gymLevel","curUseGymIdx","openedGyms":[int],"services":[{"gymIdx":int}],
  # school state
  "classStu":[...], "classId", "myClasses":[...],
  # crime state
  "crimeSkills":[{"crimeIdx","crimeNum"}],
  "crimeSuccess","crimeTimes","thriceNum","jailHalved",
}
```
`CGoods = {id,type,amount,category,boughtPrice,canUseTime,convertGoods}`
`CHouse = {id,estateType(800-817),systemEstate,decoration1-3,maid1,maid1ExpireAt,maid2,
maid2ExpireAt,ownerId,renterId,renterName,ownerName,status,sellPrice,rentPrice,
rentExpireAt,rentDays,maintainExpireAt,customHouseAt,customHouseTag}`

**Persistence fields** = every key above that an action mutates (money, exp, attributes,
status, missionId/Progress, goods/bags, estates, jobCategory, crimeSkills, gym/school state).
**Read-only-from-catalog** = prices/rewards/targets (looked up in `GAMEDATA`, never stored).

Helpers to add: `load_player()/save_player()` (JSON file), `catalog('crime').by_id(id)` etc.
(already provided by `city_loader`), `now()`.

---

## Phase 1 — Estate, Goods, Job, Crime (the core economy loop)

### Estate — `/city/estate/listestates`  ★ CRITICAL (only crash-linked item)
- **Current stub:** `data: []` (bare array)
- **Verified shape:** **object** `{ "myEstates": [CHouse], "spouseEstates": [CHouse] }`
  (+ optional `money, happy, liveEstate, maintainExpireAt, spouseLiveEstate`)
- **Player-state:** `estates[]`, `liveEstate`, `money`, `happy`
- **Persistence:** `estates[]` (mutated by buy/sell)
- **Dependencies:** `property.city` (estateType 800–817 via GetById — hard requirement)
- **Complexity:** **Low** — serialize `estates` into `myEstates`; empty arrays are safe.
  *This single shape fix removes the `0x756f707b` crash.*

### Estate — `/city/estate/buy` (cmd 315)
- **Current stub:** `data: _make_house()` (bare CHouse object)
- **Verified shape:** `{ "buy_house": CHouse, "estates": [CHouse] }`
- **Player-state:** deduct `money` by `property` price; append CHouse to `estates[]`
- **Persistence:** `money`, `estates[]`
- **Dependencies:** `property.city` (price), money balance
- **Complexity:** **Medium** — price lookup + append + refresh list.

### Goods — `/city/goods/playerbags`
- **Current stub:** `{ "bags": [], "goods": [] }`  ← **wrong keys**
- **Verified shape:** `{ "playerGoods": [CGoods], "specialities": [] }`
- **Player-state:** `bags[]` (the player's carried goods)
- **Persistence:** `bags[]`
- **Dependencies:** product/weapon/equipment/drugs catalogs (by `type`+`category`)
- **Complexity:** **Low** — rename keys, serialize `bags` → `playerGoods`.

### Goods — `/city/goods/playergoods` / warehouse
- **Current stub:** `{ "goods": [] }`
- **Verified shape (warehouse):** `{ "playerGoods": [CGoods], "tradeGoods": [], "specialities": [] }`
- **Player-state:** `goods[]` (warehouse)
- **Persistence:** `goods[]`
- **Complexity:** **Low**.

### Goods — `/city/goods/getcitygoods`
- **Current stub:** `{ "goodsList": [] }` (or 194 products when `SERVE_ASSET_DATA=1`)
- **Verified shape:** `{ "goodsList": [ {category, type, amount} ] }`
- **Player-state:** none (per-city market stock) — derive from `product.city`
- **Persistence:** optional (regenerated stock); none required for demo
- **Dependencies:** `product.city` ids
- **Complexity:** **Low** — already correctly shaped; populate `type` from catalog.

### Job — `/city/job/work` (cmd 285) + salary (cmd 284)
- **Current stub:** `data: _make_player()` (full player — works but heavy)
- **Verified shape:** salary → `{ "money": <new>, "salaryAt": <ts> }`; work → result int +
  reward array
- **Player-state:** award `money`/exp by `job`/`job_type`; set `salaryAt`; bump `jobCategory`
- **Persistence:** `money`, `salaryAt`, `jobCategory`
- **Dependencies:** `job.city`/`job_type.city` (salary/exp values)
- **Complexity:** **Medium** — award logic + slim response (replace full-player return).

### Crime — `/city/crime/docrime` (cmd 232)  ★ core money loop
- **Current stub:** `data: _make_player()`
- **Verified shape:** `{ result, awardType, awardMoney, awardCheque, awardGoodsType,
  awardGoodsCategory, awardGoodsAmount, awardExp, statusDuration, lostToolFlag, blood,
  consumeNum }`
- **Player-state:** roll success vs `crime.city` threshold; on success award money/exp/goods;
  on fail set `blood`/jail `statusDuration`; update `crimeSkills[]`, `crimeTimes`
- **Persistence:** `money`, `exp`, `bags[]`, `crimeSkills[]`, `playerStatus`/`coolingTime`
- **Dependencies:** `crime.city` (reward/threshold), goods catalogs (award item)
- **Complexity:** **High** — probabilistic outcome + cooldown + skill progression.

**Phase 1 exit criteria:** city + estate screens render (crash gone); inventory/market show
items; jobs and crime produce income that persists across requests.

---

## Phase 2 — School, Gym, Mission (secondary loops)

### School — `/city/school/getmyclasses`  (currently catch-all `data:{}`)
- **Verified shape:** `{ "classStu": [], "classId": 0, "myClasses": [] }`
- **Player-state:** `classStu[]`, `classId`, `myClasses[]`
- **Persistence:** enrollment list; **Dependencies:** `subject.city` (1600–1634)
- **Complexity:** **Low** (read) / **Medium** (with timed completion).

### School — `/city/school/applyclass` (catch-all `data:{}`)
- **Verified shape:** `{ "createAt": <now>, "finishAt": <now+studySecs>, "school_apply_subject": 1 }`
- **Player-state:** add to `myClasses[]` with the time window
- **Complexity:** **Medium**.

### Gym — `/city/gym/getgym`
- **Current stub:** `{ "gymTypes": [], "gymServiceDetails": [] }`  ← **wrong (impart) keys**
- **Verified shape:** player attributes object (`basicStrength…speed`, `gymLevel`) — i.e.
  returning the attribute slice (or `_make_player()`) satisfies it
- **Player-state:** attributes; **Persistence:** attributes, `gymLevel`
- **Complexity:** **Low**.

### Gym — exercise (cmd 251/252) / `/city/gym/train`
- **Current stub:** `data: _make_player()`
- **Verified shape:** updated attributes
- **Player-state:** increment one attribute (cost energy), set cooldown `statusDuration`
- **Persistence:** attributes, `playerStatus`; **Complexity:** **Medium-High** (cooldown).

### Mission — `/city/mission/updatemission` (cmd 369)
- **Current stub:** `data: _make_player()`
- **Verified shape:** `{ "missionId": <nextId> }`
- **Player-state:** advance `missionId` (1–29; 100 = parked), reset `missionProgress`
- **Persistence:** `missionId`, `missionProgress`; **Dependencies:** `mission.city`
- **Complexity:** **Low** (scalar). *Note: the full active-mission chain triggers other
  stubbed endpoints — keep `missionId:100` until the chain is built.*

**Phase 2 exit criteria:** training raises stats, classes enroll with timers, missions can
advance one step.

---

## Phase 3 — Remaining systems

- **Dead routes:** delete `/city/job/getjobs`, `/city/mission/getmission` (no binary string).
- **Goods buy/sell currency deltas** (`excess, gold, mercenaryExp, huntCoin`).
- **Estate sell/rent/maintain** (cmds 317–323) — per-branch refinement; check-in (335)
  income collection `{money, happy, liveEstate, maintainExpireAt, checkin_house}`.
- **Decorate** (316) `{idx, decoration, num, happy, money, exipreAt}`.
- **Unverified subsystems** (faction, mercenary, racing, hunt, etc.) — keep crash-guard
  stubs; verify with the JOB→…→CRIME methodology **only if** the demo needs them.
- **Catch-all & crash-guard `data:[]` stubs:** leave intact — they protect legitimately-empty
  player-state arrays.

---

## Global rules (apply to every endpoint)

1. **Containers are fixed** — list keys (`estates/myEstates/spouseEstates`, `goodsList`,
   `playerGoods/tradeGoods/specialities`, `classStu/myClasses`, CPlayer `goods/bags`) **must
   be arrays**; `{}` where an array is expected = Class-A SIGSEGV. (No live risk today; only
   when populating.)
2. **`data:{}` is always crash-safe** — every verified key is null-guarded; ship a stub,
   then fill keys incrementally.
3. **`estateType` must be 800–817** in any CHouse, or `GetById` null-derefs (fault 0x84).
4. **Catalog rows never leave the server** — send ids/references only; the client merges via
   its own `.city` pack.
5. **Validate populated array/object responses on real ARM** before trusting them (the
   residual `0x756f707b`-class fault lived in the Houdini allocator, not the JSON contract).

---

## Complexity / effort summary

| Phase | Endpoints | Dominant work | Complexity |
|-------|-----------|---------------|-----------|
| 1 | estate listestates/buy, goods bags/warehouse/getcitygoods, job work/salary, crime docrime | player record + award/cooldown logic | listestates **Low**; goods **Low**; job **Medium**; crime **High** |
| 2 | school getmyclasses/applyclass, gym getgym/train, mission updatemission | timers + attribute logic | mostly **Medium** |
| 3 | buy/sell deltas, estate sell/rent/decorate/checkin, dead-route cleanup | breadth | **Low–Medium** |

## Definition of "playable demo"
Minimum to play the core loop: **PlayerState JSON model (§0)** +
**Phase 1** (estate object-shape fix, real inventory/market, job income, crime income).
That set makes the city navigable and the economy functional without any further reverse
engineering — every field name, container, and id dependency is already pinned in
`PLAYER_STATE_MASTER_MAP.md`.
