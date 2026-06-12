# PLAYER_STATE_MASTER_MAP.md — Consolidated Subsystem Contract

Single source of truth merging the eight verified subsystem reports (JOB, GYM, ESTATE,
ESTATE_ACTIONS, GOODS_MARKET, SCHOOL, MISSION, CRIME). All facts binary-verified
(libcity_ar.so v1.1.38); JSON keys resolved deterministically against PIC base `0x75ab20`.
Vtable convention: `+0x14`=begin-iterator (ARRAY), `+0x40`=GetObjectItem(key),
`+0x10`=IntValue; catalog lookup `GetById` `0x69341c`.

---

## 0. The universal architecture (one paragraph)

Across **all eight subsystems** the model is identical: every `.city` table is a
**client-side content pack** (loaded by a `CGameData::Load*` method); the server **never**
sends catalog rows. The server's entire job is **player state** + **action results**, which
reference catalogs **by id only** (merged client-side via `GetById`). Endpoints are
**numeric commands**, not path strings — fabricated "list" routes (`getjobs`, `getgym`,
`getmission`, `docrime`-as-path) do **not** exist in the binary. Therefore implementation
work = **shaping player-state/action objects**, never serving catalogs.

---

## 1. Client-local catalogs (ASSET_ONLY — never crosses the network)

| Subsystem | Catalogs (ids) | Loader(s) |
|-----------|----------------|-----------|
| Job | `job` (1200–1253), `job_type` (1300–1311) | `LoadJobs`, `LoadJobTypes` |
| Gym | `gym_type` (1–3), `gym_service` (1–15), `gym_service_cost` (1–26), `gym_item` (1100–1130) | `LoadGymType/Service/ServiceCost/Item` |
| Estate | `property` (800–817), decorations | `LoadProperties`, `LoadDecorations` |
| Goods/Market | `product` (600–823), `weapon` (200–499), `equipment` (300–596), `drugs` (500–525), CBweapon/special | `LoadProducts/Weapons/Armors/Drugs/CBWeapon` |
| School | `subject` (1600–1634), `subject_type` (1500–1504) | `LoadSubject`, `LoadSubjectType` |
| Mission | `mission` (1–29) | `LoadMissions` |
| Crime | `crime` (100–182), `crime_type` (1–17), `drugs` (500–525) | `LoadCrimes/CrimeTypes/Drugs` |

---

## 2. Network endpoints (command id where verified)

| Subsystem | Endpoint / command | Class | Notes |
|-----------|-------------------|-------|-------|
| Job | `/city/job/work` (cmd 285) | ACTION | `ParseDoJobResponse` |
| Job | salary (cmd 284) | ACTION | `ParseGetSaleryResponse` |
| Job | ~~`/city/job/getjobs`~~ | DEAD | no string; catalog is client-local |
| Gym | `/city/gym/getgym` | PLAYER_STATE | `ParseResponse` (attributes) |
| Gym | exercise (cmd 251/252), open (601), join (602) | ACTION | `OnReceiveResponse` |
| Gym | enter-gym | PLAYER_STATE | `ParseEnterGymInfo` |
| Estate | `/city/estate/listestates` | PLAYER_STATE | `CPropertyCateScreen::OnReceiveResponse` |
| Estate | buy (315), decorate (316), sell/rent/maintain (317–323), check-in (335) | ACTION | see §4 |
| Goods | `/city/goods/getcitygoods` | PLAYER_STATE/MIXED | `ParseGoodsAmount` |
| Goods | `/city/goods/playerbags`, warehouse | PLAYER_STATE | `ParseBag`/`ParseWarehouse` |
| Goods | buy, sell | ACTION | `CGoodsBuyScreen`/`CGoodsSellScreen` |
| School | `/city/school/getmyclasses` | PLAYER_STATE | `ParseSubject` |
| School | `/city/school/applyclass` | ACTION | `CSchoolCateScreen` |
| School | graduate/exam | ACTION | `CGraduateScreen` |
| Mission | `/city/mission/updatemission` (cmd 369) | ACTION | `CGameMissionManager` |
| Mission | ~~`/city/mission/getmission`~~ | DEAD | no string |
| Crime | `/city/crime/docrime` (cmd 232/0xe8) | ACTION/MIXED | `ParseDoCrimeResponse` |

