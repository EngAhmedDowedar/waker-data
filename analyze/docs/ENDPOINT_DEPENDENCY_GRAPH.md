# Endpoint Dependency Graph

Maps every known/predicted endpoint to its screen class, parser, expected data shape,
and crash behavior when served by the catch-all.

## Legend

- **Shape**: `[]` = array, `{}` = object, `{...}` = object with required fields
- **Catch-all safe**: YES = `data:{}` doesn't crash, NO = crashes with SIGSEGV
- **Route exists**: ✓ = has dedicated server.py route, ✗ = hits catch-all
- **Seen**: ✓ = observed in server logs, ✗ = predicted from binary only

---

## Boot & Auth

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/checkversion` | CLoadingScreen | ParseLastLoginPlayerInfo | `{...}` | YES | ✓ | ✓ |
| `/api/connect` | — | — | `{...}` | YES | ✓ | ✓ |
| `/api/authplayerkey` | — | — | `{...}` | YES | ✓ | ✓ |
| `/api/getallserver` | CServerChooseScreen | — | `{...}` | YES | ✓ | ✗ |
| `/city/connect/getplayerlist` | — | — | `[]` | NO | ✓ | ✓ |
| `/city/connect/create` | CPlayer | Parse | `{...}` | YES | ✓ | ✓ |
| `/city/connect/connect` | CPlayer | Parse | `{...}` | YES | ✓ | ✓ |
| `/city/impart` | CImpart | Parse | `{...}` | YES | ✓ | ✓ |
| `/city/heartbeat` | CHeartBeat | — | `{}` | YES | ✓ | ✓ |
| `/game/maintenance/check` | CFunGame | ParseMaintenance | `{}` | YES | ✓ | ✗ |

## Chat System

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/chat/getsysmsgs` | CTopScreen | ParseSysMsg | `[]` | **NO** | ✓ | ✓ |
| `/city/chat/gettopmsgs` | CTopScreen | ParseMsg | `[]` | **NO** | ✓ | ✗ |
| `/city/chat/getmsg` | CChatScreen | ParseMsg | `[]` | **NO** | ✓ | ✓ |
| `/city/chat/sendmsg` | CChatScreen | — | `{}` | YES | ✓* | ✗ |

## City Core — Property & Estate

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/estate/listestates` | CPropertyCateScreen | Parse | `{}` | YES† | ✓ | ✓ |
| `/city/estate/listbytype` | CPropertyListScreen | ParseNumberData | `{}` | YES | ✗ | ✗ |
| `/city/estate/listbycate` | CPropertyListCateScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/estate/buy` | — | — | `{}` | YES | ✓ | ✗ |
| `/city/estate/decorate` | CDecorateScreen | Parse | `{}` | YES | ✗ | ✗ |

†CPropertyCateScreen::Parse is array-iterator but OnReceiveResponse null-guards before calling it.

## City Core — Goods & Market

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/goods/getcitygoods` | CGoodsScreen | — | `{}` | YES† | ✓ | ✓ |
| `/city/goods/playerbags` | CGoodsScreen | ParseBag | `{...}` | YES | ✓ | ✓ |
| `/city/goods/playergoods` | CGoodsScreen | — | `{}` | YES | ✓ | ✗ |
| `/city/goods/equipment` | CEquipmentScreen | ParseBag, ParseWarehouse | `{}` | YES | ✗ | ✗ |
| `/city/goods/blackmarket` | CBlackMarketScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/goods/market` | CMarketCateScreen | ParseGoodsAmount | `{}` | YES† | ✗ | ✗ |
| `/city/goods/marketlist` | CMarketScreen | ParseGoodsAmount | `[]`? | **MAYBE** | ✗ | ✗ |
| `/city/deal/list` | CDealMarketScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/deal/detail` | CDealMarketDetailScreen | ParseDetailTaobao | `{}` | YES† | ✗ | ✗ |
| `/city/trade/list` | CPersonalExchangeListScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/trade/info` | CPersonalExchangeScreen | ParseExchangeInfo | `{}` | YES | ✗ | ✗ |
| `/city/trade/records` | CPersonalExchangeRecordScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/store/catelist` | CStoreCateScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/store/package` | CStorePackage | Parse | `{}` | YES | ✗ | ✗ |
| `/city/showwindow/list` | CUpdateWindowOrderScreen | — | `[]` | **NO** | ✗ | ✗ |

