# ASSET_SCHEMA.md — Waker `.city` Catalog Data Layer

Reverse-engineered schema of every `assets/*.city` config table, the decoder, the
loaded data layer, and the entity-relationship map. Source assets:
`analyze/baseline-apk-src/assets/` (93 `.city` files). Decoder/loader:
`analyze/tools/city_extract.py`, `local-server/python/city_loader.py`.
Decoded JSON snapshot: `local-server/python/gamedata/` (committed).

---

## 1. Asset Format Census (`assets/`)

| Type | Count | Role |
|------|-------|------|
| `.png` | 3544 | sprites / UI / NPC / building art |
| `.wav` / `.mp3` | 138 | audio |
| `.jpg` | 128 | backgrounds |
| `.json` | 102 | client UI layout / particle / atlas configs |
| **`.city`** | **93** | **binary gameplay catalog tables (this document)** |
| `.bin` | 44 | packed binary (atlas / mesh) |
| `.psi` | 20 | particle system definitions |
| `ar` | 1 | localized string table (Arabic); string-ids resolve here client-side |
| misc | ~6 | `.ttf .package .dri .drf .buipj .bsprites .payssion` |

The gameplay data layer is the **93 `.city` tables**. Localized text is **not** in
`.city` — records carry numeric **string-ids** that the client resolves against the
bundled `ar` table locally (so the server sends ids, the client renders text).

---

## 2. `.city` Binary Format (recovered)

```
offset 0   u16  COUNT            (big-endian record count)
offset 2   COUNT × record
record     ordered fixed schema of fields, each:
             int     -> u32 big-endian
             string  -> u32 big-endian length L, then L ASCII/UTF-8 bytes
```

- Endianness: **big-endian** throughout.
- The **first field of every record is the `id`** — the `GetById(0x69341c)` lookup
  key (confirmed against SCHEMAS.md: "loader reads id (BE32) first").
- The per-file field schema (order/types) is **not stored**; it is inferred by the
  decoder and validated by requiring the file to parse into exactly `COUNT` records
  with zero trailing bytes.
- Strings may appear mid-record (e.g. `job` = `iiisi` → id, jobTypeId, nameStrId,
  name, tail).

### Worked example — `job.city` (`iiisi`, 54 records)
```
{id:1200, f1:1300, f2:474, name:"ShuaWanGong", f4:2530}
       │      │       │           │                └ tail id (+1/record)
       │      │       │           └ romanized key (display via nameStrId→ar)
       │      │       └ nameStrId (474→ar)
       │      └ jobTypeId  →  job_type.id (1300 = "CanTing")
       └ id (GetById key, +1/record)
```

### Decode coverage
- **80 / 93 decoded** (fixed schema fully recovered).
- **13 ambiguous** — variable-length records (per-row optional/list fields):
  `ForceGenerator_data, HG_Animal, HG_HuntTool, HG_TransportTool, RG_car,
  RG_component, RG_map_data, ThemeGift, cities, mercenary, pseudo_target,
  yb_class, yb_consumable`. All are non-core (racing / hunt / mercenary). The
  loader still extracts their id + name tokens via a raw-token fallback.

---

## 3. Master Catalog Table (filename · count · schema · id-range · sample name)

Schema legend: `i`=u32 int, `s`=length-prefixed string. Status `decoded`=full schema,
`ambiguous`=variable layout (tokens only).

