# MISSION_PARSER_FINAL.md — Verified Mission Subsystem Contract

Binary-verified (libcity_ar.so v1.1.38), JOB→GYM→ESTATE→GOODS→SCHOOL methodology. Reused
the symbol DB (targeted greps) + fresh disassembly; the one JSON key resolved
deterministically against PIC base `0x75ab20`. Catalog lookup `GetById` `0x69341c`;
int64 helper `0x69300c`; mission-manager accessor `0x69524c`.

---

## 1. Ownership (verified)

| Catalog | rows / ids | Loader (client-local) |
|---------|-----------|----------------------|
| `mission.city` (29) | ids 1–29 | `CGameData::LoadMissions` |

`mission.city` is the **only** mission catalog and is **client-local**. Each row is 14
ints: `id` (=missionId), `f1` order, `f2/f3/f4` = `assets/ar` string-ids (title 2220+,
desc 2250+, **tip 2280+** = the mascot bubble), `f7` = **reward amount** (100/200/300/500…),
`f9` target-type, `f10` = **target id** (references job/crime/goods catalogs, e.g. 23/708/511/7),
`f11` target count, `f13` another string-id. **ASSET_ONLY** — no endpoint sends these rows.
(Daily tasks — `dailyTask`/`taskId` strings — are a **separate** system on `CPlayer.dailyTask`,
not `mission.city`; out of scope here.)

---

## 2. Screens & managers (verified symbols)

| Symbol | Role |
|--------|------|
| `CGameMissionManager::OnReceiveResponse` @0x40643c | **the** mission network handler (cmd 369) |
| `CGameMissionManager::UpdateCurMission` / `FinishCurMission` @0x4072c0 | internal advance/finish (no network read) |
| `CMissionManager::OnReceiveResponse` @0x4eaf8a | **4-byte stub** (no-op) |
| `CMissionScreen`, `CMissionEndScreen`, `CFinishMissionScreen`, `CFinishBranchMissionScreen` | display only — **no `Parse*`** |
| `CPlayer` | carries `missionId` + `missionProgress` (parsed by generic `CPlayer::Parse`) |

**There is no `ParseMission*` anywhere** and **no `CPlayer::ParseMission*`** — missions are
never parsed as an object/array. Mission state is two scalar CPlayer fields.

---

## 3. Verified network contract

### `CGameMissionManager::OnReceiveResponse(cmd, data)` @0x40643c
- Dispatches on **`cmd == 369 (0x171)`** only (no other command compare in the body).
- Reads exactly one key: `GetObjectItem("missionId")` → `GetInt64` → compares against the
  current mission (via accessor `0x69524c`) and `GetById(0x69341c)` into `mission.city`,
  then advances the player's current mission.
- ⇒ response shape: **`data = { "missionId": <int> }`** (object, single scalar). No
  `missionProgress` key, **no reward array, no array iteration, no nested objects**.

`missionProgress` does **not** cross the wire in this response — it is updated internally
and delivered in the CPlayer payload.

---

## 4. JSON keys (complete)

| Endpoint / payload | Keys | Container |
|--------------------|------|-----------|
| `/city/mission/updatemission` (cmd 369) | `missionId` | object, scalar |
| CPlayer payload | `missionId`, `missionProgress` | scalars |
| `/city/mission/getmission` | — (string **absent** in binary → not called) | n/a |

There is **no reward-claim endpoint** — rewards derive from `mission.city.f7` client-side
when a mission completes.

---

## 5. Containers (task 5)

| Item | Container |
|------|-----------|
| mission **list** | n/a over network — built client-side from `mission.city` + `CPlayer.missionId` |
| mission **progress** | **scalar** int (`CPlayer.missionProgress`) |
| **reward** | n/a over network — `mission.city.f7`, client-side |
| **completion state** | scalar `missionId` (advanced by cmd 369) |

---

## 6. Endpoint classification

| Endpoint | Class | Container |
|----------|-------|-----------|
| `mission.city` | **ASSET_ONLY** (client-local) | n/a |
| `/city/mission/updatemission` (cmd 369) | **ACTION_RESPONSE** (advances current mission) | object `{missionId}` |
| `/city/mission/getmission` | **dead** (no binary string; never called) | — |
| CPlayer `missionId`/`missionProgress` | **PLAYER_STATE** | scalars |

No MIXED beyond the implicit `missionId`→`mission.city` `GetById` merge.

---

## 7. Definitions local, only state crosses — VERIFIED

Confirmed: **mission definitions are 100% client-local** (`mission.city` via
`LoadMissions`; titles/tips from `assets/ar`; rewards/targets are catalog fields). The
**only** mission data crossing the network is **scalar state**: `missionId` (in cmd-369
and the CPlayer payload) and `missionProgress` (CPlayer payload). No definition fields are
ever sent by the server.

---

## 8. Minimal valid payloads

```
mission list        → (no endpoint; client uses mission.city + CPlayer.missionId)
mission progress    → in CPlayer: "missionId": <1..29 | 100>, "missionProgress": <int>
reward claim        → (no endpoint; client awards mission.city.f7 on completion)
mission completion  → updatemission (cmd 369): { "missionId": <nextMissionId> }
                      (data:{} is safe but does NOT advance — missionId omitted → null-guarded)
```
- `missionId` ∈ `mission.city` ids **1–29** to activate a mission; **100** (or any id past
  29) = "no active mission" (the current park value).
- `data:{}` never crashes (single null-guarded scalar key).

---

## 9. Class-A risks & shape mismatches

- **No Class-A risk at all.** The cmd-369 response reads a single scalar via
  `GetObjectItem` (null-guarded); there is **no array iteration** anywhere in the mission
  network path. `data:{}` is fully safe.
- **No Estate-style object/array hazard** — there is no array or nested-object expectation
  to mis-shape. Mission is the simplest verified subsystem: one scalar key.
- **Dead route note:** `/city/mission/getmission` exists in server.py but the string is
  absent from the binary → the client never calls it (analogous to `/city/job/getjobs`).

---

## 10. Explicit answers (task 10)

- **Which fields are mission IDs:** `missionId` (CPlayer payload **and** the cmd-369
  response) and `mission.city.id` (the catalog key, 1–29).
- **Which reference `mission.city`:** `missionId` → `GetById(0x69341c)` into `mission.city`;
  also `mission.city.f10` references job/crime/goods catalogs as the mission **target**.
- **Progress semantics:** `missionProgress` is a **SCALAR int** (not object, not array) on
  CPlayer; it counts toward `mission.city.f11` (target count). The completion signal is the
  server advancing `missionId` via cmd 369.

---

## Confidence

- Command id (369), the `missionId` key, scalar progress, no-reward-endpoint, no arrays:
  **High** (single-command dispatch fully disassembled; only one key; no `Parse*` exists).
- `mission.city` field-semantics (`f7` reward / `f10` target / `f2-4` string-ids): **Medium**
  (inferred from values + cross-catalog ranges; not each disassembled — but irrelevant to
  the network contract since definitions never cross the wire).

Success criterion met: the mission network surface is a **single command (369) carrying one
scalar `missionId`**, with progress as a CPlayer scalar and rewards/definitions fully local
— implementable with zero guesswork on ids, field names, containers, or progress semantics.