†OnReceiveResponse null-guards before array sub-parsers.

## City Core — Jobs & School

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/job/getjobs` | CHrMarketCateScreen | — | `[]` | **NO** | ✓ | ✗ |
| `/city/job/work` | CHrMarketCateScreen | ParseDoJobResponse | `{}` | YES | ✓ | ✗ |
| `/city/school/applyclass` | CSchoolScreen | — | `{}` | YES | ✗ | ✓ |
| `/city/school/getmyclasses` | CSchoolScreen | ParseSubject | `{}` | YES | ✗ | ✓ |
| `/city/school/subjects` | CSchoolCateScreen | — | `{}` | YES | ✗ | ✗ |

## City Core — Gym, Hospital, Crime, Prison, Bank

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/gym/enter` | CGymScreen | ParseEnterGymInfo | `{}` | YES | ✗ | ✓ |
| `/city/gym/getgym` | CGymScreen | ParseResponse | `{}` | YES | ✓ | ✗ |
| `/city/gym/train` | CGymScreen | — | `{}` | YES | ✓ | ✗ |
| `/city/hospital/patients` | CHospitalScreen | ParsePatient | `[]` | **NO** | ✓ | ✓ |
| `/city/crime/docrime` | CCrimeScreen | ParseDoCrimeResponse | `{}` | YES | ✓ | ✗ |
| `/city/jail/prisonerlist` | CPrisonScreen | ParsePrisonerList | `[]` | **NO** | ✓ | ✓ |
| `/city/bank/checkbalance` | CBankScreen | — | `{}` | YES | ✗ | ✓ |

## Airline

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/airline/airlines` | CAirportScreen | ParseAirlines | `[]` | **NO** | ✓ | ✓ |
| `/city/airline/arrived` | CAirLineScreen | ParseArrived | `{}` | YES | ✗ | ✗ |

## Gang & Gang Boss

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/gang/randomgangs` | — | — | `[]` | **NO** | ✓ | ✓ |
| `/city/gangboss/info` | CBossWarScreen | ParseCurrentBossDetail | `{}` | YES† | ✗ | ✗ |

## Social

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/friend/getfriends` | CFriendScreen | ParseFriends | `{}` | YES† | ✓ | ✗ |
| `/city/marital/candidates` | — | — | `[]` | **NO** | ✓ | ✓ |
| `/city/marital/status` | CMaritalStatusScreen | ParseSpouse | `{}` | YES | ✗ | ✗ |
| `/city/marital/register` | — | — | `{}` | YES | ✗ | ✓ |
| `/city/marital/marry` | CMarriageScreen | ParseMarrier | `{}` | YES† | ✗ | ✗ |
| `/city/mentoring/list` | CMasterScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/mentoring/relation` | CMasterRelationScreen | ParseList | `{}` | YES† | ✗ | ✗ |

