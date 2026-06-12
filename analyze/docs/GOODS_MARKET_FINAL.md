# GOODS_MARKET_FINAL.md — Verified Goods/Market Subsystem Contract

Binary-verified (libcity_ar.so v1.1.38), JOB→GYM→ESTATE methodology. Reused the symbol DB
(targeted greps) + fresh disassembly of the goods/market parsers; all JSON keys resolved
deterministically against PIC base `0x75ab20`. Vtable: `+0x14`=begin-iterator (ARRAY),
`+0x40`=GetObjectItem; int64 helper `0x69300c`. Shared array-parser helpers:
`0x69d34c`=goods-list, `0x69d36c`=bags-list, `0x69d37c`/`0x69d35c`=specialities,
`0x6a607c`/`0x6a5e1c`=tradeGoods.

---

## 1. Ownership split (verified)

| Catalog | ids | Loader (client-local) |
|---------|-----|----------------------|
| `product.city` (194) | 600–823 | `CGameData::LoadProducts` |
| `weapon.city` (274) | 200–499 | `CGameData::LoadWeapons` |
| `equipment.city` (223) | 300–596 | `CGameData::LoadArmors` |
| `drugs.city` (21) | 500–525 | `CGameData::LoadDrugs` |
| CB weapon / special goods | — | `LoadCBWeapon`, `LoadDummySpcialGoods`, `LoadSpecialGoodsHouse` |

**All catalogs are client-local** (no endpoint sends rows). Note weapon (200–499) and
equipment (300–596) **id ranges overlap** → the runtime `category` field disambiguates
which catalog a `type` id resolves against. **ASSET_ONLY.**

---

## 2. Screens & parsers (verified symbols)

| Screen / model | Parsers |
|----------------|---------|
| `CGoodsScreen` | `OnReceiveResponse`, `ParseBag`, `ParseWarehouse`, `ParseSpecialPrice`, `ParseRareTool`, `ParseYBComsumble`, `ParseAllGoodsForShowcaseUpload` |
| `CMarketScreen` / `CMarketCateScreen` | `OnReceiveResponse`, `ParseGoodsAmount` |
| `CGoodsBuyScreen` / `CGoodsSellScreen` / `CGoodsSelltoNPCScreen` / `CGoodsLockInScreen` / `CBlackMarketScreen` / `CEquipmentScreen` | `OnReceiveResponse` (+`ParseBag`/`ParseWarehouse` on CEquipmentScreen) |
| `CGoods` (model) | `Parse`, `ParseDeal`, `ParseReward`, `ParseShowcase`, `ParseYBConsumble`, `ParseGoodsOfExtra` |
| `CPlayer` | `ParseGoods`, `ParseBags`, `ParseNormalDropGoods` |

---

## 3. Verified JSON keys & containers

### `CGoods::Parse` @0x40cc70 — one goods item (OBJECT)
```
id  type  amount  category  boughtPrice  canUseTime  convertGoods
```
All `GetObjectItem` null-guarded. Matches SCHEMAS.md exactly.

### `CMarketCateScreen::ParseGoodsAmount` @0x4c2fe8 — market/city stock
`GetObjectItem("goodsList")` → **ARRAY** (begin-iter); each element:
`{ category, type, amount }`.
⇒ `data = { "goodsList": [ {category, type, amount}, … ] }`. **OBJECT containing ARRAY.**

### `CGoodsScreen::ParseBag` @0x41c43c — bag (OBJECT containing ARRAYS)
`GetObjectItem("playerGoods")` → bags-array helper; `GetObjectItem("specialities")` → array.
⇒ `data = { "playerGoods": [CGoods…], "specialities": [...] }`.

### `CGoodsScreen::ParseWarehouse` @0x41c380 — warehouse (OBJECT containing ARRAYS)
`GetObjectItem("playerGoods")` → goods-array; `GetObjectItem("tradeGoods")` → array;
`GetObjectItem("specialities")` → array.
⇒ `data = { "playerGoods": [CGoods…], "tradeGoods": [CGoods…], "specialities": [...] }`.

### `CPlayer::ParseGoods` @0x516180 / `ParseBags` @0x516194 — player payload inventory
Tiny delegators to the array helpers. The CPlayer payload carries **`goods`** (array) and
**`bags`** (array) of CGoods — these are the **connect/create** keys, distinct from the
goods-screen keys above.

### Action dispatchers
- `CGoodsBuyScreen::OnReceiveResponse` (purchase): `excess`, `gold`, `mercenaryExp`,
  `huntCoin` — currency deltas.
- `CGoodsScreen::OnReceiveResponse` (use/equip): `boughtPrice`, `expiredAt`.
- `CMarketCateScreen::OnReceiveResponse`: `idx`.
- `CGoodsSellScreen` / `CMarketScreen::OnReceiveResponse`: no named keys (delegate to the
  goods-array / ParseGoodsAmount paths).

---

## 4. Field provenance (task 8)

| Field | Source | Notes |
|-------|--------|-------|
| `type` | **server (references catalog id)** | product 600–823 / weapon 200–499 / equipment 300–596 / drugs 500–525 |
| `category` | **server (selects which catalog)** | disambiguates the overlapping weapon/equipment ranges |
| `amount` | **server runtime** | quantity |
| `boughtPrice`, `canUseTime`, `convertGoods`, `expiredAt` | **server runtime** | **amount is NOT the only runtime field** — these per-instance fields also cross the wire |

