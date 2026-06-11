# CImpart Reverse Engineering Analysis

## What is CImpart?

CImpart is a game-configuration singleton that holds ~199 key-value pairs controlling
gameplay constants (intervals, ratios, limits, feature flags, item type tables, dungeon
configs, etc.). It is fetched from `/city/impart` on port 9090 during LoadingMnger step 10.

## The Error

```
[ERROR][Impart]parseImpart,but there has no data!!!!
```

**This error also appeared during the May 29 known-good boot with the original server.**
The original server returned `data:{}` for `/city/impart` (confirmed in
`analyze/logs/protocol_dump.log` lines 62–93). The error is expected when no
server-side impart config is populated.

## Binary Analysis

### Key Symbols

| Symbol | Address (THUMB) | Purpose |
|--------|----------------|---------|
| `CImpart::ParseImpart(void*)` | `0x468EF9` | Main parser — receives JSON `data` node |
| `CImpart::Parse(void*)` | `0x468D01` | Thin wrapper → calls `ParseImpart` |
| `CImpart::LoadImpart()` | `0x468E65` | Loads from local cache `city_impart.bin` |
| `CImpart::SaveImpart(void*)` | `0x468D09` | Saves to local cache `city_impart.bin` |
| `CImpart::Clear()` | via `BL` at `0x468F10` | Resets all 199 fields to defaults |
| `CImpart::GetImpartTime()` | `0x11BF22` (sym) | Returns cached timestamp |

### Error String Location

```
.rodata offset 0x6FF469: "[ERROR][Impart]parseImpart,but there has no data!!!!"
```

### Local Cache Files

- `city_impart.bin` — serialized impart data (string offset `0x6FF404`)
- `city_impart_time.bin` — timestamp of last successful impart fetch (string offset `0x6FF445`)

## ParseImpart Control Flow

Disassembly of `CImpart::ParseImpart` at `0x468EF8` (THUMB-2):

```arm
PUSH    {R4-R7, LR}
SUB     SP, SP, #0xC
MOV     R5, R1              ; R5 = data (JSON node pointer)
MOV     R4, R0              ; R4 = this (CImpart*)
CMP     R5, #0              ; data == NULL?
BNE     skip_log            ; if not null, skip error log
BL      __android_log_print ; "[ERROR][Impart]parseImpart,but there has no data!!!!"
skip_log:
MOVS    R6, #0
STR     R6, [SP, #8]
STR     R6, [R4, #0x40]     ; this->field_0x40 = 0
MOV     R0, R4
BL      CImpart::Clear      ; reset all 199 fields to defaults
MOVS    R0, #0x35            ; 53
LSLS    R0, R0, #5           ; 53 * 32 = 1696
STR     R6, [R4, R0]         ; this[1696] = 0
ADDS    R6, R4, R0           ; R6 = this + 1696
; ... continues to look up each key from R5 (JSON data node) ...
```

### Critical finding: NO early return on null data

When `data == NULL`, the function:
1. Logs the error
2. **Falls through** (does NOT return)
3. Calls `CImpart::Clear()` — zeros all 199 config fields
4. Proceeds to attempt key lookups from the null JSON node
5. Each lookup returns null/0, so each field keeps its cleared default

This means the game continues with **all 199 impart config values at zero/default**.

## Why data is NULL

The server returns `{"result":0, "code":200, "errorMsg":"", "data":{}}`.

The native JSON parser (likely cJSON or similar) creates a valid node for `{}`, but
the node has no children (`node->child == NULL`). The response envelope parser
extracts `data` and gets a valid empty-object node. The call chain then passes
`node->child` (NULL) to `ParseImpart`, triggering the error.

Evidence: the format strings `"impart to string length %d"` and `"impart file length %d"`
at `.rodata 0x6FF414` are in `LoadImpart`/`SaveImpart` — these reference the raw
response body size, suggesting the cipher-decoded body is parsed, then `data`'s child
pointer is forwarded.

## The 199 Config Keys

Extracted from `.rodata` starting at offset `0x6FF4A0` (immediately after the error
string). These are the JSON keys that `ParseImpart` looks up sequentially:

