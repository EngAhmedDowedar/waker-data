# Release Summary — `release-candidate-server-validated`

Highest-confidence server-validated build. Status: **CONDITIONAL** (server fully
validated; in-game runtime confirmation on a real ARM device pending).

## Commits (this release: `2cf3bf0..HEAD`)

| Hash | Summary |
|------|---------|
| `ff20020` | audit: binary-proven parser-contract fixes for city boot + gameplay |
| `045a175` | fix: cache ciphered request body before form access; add release validation |
| `786dd6b` | docs: RUN_SERVER deployment method (USB/ADB-reverse, pm clear, USB-signed APK) |
| _(+ this commit: release summary)_ | |

## Files changed (15 files, +2198 / −39)

```
.gitignore                                  +6
RELEASE_AUDIT.md                            +77   (parser-contract audit report)
RELEASE_VALIDATION.md                       +97   (gameplay flow validation report)
RUN_SERVER.md                               +98/-21 (deployment/operation method)
analyze/docs/CITY_BOOT_DEPENDENCY_GRAPH.md  +73
analyze/docs/PARSER_CONTRACT_AUDIT.txt       +59  (audit output)
analyze/docs/TOMBSTONE_CRASH_MAP.md         +70
analyze/hook_probe.js / run_hook.py / timed_hook.py  (Houdini/Frida finding evidence)
analyze/parser_contract_audit.py            +315  (re-runnable contract audit tool)
local-server/python/player_state.py         +30/-? (convertGoods/customHouseTag migration)
local-server/python/release_validation.py   +175  (re-runnable gameplay validation)
local-server/python/server.py               +871  (5 type fixes, body-parse fix, working server)
local-server/python/subsystem_audit.py      +164  (re-runnable container audit)
```

## Gameplay validation results — 16/16 PASS

From a clean player state, end-to-end through the server, persistence read back
from `player_state.json` on disk:

- **Persisting actions (10/10 Y):** Estate buy, Bank deposit, Bank withdraw, Job
  work, Crime, Fight attack, Hospital cure, Goods buy (+ Login, Character load).
- **Read-only loads (6/6 valid):** Mission, Ranking, Mail, Gang, Store, Lottery.
- **Bug fixed during validation:** ciphered request bodies were dropped
  (`request.form` consumed the stream before caching) → bank deposit/withdraw
  no-op'd with a real client. Fixed; re-validated 16/16.

Full table: `RELEASE_VALIDATION.md`.

## Parser audit results

`analyze/parser_contract_audit.py`: **TOTAL_MISMATCH_COUNT = 0**,
**TOTAL_UNAUDITED_PARSERS = 0**. Five binary-proven type fixes shipped:
`convertGoods`, `customHouseTag`, `bucket`, `flag`, `gangFlag`
(each with parser + field + payload evidence; `RELEASE_AUDIT.md`).

## Container audit results

`local-server/python/subsystem_audit.py`: **21/21 WORKING**, 0 PARTIAL, 0 BROKEN.

## Known limitations

1. **In-game runtime unconfirmed** — the x86/Houdini emulator crashes in native
   GL render and defeats Frida (proven); needs a real ARM device for a
   boot-to-city + screen-open pass. This is the gate from CONDITIONAL → READY.
2. **Read-only feature endpoints return empty content** (rankings/mail/store/
   lottery/auction/school) — load safely, no content. Cosmetic.
3. **Hospital cure** validated idempotent (blood stayed 100); the heal-cost path
   wasn't triggered (random successes). Low risk.

## Reproduce the validation

```
cd local-server/python
rm -f player_state.json && PYTHONUTF8=1 python -X utf8 server.py &   # clean state
curl -s -X PUT http://127.0.0.1:8080/city/player/setname >/dev/null  # materialize
python release_validation.py        # 16/16 gameplay flows
python subsystem_audit.py           # 21/21 container
cd ../../analyze && python parser_contract_audit.py   # 0 mismatches
```