The catalog rows (name/price/stats) stay **client-local**; the network sends a CGoods
*instance* (`type`+`category` reference + runtime fields), merged client-side by id.

---

## 5. Endpoint classification

| Endpoint | Parser | Class | Container |
|----------|--------|-------|-----------|
| catalogs (product/weapon/equipment/drugs) | `CGameData::Load*` | **ASSET_ONLY** (client-local) | n/a |
| `/city/goods/getcitygoods` | `ParseGoodsAmount` | **PLAYER_STATE / MIXED** (per-city stock, refs catalog) | object `{goodsList:[…]}` |
| `/city/goods/playerbags` | `CGoodsScreen::ParseBag` | **PLAYER_STATE** | object `{playerGoods:[],specialities:[]}` |
| `/city/goods/playergoods` / warehouse | `CGoodsScreen::ParseWarehouse` | **PLAYER_STATE** | object `{playerGoods:[],tradeGoods:[],specialities:[]}` |
| goods buy | `CGoodsBuyScreen::OnReceiveResponse` | **ACTION_RESPONSE / MIXED** | object (currency deltas) |
| goods sell | `CGoodsSellScreen::OnReceiveResponse` | **ACTION_RESPONSE / MIXED** | object |
| CPlayer payload `goods[]`/`bags[]` | `CPlayer::ParseGoods/ParseBags` | PLAYER_STATE | arrays |

---

## 6. Container expectations (task 6/7 summary)

| Structure | Container |
|-----------|-----------|
| `goodsList` (market/city stock) | **ARRAY** of `{category,type,amount}` inside object |
| bag inventory | object with **ARRAY** `playerGoods` + `specialities` |
| warehouse | object with **ARRAYS** `playerGoods`, `tradeGoods`, `specialities` |
| CPlayer `goods` / `bags` | **ARRAYS** of CGoods |
| a CGoods element | **OBJECT** (7 keys) |

---

## 7. Minimal valid payloads (task 9)

CGoods element (reused below): `{ "id":<n>, "type":<catalogId>, "amount":<n>,
"category":<cat>, "boughtPrice":0, "canUseTime":0, "convertGoods":0 }`.

```
getcitygoods   → { "goodsList": [ {"category":<cat>,"type":600,"amount":99} ] }
                 (minimal-safe: { "goodsList": [] })
market list    → same as getcitygoods (ParseGoodsAmount)
warehouse      → { "playerGoods": [CGoods…], "tradeGoods": [], "specialities": [] }
                 (minimal-safe: { "playerGoods": [] }  — or {} )
bag (playerbags)→ { "playerGoods": [CGoods…], "specialities": [] }
                 (minimal-safe: { "playerGoods": [] }  — or {} )
purchase result→ { "gold": <new>, "excess": 0, "mercenaryExp": 0, "huntCoin": 0 }
                 (minimal-safe: {} ; populate to update currencies/inventory)
sell result    → { } (money/goods refresh; minimal-safe {} )
CPlayer payload→ "goods": [CGoods…], "bags": [CGoods…]   (already arrays in _make_player)
```
All keys null-guarded ⇒ `data:{}` never crashes; populate to make the screen show data.

---

## 8. Class-A risks & shape mismatches (task 10)

**Class-A (array-iterator) requirements — these keys, IF present, MUST be arrays:**
`goodsList`, `playerGoods`, `tradeGoods`, `specialities`, and CPlayer `goods`/`bags`.
All are begin-iterated (`+0x14`); a non-array (`{}`) value ⇒ null-iterator SIGSEGV.
(Current `_make_player` `goods:[]`/`bags:[]` and `getcitygoods {goodsList:[]}` are correct.)

**Shape mismatch (like Estate) — CONFIRMED, non-crashing:**
`/city/goods/playerbags` currently returns `{ "bags":[], "goods":[] }`, but
`CGoodsScreen::ParseBag` reads **`playerGoods`** and **`specialities`**. The wrong keys are
simply not found (object-accessor null-guarded) ⇒ **no crash, but the bag shows empty**.
To actually populate the bag, use `{ "playerGoods":[…], "specialities":[…] }`. Same for
warehouse (`playerGoods`/`tradeGoods`/`specialities`).
Note: `goods`/`bags` are **correct** for the *CPlayer payload* (connect/create) — only the
*goods-screen* endpoints use the `playerGoods`/`tradeGoods` keys. Don't confuse the two.

**No bare-array-vs-object hazard** (unlike Estate `listestates`): getcitygoods/playerbags
are already correctly object-shaped; the only issue is the key names for the inventory
screens.

---

## 9. Confidence

- CGoods keys, `goodsList`/bag/warehouse keys & containers: **High** (deterministically
  resolved; `+0x14` array markers observed).
- Purchase currency keys (`excess/gold/mercenaryExp/huntCoin`): **High** (resolved).
- `category` exact value semantics (which int = which catalog class): **Medium** (key
  verified; the numeric mapping to food/weapon/etc. not enumerated here).
- goods/market command ids: **not extracted** (dispatchers use non-uniform compares; not
  required to shape the payloads — endpoints are keyed by path here).

Success criterion met: field names, ids referenced, containers, and payload shapes for
every Goods/Market endpoint are verified — implementable without guessing. The one
actionable correction (no change made): inventory endpoints need `playerGoods`/
`specialities`/`tradeGoods`, not `bags`/`goods`.
