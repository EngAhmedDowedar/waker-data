# Reverse-engineered JSON schemas (libcity_ar.so, v1.1.38)

Field names extracted from parser bodies via PIC string base 0x75ab20.
Type inference: `*Types`/plural/`giftProbabilities`/`exchanges`/`classes` = arrays;
`*Ratio`/`*Interval`/`*Cost`/`*Max`/`*Min`/`*Closed`/`show*`/`enable*`/`*Flag` = scalar int/bool.

## /city/impart  (CImpart::ParseImpart @0x468ef8) — game config, 201 keys
Scalars (sample): goldBuyShow heartbeat tapjoyAd popupAd popup91 gridCapacity recoverInterval
moralRecoverInterval bloodMoneyRatio battleContinuousFightInterval maxRounds bankLocalCostPercent
bankTravelCostPercent randomGoodsRatio breakPrisonCostBrave bustPrisonCostEnergy flowerGoldRatio
gangBattleTimeLimit rewardRatio adCost warehouseMaxSize warehouseMinSize achievementLevels gangSkillLevels
chatMsgInterval topMsgInterval gangBatlleInitLimit GMTTimeOffset recoverBraveAmount recoverEnergyAmount
newbieChatAgeLimit newbieChatLevelLimit gamblingClosed slotClosed point21Closed slotDelayTimeMS slotExit
point21Exit point21MaxMoney slotMeddleRatio dealTaxRatio cityWarNpcGoodsUpRatio cityWarNpcGoodsDownRatio
cityWarRegisterEndTime cityWarRegisterStartTime fightMinBloodRatio enterDungeonsBloodLimit luckyLimit
playerBodyPropLimit cityWarRefreshInterval cityWarDeclareCost braveCoolingMax minRentDays estateRentTax
estateSellTax guardMax guardMin multiple vipShowType fortumoswitch bossWarRefreshTimeS turntableMs
turntableFlag turntablePrice tenTurntablePrice expireSecond enableRater chatInterval isToLock
strengthenStoneRatio strengthenHonorRatio strengthenMoneyRatio strengthenAttrRatio strengthenMultiple
showHelp showDealStrengthen fightFailMsgLevel vipExtraLoginGiftTimes loginGiftGoldToolRatio maxChannelCount
maxUserPerChannel voiceRoomTime ladderFightInterval ladderRefreshFreeTimes FBShareShow FBShareRewardCategory
FBShareRewardType FBShareRewardAmount maxPlayerEnergy useDailyLogType notVipBigHornNum showMasterAlert
troopTimes openTroopTimes joinedPoints useOptimizeMapRender optimizeMapMainSubNum showTravelMap travelMapURL
goldBuyFullHP coolingTime maxFriendNum unVipGoodsLockLim vipGoodsLockLim useSysEmailFdBk sysEmailAddress
faqUseGameHelp GHcontactForPayOnly GHContactHideForBan GHNewBieLevelLimit EnableGH modNeedProof
itemScreenUseOldWay enableVerifyACCT verifyAllowTimes verifyWTS verifyPWTS verifyUTA enableDGTip
point21WinRatio levelBodyPropRatio customHousePicCostType customHousePicCostNum verfiyEmailCheckNum
changeWindowStatusGold flySpeedUpCost
Array/object sections: gymTypes gymServiceDetails jobTypes armsTypes armorTypes cbWeapons collectTypes
foodTypes medicineTypes drugTypes estateTypes maidTypes decorationTypes companyTypes specialityTypes
crimeTypes funcToolTypes goldToolTypes pointCards pointcardOverride meritSkillTypes gangSkillTypes
debrisTypes gangLevels robots inviteRewards loginGifts gangSKillLimit vipSkillTypes mountsTypes
giftPackTypes giftPackDetails classes giftProbabilities exchanges mentoringConstant dungeonConditions
dungeonInfos dungeonDetails dungeonConstant ladderConstant aerolites strengthens dungeonActions
rewardContents fund showDecoratorTypes auctionConstant volunteerAuths crimeCategories troopPrizes
bossDiffculty bossFixInfo ybItems titleTypes titleRights activityTasks gangBosses dealBossLevel tradeConfig
crossServerWarConfig payssionItemIdx arsenals selfArsenals forceConfig forceAwake verifyPayment clientConfig
customHouseConfig carTypes carEquipTypes huntGoodsTypes huntCar huntTool cuisines

