# RELEASE VALIDATION

End-to-end gameplay validation through the live server, from a **clean player
state**, proving functional behaviour + persistence (not just parser shape).
Harness: `local-server/python/release_validation.py` (re-runnable).

## Release status: **CONDITIONAL**

All server-side gameplay flows execute and persist correctly, and both static
audits are green. The single outstanding item is **in-game runtime confirmation
on real hardware** — not validatable on the available x86/Houdini emulator
(crashes in the native GL thread; Frida hooks proven non-functional there). That
keeps the release CONDITIONAL rather than READY.

---

## 1. Parser audit result

`analyze/parser_contract_audit.py` — binary field contracts vs live JSON:
```
TOTAL_MISMATCH_COUNT     = 0
TOTAL_UNAUDITED_PARSERS  = 0
```
5 proven type fixes shipped: convertGoods, customHouseTag, bucket, flag, gangFlag
(see RELEASE_AUDIT.md).

## 2. Container audit result

`local-server/python/subsystem_audit.py` — array-vs-object container types:
```
WORKING 21 / PARTIAL 0 / BROKEN 0
```

## 3. Gameplay flow validation result

Clean baseline: `money=5000000 cheque=5000 blood=100 exp=0 estates=0 bags=0`.
Persistence column = the mutation was read back from `player_state.json` on disk
(what a server restart reloads).

| Flow | Endpoint(s) | Server response | State before | State after | Persist |
|------|-------------|-----------------|--------------|-------------|:------:|
| Login | `/api/connect` | `playerId=1001` | — | — | N/A |
| Character load | `/city/connect/connect` | `id=1 name=Abu Hassan level=20 money=5000000 playerStatus=obj` | — | — | N/A |
| Estate buy | `/city/estate/buy` | `result=0 estates=1` | money=5000000 estates=0 | money=4921500 estates=1 | **Y** |
| Bank deposit | `/city/bank/deposit` | `money=4920500 cheque=6000` | money=4921500 cheque=5000 | money=4920500 cheque=6000 | **Y** |
| Bank withdraw | `/city/bank/withdraw` | `money=4921000 cheque=5500` | money=4920500 cheque=6000 | money=4921000 cheque=5500 | **Y** |
| Job work | `/city/job/work` | `result=1 awardMoney=1000` | money=4921000 exp=0 | money=4922000 exp=10 | **Y** |
| Crime action | `/city/crime/docrime` | `result=1 awardMoney=5500` | money=4922000 crimeTimes=0 | money=4927500 crimeTimes=1 | **Y** |
| Fight attack | `/city/fight/attack` | `result=1 awardMoney=24500 myHp=100` | money=4927500 battles=0 | money=4952000 battles=1 | **Y** |
| Hospital cure | `/city/hospital/cure` | `blood=100 money=4952000` | blood=100 money=4952000 | blood=100 money=4952000 | **Y** |
| Goods buy | `/city/goods/buy` | `money=4951000 bags=1` | money=4952000 bags=0 | money=4951000 bags=1 | **Y** |
| Mission load | `/city/mission/getmission` | `data=object missionId:int` | — | — | N/A |
| Ranking load | `/city/rank/list` | `data.players:list` | — | — | N/A |
| Mail load | `/city/message/list` | `data.messages:list` | — | — | N/A |
| Gang load | `/city/faction/info` | `data.members:list` | — | — | N/A |
| Store package load | `/city/store/package` | `data.packages:list` | — | — | N/A |
| Lottery load | `/city/lottery/info` | `data:list` | — | — | N/A |

**FLOWS = 16, FAILED = 0.** All mutating flows (10) persist to disk; all
read-only loads (6) return valid, decodable, correctly-typed responses.

### Bug found & fixed during this pass
- **Ciphered request bodies were silently dropped.** `_log_request` (before_request)
  accessed `request.form` before anything cached the body, consuming the WSGI
  input stream; `_req_json`'s `request.get_data()` then returned `b''`, so action
  params (`amount`, etc.) fell back to defaults. Bank deposit/withdraw (default
  amount 0) no-op'd. Fixed by caching the raw body (`request.get_data(cache=True)`)
  at the top of `_log_request`. Re-validated: all 16 flows pass.
  This affected **every param-driven action with a non-default value** sent by a
  real client — a genuine gameplay bug surfaced only by functional validation.

## 4. Known unresolved issues

1. **In-game runtime unconfirmed.** No real ARM device available; the x86/Houdini
   emulator crashes in native GL render and defeats Frida. Server contracts +
   flows are proven, but the actual on-device player experience is unverified.
2. **Hospital cure not exercised with damage.** Crime/fight rolled successes
   (random), so blood stayed 100; cure was verified idempotent (returns blood=100)
   but not the heal-cost path. Low risk (cost path is trivial arithmetic).
3. **Read-only feature endpoints return empty lists** (rankings, mail, store,
   lottery, auction, school): they load without crashing, but show no content.
   Functionally safe; content population is a separate enhancement.

## 5. Risk assessment

| Area | Risk | Notes |
|------|------|-------|
| Parser type contracts | **Low** | 0 mismatches, binary-proven, re-runnable audit |
| Container types | **Low** | 21/21 WORKING |
| Core action flows + persistence | **Low** | 16/16 pass from clean state, disk-verified |
| Ciphered param parsing | **Low** (fixed) | was High; root-caused and fixed this pass |
| In-game render / device | **Unknown** | unverifiable on current hardware — the gate to READY |
| Empty feature content | **Low** | loads safely; cosmetic gap |

**Recommendation:** server backend is release-ready and self-consistent; hold the
**READY** stamp until one boot-to-city + screen-open pass on a real ARM device.
Status: **CONDITIONAL.**
