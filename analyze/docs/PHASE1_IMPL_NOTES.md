# PHASE 1 Implementation Notes — Player-State Endpoints

Implements Phase 1 of `PLAYER_STATE_IMPLEMENTATION_PLAN.md` (Estate, Goods, Job, Crime).
Working code, no further reverse engineering. All shapes from the verified subsystem reports.

## Files

| File | Role |
|------|------|
| `local-server/python/player_state.py` | PlayerState model + JSON persistence + element builders |
| `local-server/python/server.py` | endpoints wired to player_state (see below) |
| `local-server/python/test_phase1.py` | Flask-test-client checks (24 assertions, all pass) |
| `player_state.json` | runtime state (gitignored, auto-created) |

## Persistence layer

- Single mutable dict, one demo player, persisted to `player_state.json` next to the server.
- `player_state.load()` (cached), `save()` (atomic via `.tmp` + `os.replace`), `reset()`.
- Seed (`default_state()`) mirrors the boot-safe `_make_player()` defaults.
- Action endpoints mutate the dict then `save()`; state endpoints serialize slices.
- `_make_player()` now sources mutable fields (money/exp/mission/goods/bags/estates) from
  player_state while keeping the verified boot-safe structure verbatim.

## Request parsing

`_req_json()` / `_req_int(name, default)` read action parameters from query args, form, or
the request body (tries cipher `base64(XOR(json))` then plaintext). Missing params fall back
to safe defaults, so actions work even when the body can't be decoded.

---

## Endpoint-by-endpoint (current → implemented)

### `/city/estate/listestates` (PLAYER_STATE) ★ crash fix
- **Was:** `data: []` (bare array — the `0x756f707b` JSON-cleanup crash shape).
- **Now:** `data: { myEstates:[CHouse], spouseEstates:[], money, happy, liveEstate,
  maintainExpireAt, spouseLiveEstate }` (object, verified).
- **Mutations:** none (read). **Reads:** `estates`, `money`, `happy`, `liveEstate`.

### `/city/estate/buy` (ACTION, cmd 315)
- **Was:** `data: _make_house()` (bare CHouse).
- **Now:** `data: { buy_house:CHouse, estates:[CHouse] }`.
- **Mutations:** `money -= price` (from `property.city`), append CHouse to `estates`,
  set `liveEstate` if first. **Guards:** rejects if `money < price`; clamps
  `estateType` to 800–817 (valid `property.city` id → GetById safe).

### `/city/goods/playerbags` (PLAYER_STATE)
- **Was:** `{ bags:[], goods:[] }` (wrong keys → empty bag).
- **Now:** `{ playerGoods:[CGoods], specialities:[] }` (verified `ParseBag` keys).
- **Mutations:** none. **Reads:** `bags`.

### `/city/goods/playergoods` (PLAYER_STATE, warehouse)
- **Was:** `{ goods:[] }`.
- **Now:** `{ playerGoods:[CGoods], tradeGoods:[], specialities:[] }` (verified
  `ParseWarehouse` keys). **Reads:** `goods`.

### `/city/job/work` (ACTION, cmd 285/284)
- **Was:** `data: _make_player()` (full player).
- **Now:** `data: { result:1, money, salaryAt, awardMoney, awardExp }` (verified salary
  slice + null-guarded extras).
- **Mutations:** `money += salary` (salary scales with `jobCategory` level),
  `exp += gain`, `jobCategory[jobTypeId] += 1`, `salaryAt = now`.
  `jobTypeId` resolved via `job.city.f1`.

### `/city/crime/docrime` (ACTION, cmd 232)
- **Was:** `data: _make_player()`.
- **Now:** verified `ParseDoCrimeResponse` object:
  `{ result, awardType, awardMoney, awardCheque, awardGoodsType, awardGoodsCategory,
  awardGoodsAmount, awardExp, statusDuration, lostToolFlag, blood, consumeNum }`
  (scalars only — zero Class-A risk).
- **Logic:** success chance `min(0.55 + crimeNum*0.03, 0.9)`; reward range from
  `crime_type.{f3,f4}` (min/max) via `crime.f1`.
- **Mutations (success):** `money += award`, `exp += 20`, `crimeSuccess += 1`,
  cooldown 60s. **(fail):** `blood -= 20`, jail cooldown 300s. **Always:** `crimeTimes += 1`,
  `crimeSkills[crimeIdx].crimeNum += 1`, `playerStatus.{status,statusAt,statusDuration}`,
  `coolingTime`.

---

## State-mutation summary table

| Endpoint | Reads | Writes |
|----------|-------|--------|
| estate/listestates | estates, money, happy, liveEstate | — |
| estate/buy | money, property.city | money, estates, liveEstate |
| goods/playerbags | bags | — |
| goods/playergoods | goods | — |
| job/work | jobCategory, job.city | money, exp, jobCategory, salaryAt |
| crime/docrime | crime.city, crime_type.city, crimeSkills | money, exp, blood, crimeSuccess, crimeTimes, crimeSkills, playerStatus, coolingTime |

All money/exp/state changes persist and surface on the next `/city/connect/connect`
(`_make_player` reads from player_state).

---

## Verification

`python local-server/python/test_phase1.py` → **24 passed, 0 failed** (Flask test client,
no emulator). Confirms: verified containers/keys, money deduction on buy, salary award,
crime success/fail mix + skill tracking + cooldown, persistence across reload, and that
`/connect/connect` reflects mutated state. Boot endpoints (`/checkversion`,
`/connect/create|connect`, `/impart`, `/estate/listestates`) all return safe object shapes.

## Caveat (carried from the ARM risk assessment)

Populated array/object responses (esp. estate `myEstates`, market goods) are verified by
**shape** but should be confirmed on real ARM hardware before trusting at runtime — the
residual `0x756f707b`-class fault lived in the Houdini-translated allocator, not in the JSON
contract. The empty-array baselines are unconditionally safe.
