# RELEASE AUDIT — Parser-Contract Verification

Binary-proven audit of every native JSON parser reached during city boot **and**
post-city gameplay, versus the live server payloads. Goal: a playable game — no
native parser crashes from type-mismatched fields.

## Result

```
TOTAL_MISMATCH_COUNT     = 0
TOTAL_UNAUDITED_PARSERS  = 0
Container-type audit (subsystem_audit.py): 21/21 WORKING, 0 BROKEN
```

All proven mismatches fixed. Every fix is grounded in three pieces of evidence:
the **parser** instruction that reads the field, the **field** name (recovered
from the binary), and the **payload** value the server sent.

## Methodology (works under Houdini; Frida native hooks do not — proven)

`analyze/parser_contract_audit.py` (re-runnable). For each parser it extracts the
field map directly from `libcity_ar.so`:

* **Field name** — GOT-relative literal pair (`ldr;add pc` + `ldr;adds`, GOT
  `0x75ab20`), handling both per-field and hoisted-GOT key-load patterns.
* **Field type** — by the exact value-accessor veneer called after `GetNode`:
  `0x69300c`→**int** (node+8), `0x692fcc`→**string** (node+4, `movs r1,#1`),
  `0x694fbc`→**bool** (node+4, no arg). Sub-parser `bl` → object/array; begin-
  iterate → array.
* **Optional vs required** — presence of the `cmp r0,#0; beq skip` null-check.

Then it diffs the parser's expected types against the live JSON. Note: every
per-record parser null-checks each field, so a **missing** field is safe — only a
**present-but-wrong-typed** field crashes (`int`-veneer on a string → IntValue
null deref `0x10`; `string`-path on an int → bad char* deref).

## Proven fixes

| # | Field | Parser | Read site | Expected | Was sent | Endpoints | Crash |
|---|-------|--------|-----------|----------|----------|-----------|-------|
| 1 | `convertGoods` | `CGoods::Parse` | 0x40cd40 nested-iterate | object (omit) | `int 0` | connect, playerbags, goods/buy | type-confusion → SIGSEGV `0x6469af` (tomb_00) |
| 2 | `customHouseTag` | `CHouse::Parse` | 0x449b96 int veneer | `int` | `string ''` | connect.estates, estate/listestates, estate/buy | IntValue-null `0x10` (highest-freq) |
| 3 | `bucket` | `CServer::Parse` | 0x56dfde string path | `string` | `int 0` | **checkversion (boot)**, getallserver | bad char* deref |
| 4 | `flag` | `CFaction::Parse` | 0x3ce2ec string path | `string` | `int 1` | faction/list, faction/info, gang/randomgangs | bad char* deref |
| 5 | `gangFlag` | `CCitier::Parse` | 0x34e264 string path | `string` | `int 0` | fight/randomfighters, connect/getplayerlist | bad char* deref |

## Investigated, NOT a bug (no patch — would have been a speculative fix)

* **`lostToolFlag`** (`CCrimeScreen::ParseDoCrimeResponse` @0x36a210) — read via
  the **bool** accessor `0x694fbc` (node+4, no length arg), which is distinct from
  the string accessor `0x692fcc`. The game's own verified crime contract sends it
  as `int 0/1`; `bool`-accessor accepts an int scalar. An earlier heuristic
  conflated `0x694fbc` with the string reader — corrected; not a mismatch.

## Coverage

**Boot chain** (see `analyze/docs/CITY_BOOT_DEPENDENCY_GRAPH.md`): CServer,
ParseLastLoginPlayer, CImpart, CCitier (getplayerlist), CPlayer (169 fields) +
ParseStatus/Goods/Bags/Houses, CHouse, CGoods, CTopScreen::ParseMsg,
CChatScreen::ParseMsg.

**Gameplay** (post-city): Crime (ParseDoCrimeResponse), Jobs (ParseGetSalery/
ParseDoJob), Bank (CBankScreen), Gym (ParseEnterGymInfo/ParseResponse), Hospital,
Missions (CGameMissionManager), Fight (CFightingScreen/CFight::ParseNew, 29
fields), Store, Lottery, Rankings, School, Mail (CMessage), Auction, Goods Market,
Inventory, Estate. Pure-dispatcher parsers (no named-field contract; they delegate
or index-iterate) are recognized and excluded from the unaudited count.

## Not covered by this audit (out of scope, documented elsewhere)

* In-game runtime confirmation: the x86/Houdini emulator (LDPlayer android_x86)
  crashes in the native GL render thread and will not reliably boot to the city;
  Frida native Interceptor hooks do **not** fire under Houdini (canary-proven,
  `analyze/timed_hook.py`). Runtime confirmation needs a real ARM device. See
  `analyze/docs/TOMBSTONE_CRASH_MAP.md`.
* Container-type (array vs object) correctness is handled separately and verified
  green by `local-server/python/subsystem_audit.py` (21/21).
