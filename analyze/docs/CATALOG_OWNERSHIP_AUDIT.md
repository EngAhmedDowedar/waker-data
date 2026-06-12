# CATALOG_OWNERSHIP_AUDIT.md — System-Wide Catalog Ownership

Determines which `.city` catalogs cross the network vs. are loaded entirely client-side.
Reuses the existing symbol database (targeted greps), prior disassembly captures
(JOB/GYM_PARSER_FINAL), SCHEMAS.md, and the decoded catalog knowledge. No asset rescan,
no server changes, no game runs.

## Method (the decisive binary signals)

1. **`CGameData::Load<X>` exists** ⇒ catalog `<X>` is loaded **client-side** from `*.city`.
2. **Endpoint path-string absent** + **`OnReceiveResponse` handles only actions** ⇒ catalog
   rows never travel over the network (established for Job & Gym, fully verified).
3. **Screen exposes no `Parse*`** ⇒ subsystem is pure client-side (no network response).
4. A response parser that reads **player/account keys** (not `.city` columns) ⇒ PLAYER_STATE
   / ACTION, referencing catalogs only by **id**.

### Master fact

`CGameData::Load*` was enumerated in one pass. **Every catalog in this audit has a loader**
— i.e. all are client-local:

```
LoadSubject, LoadSubjectType, LoadCrimes, LoadCrimeTypes, LoadStorePackage,
LoadGoldPackage, LoadGiftPackage, LoadProducts, LoadWeapons, LoadArmors,
LoadExchange{Type,Need,Extra,TimeCtrl}, LoadMineClassAdjacent, LoadMount,
LoadAchievements, LoadAchievementSkill, LoadProperties, LoadDecorations,
LoadMissions, LoadDrugs, LoadFunctionTools, LoadRank, LoadMilitia, LoadSlaves, …
```

No catalog is fetched from the server. The endpoints that exist carry **player state** or
**action results** that *reference* catalogs by id.

---

## Per-subsystem findings

### School
1. Catalogs: `subject.city` (35), `subject_type.city` (5)
2. Loader: `CGameData::LoadSubject`, `LoadSubjectType`
3. Screen parsers: `CSchoolScreen::ParseSubject`, `OnReceiveResponse`; `CSchoolCateScreen::OnReceiveResponse`
4. OnReceiveResponse: present (player enrollment / class actions)
5. Catalog rows cross network? **No** (catalog client-local)
6. Class: **PLAYER_STATE** (`getmyclasses`) + **ACTION_RESPONSE** (`applyclass`)
7. JSON keys: not yet extracted
8. Confidence: **Medium** (parser not yet disassembled; path strings `getmyclasses`/`applyclass` confirmed)

### Crime
1. `crime.city` (83), `crime_type.city` (17)
2. `LoadCrimes`, `LoadCrimeTypes`
3. `CCrimeScreen::ParseDoCrimeResponse`, `OnReceiveResponse`
4. Only an action parser (`ParseDoCrimeResponse`)
5. **No**
6. Class: **ACTION_RESPONSE** (do-crime result)
7. not yet extracted
8. Confidence: **High** (only parser is the action result; no catalog/list parser exists)

### Store
1. `gift.city` (239), `gold_package.city` (17), `paid_tool.city` (295)
2. `LoadStorePackage`, `LoadGoldPackage`, `LoadGiftPackage`
3. `CStorePackage::Parse`, `ParseBucks`, `ParseRandomGiftByTypeAndId`; `CStoreCateScreen::OnReceiveResponse`
4. Present (purchase flow)
5. **No** (packages are client catalog; `getstoreitems` carries purchasable/recharge state)
6. Class: **MIXED** (PLAYER_STATE purchasable list + ACTION_RESPONSE on buy)
7. not yet extracted
8. Confidence: **Medium**

