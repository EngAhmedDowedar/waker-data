# Crash Correlation Report — Endpoint → Parser → Data Shape

Binary-verified mapping of every catch-all endpoint hit during the post-step-13
boot session, correlated with the native parser that handles the response and the
exact data container type each parser expects.

## Method

For each endpoint that hit the catch-all route (`/city/<path:cmd>`, server.py line 814,
returns `data:{}`), the corresponding screen class was identified via `.dynstr` symbol
lookup, and the parser function's first 48–64 bytes were disassembled to determine
whether it uses:

- **Array iterator** (`LDR R2, [R0, #0x14]` = `42 69`, or `LDR R2, [R1, #0x14]` = `4A 69`):
  vtable slot 5 = `begin()`. Returns NULL on non-array nodes → SIGSEGV at `LDR Rx, [Rx, #0]`.
  Fix: return `data:[]`.

- **Named-field accessor** (`LDR R2, [R0, #0x40]` = `02 6C`, or `03 6C`):
  vtable slot 16 = `getObjectItem(name)`. Returns NULL if field missing; caller typically
  null-checks (CMP Rx, #0 / BEQ). Fix: return `data:{}` (current catch-all is already safe).

## Crash Endpoints (MUST return `data:[]`)

These parsers iterate the `data` value as a JSON array. The catch-all's `data:{}`
causes a null-iterator dereference → SIGSEGV.

| # | Endpoint | Parser Function | Address | Pattern | Offset | Status |
|---|----------|----------------|---------|---------|--------|--------|
| 1 | `/city/airline/airlines` | `CAirportScreen::ParseAirlines` | 0x324B04 | `42 69` | +4 | **CONFIRMED CRASH** (tombstone 07) |
| 2 | `/city/chat/getsysmsgs` | `CTopScreen::ParseSysMsg` | 0x59318C | `42 69` | +4 | WILL CRASH |
| 3 | `/race/car/getcars` | `CRG_CarWarehouseScreen::ParseCarList` | 0x53084C | `42 69` | +10 | WILL CRASH |
| 4 | `/race/car/getstoreitems` | `CRG_StoreScreen::ParseStoreRandomList` | 0x549DB8 | `4A 69` | +22 | WILL CRASH |
| 5 | `/race/car/getstoreitems` | `CRG_StoreScreen::ParseStoreNum` | 0x54A108 | `4A 69` | +30 | WILL CRASH |

### Crash code pattern (all five share this)

```arm
; data node access
LDR  R0, [Rx, #4]      ; 48 68   data->child
LDR  R2, [R0, #0x14]   ; 42 69   vtable[5] = begin()
...
BLX  R2                 ;         call begin() on data node
MOV  R4, R0             ;         R4 = iterator (NULL if data is {})
...
LDR  R0, [R4, #0]       ; 20 68   *** SIGSEGV *** fault addr 0x0
```

When `data` is `[]` (empty array), `begin()` returns a valid end-sentinel and the
loop body executes zero times. No crash.

### Additional array-iterator parsers (not hit in this session but same pattern)

| Parser | Address | Pattern | Triggered By |
|--------|---------|---------|-------------|
| `CHospitalScreen::ParsePatient` | 0x448F2C | `42 69` +4 | Hospital screen visit |
| `CGoodsModel::GetRowCount` | 0x420F30 | (indirect) | Goods list render |
| `CChatScreen::ParseMsg` | 0x347EDC | `42 69` +10 | `/city/chat/getmsg` (has specific route) |
| `CAirLineScreen::ParseArrived` | 0x323338 | (unverified) | Airline arrival screen |
| `CNewspaperScreen::ParseDailyNews` | 0x503BE8 | `42 69` +10 | News sub-parser (null-guarded by parent) |
| `CNewspaperScreen::ParseFairInfo` | 0x503DB0 | `42 69` +8 | News sub-parser (null-guarded by parent) |
| `CNewspaperScreen::ParseAdvertise` | 0x503F30 | `42 69` +14 | News sub-parser (null-guarded by parent) |

## Safe Endpoints (tolerate `data:{}`)

These parsers use named-field accessors and null-check before dereferencing.
The current catch-all `data:{}` does NOT crash them.

| # | Endpoint | Parser Function | Address | Pattern | Null Guard |
|---|----------|----------------|---------|---------|------------|
| 6 | `/city/monthCard/enterMatchCard` | `CEventBuyMonthCard::ParseEvent` | 0x3AC530 | `02 6C` | CMP R5, #0 / BEQ |
| 7 | `/race/match/matchconfig` | `CRaceCoreMnger::ParseAthleticsData` | 0x543AB4 | `03 6C` | CMP R1, #0 / BEQ |
| 8 | `/city/news/frontpage` | `CNewspaperScreen::ParseNews` | 0x503B6C | `02 6C` ×3 | Sub-parsers null-check |

### ParseNews dispatch detail

`ParseNews` is a dispatcher that expects `data` as an **object** with named sub-fields.
It calls `getObjectItem()` (vtbl+0x40) three times to extract named children, then
passes each to a sub-parser:

```
data.dailyNews  → ParseDailyNews  (array-iterator, but null-checked: CMP R4,#0 / BEQ)
data.fairInfo   → ParseFairInfo   (array-iterator, but null-checked: CMP R1,#0 / BEQ)
data.advertise  → ParseAdvertise  (array-iterator, but null-checked: CMP R5,#0 / BEQ)
data.awardInfo  → ParseAwardInfo  (object accessor, no array iteration)
```

When `data:{}`, all `getObjectItem()` calls return NULL, all sub-parsers skip via
their null guards. No crash.

## Request Timeline with Crash Risk

Session request log (from `analyze/logs/server_stderr.log`):

```
 Time      Endpoint                        Route        Data Shape  Risk
──────────────────────────────────────────────────────────────────────────
 13:10:01  PUT /checkversion               specific     {}          -
 13:10:03  PUT /api/auth                   root-catch   {}          -
 13:10:03  PUT /api/connect                specific     {player}    -
 13:10:05  PUT /city/impart         (×2)   specific     {}          -
 13:10:06  PUT /city/connect/getplayerlist specific     []          -
 13:10:07  PUT /city/connect/create        specific     {CPlayer}   -
 13:10:07  PUT /city/connect/connect       specific     {CPlayer}   -
 ─── city screen loaded (step 13) ─────────────────────────────────────
 13:10:09  PUT /city/chat/getsysmsgs       CATCH-ALL    {} !!       CRASH
 13:10:10  PUT /city/monthCard/enterMatchCard CATCH-ALL  {}          safe
 13:10:10  PUT /race/match/matchconfig     CATCH-ALL    {}          safe
 13:10:11  PUT /race/car/getcars           CATCH-ALL    {} !!       CRASH
 13:10:11  PUT /race/car/getstoreitems(×3) CATCH-ALL    {} !!       CRASH
 13:10:12  PUT /city/goods/playerbags      specific     {bags,goods} -
 13:10:13  PUT /city/news/frontpage        CATCH-ALL    {}          safe
 13:10:14  PUT /city/chat/getmsg           specific     -           -
 13:10:15  PUT /city/airline/airlines      CATCH-ALL    {} !!       CRASH ← first tombstone
```

## Ranked Crash Risk (Endpoints Needing `data:[]`)

| Rank | Endpoint | Fix | Confidence |
|------|----------|-----|------------|
| 1 | `/city/airline/airlines` | `data: []` | **CONFIRMED** (tombstone 07, 0x324B18) |
| 2 | `/city/chat/getsysmsgs` | `data: []` | **BINARY-VERIFIED** (42 69 at ParseSysMsg+4) |
| 3 | `/race/car/getcars` | `data: []` | **BINARY-VERIFIED** (42 69 at ParseCarList+10) |
| 4 | `/race/car/getstoreitems` | `data: []` | **BINARY-VERIFIED** (4A 69 at ParseStoreRandomList+22) |

## Recommended Fix Strategy

**Option A — Targeted routes (recommended):**
Add 4 specific Flask routes returning `data:[]` for the crash endpoints above.
Leave the catch-all as `data:{}` — it correctly serves the safe endpoints.

**Option B — Catch-all to `data:[]`:**
Change line 814 from `data:{}` to `data:[]`. Fixes all array-expecting parsers but
may break object-expecting ones. Risk: `ParseAthleticsData` and `ParseEvent` receive
an array where they expect an object — their null-check guards (`CMP R1,#0` / `BEQ`)
test the data *parameter* for null, but a non-null array would pass the guard and then
call `getObjectItem()` on an array node, which may return garbage or crash differently.

**Option A is safer** because it preserves the correct container type for each parser.
