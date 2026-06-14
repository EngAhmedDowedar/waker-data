# Tombstone Crash Map (Houdini-translated GLThread SIGSEGVs)

Generated 2026-06-13 from the 10 tombstones on the LDPlayer x86 emulator.

## Method (how ARM frames were recovered under Houdini)

Every crash is `signal 11 SIGSEGV` in thread **GLThread**, and the unwinder's
frame #00 is always inside `libhoudini.so` — Houdini JIT-translates the ARM
`libcity_ar.so` code, so the standard unwinder cannot see guest (ARM) frames.

Recovery: the tombstone `stack:` dump contains raw 4-byte words; those falling
inside the `libcity_ar.so` executable mapping (base `0x0c800000`, size `0x71d000`)
are guest return addresses. Subtract the base → **file offset == virtual address**
(first PT_LOAD maps file off 0 → vaddr 0). Offsets resolved against `.dynsym`
(31 232 FUNC symbols) name the crashing call chain.

## Crash table (grouped by fault address)

| Fault addr | Freq | Crashing function (recovered) | +off | Category | Repro | Pre/Post connect |
|-----------|------|-------------------------------|------|----------|-------|------------------|
| **0x10** | **4** | `ngInteger::IntValue()` on null `this` | +0 | **null int field** (parser reads a missing integer, no null-check) | Y | **POST** |
| 0x0 | 1 | `CConfigure_RG_Atheltic_Reward::ParseData` → `ngHashMap::ContainsKey` → `ngBucket::Add` (null key) | chain | **race subsystem** (network-fetched config, null hashmap key) | Y | POST |
| 0x6469af | 1 | `CGoods::Parse +0xe0` | +0xe0 | **type confusion** (field expected OBJECT, got STRING — fault addr = ASCII bytes deref'd as ptr) | Y | POST (my run) |
| 0x84 | 1 | `CHouse::GetPrice` | — | already patched (`patch_chouse_getprice`) | Y | POST |
| 0x5031c22 | 3 | (title-screen render, ZERO network requests) | — | pre-connect render — IGNORED per scope | Y | **PRE** |

## Most-common POST-connect crash path

**`ngInteger::IntValue()` called on a NULL node — fault addr 0x10 (null+0x10), 4×.**
A JSON parser does `node->IntValue()` where `node` came from a key lookup that
returned NULL (missing integer field) with no null-check. The immediate caller is
hidden inside Houdini's translation (only the leaf `IntValue` survives on the
stack), so the exact field cannot be named from the tombstone alone — it needs a
runtime hook (Frida/Java) on `ngHashMap::GetNode`/`IntValue` to capture the key,
which requires a stable run.

## Mechanism summary

All POST-connect crashes are the same family: **native config/player parsers
consuming server-response (or network-config) JSON that is missing a field, has a
null key, or is the wrong container/scalar type.** This is the documented
`{}`-vs-`[]` / missing-field class (see POST_STEP13_CRASH_ANALYSIS.md), now
extended with the race-config (`CConfigure_RG_Atheltic_Reward`, network-fetched
via `RequestConfigure`) and `CGoods::Parse` type-confusion cases.

## Hard constraint on the eliminate→retest loop

The fix→retest→"5-min stable" loop cannot converge on THIS emulator: it crashes
**non-deterministically**, including the pre-network title render (`0x5031c22`,
3×) — i.e. before any server request exists to fix. Confirming a fix needs the
real ARM device (see project_emulator_render_crash_blocks_validation,
project_city_boot_working).

## Update 2026-06-14 — connect-path field-type mismatch sweep (P1/P2)

Built a static field-map extractor (parser key literals via GOT 0x75ab20; type
from the read pattern). Found CPlayer::Parse @0x5140bc null-checks EVERY field
(GetNode→cmp r0,#0→beq) so MISSING fields are safe — only WRONG-TYPED fields
crash (node passes null-check, then mistyped extraction null-derefs → IntValue
fault 0x10).

Cross-checked served JSON vs expected types across CPlayer (162 fields), CHouse,
CCitier, CGoods, ParseStatus. Two proven mismatches (both fixed):

| Endpoint | Field | Expected | Sent | Parser | Crash |
|----------|-------|----------|------|--------|-------|
| connect/connect (player.estates), estate/listestates | customHouseTag | int (0x449b96 adds r0,#8 int veneer) | string '' | CHouse::Parse | IntValue-null 0x10 (likely the 4x highest-freq) |
| connect/connect, connect/create, goods/playerbags | convertGoods | nested obj | int 0 | CGoods::Parse | 0x6469af (prev turn) |

After both fixes: **0 type mismatches** remain across all connect-path parsers.