## CPlayer::Parse @0x5140bc — self/player account, 168 fields
id uid name level exp strength endurance speed agile basicStrength basicEndurance basicSpeed basicAgile
hornNum defense gender playerKey gold vip vipExpireAt payed newPlayer createdAt maritalStatus
maritalRegistered spouse spouseName liveEstate avatarAt playerRole energyAt boughtRecoverEnergy brave braveUp
moral moralUp moralAt signature loginGift loginContinuousDays missionId missionProgress thriceNum crimeSuccess
jailHalved firstPayed firstPayGifted payLevel team raceRoomId raceMatchType energy energyUp blood bloodUp
happy happyUp money cheque merits totalMerits warehouseSize drugAddictionTreatMoney levelMathSum
rechargeMathSum friendNum holdemServer holdemStatus holdemPort holdemHost holdemEncrypted holdemHBInterval
keepLiveServer keepLiveServerPort keepLiveServerHost streetWarServer meritSkill goods bagMaxSize bags
dealMaxSize crimeSkilled playerStatus statInfo fightTimes jailTimes hospitalTimes crimeTimes flightTimes
randomAwardTimes remedyDrugTimes playerExtra highestJobs gangMember gang estates liveEstateObj messages
bankAccount employee relationRequests cityLoves activitiyExtra activities growthNums dailyTask cityOccupy
crossServerWarOccupy ladderTop crossLadderShow funcTags playerDrugs dungeonPlayer playerDailyTaskId
playerDailyTaskItemIdx playerEventFlag playerEventValue playerPendingFlag playerMeritsFlag hasGangBattle
FBSharePrize cloakingAt timeMachine gangBossFlag tradeFlag attendActiviesInfo flag clockIn
activityOpenedFlags turntables turntableOpening bigHornNum hasCooperateBoss cprtLevelLimit storedEnergy
gangLoyalty emblem goodsLocks titleList king unionKing activityVersion arsenalTopLevel isOpenFF
arsenalLimitLevel selfArsenals FGConfig forceType isCanSwitch force curLightNum returnLoginSum returnGift
regressEnd activeEnd checkSearchAd htPlayer cuisines emailVerifyOpen emailVerified merEffectStrength
merEffectSpeed merEffectEndurance merEffectAgile merToStrength merToSpeed merToEndurance merToAgile merLearnOpen

## CPlayer HUD / resource fields (verified on-device)
- The top-HUD resource bars render "current/max" where the **`*Up` field is the MAX**:
  energy/energyUp, blood/bloodUp, happy/happyUp, brave/braveUp (and moral/moralUp).
  Setting `*Up:0` => bar shows "current/0" (the regression). Set current and `*Up`.
- `playerStatus` is an OBJECT (CPlayer::ParseStatus @0x516254): {cityId, status, statusAt,
  statusDuration, statusExtra, statusExtraDesc, noFightedExpireAt}. status=0 = normal.
- `cityOccupy` object (CPlayer::ParseCityOccupy @0x516f50): {cityId, gangId, occupyFlag,
  occupyExpireAt, gang, prizeFlag, leadGang}.
- `goods`/`bags` = arrays of CGoods (CPlayer::ParseGoods @0x516180 / ParseBags @0x516194).
- `estates` = array of CHouse. `liveEstateObj` = a single CHouse.
- These objects/arrays MUST be the right type (object vs array) or the sub-parser crashes;
  omitting a key is safe (GetNode null => sub-parse skipped) but leaves that data empty.

## Per-entry sub-schemas
- CHouse::Parse @0x4498d8 (estate; estateType -> property.city id, CaoPeng=800):
  id estateType systemEstate decoration1 decoration2 decoration3 maid1 maid1ExpireAt maid2 maid2ExpireAt
  ownerId renterId renterName ownerName status sellPrice rentPrice rentExpireAt rentDays maintainExpireAt
  customHouseAt customHouseTag
- CGoods::Parse @0x40cc70: id type amount category boughtPrice canUseTime convertGoods
- CProperty::Parse @0x51f67c (property TYPE config): proxyPrice basicHappy maintainCost canDeal canSell canRent
- getcitygoods (CMarketCateScreen::ParseGoodsAmount @0x4c2fe8): { goodsList: [ {category, type, amount} ] }

## .city config tables (assets/*.city) — big-endian, u16 count @0, then records.
Per record: loader reads id (BE32, = the GetById key) first, then CProperty::Read consumes fields + name.
property.city: 18 houses, ids start 0x320=800 (CaoPeng). product.city: 194 goods.