| File | Records | Schema | Status | id range | Sample |
|------|---------|--------|--------|----------|--------|
| FF_boss_type | 2 | iiiiiiis | decoded | 1-2 | |
| FG_awaken_consume | 25 | iiiiii | decoded | 1-25 | |
| FG_awaken_material | 5 | iii | decoded | 1-5 | |
| FactionFactory_data | 132 | iiiiiiiiiiii | decoded | 1-132 | |
| FactionFactory_exp | 59 | i | decoded | 18-11690200 | |
| ForceGenerator_data | 3 | — | ambiguous | — | |
| ForceGenerator_exp | 499 | i | decoded | 200-8267000 | |
| HG_Animal | 30 | — | ambiguous | — | |
| HG_AnimalEvent | 11 | iii | decoded | 1-11 | |
| HG_HuntMap | 1 | iiisisssis | decoded | 1-1 | hunt_showMap1 |
| HG_HuntTool | 12 | — | ambiguous | — | |
| HG_ImageBg | 3 | isisss | decoded | 1-3 | hunt_search1 |
| HG_SpoilsGoods | 131 | iiisiii | decoded | 1-135 | hunt_animal1_drop1 |
| HG_TransportTool | 11 | — | ambiguous | — | |
| PersonActive_data | 28 | iiiiisii | decoded | 1-28 | |
| RG_car | 35 | — | ambiguous | — | |
| RG_component | 220 | — | ambiguous | — | |
| RG_cptType | 37 | iiii | decoded | 1-22 | |
| RG_dungeon | 18 | iisisiiiiiii | decoded | 1-18 | RG_map_01 |
| RG_map_data | 7 | — | ambiguous | — | |
| RG_skin | 5 | iiiiiiiii | decoded | 1-5 | |
| SW_BuildAdjacent | 15 | isssssss | decoded | 0-14 | |
| Strengthen | 4 | iiiiiiiiiii | decoded | 1901-487424 | |
| achievement | 893 | iiiis | decoded | 201-1610 | gongji_fadonggongji_1 |
| achievement_skill | 31 | iiisii | decoded | 1-33 | JiNeng_WuQiJingTong |
| activity_extra | 564 | iiiii | decoded | 94-280 | |
| addition | 19 | iiiii | decoded | 1-19 | |
| appellation_effect | 17 | iiii | decoded | 0-16 | |
| building_lock | 23 | iii | decoded | 0-38 | |
| cb_effect | 9 | iiiiii | decoded | 1-9 | |
| cbweapon | 9 | iisii | decoded | 2000-2008 | cbweapon_1 |
| circle_node | 5 | iii | decoded | 0-4 | |
| cities | 13 | — | ambiguous | — | |
| crime | 83 | iiisiiiii | decoded | 100-182 | HuoCheZhan |
| crime_type | 17 | iisii | decoded | 1-17 | SouSuoJieDao |
| drugs | 21 | iiiisiii | decoded | 500-525 | cannabis |
| dungeon | 4 | iiiiii | decoded | 1-4 | |
| equipment | 223 | iiisii | decoded | 300-596 | JiaKe |
| exchange_ctrl | 12 | iiiiii | decoded | 242-253 | |
| exchange_extra | 5 | iiiiii | decoded | 401-405 | |
| exchange_need | 926 | iiiiiiiii | decoded | 1-1001 | |
| exchange_type | 16 | iis | decoded | 1-18 | market_huodong |
| exp | 550 | i | decoded | 50-2121011000 | |
| faction_store | 8 | iiiiii | decoded | 0-7 | |
| faction_yb_popedom | 6 | iii | decoded | 0-5 | |
| function_tool | 79 | iiisiii | decoded | 700-784 | hunjie |
| fund | 4 | iiiiii | decoded | 1-4 | |
| gift | 239 | iisiii | decoded | 1701-2541 | shangcheng_QianXiang |
| gold_package | 17 | iiisiiiiiii | decoded | 1-20 | shangcheng_jintiao |
| guild_skills | 19 | iiiisi | decoded | 1-19 | JiNeng_BeiDongLiLiang |
| gym_item | 31 | iisiiisiis | decoded | 1100-1130 | JianShenFang1 |
| gym_service | 15 | iisiiiii | decoded | 1-15 | coach_gedou |
| gym_service_cost | 26 | iiii | decoded | 1-26 | |
| gym_type | 3 | iisi | decoded | 1-3 | JianShenFang_putong |
| job | 54 | iiisi | decoded | 1200-1253 | ShuaWanGong |
| job_type | 9 | iis | decoded | 1300-1311 | CanTing |
| king_appellation | 16 | iisii | decoded | 0-15 | |
| mercenary | 56 | — | ambiguous | — | |
| militia | 7 | iis | decoded | 1-7 | militia_lv1 |
| mine | 150 | iiisii | decoded | 1-150 | yb_mine_high |
| mineshop | 7 | iiiiii | decoded | 1-7 | |
| mission | 29 | iiiiiiiiiiiiii | decoded | 1-35 | |
| mounts | 415 | iisii | decoded | 1401-1857 | gongwenbao |
| paid_tool | 295 | iiisiiiiiii | decoded | 1-1002 | shangcheng_MeiYuan |
| paid_tool_extra | 2 | iiii | decoded | 1001-1002 | |
| payssion_ru_data | 25 | isssi | decoded | 1-25 | CASHU |
| product | 194 | iiisiiiiiiii | decoded | 600-793 | TuoNiaoDan |
| property | 18 | iiiiiiiiiisi | decoded | 800-817 | CaoPeng |
| pseudo_target | 111 | — | ambiguous | — | |
| rank | 67 | iisiiiiiii | decoded | 0-68 | BangPaiShengWang |
| rank_type | 10 | iisii | decoded | 1-10 | Rank_weekly |
| repair_type | 28 | iisi | decoded | 900-927 | ZhaoMing |
| showcase_bg | 10 | iisi | decoded | 1-10 | showbox_ud_lovelypink |
| slave | 24 | iisi | decoded | 1000-1023 | XiaoShiGong |
| slot | 19 | iiiii | decoded | 0-18 | |
| subject | 35 | iiisiiii | decoded | 1600-1634 | falv |
| subject_type | 5 | iis | decoded | 1500-1504 | falv |
| tools_effect | 53 | iiiii | decoded | 1-1006 | |
| transition | 21 | iiiiiiii | decoded | 1-21 | |
| weapon | 274 | iiisii | decoded | 200-499 | DanGong |
| yb_brainWash | 3 | iii | decoded | 1-3 | |
| yb_chip | 56 | iisiiii | decoded | 20001-20056 | a_mercenary1_1 |
| yb_class | 272 | — | ambiguous | — | |
| yb_consumable | 2 | — | ambiguous | — | |
| yb_fight_effect | 4 | iiisisi | decoded | 1-4 | fight_red.psi |
| yb_level_exp | 498 | i | decoded | 3-249000 | |
| yb_property | 5 | iisiiiii | decoded | 1-5 | yb_property_01 |
| yb_screen_tip | 12 | iiiiiii | decoded | 1-12 | |
| yb_skill_exp | 5 | i | decoded | 200-5000 | |
| yb_skill_provide | 6 | ii | decoded | 0-5 | |
| yb_star | 5 | iiiiii | decoded | 1-5 | |
| yb_upstar_factor | 3 | iiiii | decoded | 1-3 | |

