# Post-Step-13 Crash Analysis

## Summary

The post-city-screen crash is **NOT caused by CPlayer field types**. The CPlayer
payload is shape-identical (same 69 fields, same types) to the May 29 known-good boot.

The crash is caused by the **catch-all route** (`/city/<path:cmd>` at server.py line 809)
returning `data:{}` (object) for endpoints whose native parsers expect `data:[]` (array).

## Crash Mechanism

All three captured crashes share an identical ARM THUMB code pattern:

```arm
LDR  R0, [R1, #4]      ; R0 = data_node->child (JSON first child)
LDR  R2, [R0, #0x14]   ; R2 = vtable[5] — the "begin-iterator" slot
ADDS R0, R1, #4
MOVS R1, #0
BLX  R2                 ; call begin() on the data node
MOV  R4, R0             ; R4 = iterator result
...
LDR  R0, [R4, #0]       ; *** SIGSEGV *** — R4 is null
```

When `data` is `{}` (object), the native JSON node has a valid `child` pointer, but the
begin-iterator call returns NULL because `{}` is not iterable as an array. The subsequent
`LDR` from the null iterator causes SIGSEGV at fault address `0x0`.

When `data` is `[]` (empty array), the begin-iterator returns a valid end-sentinel, and
the for-loop body executes zero times. No crash.

## Three Captured Crashes

| Tombstone | Date | ARM Offset | Function | +Offset | Trigger |
|-----------|------|-----------|----------|---------|---------|
| 05 | 06-11 07:17 | `0x448F40` | `CHospitalScreen::ParsePatient(void*)` | +20 | Hospital screen |
| 06 | 06-11 07:55 | `0x420F36` | `CGoodsModel::GetRowCount()` | +6 | Goods list render |
| 07 | 06-11 08:14 | `0x324B18` | `CAirportScreen::ParseAirlines(void*)` | +20 | `/city/airline/airlines` |

All: `signal 11 (SIGSEGV), code 1 (SEGV_MAPERR), fault addr 0x0` in GLThread.

## CPlayer Payload Comparison

**Field-by-field diff: 69 keys in both, key sets are IDENTICAL.**

Only differences between known-good (May 29) and current:

| Field | Known-Good | Current | Cause |
|-------|-----------|---------|-------|
| `avatarAt` | 1779974985 | 1781084323 | Different `now` timestamp |
| `createdAt` | 1777469385 | 1778578723 | Different `now` timestamp |
| `energyAt` | 1780061385 | 1781170723 | Different `now` timestamp |
| `moralAt` | 1780061385 | 1781170723 | Different `now` timestamp |
| `missionId` | 5 | 1 | Intentional change |
| `name` | "Player" | "Abu Hassan" | Cosmetic |
| `signature` | "Welcome to Waker" | "أهلاً بك في الوكر" | Cosmetic (Arabic) |

No type mismatches. No missing fields. No extra fields.
**CPlayer is not the crash source.**

## Server Request Sequence (Full Boot to Crash)

```
PUT /checkversion                        → specific route
PUT /api/auth                            → catch-all (root_catch_all)
PUT /api/connect                         → specific route
PUT /city/impart              (×2)       → specific route (data:{})
PUT /city/connect/getplayerlist          → specific route (data:[])
PUT /city/connect/create                 → specific route (data:{...CPlayer})
PUT /city/connect/connect                → specific route (data:{...CPlayer})
--- city screen loaded (step 13) ---
PUT /city/chat/getsysmsgs                → CATCH-ALL (data:{}) ⚠️
PUT /city/monthCard/enterMatchCard       → CATCH-ALL (data:{}) ⚠️
PUT /race/match/matchconfig              → CATCH-ALL (data:{}) ⚠️
PUT /race/car/getcars                    → CATCH-ALL (data:{}) ⚠️
PUT /race/car/getstoreitems   (×3)       → CATCH-ALL (data:{}) ⚠️
PUT /city/goods/playerbags               → specific route (data:{bags:[],goods:[]})
PUT /city/news/frontpage                 → CATCH-ALL (data:{}) ⚠️
PUT /city/chat/getmsg                    → specific route
PUT /city/airline/airlines               → CATCH-ALL (data:{}) ⚠️ → CRASH
```

## Which Catch-All Endpoints Need Array Responses

Based on the crash pattern (vtbl+0x14 array iterator), these endpoints from the
session log are high-risk for crash if they expect `data:[]`:

| Endpoint | Risk | Notes |
|----------|------|-------|
| `/city/airline/airlines` | **CONFIRMED CRASH** | ParseAirlines iterates data as array |
| `/city/chat/getsysmsgs` | HIGH | Chat system messages — likely array of msgs |
| `/city/news/frontpage` | HIGH | News items — likely array |
| `/race/car/getcars` | HIGH | Car list — likely array |
| `/race/car/getstoreitems` | HIGH | Store items — likely array |
| `/city/monthCard/enterMatchCard` | MEDIUM | May be object config |
| `/race/match/matchconfig` | MEDIUM | May be object config |

## Proof: Not a Timing / Memory Issue

The earlier hypothesis that the crash was caused by `lowmemorykiller` (memory pressure
from the LDPlayer app store stealing focus) is DISPROVEN. The crash:
1. Consistently occurs at fault addr 0x0 (null pointer, not random memory corruption)
2. Always in GLThread during screen rendering
3. Has a clear code pattern (array iterator on non-array data)
4. Is reproducible by navigating to any screen whose parser hits the catch-all

## Recommended Fix (Do Not Apply Yet)

Two options:

**Option A — Safest:** Change the catch-all (line 814) from `data:{}` to `data:[]`.
This fixes array-expecting parsers but may break object-expecting ones (untested).

**Option B — Correct:** Add specific routes for each called endpoint with the right
container type ([] or {}), determined by verifying each parser's vtable call pattern
at the ARM offset.
