# ASSET_ENDPOINT_MAPPING.md — Which Endpoints Can Be Served From Local Assets

Classifies every gameplay endpoint by whether it can be satisfied **entirely from
the decoded `.city` catalogs** (no additional network-traffic reverse engineering),
using the data layer in `local-server/python/city_loader.py` (see `ASSET_SCHEMA.md`).

## Classification key

- **ASSET-SERVABLE** — a `.city` catalog supplies the records AND the JSON key names
  the parser expects are known (from SCHEMAS.md) or trivially inferable. Real data
  can be served now.
- **ASSET-READY (keys unverified)** — a catalog exists, but the exact JSON field
  names the network parser reads are not yet confirmed. Data exists; serving it
  correctly needs one parser-field check (binary, not network capture).
- **DYNAMIC** — no static catalog; the list is server-generated at runtime
  (random/live players). Cannot come from assets; stays a stub or needs game logic.
- **CONFIG (impart)** — belongs in the `/city/impart` 201-key config blob, which is
  partly asset-derived (the `*Types` arrays mirror `.city` tables).

---

## 1. ASSET-SERVABLE now (keys known)

| Endpoint | Catalog(s) | JSON shape (keys) | Status in server.py |
|----------|-----------|-------------------|---------------------|
| `/city/goods/getcitygoods` | `product` (194) | `{goodsList:[{category,type,amount}]}` | **WIRED** (behind `SERVE_ASSET_DATA`) |

`getcitygoods` is the proven end-to-end path: `type` = real `product.city` id (600+),
shape from SCHEMAS.md:81. Default-off so the frozen-safe empty baseline is unchanged;
`SERVE_ASSET_DATA=1` serves all 194 products.

---

## 2. ASSET-READY (catalog exists; verify parser keys first)

These have real catalogs and disjoint, resolvable ids; the only gap is confirming the
JSON key names each parser reads (a one-function binary check per endpoint — **not**
network capture). Listed by gameplay value.

| Endpoint | Catalog(s) | Records | Parser to field-check |
|----------|-----------|---------|------------------------|
| ~~`/city/job/getjobs`~~ | — | — | **RESOLVED: not a real endpoint — see below** |
| `/city/estate/listestates` *(owned)* / estate type list | `property` | 18 | CPropertyCateScreen::Parse — ⚠ heap-corruption risk with full CHouse (see note) |
| `/city/crime/*` (target list) | `crime` + `crime_type` | 83 + 17 | CCrimeScreen |
| `/city/gym/getgym` | `gym_service`, `gym_type`, `gym_service_cost`, `gym_item` | 15/3/26/31 | CGymScreen::ParseResponse |
| `/city/school/subjects` | `subject` + `subject_type` | 35 + 5 | CSchoolCateScreen |
| `/city/goods/market*` | `product`,`weapon`,`equipment`,`drugs` | 712 total | CMarketScreen::ParseGoodsAmount |
| `/city/store/*` | `gift`,`gold_package`,`paid_tool` | 551 total | CStoreCateScreen / CStorePackage |
| `/city/mine/*` | `mine` + `mineshop` | 150 + 7 | CMS_MineMainScreen |
| `/city/rank/*` (categories) | `rank` + `rank_type` | 67 + 10 | CRankCateScreen |
| mounts / mercenary growth | `mounts`, `yb_*` | 415 + … | CMercenaryMnger etc. |
| achievements | `achievement` (+ `_skill`) | 893 | CAchievementScreen::ParseAchievements |

**Estate note:** `server.py` records that returning a full `_make_house()` array on
`/city/estate/listestates` caused heap corruption during JSON cleanup (fault
`0x756f707b`). Estate data is asset-ready but must be served with a **minimal verified
field set**, validated on ARM — not bulk-populated blind.

---

## 3. CONFIG (impart) — asset-mirrored

`/city/impart` (CImpart, 201 keys) contains `*Types` arrays that mirror `.city`
tables: `jobTypes`←`job_type`, `crimeTypes`←`crime_type`, `estateTypes`←`property`,
`gymTypes`←`gym_type`, `drugTypes`←`drugs`, `mountsTypes`←`mounts`, `cuisines`, etc.
These can be **populated from assets** once each array's element schema (from
`SCHEMAS.md` §impart) is matched to the catalog columns. Currently `data:{}` (safe;
client falls back to bundled `.city`).

---

## 3b. RESOLVED via binary verification — `/city/job/getjobs` is NOT an endpoint

Verified in `JOB_PARSER_FINAL.md`: no `getjobs`/`jobs`/`jobId` string exists in the
binary; `CHrMarketCateScreen::OnReceiveResponse` handles only command 285 (work) and
284 (salary). The **job catalog is loaded client-side** from `job.city`/`job_type.city`
by `CGameData::LoadJobs`/`LoadJobTypes` and rendered by `GetJobList` — the server sends
no job list. The route is now a never-reached empty array (speculative fields removed).

The real, action-only job endpoints:
| Endpoint | Command | Parser | Verified keys |
|----------|---------|--------|---------------|
| `/city/job/work` | 285 | `ParseDoJobResponse` | result int + reward-item array (unnamed in body) |
| salary query | 284 | `ParseGetSaleryResponse` | `money`, `salaryAt` |

Player job *state* = the job-category object map in CPlayer (`ParseJobCategoryInfo`,
object keyed by job-type id); safely omitted today (null-guarded).

This is the model for the other ASSET-READY entries: **verify the parser before serving**
— several may likewise turn out to be client-local or action-only.

## 4. DYNAMIC — cannot be served from assets

No `.city` catalog backs these; the original server generated them from live player
state. They stay stubs (`data:[]`) or need synthesized game logic, not assets.

| Endpoint | Nature |
|----------|--------|
| `/city/gang/randomgangs` | random gang roster |
| `/city/hospital/patients` | live injured players |
| `/city/jail/prisonerlist` | live jailed players |
| `/city/marital/candidates` | live eligible players |
| `/city/fight/randomfighters` | random PvP targets |
| `/city/chat/*` | live chat stream |
| `/city/friend/getfriends` | this account's social graph |
| `/city/player/getranking` | live leaderboard standings |
| `/city/event/list`, `/city/player/logingifts` | time/server-state driven |

`/city/airline/airlines` is **partly** asset-backed (the `cities` table, currently
ambiguous-decode) but also carries live flight state — treat as DYNAMIC until `cities`
is fully decoded.

---

## 5. Summary

| Class | Endpoints | Asset source |
|-------|-----------|--------------|
| ASSET-SERVABLE (wired) | 1 (`getcitygoods`) | `product` |
| ASSET-READY (verify keys) | ~11 endpoint groups | 30+ catalogs, ~5,000 records |
| CONFIG (impart arrays) | 1 blob, ~40 arrays | mirrors ~20 catalogs |
| DYNAMIC (no assets) | ~12 | none — runtime/live |

**Bottom line:** the static, single-player-meaningful content of the game — jobs,
crimes, gym, school, market goods, store, estates, mounts, mine, achievements,
missions — is **fully present in local assets** and now loaded. The only endpoints
that genuinely require network/runtime reverse engineering are the **DYNAMIC**
multiplayer/live lists. Per the project constraint, populating the ASSET-READY group
should be driven by ARM-device validation of the JSON key sets, one parser at a time.
