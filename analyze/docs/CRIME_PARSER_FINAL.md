# CRIME_PARSER_FINAL.md — Verified Crime Subsystem Contract

Binary-verified (libcity_ar.so v1.1.38), JOB→GYM→ESTATE→GOODS→SCHOOL→MISSION methodology.
Reused the symbol DB (targeted greps) + fresh disassembly; all JSON keys resolved
deterministically against PIC base `0x75ab20`. Vtable: `+0x14`=begin-iterator (ARRAY),
`+0x40`=GetObjectItem; int64 helper `0x69300c`.

---

## 1. Ownership (verified)

| Catalog | rows / ids | Loader (client-local) |
|---------|-----------|----------------------|
| `crime.city` (83) | 100–182 | `CGameData::LoadCrimes` |
| `crime_type.city` (17) | 1–17 | `CGameData::LoadCrimeTypes` |
| `drugs.city` (21) | 500–525 | `CGameData::LoadDrugs` |

All **client-local**. `crime.f1` → `crime_type.id`; `crime.f2` = `assets/ar` string-id;
`crime.f4` (≈708) = target/reward ref; `crime.f5/f6/f7` = stat thresholds. Crime config is
also parsed from impart by `CImpart::ParseCrimes` / `ParseCrimeTypeRewardType`. The crime
*list* is built client-side. **ASSET_ONLY** — no endpoint sends rows.

---

## 2. Screens & parsers (verified symbols)

| Symbol | Role |
|--------|------|
| `CCrimeScreen::DoCrime` @0x369c58 | sends the crime request (crime id) |
| `CCrimeScreen::OnReceiveResponse` @0x36ad28 | dispatcher (cmd 232) |
| `CCrimeScreen::ParseDoCrimeResponse(data, char h)` @0x36a0bc | **the** crime result parser |
| `CCrimeScreenModel` / `CCrimeScreenRender` | UI/model (no network) |
| `CPlayer::ParseCrimeSkills` @0x5161b4 | player crime-skill array |
| `CPlayer::ParseDrugInfo` + drug buff getters/setters | drug poison/buff state (sub-system) |

**The only crime response parser is `ParseDoCrimeResponse`** — crime is action-only.

---

## 3. Verified network contract

### `CCrimeScreen::ParseDoCrimeResponse(data, h)` @0x36a0bc
- `h != 0`: reads the wrapper `GetObjectItem("crimeResult")` and parses fields from it.
- `h == 0` (the path `OnReceiveResponse` uses): parses fields directly from `data`.
- Fields (all `GetObjectItem` → GetInt64, **null-guarded**, **no array iteration**):

```
result            awardType         awardMoney        awardCheque
awardGoodsType    awardGoodsCategory  awardGoodsAmount  awardExp
statusDuration    lostToolFlag      blood             consumeNum
```
(`[%s x %d]`, `%lld` are format strings, not keys.) Container: **OBJECT** of scalars,
optionally wrapped in a `crimeResult` object. `awardGoods{Type,Category,Amount}` mirror a
single CGoods reward (type+category reference the goods catalogs; **not an array**).

### `CCrimeScreen::OnReceiveResponse` @0x36ad28
Dispatches on **`cmd 0xe8 (232)`** and calls `ParseDoCrimeResponse` with `h=0`.

### `CPlayer::ParseCrimeSkills` @0x5161b4
`begin-iter` (+0x14) over an **ARRAY**; each element `{ crimeIdx, crimeNum }` — the
player's per-crime experience (`crimeIdx` → `crime.city` id, `crimeNum` = times committed).

---

## 4. JSON keys (complete)

| Payload | Keys | Container |
|---------|------|-----------|
| docrime result | `result`, `awardType`, `awardMoney`, `awardCheque`, `awardGoodsType`, `awardGoodsCategory`, `awardGoodsAmount`, `awardExp`, `statusDuration`, `lostToolFlag`, `blood`, `consumeNum` (optionally under `crimeResult`) | object of scalars |
| CPlayer crime skills | array of `{crimeIdx, crimeNum}` | array |
| CPlayer crime scalars | `crimeSuccess`, `crimeTimes`, `thriceNum`, `jailHalved`, `coolingTime` | scalars |

---

## 5. State / progress / cooldown / target lists (task 5)

- **Stateful or action-only:** the **network** side is **action-only** (`docrime`). Crime
  *state* lives in CPlayer (scalars + the crime-skills array).
- **Progress stored?** Yes — `CPlayer.crimeSkills[]` (`{crimeIdx, crimeNum}`) tracks per-crime
  counts; plus `crimeTimes`, `thriceNum`, `crimeSuccess`.