## News

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/news/frontpage` | CNewspaperScreen | ParseNews→sub-parsers | `{}` | YES† | ✗ | ✓ |
| `/city/news/advertise` | CAdvertiseScreen | ParseList | `{}` | YES† | ✗ | ✗ |

## Faction System

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/faction/list` | CFactionScreen | ParseFactions | `{}` | YES† | ✗ | ✗ |
| `/city/faction/info` | CFactionInfoScreen | ParseFaction | `{}` | YES | ✗ | ✗ |
| `/city/faction/members` | CFactionMemberScreen | ParseMembers | `{}` | YES† | ✗ | ✗ |
| `/city/faction/create` | CFactionCreateScreen | ParseFaction | `{}` | YES | ✗ | ✗ |
| `/city/faction/requests` | CFactionRequestScreen | ParseRequests | `{}` | YES† | ✗ | ✗ |
| `/city/faction/battles` | CFactionBattleScreen | ParseBattles | `{}` | YES† | ✗ | ✗ |
| `/city/faction/manage` | CFactionManageScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/faction/skills` | CFactionSkillScreen | ParseFactionSkill | `{}` | YES† | ✗ | ✗ |
| `/city/faction/enemy` | CFactionEnemyScreen | ParseFight | `{}` | YES† | ✗ | ✗ |
| `/city/faction/contribute` | CFactionContributeScreen | ParseResponse | `{}` | YES | ✗ | ✗ |
| `/city/faction/managemember` | CFactionMngMbrScreen | ParseMembers | `{}` | YES† | ✗ | ✗ |
| `/city/faction/applications` | CApplicationListScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/faction/factoryapprove` | CFactionFactoryApproveScreen | ParseFactoryApproveData | `{}` | YES† | ✗ | ✗ |
| `/city/faction/factoryprocess` | CFactionFactoryProcessScreen | ParseFactoryProcessData | `{}` | YES† | ✗ | ✗ |

## Fight System

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/fight/randomfighters` | CFightingScreen | ParseFighters | `[]` | **NO** | ✓ | ✗ |
| `/city/fight/statistics` | CBattleStatisticsScreen | ParseBattleStatistics | `[]`? | **MAYBE** | ✗ | ✗ |
| `/city/fight/bosslist` | CFF_BossListScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/fight/bossfight` | CFF_FightScreen | GetParseRewardList | `{}` | YES† | ✗ | ✗ |
| `/city/fight/breakrecord` | CFF_BreakRecordScreen | ParseRecordDataList | `{}` | YES† | ✗ | ✗ |
| `/city/fight/lookbattle` | CLookBattleScreen | ParseLookCorp | `{}` | YES† | ✗ | ✗ |

## Events & Rewards

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/event/list` | CEventScreen | ParseEventList | `[]` | **NO** | ✓ | ✗ |
| `/city/event/weekaward` | CWeekAwardScreen | ParseAwardGoodsList | `{}` | YES† | ✗ | ✗ |
| `/city/event/valentine` | CValentineScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/event/thanksgiving` | CThanksgivingV | — | `{}` | YES | ✗ | ✗ |
| `/city/activities/list` | CActiveScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/activities/detail` | CActiveDetailScreen | ParseKillData | `{}` | YES† | ✗ | ✗ |
| `/city/activities/result` | CActiveResultScreen | ParseActiveRank | `{}` | YES† | ✗ | ✗ |
| `/city/activities/challenge` | CActiveChallengeMainScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/activities/challengerank` | CActiveChallengeRankScreen | ParsePersonRankUpData | `{}` | YES† | ✗ | ✗ |
| `/city/player/logingifts` | CLoginGiftScreen | — | `[]` | **NO** | ✓ | ✗ |
| `/city/wanted/list` | CRewardScreen | ParseWanted | `{}` | YES† | ✗ | ✗ |
| `/city/redpacket/grab` | CReceiveRedPacketScreen | ParseGrabRedPacketInfo | `{}` | YES† | ✗ | ✗ |
| `/city/monthCard/enterMatchCard` | — | ParseEvent | `{}` | YES | ✗ | ✓ |

## Achievement & Rank

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/achievement/list` | CAchievementScreen | ParseAchievements | `{}` | YES† | ✗ | ✗ |
| `/city/achievement/citier` | CCitierScreen | ParseAchievements | `{}` | YES† | ✗ | ✗ |
| `/city/rank/list` | CRankCateScreen | ParsePlayerList | `{}` | YES† | ✗ | ✗ |
| `/city/rank/tournament` | CTournamentScreen | ParseRank | `{}` | YES† | ✗ | ✗ |
| `/city/rank/nationalbid` | CNationalBidScreen | Parse | `[]`? | **MAYBE** | ✗ | ✗ |
| `/city/player/getranking` | — | — | `{}` | YES | ✓ | ✗ |

## Vote

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/vote/list` | CVoteScreen | ParseVotes | `{}` | YES† | ✗ | ✗ |

