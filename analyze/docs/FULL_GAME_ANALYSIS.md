# Full Game Analysis — Waker (وكر الاوغاد) Server Map

Binary: `libcity_ar.so` SHA256 `18D15117...`
Generated: 2026-06-11 from `.dynsym` (36,881 symbols) + server logs + route audit.

---

## 1. Endpoint Inventory

### 1a. Existing Server Routes (43 implemented)

| # | Route | Handler | Status |
|---|-------|---------|--------|
| 1 | `/checkversion` | Full v6 schema | Working |
| 2 | `/api/connect` | Login flow | Working |
| 3 | `/api/authplayerkey` | Auth resume | Working |
| 4 | `/api/getallserver` | Server list | Working |
| 5 | `/city/impart` | Config singleton | Working |
| 6 | `/city/connect/getplayerlist` | Player list | Working |
| 7 | `/city/connect/connect` | CPlayer payload | Working |
| 8 | `/city/connect/create` | CPlayer payload | Working |
| 9 | `/city/player/introplayers` | Intro list | Stub `data:[]` |
| 10 | `/city/goods/getcitygoods` | City goods | Stub `data:{}` |
| 11 | `/city/estate/listestates` | Estate list | Stub `data:{}` |
| 12 | `/city/estate/buy` | Estate purchase | Stub `data:{}` |
| 13 | `/city/fight/randomfighters` | Fighter list | Stub `data:[]` |
| 14 | `/city/chat/gettopmsgs` | Top messages | Stub `data:[]` |
| 15 | `/city/chat/getmsg` | Chat messages | Stub `data:[]` |
| 16 | `/city/chat/<path:cmd>` | Chat catch-all | Stub `data:{}` |
| 17 | `/city/gang/randomgangs` | Gang list | Stub `data:[]` |
| 18 | `/city/mission/updatemission` | Mission update | Stub `data:{}` |
| 19 | `/city/mission/getmission` | Mission query | Stub `data:{}` |
| 20 | `/city/player/updatelevel` | Level up | Stub `data:{}` |
| 21 | `/city/player/pause` | Pause | Stub `data:{}` |
| 22 | `/city/heartbeat` | Keepalive | Stub `data:{}` |
| 23 | `/game/maintenance/check` | Maint check | Stub `data:{}` |
| 24 | `/city/job/getjobs` | Job list | Stub `data:[]` |
| 25 | `/city/job/work` | Work action | Stub `data:{}` |
| 26 | `/city/gym/getgym` | Gym info | Stub `data:{}` |
| 27 | `/city/gym/train` | Gym train | Stub `data:{}` |
| 28 | `/city/crime/docrime` | Crime action | Stub `data:{}` |
| 29 | `/city/player/getplayerinfo` | Player info | Stub `data:{}` |
| 30 | `/city/friend/getfriends` | Friend list | Stub `data:{}` |
| 31 | `/city/player/getranking` | Rankings | Stub `data:{}` |
| 32 | `/city/goods/playerbags` | Bag contents | Stub `data:{}` |
| 33 | `/city/goods/playergoods` | Goods list | Stub `data:{}` |
| 34 | `/city/airline/airlines` | Airline list | Stub `data:[]` |
| 35 | `/city/chat/getsysmsgs` | System msgs | Stub `data:[]` |
| 36 | `/race/car/getcars` | Car list | Stub `data:[]` |
| 37 | `/race/car/getstoreitems` | Store items | Stub `data:[]` |
| 38 | `/city/hospital/patients` | Patient list | Stub `data:[]` |
| 39 | `/city/jail/prisonerlist` | Prisoner list | Stub `data:[]` |
| 40 | `/city/event/list` | Event list | Stub `data:[]` |
| 41 | `/city/player/logingifts` | Login gifts | Stub `data:[]` |
| 42 | `/city/marital/candidates` | Candidates | Stub `data:[]` |
| 43 | `/city/<path:cmd>` | **CATCH-ALL** | Returns `data:{}` |

### 1b. Catch-all Behavior

Two catch-alls exist:
- `/city/<path:cmd>` → returns `data:{}` (object)
- `/<path:path>` → returns `data:{}` (object)