- **Cooldowns stored?** Yes — the result's `statusDuration` sets the post-crime cooldown,
  reflected in `CPlayer.playerStatus` (statusDuration) and `CPlayer.coolingTime`. There is
  **no separate cooldown endpoint**.
- **Target lists?** No network list — built client-side from `crime.city`.

---

## 6. Endpoint classification

| Endpoint | Parser | Class | Container |
|----------|--------|-------|-----------|
| crime / crime_type / drugs catalog | `CGameData::Load*` | **ASSET_ONLY** | n/a |
| `/city/crime/docrime` (cmd 232) | `ParseDoCrimeResponse` | **ACTION_RESPONSE / MIXED** (awardGoods refs catalog; updates player money/exp/status) | object of scalars |
| CPlayer crime state | `ParseCrimeSkills` + scalars | **PLAYER_STATE** | array + scalars |

No crime *list* endpoint and no separate reward/cooldown endpoint exist.

---

## 7. Containers (task 7)

| Item | Container |
|------|-----------|
| crime list | n/a over network (client builds from `crime.city`) |
| crime execution result | **OBJECT** of scalars (optionally wrapped in `crimeResult`) |
| reward | scalar fields inside the result (`awardMoney/Cheque/Exp` + single `awardGoods*`) |
| cooldown | scalar `statusDuration` inside the result |
| crime skills (CPlayer) | **ARRAY** of `{crimeIdx, crimeNum}` |

---

## 8. Minimal valid payloads

```
crime list        → (no endpoint; client uses crime.city + crime_type.city)
crime execution   → request only (DoCrime sends the chosen crime id)
crime result      → SUCCESS:
  { "result": 1, "awardType": 1, "awardMoney": 1000, "awardCheque": 0,
    "awardGoodsType": 0, "awardGoodsCategory": 0, "awardGoodsAmount": 0,
    "awardExp": 50, "statusDuration": 60, "lostToolFlag": 0, "blood": 0,
    "consumeNum": 0 }
  CAUGHT/FAIL:
  { "result": 0, "blood": 20, "statusDuration": 300, "lostToolFlag": 1 }
reward collection → part of the crime result (no separate endpoint)
cooldown update   → `statusDuration` in the crime result (no separate endpoint)
```
- `awardGoods*` only when the reward is an item (`type`+`category` reference the goods
  catalogs; `amount` = quantity).
- All keys null-guarded ⇒ `data:{}` never crashes.
- For robustness across the `h` flag, the same fields may also be placed under a
  `crimeResult` object — harmless (extra null-guarded keys).

---

## 9. Class-A risks & shape mismatches

- **`ParseDoCrimeResponse`: no Class-A risk** — all reads are scalar `GetObjectItem`
  (null-guarded), **no array iteration**. `data:{}` is fully safe.
- **Latent Class-A in CPlayer:** the crime-skills field, *if present*, **must be an array**
  (`ParseCrimeSkills` begin-iterates); supplying `{}` would null-iterate → SIGSEGV. It is
  currently omitted from `_make_player` (commented out) ⇒ safe.
- **No Estate-style bare-array hazard** — the docrime response is object-shaped; the only
  structural subtlety is the conditional `crimeResult` wrapper (null-guarded either way).

---

## 10. Explicit answers (task 10)

- **Fields referencing `crime.city` ids:** `CPlayer.crimeSkills[].crimeIdx` (→ crime.city
  100–182); the crime executed is identified by the id `DoCrime` sends. `awardGoods*`
  reference the **goods** catalogs, not crime.city.
- **Definitions fully local?** **Yes** — `crime.city`/`crime_type.city`/`drugs.city` are
  client-local; no definition field crosses the wire.
- **Only runtime state crosses?** **Yes** — the network carries only the **action result**
  (rewards/outcome/cooldown deltas) and, in the CPlayer payload, the crime-skill array +
  scalar counters. No catalog rows.

---

## Confidence

- docrime result keys, scalar-only/no-array, `crimeSkills` element keys, ASSET_ONLY
  catalogs: **High** (deterministically resolved; single result parser).
- Command id (232/0xe8) and the `h`-flag path: **Medium-High** (dispatch compare + `h=0`
  call observed; a second crime command, if any, not separately disassembled).
- CPlayer crime-skills containing **field name** (`crimeSkilled` vs `crimeSkills`): **Medium**
  (element keys verified; the wrapping field name is set in `CPlayer::Parse`, not this body).

Success criterion met: crime is **action-only** with a fully-verified result object
(`result` + `award*` + `statusDuration`/`blood`/`lostToolFlag`/`consumeNum`), cooldown via
`statusDuration`, progress via the `{crimeIdx,crimeNum}` array, and definitions fully local —
implementable without guessing ids, field names, cooldown semantics, or container shapes.