## Guard & Helper

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/guard/list` | CGuardScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/helper/list` | CHelperScreen | ParseList | `[]`? | **MAYBE** | ✗ | ✗ |

## Skyscraper

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/skyscraper/list` | CSkyscraperScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/skyscraper/info` | CSkyscraperEntryScreen | — | `{}` | YES | ✗ | ✗ |

## Lottery

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/lottery/info` | CLotteryScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/lottery/prizes` | CLT_CollectPrizeScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/lottery/records` | CLT_CollectRecordScreen | — | `[]` | **NO** | ✗ | ✗ |

## Auction

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/auction/list` | CAuctionHouseScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/auction/events` | CAuctionEventScreen | ParseEventList | `{}` | YES† | ✗ | ✗ |

## Ladder Fight

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/ladderfight/info` | CLadderScreen | ParseFight | `{}` | YES† | ✗ | ✗ |
| `/city/ladderfight/events` | CLadderEventScreen | ParseEventList | `{}` | YES† | ✗ | ✗ |

## Mercenary System

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/mercenary/list` | CMercenaryMainScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mercenary/info` | CMercenaryMnger | ParseMercenaryAndConfigData | `{}` | YES† | ✗ | ✗ |
| `/city/mercenary/helpandbattle` | CMS_HelpAndBattleScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/mercenary/rank` | CMS_RankScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/mercenary/ybclass` | CMS_YbClassSummeScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/mercenary/class` | CMS_ClassMainScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mercenary/store` | CMS_StoreScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mercenary/fight` | CMS_FightScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mercenary/lineup` | CMS_LineupScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mercenary/loyalty` | CMS_LoyaltyScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mercenary/jinwei` | CMS_JinWeiScreen | — | `{}` | YES | ✗ | ✗ |

## Mine System

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/mine/main` | CMS_MineMainScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mine/all` | CMS_MineAllScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/mine/mymine` | CMS_MyMineScreen | ParseOccupyMerceanry | `{}` | YES | ✗ | ✗ |
| `/city/mine/bid` | CMineBidScreen | Parse, ParseList | `{}` | YES† | ✗ | ✗ |

## Hunt System

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/hunt/main` | CHG_MainScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/hunt/store/list` | CHG_StoreScreen | ParseHGStoreData | `[]` | **NO** | ✗ | ✗ |
| `/city/hunt/capture` | CHG_CaptureScreen | ParseSearchInfo | `{}` | YES† | ✗ | ✗ |
| `/city/hunt/warehouse` | CHG_WarehouseScreen | ParseHuntToolList | `{}` | YES† | ✗ | ✗ |
| `/city/hunt/samples` | CHG_SampleShowScreen | ParseSampleData | `{}` | YES | ✗ | ✗ |

## King Fight

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/kingfight/info` | CKingMainScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/kingfight/appellations` | CKingAppellationScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/kingfight/selectteam` | CKingBeatSeleTeamScreen | ParseCorp | `{}` | YES† | ✗ | ✗ |
| `/city/kingfight/rightinfo` | CKingRightInfoScreen | ParseKingRightInfo | `{}` | YES† | ✗ | ✗ |
| `/city/kingfight/wallet` | CKingWalletScreen | ParseInfo | `{}` | YES† | ✗ | ✗ |