---

## 4. Entity-Relationship Map

ID-ranges are disjoint per entity, which is how cross-table references resolve.

```
                         ┌─────────────┐
       ar string table ◄─┤ nameStrId   │  (every catalog row → localized text,
       (assets/ar)       │ on all rows │   resolved CLIENT-side)
                         └─────────────┘

 JOBS         job (1200-1253) ──jobTypeId──► job_type (1300-1311)
 SCHOOL       subject (1600-1634) ──f1──► subject_type (1500-1504)
 ESTATES      CPlayer.estates[].estateType ──► property (800-817, CaoPeng=800)
 GOODS        CGoods.type ──► one of:
                  product (600-793)  weapon (200-499)  equipment (300-596)
                  drugs (500-525)    function_tool (700-784)  paid_tool
 CRIME        crime (100-182) ──f1──► crime_type (1-17)
 GYM          gym_service (1-15) ─► gym_type (1-3), gym_service_cost (1-26),
                  gym_item (1100-1130)
 MISSIONS     mission (1-35) ── f2/f3/f4 ──► ar string-ids (title/desc/tip)
                  └ f10 = target id (job/crime/goods depending on f1 type)
 MARKET       exchange_type (1-18) ─► exchange_need (1-1001), exchange_ctrl
 RANK         rank (0-68) ──► rank_type (1-10)
 MOUNTS       mounts (1401-1857)
 SLAVE/MAID   slave (1000-1023)  (estate maid1/maid2 slots)
 MINE         mine (1-150) ─► mineshop (1-7)
 RACING       RG_dungeon, RG_skin, RG_cptType (+ ambiguous RG_car/component/map)
 HUNT         HG_HuntMap, HG_SpoilsGoods, HG_AnimalEvent (+ ambiguous HG_*)
 MERCENARY    yb_* family (yb_chip, yb_property, yb_star…) (+ ambiguous yb_class)
```

### Entities WITHOUT a static catalog (server-generated / dynamic)

These have **no `.city` table** — their lists are produced at runtime by the live
server, so they **cannot** be sourced from assets:

| Entity | Endpoint | Why dynamic |
|--------|----------|-------------|
| Gangs | `/city/gang/randomgangs` | random per-request roster |
| Hospital patients | `/city/hospital/patients` | live injured players |
| Prisoners | `/city/jail/prisonerlist` | live jailed players |
| Marriage candidates | `/city/marital/candidates` | live eligible players |
| Fighters | `/city/fight/randomfighters` | random PvP targets |
| Airlines/destinations | `/city/airline/airlines` | partly `cities` (ambiguous) + live state |

(See `ASSET_ENDPOINT_MAPPING.md` for the full endpoint classification.)

---

## 5. Loaded Data Layer (`city_loader.py`)

- `load_catalogs()` → `{name: Catalog}`; prefers a live `.city` dir
  (`CITY_ASSETS_DIR`) else the committed `gamedata/` JSON.
- `Catalog.records` (list of dicts), `.by_id(id)`, `.ids()`, `.count`, `.schema`.
- Wired into `server.py` as `GAMEDATA`; inspect live via
  `GET /debug/gamedata` (summary) or `?table=job` (full records).
- Real data is served from endpoints only when `SERVE_ASSET_DATA=1`
  (default off — preserves the frozen-safe boot baseline; populated responses
  are validated on ARM, not the emulator).
