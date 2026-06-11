# Implementation Priority — Server Route Roadmap

Systematic order for implementing all remaining server routes.
Priority based on: crash risk > boot-path reachability > feature completeness.

---

## Phase 0: Already Done (16 crash-proof routes)

These `data:[]` stubs are already in server.py and prevent Class A (null-iterator) crashes:

```
✓ /city/airline/airlines        ✓ /city/hospital/patients
✓ /city/chat/getsysmsgs         ✓ /city/jail/prisonerlist
✓ /city/chat/gettopmsgs         ✓ /city/event/list
✓ /city/chat/getmsg             ✓ /city/player/logingifts
✓ /city/gang/randomgangs        ✓ /city/marital/candidates
✓ /race/car/getcars             ✓ /city/player/introplayers
✓ /race/car/getstoreitems       ✓ /city/fight/randomfighters
✓ /city/connect/getplayerlist   ✓ /city/job/getjobs
```

---

## Phase 1: Remaining CRITICAL Crash Routes (15 routes)

**All return `data:[]`.** These crash the game if their screen is opened.
Single batch — add all at once to eliminate all Class A crashes.

```python
# --- PHASE 1: CRITICAL array-iterator crash prevention ---

# Store & Shop
@app.route('/city/store/catelist', methods=['GET', 'POST', 'PUT'])       # CStoreCateScreen
@app.route('/city/showwindow/list', methods=['GET', 'POST', 'PUT'])     # CUpdateWindowOrderScreen

# Skyscraper
@app.route('/city/skyscraper/list', methods=['GET', 'POST', 'PUT'])     # CSkyscraperScreen

# Lottery
@app.route('/city/lottery/info', methods=['GET', 'POST', 'PUT'])        # CLotteryScreen
@app.route('/city/lottery/prizes', methods=['GET', 'POST', 'PUT'])      # CLT_CollectPrizeScreen
@app.route('/city/lottery/records', methods=['GET', 'POST', 'PUT'])     # CLT_CollectRecordScreen

# Mercenary
@app.route('/city/mercenary/helpandbattle', methods=['GET', 'POST', 'PUT'])  # CMS_HelpAndBattleScreen
@app.route('/city/mercenary/rank', methods=['GET', 'POST', 'PUT'])      # CMS_RankScreen
@app.route('/city/mercenary/ybclass', methods=['GET', 'POST', 'PUT'])   # CMS_YbClassSummeScreen

# Hunt
@app.route('/city/hunt/store/list', methods=['GET', 'POST', 'PUT'])     # CHG_StoreScreen

# Cross-server War
@app.route('/city/crossserverwar/joinlist', methods=['GET', 'POST', 'PUT'])  # CNCW_JoinCorpListScreen

# Racing
@app.route('/race/match/maplist', methods=['GET', 'POST', 'PUT'])       # CRG_MapListScreen
@app.route('/race/match/dungeon/info', methods=['GET', 'POST', 'PUT'])  # CRG_RaceDungeonListScreen
@app.route('/race/match/record', methods=['GET', 'POST', 'PUT'])        # CRG_RecordScreen
@app.route('/race/match/recorddesc', methods=['GET', 'POST', 'PUT'])    # CRG_RecordDescScreen

# All return:
def _empty_array():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})
```

**Estimated effort: 15 minutes.** Copy the pattern from existing stubs. No field analysis needed.

---

## Phase 2: HIGH Risk Routes (6 routes)

These have array-iterator sub-parsers WITHOUT confirmed null guards. Need binary verification
of each before deciding `data:[]` vs `data:{}`. Verify first, then add route.

| # | Endpoint | Class | Sub-Parser | Action |
|---|----------|-------|-----------|--------|
| 1 | `/city/fight/statistics` | CBattleStatisticsScreen | ParseBattleStatistics | Verify guard → add route |
| 2 | `/city/feedback/list` | CFeedbackScreen | ParseChilds | Verify guard → add route |
| 3 | `/city/helper/list` | CHelperScreen | ParseList | Verify guard → add route |
| 4 | `/city/goods/marketlist` | CMarketScreen | ParseGoodsAmount | Verify guard → add route |
| 5 | `/city/rank/nationalbid` | CNationalBidScreen | Parse | Verify guard → add route |
| 6 | `/city/game/circle` | CCircleMnger | ParseCircle | Verify guard → add route |

**Estimated effort: 1 hour.** 10 min binary check per endpoint + route addition.

**Note:** `/city/news/frontpage` was listed as HIGH but already verified safe — ParseNews dispatcher
null-guards all sub-parser calls. No additional route needed (catch-all `data:{}` works).

---

## Phase 3: Class B (Rendering) Crash Investigation

The remaining crash class after all Class A elimination. Deferred per user instruction.

**Symptoms:**
- Fault addr: non-zero, ASCII-like (e.g., `0x657a697b` = "{ize", `0x756f707b` = "{pou")
- Stack: `ngView::LayoutNode` → rendering/layout code
- Trigger: appears on estate/goods screens

**Investigation plan:**
1. Identify which screen triggers it (estate? goods? both?)
2. Check if it's a CSS/layout string parse issue (the ASCII fault addrs suggest a string being used as pointer)
3. May need response with valid field structure (not just empty array/object)

---

## Phase 4: Core Gameplay Stubs (object-safe endpoints)

These hit the catch-all and return `data:{}` without crashing (MEDIUM/LOW risk, null-guarded).
Adding dedicated routes lets us return meaningful data later.