## Force Arena

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/forcearena/main` | CFG_MainScreen, CFA_MainScreen | ParseFAData | `{}` | YES† | ✗ | ✗ |
| `/city/forcearena/boss` | CFG_BossScreen | ParseCurrentBossDetail | `{}` | YES† | ✗ | ✗ |
| `/city/forcearena/lookpro` | CFA_LookProScreen | ParseData | `{}` | YES† | ✗ | ✗ |
| `/city/forcearena/rank` | CFA_RankScreen | ParseList | `{}` | YES† | ✗ | ✗ |

## Cooperate Boss

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/cooperateboss/list` | CCooperateListScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/cooperateboss/fight` | CCooperateFightScreen | ParseHarmRank | `{}` | YES† | ✗ | ✗ |

## Corp/War Systems

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/corp/fight` | CCorpsFightScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/corp/manage` | CCorpsManageScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/citywar/info` | CCityWarScreen | ParseCityWar | `{}` | YES† | ✗ | ✗ |
| `/city/citywar/result` | CCityWarResultScreen | ParseFactionList | `{}` | YES† | ✗ | ✗ |
| `/city/streetwar/entry` | CSW_EntryScreen | ParseStatusInfo | `{}` | YES† | ✗ | ✗ |
| `/city/streetwar/joinlist` | CSW_JoinCorpListScreen | ParseJoinList | `{}` | YES† | ✗ | ✗ |
| `/city/streetwar/enterbuild` | CSW_EnterBuildScreen | ParseBuildDataInfo | `{}` | YES† | ✗ | ✗ |
| `/city/streetwar/matchstatus` | CSW_MatchStatusScreen | ParseRoundData | `{}` | YES† | ✗ | ✗ |
| `/city/streetwar/matchresult` | CSW_MatchResultScreen | ParseWinFactionData | `{}` | YES | ✗ | ✗ |
| `/city/streetwar/revive` | CSW_ReviveScreen | ParsePersonalList | `{}` | YES† | ✗ | ✗ |
| `/city/crossserverwar/main` | CNCW_MainScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/crossserverwar/joinlist` | CNCW_JoinCorpListScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/city/crossserverwar/challenge` | CNCW_ChallengeScreen | ParseCityWar | `{}` | YES† | ✗ | ✗ |
| `/city/crossserverwar/enroll` | CNCW_EnrollHallScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/crossserverwar/mall` | CNCW_SpecialMallScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/crossserverladderfight/main` | CCBMainScreen | ParseCBRewardsStatus | `{}` | YES† | ✗ | ✗ |
| `/city/crossserverladderfight/list` | CCBListScreen | ParseList | `{}` | YES† | ✗ | ✗ |
| `/city/crossserverladderfight/fight` | CCLMainScreen | ParseFight | `{}` | YES† | ✗ | ✗ |