### Market
1. `product.city` (194), `weapon.city` (274), `equipment.city` (223), `exchange_*`
2. `LoadProducts`, `LoadWeapons`, `LoadArmors`, `LoadExchange*`
3. `CMarketScreen::ParseGoodsAmount`, `CMarketCateScreen::ParseGoodsAmount`
4. Present
5. **No** — `ParseGoodsAmount` reads `{goodsList:[{category,type,amount}]}` where `type` is a
   product **id reference** and `amount` is **stock state**; rows themselves stay client-side
6. Class: **PLAYER_STATE / MIXED** (per-city stock referencing the catalog)
7. JSON keys: `goodsList`, `category`, `type`, `amount` (known from SCHEMAS.md / getcitygoods)
8. Confidence: **High**

### Mine
1. `mine.city` (150), `mineshop.city` (7)
2. `LoadMineClassAdjacent` (+ `mine`/`mineshop` via LoadTypes family)
3. `CMineBidScreen::Parse`, `ParseList`, `OnReceiveResponse`; `CMS_MineMainScreen::OnReceiveResponse`
4. Present (bidding / occupancy)
5. **No**
6. Class: **PLAYER_STATE** (bids/occupancy) + **ACTION_RESPONSE** (bid)
7. not yet extracted
8. Confidence: **Medium**

### Mount
1. `mounts.city` (415)
2. `LoadMount`
3. **No screen Parse\* or OnReceiveResponse located** (`CMountScreen` exposes none)
4. None found
5. **No**
6. Class: **ASSET_ONLY** (pure client-side; no network response handler)
7. n/a
8. Confidence: **Medium** (absence of a parser strongly implies client-only; class name not pinned)

### Achievement
1. `achievement.city` (893), `achievement_skill.city` (31)
2. `LoadAchievements`, `LoadAchievementSkill`
3. `CAchievementScreen::ParseAchievements`, `OnReceiveResponse`
4. Present
5. **No** — `ParseAchievements` reads the player's **progress/unlock** state, referencing
   achievement ids
6. Class: **PLAYER_STATE**
7. not yet extracted (parser is an array of progress entries)
8. Confidence: **High** (catalog client-local; parser is progress, not catalog)

### Estate
1. `property.city` (18), decorations
2. `LoadProperties`, `LoadDecorations`
3. `CPropertyCateScreen::Parse`; estate objects via `CHouse::Parse`
4. `CPropertyCateScreen::OnReceiveResponse` (null-guards before the array sub-parser)
5. **No** — `listestates` returns the player's **owned** `CHouse` objects; `estateType`
   references `property.city` (CaoPeng=800)
6. Class: **PLAYER_STATE**
7. JSON keys (CHouse, from SCHEMAS.md): `id, estateType, systemEstate, decoration1..3,
   maid1, maid1ExpireAt, maid2, maid2ExpireAt, ownerId, renterId, renterName, ownerName,
   status, sellPrice, rentPrice, rentExpireAt, rentDays, …`
8. Confidence: **High** (keys known; note: full payload previously caused a JSON-cleanup
   heap crash — minimal safe field set still to be confirmed on ARM)

### Product / Goods
1. `product.city` (194) (+ weapon/equipment/drugs as goods supertypes)
2. `LoadProducts`
3. `CGoodsScreen::ParseBag`, `ParseWarehouse`, `ParseRareTool`, `ParseSpecialPrice`,
   `ParseYBComsumble`, `ParseAllGoodsForShowcaseUpload`
4. Present
5. **No** — all parsers read the player's **inventory** (bags/warehouse); `CGoods.type`
   references `product.city`
6. Class: **PLAYER_STATE**
7. JSON keys (CGoods, from SCHEMAS.md): `id, type, amount, category, boughtPrice,
   canUseTime, convertGoods`; `playerbags` → `{bags:[], goods:[]}`
8. Confidence: **High**

### Subject
Same as **School** (`subject.city`/`subject_type.city`, `LoadSubject*`,
`CSchoolScreen::ParseSubject`). Catalog client-local; enrollment is player state.
Confidence: **Medium**.