### 4a. City Navigation (most likely to be visited)

| Priority | Endpoint | Current Status |
|----------|----------|---------------|
| 1 | `/city/bank/checkbalance` | Catch-all `data:{}`, safe |
| 2 | `/city/school/applyclass` | Catch-all `data:{}`, safe |
| 3 | `/city/school/getmyclasses` | Catch-all `data:{}`, safe |
| 4 | `/city/gym/enter` | Catch-all `data:{}`, safe |
| 5 | `/city/monthCard/enterMatchCard` | Catch-all `data:{}`, safe |
| 6 | `/city/estate/listestates` | Has route, returns `data:{}` |
| 7 | `/city/goods/getcitygoods` | Has route, returns `data:{}` |
| 8 | `/city/marital/status` | Catch-all `data:{}`, safe |
| 9 | `/city/marital/register` | Catch-all `data:{}`, safe |
| 10 | `/city/news/frontpage` | Catch-all `data:{}`, safe |

### 4b. Faction System

| Priority | Endpoint |
|----------|----------|
| 11 | `/city/faction/list` |
| 12 | `/city/faction/info` |
| 13 | `/city/faction/members` |
| 14 | `/city/faction/create` |
| 15 | `/city/faction/requests` |
| 16 | `/city/faction/manage` |

### 4c. Fight System

| Priority | Endpoint |
|----------|----------|
| 17 | `/city/fight/bosslist` |
| 18 | `/city/fight/bossfight` |
| 19 | `/city/fight/breakrecord` |
| 20 | `/city/fight/lookbattle` |

### 4d. Social

| Priority | Endpoint |
|----------|----------|
| 21 | `/city/message/inbox` |
| 22 | `/city/mentoring/list` |
| 23 | `/city/mentoring/relation` |

### 4e. Economy

| Priority | Endpoint |
|----------|----------|
| 24 | `/city/auction/list` |
| 25 | `/city/auction/events` |
| 26 | `/city/deal/list` |
| 27 | `/city/deal/detail` |
| 28 | `/city/trade/list` |
| 29 | `/city/trade/info` |

---

## Phase 5: Feature-Rich Endpoints (need real data)

These need actual structured responses to be useful. Each is a mini-project.

### 5a. Estate System (enables property gameplay)
```
/city/estate/listestates  → return property categories with prices
/city/estate/listbytype   → return properties by type
/city/estate/buy          → process purchase, update player
/city/estate/decorate     → process decoration
```
Requires: property.city catalog table parsing, player money tracking.

### 5b. Goods/Market System (enables trading)
```
/city/goods/getcitygoods  → return available city goods
/city/goods/market        → return market categories
/city/goods/marketlist    → return goods for sale
/city/goods/equipment     → return equipment list
```
Requires: goods catalog parsing, pricing logic.

### 5c. Job System (enables income)
```
/city/job/getjobs         → return available jobs with requirements
/city/job/work            → process work action, award money/XP
```
Requires: job.city catalog, CPlayer stat updates.

### 5d. School System (enables training)
```
/city/school/subjects     → return available subjects
/city/school/applyclass   → enroll in class
/city/school/getmyclasses → return current enrollments
```
Requires: school catalog, time tracking.

### 5e. Crime System (enables crime gameplay)
```
/city/crime/docrime       → process crime attempt, return result
```
Requires: crime success probability, reward/punishment logic.

### 5f. Mission System (enables story progression)
```
/city/mission/getmission    → return current mission
/city/mission/updatemission → advance mission state
```
Requires: mission.city catalog, state machine.

---

## Phase 6: Advanced Systems (low priority)

Systems requiring complex game state or multi-screen flows:

| System | Endpoints | Complexity |
|--------|-----------|-----------|
| Mercenary | 11+ endpoints | High — skill trees, battles, inventory |
| King Fight | 5 endpoints | High — multiplayer combat |
| Force Arena | 4 endpoints | High — boss battles, rankings |
| Corp/War | 14+ endpoints | Very High — faction warfare |
| Racing (full) | 12+ endpoints | Very High — real-time races |
| Hunt | 5 endpoints | Medium — capture mechanics |
| Ladder | 2 endpoints | Medium — PvP rankings |
| Cross-server | 8 endpoints | Very High — would need multi-server |
| Mini-games | 4 endpoints | Medium — game logic |

---

## Quick Reference: Route Count by Phase

| Phase | Routes | Effort | Crash Risk |
|-------|--------|--------|-----------|
| 0 (Done) | 16 | — | Eliminated |
| 1 (CRITICAL) | 15 | 15 min | Eliminates all remaining Class A |
| 2 (HIGH verify) | 6 | 1 hour | Catches edge-case crashes |
| 3 (Class B) | 0 | Research | Rendering crashes |
| 4 (Core stubs) | ~29 | 2 hours | No crash risk, enables navigation |
| 5 (Feature-rich) | ~15 | Days | Enables actual gameplay |
| 6 (Advanced) | ~60 | Weeks | Full game restoration |
| **Total remaining** | **~125** | | |

---

## Immediate Next Step

**Do Phase 1 now.** Add all 15 CRITICAL routes in one batch. This eliminates every possible
Class A crash across the entire game, not just the boot path. Takes 15 minutes.

After Phase 1, the only crashes should be Class B (rendering) which require a different
investigation approach (response structure, not just container type).