## Racing System (port 9090)

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/race/car/getcars` | CRG_CarWarehouseScreen | ParseCarList | `[]` | **NO** | ✓ | ✓ |
| `/race/car/getstoreitems` | CRG_StoreScreen | ParseStoreRandomList | `[]` | **NO** | ✓ | ✓ |
| `/race/car/info` | CRG_CarInfoScreen | — | `{}` | YES | ✗ | ✗ |
| `/race/car/refit` | CRG_CarRefitScreen | — | `{}` | YES | ✗ | ✗ |
| `/race/match/matchconfig` | CRG_MatchAthleticsScreen | ParseAthleticsData | `{}` | YES | ✗ | ✓ |
| `/race/match/maplist` | CRG_MapListScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/race/match/dungeon/info` | CRG_RaceDungeonListScreen | — | `[]` | **NO** | ✗ | ✓ |
| `/race/match/record` | CRG_RecordScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/race/match/recorddesc` | CRG_RecordDescScreen | — | `[]` | **NO** | ✗ | ✗ |
| `/race/match/personalmaps` | CRG_PersonalMapListScreen | ParsePlayerMatchData | `{}` | YES† | ✗ | ✗ |
| `/race/match/start` | CRG_RaceScreen | — | `{}` | YES | ✗ | ✗ |
| `/race/skin/listcar` | CRG_ExchangeSkinScreen | ParseSkinData | `{}` | YES† | ✗ | ✗ |

## Misc

| Endpoint | Screen | Parser | Shape | Safe | Route | Seen |
|----------|--------|--------|-------|------|-------|------|
| `/city/feedback/list` | CFeedbackScreen | ParseChilds | `[]`? | **MAYBE** | ✗ | ✗ |
| `/city/game/circle` | CCircleMnger | ParseCircle | `[]`? | **MAYBE** | ✗ | ✗ |
| `/city/game/blackjack` | CBlackJackScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/game/slotmachine` | SlotMachineScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/purchase/info` | CRechargeScreen | ParseRewardInfo | `{}` | YES† | ✗ | ✗ |
| `/city/militia/status` | CMilitiaScreen | ParseMilitiaStatus | `{}` | YES† | ✗ | ✗ |
| `/city/player/search` | CSearchResultScreen | ParseCiterResult | `{}` | YES† | ✗ | ✗ |
| `/city/player/getplayerinfo` | CPersonalScreen | — | `{}` | YES | ✓ | ✗ |
| `/city/message/inbox` | CMailScreen | — | `{}` | YES | ✗ | ✗ |
| `/city/config` | CConfigureBase | ParseData | `{}` | YES | ✗ | ✗ |

---

## Summary of Crash-Risk Endpoints

**Will crash with `data:{}`** (need dedicated `data:[]` route):

| # | Endpoint | Status |
|---|----------|--------|
| 1 | `/city/airline/airlines` | ✓ FIXED |
| 2 | `/city/chat/getsysmsgs` | ✓ FIXED |
| 3 | `/city/chat/gettopmsgs` | ✓ FIXED |
| 4 | `/city/chat/getmsg` | ✓ FIXED |
| 5 | `/city/connect/getplayerlist` | ✓ FIXED |
| 6 | `/city/event/list` | ✓ FIXED |
| 7 | `/city/fight/randomfighters` | ✓ FIXED |
| 8 | `/city/gang/randomgangs` | ✓ FIXED |
| 9 | `/city/hospital/patients` | ✓ FIXED |
| 10 | `/city/jail/prisonerlist` | ✓ FIXED |
| 11 | `/city/job/getjobs` | ✓ FIXED |
| 12 | `/city/marital/candidates` | ✓ FIXED |
| 13 | `/city/player/introplayers` | ✓ FIXED |
| 14 | `/city/player/logingifts` | ✓ FIXED |
| 15 | `/race/car/getcars` | ✓ FIXED |
| 16 | `/race/car/getstoreitems` | ✓ FIXED |
| 17 | `/city/crossserverwar/joinlist` | ✗ NEEDED |
| 18 | `/city/hunt/store/list` | ✗ NEEDED |
| 19 | `/city/lottery/info` | ✗ NEEDED |
| 20 | `/city/lottery/prizes` | ✗ NEEDED |
| 21 | `/city/lottery/records` | ✗ NEEDED |
| 22 | `/city/mercenary/helpandbattle` | ✗ NEEDED |
| 23 | `/city/mercenary/rank` | ✗ NEEDED |
| 24 | `/city/mercenary/ybclass` | ✗ NEEDED |
| 25 | `/city/showwindow/list` | ✗ NEEDED |
| 26 | `/city/skyscraper/list` | ✗ NEEDED |
| 27 | `/city/store/catelist` | ✗ NEEDED |
| 28 | `/race/match/dungeon/info` | ✗ NEEDED |
| 29 | `/race/match/maplist` | ✗ NEEDED |
| 30 | `/race/match/record` | ✗ NEEDED |
| 31 | `/race/match/recorddesc` | ✗ NEEDED |

**Might crash** (HIGH risk, needs binary verification):

| # | Endpoint | Class |
|---|----------|-------|
| 32 | `/city/fight/statistics` | CBattleStatisticsScreen |
| 33 | `/city/feedback/list` | CFeedbackScreen |
| 34 | `/city/game/circle` | CCircleMnger |
| 35 | `/city/goods/marketlist` | CMarketScreen |
| 36 | `/city/helper/list` | CHelperScreen |
| 37 | `/city/news/frontpage` | CNewspaperScreen (verified safe†) |
| 38 | `/city/rank/nationalbid` | CNationalBidScreen |