---

## 3. Player-state fields (CPlayer payload + state endpoints)

| Subsystem | Fields | Container |
|-----------|--------|-----------|
| Job | `highestJobs`/job-category map (object keyed by job-type id); `money` | object map + scalar |
| Gym | `basicStrength/Agile/Endurance/Speed`, `strength/agile/endurance/speed`, `gymLevel`; `curUseGymIdx`, `openedGyms[]`, `services[{gymIdx}]` | scalars + arrays |
| Estate | `estates[]` (CHouse array), `liveEstateObj` (single CHouse); `money`, `happy`, `liveEstate`, `maintainExpireAt`, `spouseLiveEstate`; `myEstates[]`, `spouseEstates[]` | object w/ arrays |
| Goods | `goods[]`, `bags[]` (CPlayer); bag→`playerGoods[]`,`specialities[]`; warehouse→`playerGoods[]`,`tradeGoods[]`,`specialities[]` | object w/ arrays |
| School | `classStu[]`, `classId`, `myClasses[]` | object w/ arrays + scalar |
| Mission | `missionId`, `missionProgress` | scalars |
| Crime | `crimeSkills[]` `{crimeIdx,crimeNum}`; `crimeSuccess`, `crimeTimes`, `thriceNum`, `jailHalved`, `coolingTime` | array + scalars |

---

## 4. Action-response fields (verified keys)

| Subsystem | Action | Response keys |
|-----------|--------|---------------|
| Job | work (285) | result int + reward-item array (unnamed) |
| Job | salary (284) | `money`, `salaryAt` |
| Gym | exercise (251/252) | player attributes (`basicStrength…speed`, `gymLevel`) |
| Estate | buy (315) | `buy_house`, `estates[]` |
| Estate | decorate (316) | `idx`, `decoration`; (Parse) `num`, `happy`, `money`, `idx`, **`exipreAt`** (sic) |
| Estate | sell/rent (317–323) | `estates[]` refresh |
| Estate | check-in (335) | `happy`, `money`, `liveEstate`, `maintainExpireAt`, `checkin_house` |
| Goods | buy | `excess`, `gold`, `mercenaryExp`, `huntCoin` |
| Goods | use/equip | `boughtPrice`, `expiredAt` |
| School | applyclass | `createAt`, `finishAt`, `school_apply_subject` |
| Mission | updatemission (369) | `missionId` |
| Crime | docrime (232) | `result`, `awardType`, `awardMoney`, `awardCheque`, `awardGoodsType/Category/Amount`, `awardExp`, `statusDuration`, `lostToolFlag`, `blood`, `consumeNum` (opt. under `crimeResult`) |

**CGoods element** (used by goods/market/crime rewards): `id, type, amount, category,
boughtPrice, canUseTime, convertGoods`. **CHouse element**: `id, estateType, systemEstate,
decoration1-3, maid1/maid1ExpireAt/maid2/maid2ExpireAt, ownerId, renterId, renterName,
ownerName, status, sellPrice, rentPrice, rentExpireAt, rentDays, maintainExpireAt,
customHouseAt, customHouseTag`.

---

## 5. Required JSON containers

| Subsystem | Top-level `data` | Notable nested |
|-----------|------------------|----------------|
| Job (work/salary) | object | salary: scalars; work: + reward array |
| Gym (getgym/enter) | object | enter: `openedGyms[]`, `services[]` arrays |
| Estate (listestates) | **object** `{myEstates:[], spouseEstates:[]}` | arrays of CHouse |
| Estate (actions) | object | `estates[]` array; `buy_house` object |
| Goods (getcitygoods) | object `{goodsList:[…]}` | array of `{category,type,amount}` |
| Goods (bag/warehouse) | object | `playerGoods[]`/`tradeGoods[]`/`specialities[]` arrays |
| School (getmyclasses) | object | `classStu[]`, `myClasses[]` arrays |
| Mission (updatemission) | object `{missionId}` | none (scalar) |
| Crime (docrime) | object | scalars only (opt. `crimeResult` wrapper) |