The catch-all returns the correct shape for **object-expecting** parsers but crashes **array-expecting** parsers (see §3 Crash Risk).

---

## 2. Screen Inventory (277 network-active classes)

### 2a. By Subsystem

**City Core (port 8080/9090)**

| Subsystem | Screens | Base Path |
|-----------|---------|-----------|
| Connect/Auth | CPlayer, CLoadingScreen, CNewLoginScreen, CLoginEnScreen, CServerChooseScreen, CNewServerChooseScreen, CGuestLoadScreen, CRoleChooseScreen | `/checkversion`, `/api/*`, `/city/connect/*` |
| Chat | CChatScreen, CTopScreen | `/city/chat/*` |
| Estate/Property | CPropertyCateScreen, CPropertyListScreen, CPropertyListCateScreen, CDecorateScreen | `/city/estate/*` |
| Goods/Inventory | CGoodsScreen, CGoodsBuyScreen, CGoodsSellScreen, CGoodsSelltoNPCScreen, CGoodsLockInScreen, CEquipmentScreen, CBlackMarketScreen | `/city/goods/*` |
| Market/Trade | CMarketCateScreen, CMarketScreen, CDealMarketScreen, CDealMarketDetailScreen, CPersonalExchangeListScreen, CPersonalExchangeScreen, CPersonalExchangeRecordScreen | `/city/goods/market*`, `/city/deal/*`, `/city/trade/*` |
| Jobs | CHrMarketCateScreen | `/city/job/*` |
| School | CSchoolScreen, CSchoolCateScreen, CGraduateScreen | `/city/school/*` |
| Gym | CGymScreen | `/city/gym/*` |
| Hospital | CHospitalScreen, CInHospitalScreen, CCureScreen, CDetoxifcationScreen | `/city/hospital/*` |
| Crime | CCrimeScreen | `/city/crime/*` |
| Prison | CPrisonScreen, CInPrisonScreen | `/city/jail/*` |
| Bank | CBankScreen | `/city/bank/*` |
| Fight | CFightingScreen, CBattleStatisticsScreen, CLookBattleScreen | `/city/fight/*` |
| Boss Fight | CFF_BossListScreen, CFF_FightScreen, CFF_BreakRecordScreen, CFF_BreakDownScreen, CFF_FightRankScreen | `/city/fight/boss*` |
| Faction | CFactionScreen, CFactionInfoScreen, CFactionInformationScreen, CFactionMemberScreen, CFactionMngMbrScreen, CFactionCreateScreen, CFactionRequestScreen, CFactionBattleScreen, CFactionManageScreen, CFactionSkillScreen, CFactionEnemyScreen, CFactionContributeScreen, CFactionUpgradeScreen, CFactionFlagScreen, CFactionTitleScreen, CFactionFactoryApplyScreen, CFactionFactoryApproveScreen, CFactionFactoryProcessScreen, CApplicationListScreen | `/city/faction/*` |
| Gang | (uses CGangScreen via catch-all) | `/city/gang/*` |
| Gang Boss | CBossWarScreen | `/city/gangboss/*` |
| Friend | CFriendScreen | `/city/friend/*` |
| Mail | CMailScreen, CMailNewScreen, CMailShowScreen, CMailThreadScreen, CMailVerifScreen | `/city/message/*` |
| News | CNewspaperScreen, CAdvertiseScreen | `/city/news/*` |
| Marital | CMaritalStatusScreen, CMarriageScreen, CMarryRegisterScreen | `/city/marital/*` |
| Airline | CAirportScreen, CAirLineScreen | `/city/airline/*` |
| Guard | CGuardScreen, CGuardUploadScreen | `/city/guard/*` |
| Helper | CHelperScreen | `/city/helper/*` |
| Store/Shop | CStoreCateScreen, CStorePackage, CStrengthenShopScreen | `/city/store/*` |
| Showwindow | CUpdateWindowOrderScreen | `/city/showwindow/*` |
| Skyscraper | CSkyscraperScreen, CSkyscraperEntryScreen | `/city/skyscraper/*` |
| Achievement | CAchievementScreen, CAchievementSkillScreen, CCitierScreen | `/city/achievement/*` |
| Event | CEventScreen, CWeekAwardScreen, CValentineScreen, CThanksgivingV, CActiveScreen, CActiveDetailScreen, CActiveResultScreen, CActiveChallengeMainScreen, CActiveChallengeRankScreen | `/city/event/*`, `/city/activities/*` |
| Login Gifts | CLoginGiftScreen, CNewLoginRewardScreen | `/city/player/logingifts` |
| Reward | CRewardScreen, CRewardEntryScreen | `/city/wanted/*` |
| Vote | CVoteScreen, CVoteStatisticsScreen | `/city/vote/*` |
| Rank | CRankCateScreen, CTournamentScreen, CNationalBidScreen | `/city/rank/*` |
| Player | CPersonalScreen, CPersonActiveScreen, CSetPersonDataScreen, CAvatarScreen, CSearchResultScreen | `/city/player/*` |
| Feedback | CFeedbackScreen | `/city/feedback/*` |
| Red Packet | CReceiveRedPacketScreen | `/city/redpacket/*` |
| Purchase | CRechargeScreen | `/city/purchase/*` |
| Lottery | CLotteryScreen, CLT_CollectPrizeScreen, CLT_CollectRecordScreen, CLT_LotteryActiveScreen | `/city/lottery/*` |
| Auction | CAuctionHouseScreen, CAuctionEventScreen, CAuctionBuyScreen, CAuctionSubmitScreen | `/city/auction/*` |
| Ladder | CLadderScreen, CLadderEventScreen | `/city/ladderfight/*` |
| Month Card | (via catch-all) | `/city/monthCard/*` |
| Heartbeat | CHeartBeat | `/city/heartbeat` |
| Impart | (CImpart) | `/city/impart` |

