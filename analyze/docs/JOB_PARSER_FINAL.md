# JOB_PARSER_FINAL.md — Verified Job Subsystem Contract

Binary-verified (libcity_ar.so v1.1.38). Built only from already-extracted symbols and
the captured disassembly of the four job functions — no rescans. Vtable byte-offsets
observed: `+0x0c`=child count, `+0x10`=IntValue, `+0x14`=begin-iterator (array),
`+0x2c`=GetArrayElement(i), `+0x40`=GetObjectItem(key). PIC string base = `0x75ab20`.

---

## A. Findings

### A1. Is `/city/job/getjobs` required?  →  **NO.**

- The strings `getjobs`, `job/getjobs`, `jobs`, `jobId` do **not** exist anywhere in the
  binary (verified earlier).
- `CHrMarketCateScreen::OnReceiveResponse` @0x44c78c dispatches on the command id and
  handles **exactly two** commands:
  - **285 (0x11d)** → do-work result
  - **284 (0x11c)** → get-salary result
  There is **no** "list jobs" command and **no** `ParseJobList`/`ParseJobs` symbol.
- The job list shown on screen is built by `CHrMarketCateScreen::GetJobList` @0x44bddc,
  which calls `GetById` (0x69341c) over the **local** catalog loaded by
  `CGameData::LoadJobs` / `CGameData::LoadJobTypes` from `job.city` / `job_type.city`.

**Conclusion:** `/city/job/getjobs` is a fabricated route name; the client never calls it.
The current server stub for it is never reached.

### A2. Are job lists entirely asset-driven?  →  **YES.**

The catalog (54 jobs in `job.city`, 9 types in `job_type.city`) is loaded and rendered
**client-side**. The server supplies **no** job catalog. This is purely local data.

### A3. Which player fields represent current job state?

| Field | Container | Parsed by | Meaning |
|-------|-----------|-----------|---------|
| job-category map | **object** (map keyed by job-type id) | `CPlayer::ParseJobCategoryInfo` @0x516ad8 | per-job-type progress/level the player has reached |
| `money` | int | `CPlayer::Parse` / salary response | player cash (updated by salary action) |
| `salaryAt` | int (timestamp) | `ParseGetSaleryResponse` | last salary-collection time |

The catalog of *which* jobs exist is **not** player state — it is asset data.

### A4. What does `ParseJobCategoryInfo` read?  (verified, @0x516ad8)

```
ParseJobCategoryInfo(data):
  if data == NULL: return                      ; null-guard (cmp r5,#0; beq)
  cat = GameData[0x18c]                         ; LOCAL job_type catalog vector
  n   = cat.Count()                             ; vtable +0x0c
  if n == 0: return
  for i in 0..n-1:
      jt   = cat.GetElement(i)                  ; vtable +0x2c
      jtid = jt.IntValue()                      ; vtable +0x10  (a job-type id)
      node = data.GetObjectItem(<jtid-as-key>)  ; vtable +0x40  (probe data BY KEY)
      if node != NULL:
          val = node.IntValue()                 ; vtable +0x10
          store val into player job map (+0x44/+0x48)
```

**Key facts:** `data` is treated as an **OBJECT** (map). Its keys are **job-type ids**
(numeric, from the local `job_type` catalog 1300–1311), each value an int. It does **not**
iterate `data` as an array. Omitting the field entirely is safe (the null-guard skips it).

---

## B. Response Trace — every JSON key accessed

### `OnReceiveResponse(cmd, data)` @0x44c78c
- `cmd == 285 (0x11d)`: work-done branch — UI/animation path; references the literal
  **`"job_salary"`** (string @0x6fa7dd) for the money-fly label; toggles screen flags.
- `cmd == 284 (0x11c)`: salary branch — reads screen state + a bool, then the salary data.
- The per-command **data parsing** is performed by the registered parsers below
  (`ParseDoJobResponse` / `ParseGetSaleryResponse`), which populate player/global state;
  `OnReceiveResponse` is the screen's post-parse UI callback.

### `ParseDoJobResponse(data)` @0x44c5dc   (command 285 = `/city/job/work`)
```
res  = data.IntValue()                    ; vtable +0x10  (result code)
(two 64-bit values read via helper pair 0x69406c/0x69407c → stored to globals;
 these are the work payout deltas — exact JSON key names are resolved inside the
 helper, NOT as literals in this function body, so they are left UNNAMED here)
cnt  = data.Count()                        ; vtable +0x0c  (null-guarded: cmp 0; beq)
for i in 0..cnt-1:
    el = data.GetElement(i)                ; vtable +0x2c
    if el[+0x44] == <job id>: el[+0x48] = ...   ; reward-item id / amount
```
**Verified JSON keys:** none by literal name in the body (result is the top-level int;
rewards are an **array** of items with id/amount). Container: object with an **array**
of reward items. Null-guarded.

### `ParseGetSaleryResponse(data)` @0x44c694   (command 284 = salary query)
```
pay = data+4
m   = pay.GetObjectItem("money")     ; vtable +0x40  → GetInt64 if present
s   = pay.GetObjectItem("salaryAt")  ; vtable +0x40  → GetInt64 if present
store m, s into player/global state
... then iterate an array, matching element[+0x44] == job id, to set per-job salary
```
**Verified JSON keys:** **`"money"`** (@0x6f8f8e), **`"salaryAt"`** (@0x6fd190).
Container: object. Both reads are null-guarded (GetObjectItem → NULL skips).

---

## C. Comparison against `_make_player()` (server.py)

| Verified field | Used by | In `_make_player()`? | Action |
|----------------|---------|----------------------|--------|
| job-category map (object) | ParseJobCategoryInfo | **No** | Safe to omit (null-guard). Optional `: {}` documents "no job progress". |
| `money` | salary response, HUD | **Yes** (`money: 5000000`) | ✓ matches |
| `salaryAt` | ParseGetSaleryResponse | **No** | Only needed after a salary action; not a boot field |

`_make_player()` is **consistent** with the verified parsers. No missing field breaks the
boot path; the job-category map being absent simply means the player has no job progress.

---

## D. Endpoint disposition

`/city/job/getjobs` is **ASSET-DRIVEN / not required**:
- The server route is never called by the client.
- The job catalog is local (`job.city` + `job_type.city` via `CGameData`).
- The current stub returned **speculative, unverified** fields
  (`jobType, salary, exp, energy, duration, status, playerId`) — none confirmed in the
  binary. These are removed (see server.py change) and the route reduced to a harmless,
  never-reached empty array.

The **real** job endpoints (only fired by player action, not boot):
- `/city/job/work` → command 285 → `ParseDoJobResponse` (result int + reward array).
- salary → command 284 → `ParseGetSaleryResponse` (keys `money`, `salaryAt`).

`ASSET_ENDPOINT_MAPPING.md` is updated to reflect this.