---

## 6. Class-A crash risks (array-iterator; `{}` where array expected → SIGSEGV)

| Subsystem | Keys that MUST be arrays if present | Current status |
|-----------|-------------------------------------|----------------|
| Estate | `estates`, `myEstates`, `spouseEstates` | `_make_player.estates:[]` safe; listestates returns bare `[]` (see §7) |
| Goods | `goodsList`, `playerGoods`, `tradeGoods`, `specialities`, CPlayer `goods`/`bags` | defaults `[]` / `{goodsList:[]}` safe |
| School | `classStu`, `myClasses` | nested+null-guarded → catch-all `data:{}` safe |
| Crime | CPlayer `crimeSkills` | omitted (commented out) → safe |
| Job | `highestJobs` is an **object** map (NOT array) | safe |
| Gym | `openedGyms`, `services` | omitted → safe |
| Mission | none (scalar only) | safe |

**No live Class-A crash exists today.** All risks are *latent* — triggered only by
populating a list key with a non-array value.

---

## 7. Shape mismatches discovered

| Subsystem | Mismatch | Severity |
|-----------|----------|----------|
| **Estate** | `/city/estate/listestates` returns a **bare array**, but the parser needs an **object** `{myEstates:[…], spouseEstates:[…]}`. This bare-array shape was the **`0x756f707b`** heap-cleanup crash (NOT a CHouse field issue — `liveEstateObj` proves a 22-field CHouse object is safe). | **High** (only crash-linked mismatch) |
| **Goods** | `/city/goods/playerbags` returns `{bags, goods}`, but `ParseBag` reads `playerGoods`/`specialities`. Wrong keys → null-guarded → empty bag, **no crash**. | Medium (silent empty) |
| Estate | `/city/estate/buy` returns a bare CHouse object, but handler reads `buy_house`+`estates`. | Low (silent) |
| Note | `goods`/`bags` ARE correct for the **CPlayer payload**; only the *goods-screen* endpoints use `playerGoods`/`tradeGoods`. Don't conflate the two contexts. | — |

---

## 8. Minimal valid payloads (quick reference; `data:{}` is universally crash-safe)

```
job work (285)    → {}              (or result int + reward array)
job salary (284)  → { "money": <n>, "salaryAt": <ts> }
gym getgym        → _make_player()  (attribute keys already top-level) ; minimal {}
gym enter         → { "curUseGymIdx":0, "openedGyms":[], "services":[] }
estate listestates→ { "myEstates": [], "spouseEstates": [] }    ← FIX (not bare [])
estate buy (315)  → { "buy_house": {CHouse,estateType:800}, "estates": [ {CHouse} ] }
estate decorate   → { "idx":1, "decoration":<id>, "num":1, "happy":<n>, "money":<n>, "exipreAt":0 }
estate checkin    → { "money":<n>, "happy":<n>, "liveEstate":<id>, "maintainExpireAt":<ts>, "checkin_house":1 }
getcitygoods      → { "goodsList": [ {"category":<c>,"type":600,"amount":99} ] }   (minimal {goodsList:[]})
playerbags        → { "playerGoods": [CGoods…], "specialities": [] }   ← keys, not bags/goods
warehouse         → { "playerGoods":[…], "tradeGoods":[], "specialities":[] }
goods buy         → { "gold":<n>, "excess":0, "mercenaryExp":0, "huntCoin":0 }
school getmyclasses→ { "classStu":[], "classId":0, "myClasses":[] }
school applyclass → { "createAt":<now>, "finishAt":<now+secs>, "school_apply_subject":1 }
mission update(369)→ { "missionId": <1..29 | 100> }
crime docrime(232)→ { "result":1, "awardType":1, "awardMoney":1000, "awardExp":50,
                      "statusDuration":60, "blood":0, "lostToolFlag":0, "consumeNum":0 }
```
CHouse requires a valid `estateType` (800–817) or `GetById` null-derefs (fault 0x84).

---

## 9. Catalog-id dependencies (the only ids that cross the wire)