**Mercenary System**

| Screens | Base Path |
|---------|-----------|
| CMercenaryMainScreen, CMercenaryMnger, CMS_HelpAndBattleScreen, CMS_RankScreen, CMS_YbClassSummeScreen, CMS_ClassMainScreen, CMS_StoreScreen, CMS_FightScreen, CMS_LineupScreen, CMS_LoyaltyScreen, CMS_JinWeiScreen, CMercenaryGymScreen, CMercenaryHouseScreen, CMercenaryInfoScreen, CMercenaryStoreScreen, CMercenaryStoreShelveScreen, CMercenaryChooseScreen, CMercenaryBrainwashScreen, CMercenaryFireScreen, CMercenaryUpSkillScreen, CMercenaryUpStarScreen, CMercenaryWarehouseScreen, CMercenaryCellScreen | `/city/mercenary/*`, `/city/mercenaryGrow/*`, `/city/mercenaryPit/*` |

**Mine System**

| Screens | Base Path |
|---------|-----------|
| CMineBidScreen, CMS_MyMineScreen, CMS_MineMainScreen, CMS_MineAllScreen | `/city/mine/*` |

**Hunt System**

| Screens | Base Path |
|---------|-----------|
| CHG_StoreScreen, CHG_MainScreen, CHG_CaptureScreen, CHG_WarehouseScreen, CHG_SampleShowScreen, CHG_FindPreyScreen | `/city/hunt/*` |

**King Fight**

| Screens | Base Path |
|---------|-----------|
| CKingMainScreen, CKingAppellationScreen, CKingBeatSeleTeamScreen, CKingRightInfoScreen, CKingWalletScreen, CKingFightMnger | `/city/kingfight/*` |

**Force Arena**

| Screens | Base Path |
|---------|-----------|
| CFG_MainScreen, CFG_BossScreen, CFG_AttributeScreen, CFG_AwakenScreen, CFG_ChoiceScreen, CFG_ExchangeScreen, CFG_UpgradeScreen, CFA_MainScreen, CFA_LookProScreen, CFA_RankScreen | `/city/forcearena/*` |

**Corp/War**