### Scalar configs (gameplay constants)
```
goldBuyShow, tapjoyAd, popupAd, popup91, gridCapacity, recoverInterval,
moralRecoverInterval, bloodMoneyRatio, battleContinuousFightInterval, maxRounds,
bankLocalCostPercent, bankTravelCostPercent, randomGoodsRatio, breakPrisonCostBrave,
bustPrisonCostEnergy, flowerGoldRatio, gangBattleTimeLimit, rewardRatio, adCost,
warehouseMaxSize, warehouseMinSize, chatMsgInterval, topMsgInterval,
gangBatlleInitLimit, GMTTimeOffset, recoverBraveAmount, recoverEnergyAmount,
newbieChatAgeLimit, newbieChatLevelLimit, gamblingClosed, slotClosed, point21Closed,
slotDelayTimeMS, slotExit, point21Exit, point21MaxMoney, slotMeddleRatio,
dealTaxRatio, cityWarNpcGoodsUpRatio, cityWarNpcGoodsDownRatio,
cityWarRegisterEndTime, cityWarRegisterStartTime, fightMinBloodRatio,
enterDungeonsBloodLimit, luckyLimit, playerBodyPropLimit, cityWarRefreshInterval,
cityWarDeclareCost, braveCoolingMax, minRentDays, estateRentTax, estateSellTax,
guardMax, guardMin, multiple, vipShowType, fortumoswitch, bossWarRefreshTimeS,
turntableMs, turntableFlag, turntablePrice, tenTurntablePrice, expireSecond,
enableRater, chatInterval, isToLock, strengthenStoneRatio, strengthenHonorRatio,
strengthenMoneyRatio, strengthenAttrRatio, strengthenMultiple, showHelp,
showDealStrengthen, fightFailMsgLevel, vipExtraLoginGiftTimes,
loginGiftGoldToolRatio, maxChannelCount, maxUserPerChannel, voiceRoomTime,
ladderFightInterval, ladderRefreshFreeTimes, FBShareShow, FBShareRewardCategory,
FBShareRewardType, FBShareRewardAmount, maxPlayerEnergy, useDailyLogType,
notVipBigHornNum, showMasterAlert, troopTimes, openTroopTimes, joinedPoints,
useOptimizeMapRender, optimizeMapMainSubNum, showTravelMap, travelMapURL,
goldBuyFullHP, coolingTime, maxFriendNum, unVipGoodsLockLim, vipGoodsLockLim,
useSysEmailFdBk, sysEmailAddress, faqUseGameHelp, GHcontactForPayOnly,
GHContactHideForBan, GHNewBieLevelLimit, EnableGH, modNeedProof,
itemScreenUseOldWay, enableVerifyACCT, verifyAllowTimes, verifyWTS, verifyPWTS,
verifyUTA, enableDGTip
```

### Array/object configs (type tables, parsed by dedicated sub-methods)
```
gymTypes, gymServiceDetails, jobTypes, armsTypes, armorTypes, cbWeapons,
collectTypes, foodTypes, medicineTypes, drugTypes, estateTypes, maidTypes,
decorationTypes, companyTypes, specialityTypes, crimeTypes, funcToolTypes,
goldToolTypes, pointCards, pointcardOverride, meritSkillTypes, gangSkillTypes,
debrisTypes, gangLevels, robots, inviteRewards, loginGifts, gangSKillLimit,
vipSkillTypes, mountsTypes, giftPackTypes, giftPackDetails, point21WinRatio,
levelBodyPropRatio, classes, giftProbabilities, exchanges, mentoringConstant,
dungeonConditions, dungeonInfos, dungeonDetails, dungeonConstant, ladderConstant,
aerolites, strengthens, dungeonActions, rewardContents, fund, showDecoratorTypes,
auctionConstant, volunteerAuths, crimeCategories, troopPrizes, bossDiffculty,
bossFixInfo, ybItems, titleTypes, titleRights, activityTasks, gangBosses,
dealBossLevel, tradeConfig, payssionItemIdx, arsenals, forceConfig, forceAwake,
verifyPayment, clientConfig, customHouseConfig, customHousePicCostType,
customHousePicCostNum, carTypes, carEquipTypes, huntGoodsTypes, huntCar, huntTool,
verfiyEmailCheckNum, changeWindowStatusGold, flySpeedUpCost, HBCCV2, HBCCTime
```

**82 dedicated `CImpart::Parse*` sub-methods** handle the array/object configs.

## Does Empty Impart Hide Future Crashes?

**No.** The empty impart does NOT cause the post-step-13 crash. Evidence:

1. The May 29 known-good boot also received `data:{}` and still reached the city
   screen without crashing.
2. The post-step-13 crash pattern (`building N released` → `lowmemorykiller` →
   "has stopped") matches the known CPlayer field-type issue documented in
   `feedback_cplayer_field_types_unverified.md`, not an impart config issue.
3. ParseImpart handles null data gracefully — it clears to defaults and continues.
   The bundled `.city` asset tables provide fallback data for type lookups.

### Potential latent issues from zero impart values

While not causing crashes, zero defaults for these configs could cause gameplay bugs:

| Key | Risk if zero |
|-----|-------------|
| `gridCapacity` | Zero grid/bag slots |
| `recoverInterval` | Zero-interval recovery timer (potential tight loop) |
| `maxRounds` | Zero max fight rounds |
| `warehouseMaxSize` | Zero warehouse capacity |
| `chatMsgInterval` | Zero chat throttle |
| `maxPlayerEnergy` | Zero energy cap |

These would only matter during actual gameplay interactions, not during boot.
The original live server would have populated these with real values.

## Fetch Flow

```
Step 10 starts
  → Client checks city_impart_time.bin (local cache timestamp)
  → Client sends PUT /city/impart to keepLiveServerHost:9090
  → Server returns {result:0, data:{}}
  → Native JSON parser: data node exists but has no children
  → ParseImpart receives NULL (child pointer of empty object)
  → Logs error, calls Clear(), all 199 keys → defaults
  → SaveImpart skipped (no data to cache)
  → Step 10 continues → keepalive established → step 11+
```

## Recommendation

The impart error is **safe to ignore** for boot-flow work. To fix it properly later:

1. Populate `data` with non-empty values for the scalar configs that affect gameplay
2. The array/object configs can remain empty — they fall back to bundled `.city` tables
3. Priority keys to populate first: `gridCapacity`, `recoverInterval`, `maxRounds`,
   `warehouseMaxSize`, `maxPlayerEnergy`, `maxFriendNum`
4. Values can be reverse-engineered from the bundled .city asset defaults or from
   captures of the original live server