| Field | References |
|-------|-----------|
| job-category map keys | `job_type` ids (1300–1311) |
| `estateType` (CHouse) | `property` ids (800–817) — **hard requirement, GetById** |
| `type`+`category` (CGoods) | goods catalogs (product/weapon/equipment/drugs); `category` disambiguates overlapping weapon/equipment ranges |
| `classId`, `myClasses[].id` | `subject` ids (1600–1634) |
| `missionId` | `mission` ids (1–29; 100=parked) |
| `crimeSkills[].crimeIdx` | `crime` ids (100–182) |
| `awardGoods*` (crime/job reward) | goods catalogs |

---

## 10. Confidence

| Subsystem | Confidence | Residual unknown |
|-----------|-----------|------------------|
| Job | High | reward-array element keys (work) |
| Gym | High | — |
| Estate (parse) | High | minimal safe field set for the populated array (ARM-validate) |
| Estate (actions) | High (cmds 315/316/323/335); Medium (317–322 mapping) | per-branch sub-action keys |
| Goods/Market | High | `category` numeric→catalog-class mapping; goods cmd ids |
| School | High (top-level) | `myClasses`/`classStu` element sub-fields (positional) |
| Mission | High | — (single scalar) |
| Crime | High (result); Medium-High (cmd 232/`h`) | CPlayer crime-skills container field name |

---

# Prioritized Implementation Roadmap → stable playable demo

Ranked by: crash-elimination > boot-path reachability > core-loop gameplay > depth.
Every item is **player-state/action shaping** (no catalog serving).

## CRITICAL — correctness/crash, do first
1. **Estate `listestates` → object shape.** Change the bare `[]` to
   `{ "myEstates": [], "spouseEstates": [] }`. This is the **only crash-linked mismatch**
   (`0x756f707b`) and the highest-value single fix. (Empty arrays = guaranteed safe; add
   real CHouse entries with `estateType:800` once ARM-validated.)
2. **Keep all crash-guard `data:[]` stubs** (airline/hospital/jail/gang/etc.) — they protect
   legitimately-empty player-state arrays; removing them re-introduces Class-A crashes.

## HIGH — core single-player loop
3. **Goods inventory keys.** `playerbags` → `{playerGoods:[], specialities:[]}`; warehouse →
   add `tradeGoods`. Enables the bag/inventory screen to actually show items.
4. **`getcitygoods` real stock** (already correctly shaped) — populate `goodsList` with real
   `product` ids to make the market non-empty.
5. **Crime `docrime` result.** Return the verified result object (`result`,`award*`,
   `statusDuration`) so crime — a core money loop — functions.
6. **Job work/salary results.** `{money, salaryAt}` for salary; result+reward for work.

## MEDIUM — depth & secondary loops
7. **Estate actions** (buy 315 `{buy_house,estates[]}`, decorate 316, check-in 335) — property
   gameplay.
8. **School** `getmyclasses` `{classStu,classId,myClasses}` + `applyclass` `{createAt,finishAt}`.
9. **Gym** `getgym`/exercise (return player attributes) — training loop.
10. **Mission `updatemission`** `{missionId}` to advance the story chain (pairs with the
    existing fight-target work; the rest of the mission chain is still unimplemented).

## LOW — polish / rarely-hit
11. Goods buy/sell currency deltas (`excess,gold,mercenaryExp,huntCoin`).
12. Estate sell/rent (317–322) per-branch refinement; graduate/exam.
13. Delete dead routes (`/city/job/getjobs`, `/city/mission/getmission`) — cosmetic.

## Critical path to "stable playable demo"
**CRITICAL #1 alone** removes the last known data-driven crash and lets the city +
estate screens render. **HIGH #3–6** turn the empty HUD into a working economy
(inventory, market, crime income, jobs). That set — one shape fix + four player-state
objects — is the shortest path from "boots to city" to "playable core loop," and none of
it requires catalog serving or new endpoints, only correct player-state payloads.

> Caveat carried from the ARM risk assessment: populated array/object responses (esp.
> estate) should be confirmed on real ARM hardware, since the residual `0x756f707b`-class
> fault lived in the Houdini-translated allocator, not in the verified JSON contract.