| Screens | Base Path |
|---------|-----------|
| CCorpsFightScreen, CCorpsManageScreen | `/city/corp/*` |
| CCityWarScreen, CCityWarResultScreen | `/city/citywar/*` |
| CSW_EntryScreen, CSW_JoinCorpListScreen, CSW_EnterBuildScreen, CSW_MatchStatusScreen, CSW_MatchResultScreen, CSW_ReviveScreen, CMainScreen | `/city/streetwar/*` |
| CNCW_MainScreen, CNCW_JoinCorpListScreen, CNCW_ChallengeScreen, CNCW_EnrollHallScreen, CNCW_SpecialMallScreen | `/city/crossserverwar/*` |
| CCBMainScreen, CCBListScreen, CCLMainScreen | `/city/crossserverladderfight/*` |

**Cooperate Boss**

| Screens | Base Path |
|---------|-----------|
| CCooperateListScreen, CCooperateFightScreen | `/city/cooperateboss/*` |

**Racing System (port 9090)**

| Screens | Base Path |
|---------|-----------|
| CRG_CarWarehouseScreen, CRG_StoreScreen, CRG_CarInfoScreen, CRG_CarRefitScreen, CRG_ChooseComponentScreen | `/race/car/*` |
| CRG_MapListScreen, CRG_RaceDungeonListScreen, CRG_RecordScreen, CRG_RecordDescScreen, CRG_PersonalMapListScreen, CRG_RaceScreen, CRG_MatchAthleticsScreen, CRG_RaceActivityScreen, CRG_RaceDungeonScreen, CRG_MapDetailScreen, CRG_CreatePersonalMatchScreen, CRG_ExchangeSkinScreen | `/race/match/*`, `/race/skin/*` |

**Mini-Games**