### Mission
1. `mission.city` (29)
2. `LoadMissions`
3. No screen `Parse*` (mission state lives in CPlayer; `CGameMissionManager` has no parser)
4. Mission progress parsed inside `CPlayer::Parse`; `updatemission` is an action
5. **No** — catalog client-local; only `missionId`/`missionProgress` (player) cross
6. Class: **PLAYER_STATE** (`missionId`, `missionProgress` in CPlayer) + **ACTION_RESPONSE**
   (`updatemission`)
7. JSON keys: `missionId`, `missionProgress` (CPlayer, already served)
8. Confidence: **High**

---

## Required conclusion table

| Subsystem | Asset Local | Network Required | Endpoint Class | Confidence |
|-----------|-------------|------------------|----------------|------------|
| School | Yes | player state only | PLAYER_STATE + ACTION | Medium |
| Crime | Yes | action only | ACTION_RESPONSE | High |
| Store | Yes | player/action | MIXED | Medium |
| Market | Yes | per-city stock (refs) | PLAYER_STATE / MIXED | High |
| Mine | Yes | bid/occupancy | PLAYER_STATE + ACTION | Medium |
| Mount | Yes | **none** | ASSET_ONLY | Medium |
| Achievement | Yes | progress | PLAYER_STATE | High |
| Estate | Yes | owned estates | PLAYER_STATE | High |
| Product/Goods | Yes | inventory | PLAYER_STATE | High |
| Subject | Yes | enrollment | PLAYER_STATE + ACTION | Medium |
| Mission | Yes | missionId/progress | PLAYER_STATE + ACTION | High |

**Every catalog is asset-local. No subsystem requires the server to send catalog rows.**

---

## Estimates

### Endpoints that can be deleted entirely
Routes whose only purpose was to *serve a catalog list* (the client already has it):
- **`/city/job/getjobs`** — confirmed dead (already neutralized).
- Any analogous "list-the-catalog" route is redundant. In practice the server has **few
  pure catalog-fetch routes** (most stubs are crash-guards, see below), so the count of
  truly *deletable* routes is **~1–3**. The larger win is **not implementing** new ones.

### Existing stubs that are unnecessary
- The entire **"ASSET-READY" category in ASSET_ENDPOINT_MAPPING.md (~11 groups / ~30
  catalogs)** does **not** need asset-serving work — catalogs are client-local. That
  planned effort is unnecessary.
- **`SERVE_ASSET_DATA` for catalog rows is moot** (e.g. pushing `product`/`gym_service`
  rows). Keep `getcitygoods` (it carries per-city stock state, not catalog rows).
- **Crash-guard `data:[]` stubs must stay** — they protect PLAYER_STATE/array endpoints
  that legitimately return empty lists; deleting them would re-introduce Class-A crashes.
- Net: ~30 catalog-serving *implementations* avoided; ~0 crash-guard stubs removable.

### Top 5 subsystems for further parser verification (highest value)
Chosen for: client actually calls the endpoint, it carries player state we must shape
correctly, and it unlocks gameplay:
1. **Estate** — `CPropertyCateScreen::Parse` + `CHouse`; keys known but the safe field set
   (avoid the JSON-cleanup heap crash) must be verified.
2. **Product/Goods** — `CGoodsScreen::ParseBag/ParseWarehouse`; core inventory; `playerbags`
   already partly shaped.
3. **Market** — `ParseGoodsAmount` (`goodsList/category/type/amount` known); enables trading.
4. **School** — `CSchoolScreen::ParseSubject` + `getmyclasses`/`applyclass`; enrollment state.
5. **Mission** — `CPlayer` mission fields + `updatemission`; drives story progression.

(Job & Gym are already fully verified; Crime/Mine/Store/Mount are lower priority —
action-only or pure client-side.)

---

## Bottom line

The job/gym pattern **generalizes to the whole game**: `.city` catalogs are a client-side
content pack; the server's role is **player state + action results**, referencing catalogs
by id. Future endpoint work should target **player-state shaping** (Estate, Goods, Market,
School, Mission), not catalog serving — and parser verification should precede any
`server.py` change, exactly as done for Job and Gym.