| Screens | Base Path |
|---------|-----------|
| SlotMachineScreen, CBlackJackScreen, CBlackMatrixScreen, CMatrixBetScreen | `/city/game/*` |
| CDZ_* (Texas Hold'em) | `/city/game/dz*` |

**Mentoring**

| Screens | Base Path |
|---------|-----------|
| CMasterScreen, CMasterRelationScreen | `/city/mentoring/*` |

---

## 3. Parser Inventory & Crash Risk

### 3a. CRITICAL — OnReceiveResponse itself iterates array (15 classes)

These crash immediately when catch-all returns `data:{}`. Fix: dedicated route returning `data:[]`.

| Class | OnReceiveResponse Addr | Likely Endpoint | Already Fixed? |
|-------|----------------------|-----------------|----------------|
| CHG_StoreScreen | 0x43F701 | `/city/hunt/store/list` | NO |
| CLT_CollectPrizeScreen | 0x4874FD | `/city/lottery/prizes` | NO |
| CLT_CollectRecordScreen | 0x488551 | `/city/lottery/records` | NO |
| CLotteryScreen | 0x495811 | `/city/lottery/info` | NO |
| CMS_HelpAndBattleScreen | 0x49E4B9 | `/city/mercenary/helpandbattle` | NO |
| CMS_RankScreen | 0x4AAD95 | `/city/mercenary/rank` | NO |
| CMS_YbClassSummeScreen | 0x4AD3C9 | `/city/mercenary/ybclass` | NO |
| CNCW_JoinCorpListScreen | 0x4F1301 | `/city/crossserverwar/joinlist` | NO |
| CRG_MapListScreen | 0x538799 | `/race/match/maplist` | NO |
| CRG_RaceDungeonListScreen | 0x53D78D | `/race/match/dungeon/info` | NO |
| CRG_RecordDescScreen | 0x5471C5 | `/race/match/recorddesc` | NO |
| CRG_RecordScreen | 0x547D81 | `/race/match/record` | NO |
| CSkyscraperScreen | 0x575509 | `/city/skyscraper/list` | NO |
| CStoreCateScreen | 0x57AC69 | `/city/store/catelist` | NO |
| CUpdateWindowOrderScreen | 0x59D171 | `/city/showwindow/list` | NO |

### 3b. HIGH — Sub-parser iterates array, NO null guard detected in OnReceiveResponse (7 classes)

May crash if the dispatch path reaches the array sub-parser.

| Class | Addr | Sub-Parser | Likely Endpoint |
|-------|------|-----------|-----------------|
| CBattleStatisticsScreen | 0x332F21 | ParseBattleStatistics | `/city/fight/statistics` |
| CCircleMnger | 0x357AD1 | ParseCircle, ParseCircleNodes | `/city/game/circle` |
| CFeedbackScreen | 0x3F6F4D | ParseChilds | `/city/feedback/list` |
| CHelperScreen | 0x446591 | ParseList | `/city/helper/list` |
| CMarketScreen | 0x4A6F39 | ParseGoodsAmount | `/city/goods/marketlist` |
| CNationalBidScreen | 0x4E8F79 | Parse | `/city/rank/nationalbid` |
| CNewspaperScreen | 0x503A19 | ParseDailyNews, ParseFairInfo, ParseAdvertise | `/city/news/frontpage` |

**Note:** CNewspaperScreen (`/city/news/frontpage`) has an existing route but needs verification — its sub-parsers are array-iterators. Analysis showed the parent `ParseNews` null-guards before calling sub-parsers, so it's actually safe. But the others in this list may crash.

### 3c. MEDIUM — Sub-parser iterates array, null guard present (88 classes)

The OnReceiveResponse null-checks before dispatching to array sub-parsers. Safe with `data:{}` but would crash if data contains a malformed object with wrong field types.

<details><summary>Full list (88 classes)</summary>

| Class | Parse Methods (asterisk = array-iterator) |
|-------|------------------------------------------|
| CAchievementScreen | ParseAchievements* |
| CActiveChallengeRankScreen | ParseFactionRankData*, ParsePersonRankDownData*, ParsePersonRankMidData*, ParsePersonRankUpData* |
| CActiveDetailScreen | ParseKillData* |
| CActiveResultScreen | ParseActiveRank* |
| CAdvertiseScreen | ParseList* |
| CAirportScreen | ParseAirlines* |
| CApplicationListScreen | ParseList* |
| CAuctionEventScreen | ParseEventList* |
| CBossWarScreen | ParseCurrentBossDetail*, ParseDisplayRank* |
| CCBListScreen | ParseList* |
| CCBMainScreen | ParseCBRewardsStatus* |
| CCLMainScreen | ParseFight*, ParseReward* |
| CChatScreen | ParseMsg*, ParsePulledMsg*, ParseTeamMsg*, ParseCKFPublishMsg*, ParseCarPublishMsg*, ParseDzpkPublishMsg*, ParseRedPacketInfo*, ParseNewMsgFlag*, _ParseKingFightMsg*, _ParseKingTitleList* |
| CCitierScreen | ParseAchievements*, ParseHuntSampleData* |
| CCityWarResultScreen | ParseFactionList* |
| CCityWarScreen | ParseCityWar* |
| CCooperateFightScreen | ParseHarmRank* |
| CCooperateListScreen | ParseList* |
| CCorpsFightScreen | ParseFightInfo*, ParseFightResult*, ParseList* |
| CCorpsManageScreen | ParseList* |
| CDealMarketDetailScreen | ParseDetailTaobao* |
| CEventScreen | ParseEventList*, ParseFactionEvents*, ParseValentineEvents* |
| CFA_LookProScreen | ParseData* |
| CFA_MainScreen | ParseFAData*, ParseFightResult* |
| CFA_RankScreen | ParseList* |
| CFF_BossListScreen | ParseList* |
| CFF_BreakRecordScreen | ParseRecordDataList* |
| CFF_FightScreen | GetParseRewardList* |
| CFG_BossScreen | GetParseRewardList*, ParseConsistReward*, ParseCurrentBossDetail* |
| CFG_ManageInfo | ParseFGDataInfo* |
| CFactionBattleScreen | ParseBattles* |
| CFactionEnemyScreen | ParseCrossServerFight*, ParseFight*, ParseFightResult*, ParseMembers* |
| CFactionFactoryApproveScreen | ParseFactoryApproveData* |
| CFactionFactoryProcessScreen | ParseFactoryProcessData* |
| CFactionMemberScreen | ParseMembers* |
| CFactionMngMbrScreen | ParseMembers* |
| CFactionRequestScreen | ParseRequests* |
| CFactionScreen | ParseFactionBySearch*, ParseFactionBySearchID*, ParseFactions* |
| CFactionSkillScreen | ParseFactionSkill* |
| CFightingScreen | ParseFighters* |
| CFriendScreen | ParseFriends*, ParsePendings* |
| CGoodsScreen | ParseYBComsumble*, ParseAllGoodsForShowcaseUpload*, ParseBag, ParseRareTool, ParseSpecialPrice, ParseWarehouse |
| CGuardScreen | ParseList* |
| CHG_CaptureScreen | ParseAttackMessage*, ParseSearchInfo*, ParseSpoils*, __ParsePlayerStatus* |
| CHG_WarehouseScreen | ParseHuntToolList*, ParsePackBoxInfo*, ParseTransToolList* |
| CHospitalScreen | ParsePatient* |
| CKingAppellationScreen | ParseList*, ParseResult* |
| CKingBeatSeleTeamScreen | ParseCorp*, ParseSelf* |
| CKingRightInfoScreen | ParseKingRightInfo* |
| CKingWalletScreen | ParseInfo*, ParseItem* |
| CLadderEventScreen | ParseEventList*, ParseFight* |
| CLadderScreen | ParseFight*, ParseFighterInfo*, ParseMyInfo*, ParseReward* |
| CLookBattleScreen | ParseLookCorp* |
| CMainScreen | ParseSWGangsData*, ParseSWBuildData*, ParseSWEnterData*, etc. |
| CMarketCateScreen | ParseGoodsAmount* |
| CMarriageScreen | ParseMarrier* |
| CMasterRelationScreen | ParseList* |
| CMasterScreen | ParseList* |
| CMercenaryMnger | ParseAddMercenary*, ParseMercenaryAndConfigData*, ParseMercenaryChip*, etc. |
| CMilitiaScreen | ParseMilitiaStatus* |
| CMineBidScreen | Parse*, ParseList* |
| CNCW_ChallengeScreen | ParseCityWar* |
| CNewLoginRewardScreen | ParseListData*, ParseNewLoginData* |
| CPersActSubmit | GoParse*, ParseRewardData* |
| CPersonalExchangeListScreen | ParseList* |
| CPlayer | Parse* (extensive — 40+ sub-parsers) |
| CPrisonScreen | ParsePrisonerList* |
| CPropertyCateScreen | Parse* |
| CRG_CarWarehouseScreen | ParseCarList*, ParseShowcase* |
| CRG_ExchangeSkinScreen | ParseSkinData* |
| CRG_PersonalMapListScreen | ParsePlayerMatchData*, ParseSearchResultData* |
| CRG_StoreScreen | ParseStoreNum*, ParseStoreRandomList* |
| CRankCateScreen | ParseCarRaceServerData*, ParseFactionList*, ParsePlayer*, ParsePlayerList* |
| CReceiveRedPacketScreen | ParseGrabRedPacketInfo*, ParseGrabRedPacketRecord* |
| CRechargeScreen | ParseRewardInfo* |
| CRewardScreen | ParseWanted* |
| CSW_EnterBuildScreen | ParseBuildDataInfo*, ParseFightResult*, etc. |
| CSW_EntryScreen | ParseAirlines*, ParseCellListData*, ParseRoundData*, ParseStatusInfo* |
| CSW_JoinCorpListScreen | ParseJoinList* |
| CSW_MatchStatusScreen | ParseRoundData*, ParseStatusInfo* |
| CSW_ReviveScreen | ParsePersonalList*, ParseSingleMemberData*, etc. |
| CSearchResultScreen | ParseCiterResult* |
| CTopScreen | ParseMsg*, ParseSysMsg* |
| CTournamentScreen | ParseRank* |
| CValentineScreen | ParseList* |
| CVoteScreen | ParseVotes* |
| CVoteStatisticsScreen | ParseVotesStatistics* |
| CWeekAwardScreen | ParseAwardGoodsList*, ParseRankList* |

</details>

### 3d. LOW — Object accessor only, tolerates `data:{}` (57 classes)

### 3e. SAFE — No data access pattern detected (110 classes)

---

## 4. Endpoint → Parser → Screen Mapping

### 4a. Boot Sequence (steps 1–13)

```
/checkversion         → CLoadingScreen::ParseLastLoginPlayerInfo   → data:{} (obj)
/api/connect          → (auth handler)                             → data:{} (obj)
/city/connect/create  → CPlayer::Parse                             → data:{} (obj)
/city/connect/connect → CPlayer::Parse                             → data:{} (obj)
/city/impart          → CImpart::Parse                             → data:{} (obj)
```

### 4b. Post-Step-13 Automatic Requests

These fire immediately after city screen loads, in this order:

```
/city/chat/getsysmsgs        → CTopScreen::ParseSysMsg       → data:[] REQUIRED ✓
/city/monthCard/enterMatchCard → CEventBuyMonthCard::ParseEvent → data:{} safe
/race/match/matchconfig      → CRaceCoreMnger::ParseAthleticsData → data:{} safe
/race/car/getcars            → CRG_CarWarehouseScreen::ParseCarList → data:[] REQUIRED ✓
/race/car/getstoreitems      → CRG_StoreScreen::ParseStoreRandomList → data:[] REQUIRED ✓
/city/goods/playerbags       → CGoodsScreen                   → data:{} safe
/city/news/frontpage         → CNewspaperScreen::ParseNews     → data:{} safe
/city/chat/getmsg            → CChatScreen::ParseMsg           → data:[] REQUIRED ✓
/city/airline/airlines       → CAirportScreen::ParseAirlines   → data:[] REQUIRED ✓
```

### 4c. Navigation-Triggered Requests (observed in logs)

```
/city/gang/randomgangs    → data:[] REQUIRED ✓
/city/hospital/patients   → data:[] REQUIRED ✓
/city/jail/prisonerlist   → data:[] REQUIRED ✓
/city/gym/enter           → data:{} safe
/city/bank/checkbalance   → data:{} safe
/city/school/applyclass   → data:{} safe
/city/school/getmyclasses → data:{} safe
/city/event/list          → data:[] REQUIRED ✓
/city/player/logingifts   → data:[] REQUIRED ✓
/city/marital/candidates  → data:[] REQUIRED ✓
/city/heartbeat           → data:{} safe
/city/goods/getcitygoods  → data:{} safe
/city/estate/listestates  → data:{} safe
```

---

## 5. Related Models

| Model Class | Used By | Key Parser |
|-------------|---------|-----------|
| CPlayer | Connect/Auth, City HUD | 40+ sub-parsers, 168 fields |
| CImpart | Boot config | 199-key singleton |
| CMercenaryMnger | Mercenary system | ParseMercenaryAndConfigData |
| CKingFightMnger | King fight | ParseHeartBeatInfo, ParseDetailInfo |
| CFG_ManageInfo | Force arena | ParseFGDataInfo |
| CStorePackage | Store | Parse, ParseBucks, ParseRandomGiftByTypeAndId |
| CConfigureBase | Config | ParseData |
| CRaceCoreMnger | Racing | ParseAthleticsData |
| CCircleMnger | Mini-game | ParseCircle, ParseCircleNodes |
| CFunGame | Mini-game | ParseCircleData, ParseHeartBeat, ParseMaintenance |
| CGameMissionManager | Missions | (no parse methods) |
| CHouse | Estate | Parse |

---

## 6. Statistics

| Metric | Count |
|--------|-------|
| Total symbols in `.dynsym` | 36,881 |
| Total classes | 1,524 |
| Network-active classes (OnReceiveResponse) | 277 |
| Parse methods total | 309 with array-iterator pattern |
| Existing server routes (specific) | 43 |
| Total endpoints mapped | 161 |
| Missing routes | 142 |
| CRITICAL risk (crash guaranteed) | 15 |
| HIGH risk (crash likely) | 7 |
| MEDIUM risk (guarded, safe with `data:{}`) | 88 |
| LOW risk (object accessor) | 57 |
| SAFE (no data access pattern) | 110 |
