# BACKEND SPEC — machine-extracted index

_Auto-generated from libcity_ar.so .rodata + .dynsym + assets/ + server.py. Re-run `python analyze/tools/build_backend_spec.py` to refresh._

- Commands found in .rodata cluster 0x6fd000..0x6ff400: **789** strings, **774 unique**
- mission.city entries: **29** (ids [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 26, 27, 28, 30, 31, 35])
- assets/ar strings: **10347**
- server.py explicit routes: **19**

## Index by category

Each entry is a command-name string from .rodata. `[OK]` = explicitly handled by server.py; `[CA]` = falls through to a catch-all (/city/<cmd> or /<path>) that returns `data:{}` or `data:[]`; `[?]` = unknown (no static signal it's been observed in flight).

### auth/session

- [OK] `authplayerkey`   .rodata@0x6fd24c
- [CA] `completeinfo`   .rodata@0x6fd20e
- [OK] `connect`   .rodata@0x6fd1af
- [CA] `connectFacebook`   .rodata@0x6fd284
- [OK] `create`   .rodata@0x6fd1a8
- [CA] `modifyemail`   .rodata@0x6fd236
- [CA] `modifyname`   .rodata@0x6fd1c1
- [CA] `modifypassword`   .rodata@0x6fd227
- [CA] `register`   .rodata@0x6fd1fc

### server-list

- [OK] `checkversion`   .rodata@0x6fd348
- [OK] `getallserver`   .rodata@0x6fd88a

### session-tick

- [CA] `atHome`   .rodata@0x6fd2dc
- [CA] `heartbeat`   .rodata@0x6fd355
- [CA] `open`   .rodata@0x6fd3aa
- [CA] `pause`   .rodata@0x6fd2d6
- [CA] `self`   .rodata@0x6fd300

### config

- [OK] `impart`   .rodata@0x6fd384
- [CA] `matchconfig`   .rodata@0x6fef6e

### player

- [CA] `avatarinfo`   .rodata@0x6fd843
- [CA] `completedailytask`   .rodata@0x6fe16f
- [OK] `introplayers`   .rodata@0x6fd836
- [CA] `playerbags`   .rodata@0x6fdc45
- [CA] `playerequip`   .rodata@0x6fea51
- [CA] `playergoods`   .rodata@0x6fdc39
- [CA] `updateProjectFinish`   .rodata@0x6ff220
- [CA] `updateavatar`   .rodata@0x6fd4de
- [CA] `updatecamps`   .rodata@0x6feb19
- [CA] `updatedailytask`   .rodata@0x6fe15f
- [CA] `updatelevel`   .rodata@0x6fd797
- [CA] `updatelevelexp`   .rodata@0x6feaa3
- [CA] `updateplayerinfo`   .rodata@0x6fe919
- [CA] `updatesignature`   .rodata@0x6fd305
- [CA] `updateskill`   .rodata@0x6fe142
- [CA] `updateskillexp`   .rodata@0x6fea94
- [CA] `updatewindowstatus`   .rodata@0x6ff0e7

### chat/message

- [CA] `delete`   .rodata@0x6fd3f5
- [CA] `deletechatmsgs`   .rodata@0x6fd42c
- [CA] `getmsg`   .rodata@0x6fd4ac
- [CA] `getoldmsg`   .rodata@0x6fd4b3
- [CA] `getsysmsgs`   .rodata@0x6fd4d3
- [OK] `gettopmsgs`   .rodata@0x6fd4c8
- [CA] `getvalentinemsg`   .rodata@0x6fe0f2
- [CA] `read`   .rodata@0x6fd3f0
- [CA] `readchat`   .rodata@0x6fd423
- [CA] `reply`   .rodata@0x6fd3b8
- [CA] `send`   .rodata@0x6fd3ca
- [CA] `sendSysMsg`   .rodata@0x6fd4bd
- [CA] `sendbyuid`   .rodata@0x6fd3db
- [CA] `write`   .rodata@0x6fe35e

### mission

- [CA] `finishtask`   .rodata@0x6fec0c
- [CA] `inMission`   .rodata@0x6fd9f3
- [CA] `missionRefill`   .rodata@0x6fdfbc

### economy:goods

- [OK] `buy`   .rodata@0x6fd721
- [CA] `buygoldtool`   .rodata@0x6fe0e6
- [CA] `buygoods`   .rodata@0x6feb71
- [OK] `getcitygoods`   .rodata@0x6fdc15
- [CA] `getgoods`   .rodata@0x6feb25
- [CA] `goodspackage`   .rodata@0x6fe0aa
- [CA] `importgoods`   .rodata@0x6feb40
- [CA] `lockgoods`   .rodata@0x6ff3b5
- [CA] `mergefood`   .rodata@0x6fdbdd
- [CA] `mergegold`   .rodata@0x6fdbca
- [CA] `mergegoods`   .rodata@0x6fdbfe
- [CA] `movegoods`   .rodata@0x6fdbb2
- [CA] `multigoodspackage`   .rodata@0x6fdc8f
- [CA] `randomgoods`   .rodata@0x6fdc2d
- [CA] `removegoods`   .rodata@0x6feb65
- [CA] `sell`   .rodata@0x6fdea5
- [CA] `selltonpc`   .rodata@0x6fd9fd
- [CA] `splitsgoldgoods`   .rodata@0x6fe45c
- [CA] `strengthen`   .rodata@0x6fdccf
- [CA] `transgoods`   .rodata@0x6fdd03
- [CA] `upgrade`   .rodata@0x6fdce3
- [CA] `usegoldtool`   .rodata@0x6fe0d1
- [CA] `usegoods`   .rodata@0x6fdc50

### economy:estate

- [CA] `buycancel`   .rodata@0x6fdf9e
- [CA] `buydecoration`   .rodata@0x6fdeb2
- [CA] `buymaid`   .rodata@0x6fdec9
- [CA] `buyplayerestate`   .rodata@0x6fdf8e
- [CA] `cancelsell`   .rodata@0x6fdf83
- [CA] `changerentinfo`   .rodata@0x6fdf69
- [CA] `changesellinfo`   .rodata@0x6fdf47
- [CA] `checkin`   .rodata@0x6fdeaa
- [CA] `driveout`   .rodata@0x6fdede
- [CA] `getdecorators`   .rodata@0x6fe816
- [CA] `getonrentamount`   .rodata@0x6fdf37
- [OK] `listestates`   .rodata@0x6fdf2b
- [CA] `listonrent`   .rodata@0x6fdf15
- [CA] `listonsell`   .rodata@0x6fdf20
- [CA] `maintaincost`   .rodata@0x6fded1
- [CA] `modifydecorator`   .rodata@0x6fe824
- [CA] `onrent`   .rodata@0x6fdf5d
- [CA] `onsell`   .rodata@0x6fdf56
- [CA] `rent`   .rodata@0x6fdf64
- [CA] `rentcancel`   .rodata@0x6fdf78
- [CA] `spouseestates`   .rodata@0x6fde81

### economy:bank

- [CA] `checkbalance`   .rodata@0x6fdba5
- [CA] `drawmoney`   .rodata@0x6fd5f6
- [CA] `savemoney`   .rodata@0x6fdb9b

### economy:job

- [CA] `applyjob`   .rodata@0x6fd8e9
- [CA] `collectsalary`   .rodata@0x6fd8cf
- [CA] `salary`   .rodata@0x6fd8c8

### economy:gym

- [CA] `agileEnergy`   .rodata@0x6fda1d
- [CA] `buyservice`   .rodata@0x6fda5d
- [CA] `enduranceEnergy`   .rodata@0x6fda35
- [CA] `frontpage`   .rodata@0x6fda6e
- [CA] `join`   .rodata@0x6fda54
- [CA] `speedEnergy`   .rodata@0x6fda29
- [CA] `strengthEnergy`   .rodata@0x6fda0e
- [CA] `use`   .rodata@0x6fda59

### economy:gamble

- [CA] `gambling`   .rodata@0x6fd7ea
- [CA] `getfreeturntable`   .rodata@0x6fe41b
- [CA] `getturntablemsgs`   .rodata@0x6fe40a
- [CA] `multiturntable`   .rodata@0x6fe3fb
- [CA] `point21bust`   .rodata@0x6fd7f3
- [CA] `redblackbet`   .rodata@0x6fd7c4
- [CA] `redblackshow`   .rodata@0x6fd7a3
- [CA] `turntable`   .rodata@0x6fe3ea

### crime

- [CA] `crime`   .rodata@0x6fd8c2
- [CA] `crimeSkilled`   .rodata@0x6fd8a1
- [CA] `crimeType`   .rodata@0x6fd897
- [CA] `rewardCrimeCategory`   .rodata@0x6fd8ae

### medical

- [CA] `cure`   .rodata@0x6fd99b
- [CA] `drugaddictiontreat`   .rodata@0x6fd863
- [CA] `eatcuisines`   .rodata@0x6ff106
- [CA] `eatdrug`   .rodata@0x6fd807
- [CA] `eatfood`   .rodata@0x6fd7ff
- [CA] `eatredbull`   .rodata@0x6fe202
- [CA] `getdrugaddictioninfo`   .rodata@0x6fd84e
- [CA] `goldcure`   .rodata@0x6fd9a0
- [CA] `medicine`   .rodata@0x6fd987
- [CA] `outhospital`   .rodata@0x6fd96e
- [CA] `patients`   .rodata@0x6fd965
- [CA] `recover`   .rodata@0x6fd78f
- [CA] `recoverblood`   .rodata@0x6feaeb
- [CA] `recoverbrave`   .rodata@0x6fdfd8
- [CA] `recoverenergy`   .rodata@0x6fdfca
- [CA] `recoverloyalty`   .rodata@0x6feaf8
- [CA] `recovermoral`   .rodata@0x6fd782

### jail

- [CA] `bail`   .rodata@0x6fd9b4
- [CA] `bust`   .rodata@0x6fd9b9
- [CA] `outjail`   .rodata@0x6fd9e6
- [CA] `prisonbreak`   .rodata@0x6fd9be
- [CA] `prisonerlist`   .rodata@0x6fd9d9
- [CA] `searchprisoner`   .rodata@0x6fd9ca

### combat:player

- [CA] `battlefightresult`   .rodata@0x6fdda3
- [CA] `buyFightTime`   .rodata@0x6fe4fc
- [CA] `buyfighttimes`   .rodata@0x6fe522
- [CA] `fightcompetition`   .rodata@0x6fe23b
- [CA] `fightcompetitionnew`   .rodata@0x6fde0d
- [CA] `fightgangboss`   .rodata@0x6fec2f
- [CA] `fightjudge`   .rodata@0x6fdd1d
- [CA] `fightnew`   .rodata@0x6fde21
- [CA] `fightresult`   .rodata@0x6fdd7c
- [CA] `fightrobot`   .rodata@0x6fdd3c
- [CA] `fightrobotnew`   .rodata@0x6fddc3
- [CA] `fightskyscraper`   .rodata@0x6fe9f2
- [CA] `fightskyscrapernew`   .rodata@0x6fdde6
- [CA] `fightteamworkboss`   .rodata@0x6fe9b9
- [CA] `fightteamworkbossnew`   .rodata@0x6fddd1
- [CA] `kingfight`   .rodata@0x6fe2de
- [CA] `ladderfightjudge`   .rodata@0x6fe6bf
- [CA] `ladderfightjudgenew`   .rodata@0x6fddf9
- [CA] `ladderrandomfighters`   .rodata@0x6fe6aa
- [CA] `pvefightresult`   .rodata@0x6fdd4c
- [CA] `pvpfightresult`   .rodata@0x6fdd6d
- [OK] `randomfighters`   .rodata@0x6fdd0e
- [CA] `thoughtrap`   .rodata@0x6fe736
- [CA] `thoughtrapnpc`   .rodata@0x6fe741
- [CA] `unionkingfight`   .rodata@0x6fe2e8
- [CA] `wantedfightresult`   .rodata@0x6fdd88

### combat:gang

- [CA] `applyclass`   .rodata@0x6fe3c6
- [CA] `applylist`   .rodata@0x6fe28c
- [CA] `approveinvite`   .rodata@0x6fd506
- [CA] `battle`   .rodata@0x6fd5d5
- [CA] `buybasicskill`   .rodata@0x6fd581
- [CA] `buyspecialskill`   .rodata@0x6fd58f
- [CA] `changeowner`   .rodata@0x6fd62e
- [CA] `donate`   .rodata@0x6fec46
- [CA] `fight`   .rodata@0x6fd5e5
- [CA] `ganginvite`   .rodata@0x6fd4fb
- [CA] `gangs`   .rodata@0x6fdaeb
- [CA] `getgangskill`   .rodata@0x6fd59f
- [CA] `joinlocaltroops`   .rodata@0x6fd6ea
- [CA] `joinwar`   .rodata@0x6fe22c
- [CA] `judgebattle`   .rodata@0x6fd67c
- [CA] `listapplygangs`   .rodata@0x6feced
- [CA] `listapplymembers`   .rodata@0x6fd55e
- [CA] `listbattles`   .rodata@0x6fd5ac
- [CA] `listjoinedmembers`   .rodata@0x6fd56f
- [CA] `listrankgangs`   .rodata@0x6fecfc
- [CA] `manageapply`   .rodata@0x6fe29d
- [CA] `modifygangname`   .rodata@0x6fe066
- [CA] `modifyguardinfo`   .rodata@0x6fdabb
- [CA] `openlocaltroop`   .rodata@0x6fd6db
- [CA] `randomfightgangs`   .rodata@0x6fd54d
- [CA] `randomgangs`   .rodata@0x6fd537
- [CA] `rejectinvite`   .rodata@0x6fd514
- [CA] `removemember`   .rodata@0x6fd609
- [CA] `resetskill`   .rodata@0x6fe075
- [CA] `switchdonate`   .rodata@0x6fec4d
- [CA] `troopsituation`   .rodata@0x6fd6fa
- [CA] `updatemembertitle`   .rodata@0x6fd651
- [CA] `wargangs`   .rodata@0x6fe223

### relation

- [CA] `candidates`   .rodata@0x6fdb25
- [CA] `divorcecancel`   .rodata@0x6fdb73
- [CA] `divorcereject`   .rodata@0x6fdb8d
- [CA] `divorcerequest`   .rodata@0x6fdb64
- [CA] `friendnum`   .rodata@0x6fde6e
- [CA] `friends`   .rodata@0x6fde3c
- [CA] `friendsharelist`   .rodata@0x6fe97c
- [CA] `maritalstatus`   .rodata@0x6fdb4a
- [CA] `marryapprove`   .rodata@0x6fdb3d
- [CA] `marrycancel`   .rodata@0x6fdb58
- [CA] `marryreject`   .rodata@0x6fdb81
- [CA] `marryrequest`   .rodata@0x6fdb30
- [CA] `pendingrequests`   .rodata@0x6fde44
- [CA] `request`   .rodata@0x6fde54
- [CA] `updateremark`   .rodata@0x6fde2f

### guard

- [CA] `cancelguardinfo`   .rodata@0x6fdaa3
- [CA] `fireout`   .rodata@0x6fdab3
- [CA] `hireguard`   .rodata@0x6fda99
- [CA] `listguards`   .rodata@0x6fda7c
- [CA] `searchguardbyname`   .rodata@0x6fda87

### airline/travel

- [CA] `airlines`   .rodata@0x6fd91d
- [CA] `arrive`   .rodata@0x6fd947
- [CA] `fastarrive`   .rodata@0x6fd95a
- [CA] `flightAward`   .rodata@0x6fd94e
- [CA] `travel`   .rodata@0x6fd940

### activity

- [CA] `clockin`   .rodata@0x6fe20d
- [CA] `code`   .rodata@0x6fe1d2
- [CA] `facebooksharereward`   .rodata@0x6fd876
- [CA] `getachievements`   .rodata@0x6fe132
- [CA] `getactivities`   .rodata@0x6fe194
- [CA] `getactivitydetail`   .rodata@0x6fe1a2
- [CA] `getactivityrank`   .rodata@0x6fe1b4
- [CA] `getoccupyinfo`   .rodata@0x6fe215
- [CA] `getplayergrowth`   .rodata@0x6fe1e4
- [CA] `logingift`   .rodata@0x6fd80f
- [CA] `logingifts`   .rodata@0x6fec71
- [CA] `newlogingift`   .rodata@0x6fd81f
- [CA] `receivinggift`   .rodata@0x6fe1f4
- [CA] `validatecode`   .rodata@0x6fe1d7

### auction

- [CA] `bid`   .rodata@0x6fe893
- [CA] `cancelauction`   .rodata@0x6fe85a
- [CA] `listallgoods`   .rodata@0x6fe834
- [CA] `listauctions`   .rodata@0x6fe886
- [CA] `listinvolvedauctions`   .rodata@0x6fe868
- [CA] `listmyauctions`   .rodata@0x6fe841
- [CA] `showsystemauction`   .rodata@0x6fe897

### dungeon

- [CA] `bugdungeontimes`   .rodata@0x6fe775
- [CA] `dungeonplayers`   .rodata@0x6fdaf1
- [CA] `enterdungeon`   .rodata@0x6fe6d9
- [CA] `exitdungeon`   .rodata@0x6fe6e6
- [CA] `fallback`   .rodata@0x6fe74f
- [CA] `obtainremainingtimes`   .rodata@0x6fe758
- [CA] `passlevel`   .rodata@0x6fe72c
- [CA] `recordaction`   .rodata@0x6fe71f
- [CA] `unfoldallcells`   .rodata@0x6fe785

### hunting

- [CA] `escape`   .rodata@0x6ff0b6
- [CA] `exit`   .rodata@0x6ff057
- [CA] `giveup`   .rodata@0x6ff094
- [CA] `hitback`   .rodata@0x6ff0bd
- [CA] `huntTools`   .rodata@0x6fd00c
- [CA] `hunttool`   .rodata@0x6ff079
- [CA] `hunttools`   .rodata@0x6ff02a
- [CA] `pursue`   .rodata@0x6ff09b
- [CA] `rentbox`   .rodata@0x6ff0a2
- [CA] `repair`   .rodata@0x6ff072
- [CA] `supplyfuel`   .rodata@0x6ff05c
- [CA] `transtools`   .rodata@0x6fd001

### mercenary

- [CA] `addAttack`   .rodata@0x6fe55c
- [CA] `addCrit`   .rodata@0x6fe581
- [CA] `addDefense`   .rodata@0x6fe576
- [CA] `addDodge`   .rodata@0x6fe56d
- [CA] `addHit`   .rodata@0x6fe566
- [CA] `addLoyalty`   .rodata@0x6ff26b
- [CA] `addShield`   .rodata@0x6fe552
- [CA] `addTenacity`   .rodata@0x6fe589
- [CA] `addexp`   .rodata@0x6fe5b8
- [CA] `chooseMercenary`   .rodata@0x6ff29b
- [CA] `costMercenaryIds`   .rodata@0x6fea83
- [CA] `costMercenarys`   .rodata@0x6fea5d
- [CA] `distribute`   .rodata@0x6fe595
- [CA] `equip`   .rodata@0x6fea7d
- [CA] `fire`   .rodata@0x6feb14
- [CA] `getMercenary`   .rodata@0x6ff351
- [CA] `getMercenaryRank`   .rodata@0x6ff28a
- [CA] `getmercenarys`   .rodata@0x6fea43
- [CA] `mercenaryIds`   .rodata@0x6feb07
- [CA] `mercenaryLearnProject`   .rodata@0x6ff234
- [CA] `mercenaryLoyal`   .rodata@0x6ff24a
- [CA] `replenish`   .rodata@0x6fe5bf
- [CA] `resetattributes`   .rodata@0x6fe5a8
- [CA] `starup`   .rodata@0x6fea76
- [CA] `train`   .rodata@0x6feae5

### race

- [CA] `getmatchingprize`   .rodata@0x6fee5b
- [OK] `history`   .rodata@0x6fef54
- [CA] `joinCostMoney`   .rodata@0x6feeff
- [CA] `listroom`   .rodata@0x6feeb0
- [CA] `match`   .rodata@0x6fee75
- [CA] `matching`   .rodata@0x6fee52
- [CA] `matchinginfo`   .rodata@0x6fee33
- [CA] `matchingprizelist`   .rodata@0x6fee40
- [CA] `raceStartCountDown`   .rodata@0x6feeec
- [CA] `roomcreate`   .rodata@0x6feed8
- [CA] `start`   .rodata@0x6fef33
- [CA] `trackId`   .rodata@0x6fee01
- [CA] `tracks`   .rodata@0x6fedec

### city-war

- [CA] `buyTimes`   .rodata@0x6fef95
- [CA] `buycooling`   .rodata@0x6fe517
- [CA] `buyseat`   .rodata@0x6fe2ce
- [CA] `enterMatchCard`   .rodata@0x6ff1da
- [CA] `enterbuilding`   .rodata@0x6fea2b
- [CA] `enterwar`   .rodata@0x6ff175
- [CA] `gangresult`   .rodata@0x6ff1c6
- [CA] `getscore`   .rodata@0x6ff1d1
- [CA] `rewardReceive`   .rodata@0x6ff1e9
- [CA] `streetwarfight`   .rodata@0x6ff17e
- [CA] `streetwarfightresult`   .rodata@0x6ff18d
- [CA] `switchmatch`   .rodata@0x6ff1ba
- [CA] `useAircraft`   .rodata@0x6ff1a2
- [CA] `useaircraft`   .rodata@0x6ff1ae

### debug/misc

- [CA] `check`   .rodata@0x6fd334
- [CA] `no_heartbeat`   .rodata@0x6fd051
- [CA] `sysTime`   .rodata@0x6fd294
- [CA] `verifySI`   .rodata@0x6ff3d6
- [CA] `verifyhuman`   .rodata@0x6ff3a9
- [CA] `verifymedal`   .rodata@0x6ff395

### unknown

- [CA] `accelerateLearn`   .rodata@0x6ff210
- [CA] `acceptinvite`   .rodata@0x6fe657
- [CA] `accuracy`   .rodata@0x6ff082
- [CA] `actionIdx`   .rodata@0x6fe6f2
- [CA] `add`   .rodata@0x6fda78
- [CA] `adddealnum`   .rodata@0x6fe043
- [CA] `adfa`   .rodata@0x6fd2d1
- [CA] `adjust`   .rodata@0x6fe9eb
- [CA] `advertises`   .rodata@0x6fdad4
- [CA] `agilePoint`   .rodata@0x6feac0
- [CA] `android`   .rodata@0x6fd37c
- [CA] `appflyercheckmoney`   .rodata@0x6fe11f
- [CA] `apple`   .rodata@0x6fd485
- [CA] `apply`   .rodata@0x6fd521
- [CA] `applyId`   .rodata@0x6fd63a
- [CA] `approve`   .rodata@0x6fd642
- [CA] `approveapply`   .rodata@0x6fe664
- [CA] `areaInfo`   .rodata@0x6ff2db
- [CA] `armor`   .rodata@0x6fd74a
- [CA] `arms`   .rodata@0x6fd745
- [CA] `atWarehouse`   .rodata@0x6fd76c
- [CA] `attend`   .rodata@0x6fec8d
- [CA] `auctionId`   .rodata@0x6fe850
- [CA] `auth`   .rodata@0x6fd25a
- [CA] `battleId`   .rodata@0x6fd5dc
- [CA] `battleInfo`   .rodata@0x6ff2d0
- [CA] `battlePrestiges`   .rodata@0x6fd5c5
- [CA] `blackMoney`   .rodata@0x6fd7b9
- [CA] `bloodlotterygetprize`   .rodata@0x6fecc8
- [CA] `bloodlotterylistprizes`   .rodata@0x6feca7
- [CA] `bloodlotterylog`   .rodata@0x6fecdd
- [CA] `bloodrecoverdouble`   .rodata@0x6fdffc
- [CA] `blueSelfPay`   .rodata@0x6fe43d
- [CA] `bossId`   .rodata@0x6fec17
- [CA] `bosshurtrank`   .rodata@0x6fe9a3
- [CA] `bossinfo`   .rodata@0x6fe9b0
- [CA] `brainwash`   .rodata@0x6feb94
- [CA] `braverecoverdouble`   .rodata@0x6fe00f
- [CA] `bugFix`   .rodata@0x6fea24
- [CA] `bugFixed`   .rodata@0x6fd2f7
- [CA] `buildId`   .rodata@0x6ff154
- [CA] `buildinginfo`   .rodata@0x6ff168
- [CA] `bulletinId`   .rodata@0x6fd2a6
- [CA] `buyType`   .rodata@0x6fe76d
- [CA] `buyapplevip`   .rodata@0x6fd48b
- [CA] `buyblood`   .rodata@0x6fea02
- [CA] `buycash`   .rodata@0x6fdfb4
- [CA] `buygoogleplay`   .rodata@0x6fd46f
- [CA] `buytimes`   .rodata@0x6fea0b
- [CA] `byDiscount`   .rodata@0x6fd990
- [CA] `cancel`   .rodata@0x6fd71a
- [CA] `cancelapply`   .rodata@0x6fe64b
- [CA] `cancelgang`   .rodata@0x6fd671
- [CA] `cancletitle`   .rodata@0x6fe325
- [CA] `canvass`   .rodata@0x6fe284
- [CA] `canvassinworld`   .rodata@0x6fe383
- [CA] `carId`   .rodata@0x6fed75
- [CA] `carLevel`   .rodata@0x6fef0d
- [CA] `cbWeapon`   .rodata@0x6fd757
- [CA] `cbWeaponNum`   .rodata@0x6fd760
- [CA] `changeMode`   .rodata@0x6feda8
- [CA] `channelId`   .rodata@0x6fe7a0
- [CA] `channelName`   .rodata@0x6fe794
- [CA] `cheat`   .rodata@0x6fd7dc
- [CA] `checkSize`   .rodata@0x6fdc79
- [CA] `checkin_house`   .rodata@0x6fd170
- [CA] `cksum`   .rodata@0x6fd246
- [CA] `classCategory`   .rodata@0x6fe3b0
- [CA] `classId`   .rodata@0x6fe3be
- [CA] `cleanEstateAvatar`   .rodata@0x6fe92a
- [CA] `clearSign`   .rodata@0x6fe8fa
- [CA] `cn91Id`   .rodata@0x6fd25f
- [CA] `commonept`   .rodata@0x6fd397
- [CA] `compare`   .rodata@0x6fe53b
- [CA] `componentType`   .rodata@0x6fed60
- [CA] `confertitle`   .rodata@0x6fe319
- [CA] `consumeType`   .rodata@0x6fdfa8
- [CA] `consumevip`   .rodata@0x6fe02c
- [CA] `contribute`   .rodata@0x6fd5eb
- [CA] `cooperationrank`   .rodata@0x6fdb0c
- [CA] `costGoods`   .rodata@0x6fea6c
- [CA] `costGoodsType`   .rodata@0x6fe08c
- [CA] `createchannel`   .rodata@0x6fe7af
- [CA] `crossPlat`   .rodata@0x6fd372
- [CA] `ctrlVersion`   .rodata@0x6fdc83
- [CA] `cuisineType`   .rodata@0x6ff0fa
- [CA] `curDistance`   .rodata@0x6ff0aa
- [CA] `currSteps`   .rodata@0x6fe707
- [CA] `customHouseAt`   .rodata@0x6fd148
- [CA] `customHouseTag`   .rodata@0x6fd156
- [CA] `dailyTaskId`   .rodata@0x6fd2b1
- [CA] `dailyTaskItemIdx`   .rodata@0x6fe14e
- [CA] `dealId`   .rodata@0x6fd713
- [CA] `dealSizeInc`   .rodata@0x6fe037
- [CA] `decomposerecord`   .rodata@0x6fe4e1
- [CA] `decoration1`   .rodata@0x6fd0cb
- [CA] `decoration2`   .rodata@0x6fd0d7
- [CA] `decoration3`   .rodata@0x6fd0e3
- [CA] `deletechannel`   .rodata@0x6fe7bd
- [CA] `developlist`   .rodata@0x6fe450
- [CA] `diffculty`   .rodata@0x6fe94d
- [CA] `difficulty`   .rodata@0x6fdd31
- [CA] `disableDeviceHours`   .rodata@0x6fe8cb
- [CA] `disablePlayerHours`   .rodata@0x6fe8de
- [CA] `done`   .rodata@0x6fec61
- [CA] `durationUnit`   .rodata@0x6fdfe5
- [CA] `email`   .rodata@0x6fd1a2
- [CA] `emotionId`   .rodata@0x6fe364
- [CA] `encounterId`   .rodata@0x6fdadf
- [CA] `endurancePoint`   .rodata@0x6fead6
- [CA] `enemyId`   .rodata@0x6fde5c
- [CA] `enemyName`   .rodata@0x6fde64
- [CA] `energyCardId`   .rodata@0x6feb4c
- [CA] `enroll`   .rodata@0x6fe276
- [CA] `enter`   .rodata@0x6fda68
- [CA] `enterkingfight`   .rodata@0x6fe25e
- [CA] `enterskyscraper`   .rodata@0x6fea14
- [CA] `equipId`   .rodata@0x6feda0
- [CA] `equipment`   .rodata@0x6fd778
- [CA] `estateId`   .rodata@0x6fde9c
- [CA] `exchangeIdx`   .rodata@0x6fdc09
- [CA] `exchangetype`   .rodata@0x6fe5d4
- [CA] `exitchannel`   .rodata@0x6fe7d7
- [CA] `expdouble`   .rodata@0x6fdff2
- [CA] `extend`   .rodata@0x6fed4c
- [CA] `extendMoney`   .rodata@0x6fd01b
- [CA] `facebookId`   .rodata@0x6fd1d6
- [CA] `factionId`   .rodata@0x6fe4cd
- [CA] `failerId`   .rodata@0x6ff311
- [CA] `fate`   .rodata@0x6fdd47
- [CA] `fightjudgenew`   .rodata@0x6fddb5
- [CA] `fixNum`   .rodata@0x6fed6e
- [CA] `fixType`   .rodata@0x6fed82
- [CA] `fixcar`   .rodata@0x6fed7b
- [CA] `fixcomponent`   .rodata@0x6fed53
- [CA] `forceAction`   .rodata@0x6ff37d
- [CA] `forcebossthumbup`   .rodata@0x6fec7c
- [CA] `formulaId`   .rodata@0x6fdbf4
- [CA] `friendId`   .rodata@0x6fd3fc
- [CA] `fromBuildId`   .rodata@0x6ff15c
- [CA] `gamecenterId`   .rodata@0x6fd1e1
- [CA] `gangBattleId`   .rodata@0x6fd5b8
- [CA] `gangUid`   .rodata@0x6fd694
- [CA] `gangevents`   .rodata@0x6fd6cb
- [CA] `getRank`   .rodata@0x6ff282
- [CA] `getbossdetail`   .rodata@0x6fe1c4
- [CA] `getcars`   .rodata@0x6fed44
- [CA] `getdebris`   .rodata@0x6fea39
- [CA] `getdisablestauts`   .rodata@0x6fe93c
- [CA] `getfcgroupmembers`   .rodata@0x6fe24c
- [CA] `getforcebossdetail`   .rodata@0x6fec94
- [CA] `getforcescore`   .rodata@0x6fe509
- [CA] `getfreeinfo`   .rodata@0x6febf3
- [CA] `getgoldtoolrank`   .rodata@0x6fe102
- [CA] `getlatestfightinfo`   .rodata@0x6fd6a8
- [CA] `getlocks`   .rodata@0x6ff3bf
- [CA] `getmedal`   .rodata@0x6fe3a7
- [CA] `getmerit`   .rodata@0x6fe6d0
- [CA] `getmyclasses`   .rodata@0x6fe3dd
- [CA] `getplayergang`   .rodata@0x6fd663
- [OK] `getplayerlist`   .rodata@0x6fd72c
- [CA] `getreward`   .rodata@0x6fee84
- [CA] `getstalls`   .rodata@0x6feb2e
- [CA] `getstoreitems`   .rodata@0x6fed8a
- [CA] `gettaskinfo`   .rodata@0x6fe9df
- [CA] `giftNum`   .rodata@0x6fe347
- [CA] `giftPackType`   .rodata@0x6fdc59
- [CA] `giftgoods`   .rodata@0x6fd2e3
- [CA] `giftmoney`   .rodata@0x6fd2ed
- [CA] `giftrose`   .rodata@0x6fe0dd
- [CA] `giveUpPit`   .rodata@0x6ff323
- [CA] `goldToolType`   .rodata@0x6ff005
- [CA] `goodsResource`   .rodata@0x6fdbbc
- [CA] `goodsvalue`   .rodata@0x6fe498
- [CA] `grab`   .rodata@0x6fe34f
- [CA] `granter`   .rodata@0x6fe307
- [CA] `grownup`   .rodata@0x6fe687
- [CA] `gym`   .rodata@0x6fda50
- [CA] `hasRoundTime`   .rodata@0x6ff134
- [CA] `home`   .rodata@0x6fd9ee
- [CA] `horn`   .rodata@0x6fe0cc
- [CA] `hornNum`   .rodata@0x6fe0c4
- [CA] `housecarl`   .rodata@0x6ff2fb
- [CA] `huntToolId`   .rodata@0x6ff067
- [CA] `huntToolIds`   .rodata@0x6ff040
- [CA] `hurtRate`   .rodata@0x6ff08b
- [CA] `hurtrank`   .rodata@0x6fec3d
- [CA] `iad_info`   .rodata@0x6ff112
- [CA] `impartedAt`   .rodata@0x6fd315
- [CA] `index`   .rodata@0x6fd819
- [CA] `info`   .rodata@0x6fef82
- [CA] `info2`   .rodata@0x6fec66
- [CA] `infos`   .rodata@0x6fe42c
- [CA] `init`   .rodata@0x6fe543
- [CA] `inspire`   .rodata@0x6fe2d6
- [CA] `introUid`   .rodata@0x6fd205
- [CA] `invite`   .rodata@0x6fe644
- [CA] `isClientOpen`   .rodata@0x6fdc66
- [CA] `isCrossVersion`   .rodata@0x6fd8fb
- [CA] `isExtraAccount`   .rodata@0x6fd275
- [CA] `isFaction`   .rodata@0x6febb7
- [CA] `isLucky`   .rodata@0x6fdcb9
- [CA] `isNew`   .rodata@0x6fd36c
- [CA] `isRefresh`   .rodata@0x6febcf
- [CA] `isReview`   .rodata@0x6fd3a1
- [CA] `isStreetWarVersion`   .rodata@0x6fd90a
- [CA] `isStrengStone`   .rodata@0x6fdcc1
- [CA] `isSystem`   .rodata@0x6fe87d
- [CA] `itemIdx`   .rodata@0x6fe5a0
- [CA] `jobCategory`   .rodata@0x6fd8dd
- [CA] `joinchannel`   .rodata@0x6fe7cb
- [CA] `joinfc`   .rodata@0x6fe234
- [CA] `joinlist`   .rodata@0x6ff14b
- [CA] `key`   .rodata@0x6fd242
- [CA] `kickchanneluser`   .rodata@0x6fe7ea
- [CA] `kingfightresult`   .rodata@0x6fe2f7
- [CA] `kinglist`   .rodata@0x6febc6
- [CA] `kingrank`   .rodata@0x6febd9
- [CA] `lang`   .rodata@0x6ff3df
- [CA] `lastMsgId`   .rodata@0x6fd4a2
- [CA] `lastReceivedMsgId`   .rodata@0x6fd405
- [CA] `leaderId`   .rodata@0x6febae
- [CA] `leave`   .rodata@0x6fe2c8
- [CA] `left`   .rodata@0x6fee15
- [CA] `lightscore`   .rodata@0x6fed2f
- [CA] `lightup`   .rodata@0x6fed27
- [CA] `list`   .rodata@0x6fd6d6
- [CA] `listapply`   .rodata@0x6fe67d
- [CA] `listapprs`   .rodata@0x6fe632
- [CA] `listcar`   .rodata@0x6feff4
- [CA] `listclasses`   .rodata@0x6fe3d1
- [CA] `listmasters`   .rodata@0x6fe5f7
- [CA] `liveEstate`   .rodata@0x6fd165
- [CA] `lockedSkills`   .rodata@0x6feb87
- [CA] `loserId`   .rodata@0x6fdd5b
- [CA] `loserName`   .rodata@0x6fdd63
- [CA] `luckyNum`   .rodata@0x6fdcda
- [CA] `maid1`   .rodata@0x6fd0ef
- [CA] `maid1Expire`   .rodata@0x6fdee7
- [CA] `maid1ExpireAt`   .rodata@0x6fd0f5
- [CA] `maid2`   .rodata@0x6fd103
- [CA] `maid2Expire`   .rodata@0x6fdef3
- [CA] `maid2ExpireAt`   .rodata@0x6fd109
- [CA] `maidType`   .rodata@0x6fdec0
- [CA] `maidexpire`   .rodata@0x6fdeff
- [CA] `maintainCost`   .rodata@0x6fde8f
- [CA] `maintainExpireAt`   .rodata@0x6fd137
- [CA] `majorVersion`   .rodata@0x6fd35f
- [CA] `mark`   .rodata@0x6fe36e
- [CA] `massageId`   .rodata@0x6ff336
- [CA] `masterregister`   .rodata@0x6fe68f
- [CA] `materialIdx`   .rodata@0x6fdca1
- [CA] `maxGangId`   .rodata@0x6fd543
- [CA] `maxPaymentId`   .rodata@0x6fe112
- [CA] `medicineType`   .rodata@0x6fd97a
- [CA] `memberId`   .rodata@0x6fd600
- [CA] `memberlist`   .rodata@0x6fe2a9
- [CA] `messageId`   .rodata@0x6fd29c
- [CA] `messageKey`   .rodata@0x6fd3e5
- [CA] `messageType`   .rodata@0x6fd417
- [CA] `miUid`   .rodata@0x6fd266
- [CA] `modifygender`   .rodata@0x6fe0b7
- [CA] `mopup`   .rodata@0x6fefbb
- [CA] `mounts`   .rodata@0x6fd750
- [CA] `myPitInfo`   .rodata@0x6ff2ab
- [CA] `mybosslist`   .rodata@0x6fe957
- [CA] `nameteam`   .rodata@0x6fe26d
- [CA] `newAPI`   .rodata@0x6ff0c5
- [CA] `newEvent`   .rodata@0x6fdd9a
- [CA] `newGangFlag`   .rodata@0x6fe05a
- [CA] `newGangName`   .rodata@0x6fe04e
- [CA] `newMedalNum`   .rodata@0x6ff389
- [CA] `newOwnerId`   .rodata@0x6fd616
- [CA] `newOwnerName`   .rodata@0x6fd621
- [CA] `newVersion`   .rodata@0x6fe331
- [CA] `newbie`   .rodata@0x6ff36b
- [CA] `nextGymIdx`   .rodata@0x6fda45
- [CA] `nextSize`   .rodata@0x6fd027
- [CA] `noChatHours`   .rodata@0x6fe8bf
- [CA] `noSendMsgHours`   .rodata@0x6fe904
- [CA] `nofighted`   .rodata@0x6fe022
- [CA] `nowFinishTime`   .rodata@0x6fe711
- [CA] `number`   .rodata@0x6fe3f4
- [CA] `occpyPit`   .rodata@0x6ff31a
- [CA] `oldPassword`   .rodata@0x6fd21b
- [CA] `onlyRound`   .rodata@0x6ff12a
- [CA] `opType`   .rodata@0x6fe296
- [CA] `operbyvolunteer`   .rodata@0x6fd4eb
- [CA] `orderType`   .rodata@0x6fe4d7
- [CA] `oreAmount`   .rodata@0x6ff347
- [CA] `origCity`   .rodata@0x6fd8f2
- [CA] `origCityId`   .rodata@0x6fd926
- [CA] `originalIdx`   .rodata@0x6fdcad
- [CA] `packetlist`   .rodata@0x6fe33c
- [CA] `password`   .rodata@0x6fd199
- [CA] `placeType`   .rodata@0x6fd709
- [CA] `playerKey`   .rodata@0x6fd1b7
- [CA] `playerUid`   .rodata@0x6fd82c
- [CA] `portal`   .rodata@0x6fefd5
- [CA] `positionId`   .rodata@0x6fe6fc
- [CA] `pourin`   .rodata@0x6feb9e
- [CA] `prices`   .rodata@0x6fda07
- [CA] `prisonerId`   .rodata@0x6fd9a9
- [CA] `productId`   .rodata@0x6fd441
- [CA] `productTypes`   .rodata@0x6fdbe7
- [CA] `products`   .rodata@0x6fdbd4
- [CA] `projectInfo`   .rodata@0x6ff204
- [CA] `projectParam`   .rodata@0x6ff1f7
- [CA] `proof`   .rodata@0x6fe913
- [CA] `purchaseData`   .rodata@0x6fd45c
- [CA] `purchaseDate`   .rodata@0x6fd44b
- [CA] `push`   .rodata@0x6fd497
- [CA] `quit`   .rodata@0x6fd688
- [CA] `randomGoodsType`   .rodata@0x6fe09a
- [CA] `ratingGold`   .rodata@0x6ff372
- [CA] `reAvatar`   .rodata@0x6fe8f1
- [CA] `recalllist`   .rodata@0x6fe5ec
- [CA] `receipt`   .rodata@0x6fd47d
- [CA] `receivePitYield`   .rodata@0x6ff2c0
- [CA] `receiverKey`   .rodata@0x6fd3be
- [CA] `receiverUid`   .rodata@0x6fd3cf
- [CA] `redMoney`   .rodata@0x6fd7b0
- [CA] `redSelfPay`   .rodata@0x6fe432
- [CA] `refreshType`   .rodata@0x6fe69e
- [CA] `refreshkillranknew`   .rodata@0x6fe181
- [CA] `refreshspecialstore`   .rodata@0x6fed13
- [CA] `refreshteaminfo`   .rodata@0x6fe373
- [CA] `refuse`   .rodata@0x6fe449
- [CA] `reject`   .rodata@0x6fd64a
- [CA] `rejectapply`   .rodata@0x6fe671
- [CA] `release`   .rodata@0x6fec1e
- [CA] `remove`   .rodata@0x6fe479
- [CA] `removeReason`   .rodata@0x6fe46c
- [CA] `removeexpiredchannel`   .rodata@0x6fe7fa
- [CA] `rentDays`   .rodata@0x6fd12e
- [CA] `rentExpire`   .rodata@0x6fdf0a
- [CA] `rentExpireAt`   .rodata@0x6fd121
- [CA] `report`   .rodata@0x6ff340
- [CA] `resend`   .rodata@0x6fec5a
- [CA] `reviewVersion`   .rodata@0x6fd33a
- [CA] `revive`   .rodata@0x6fe9cb
- [CA] `revivelist`   .rodata@0x6fe971
- [CA] `reward`   .rodata@0x6fefb4
- [CA] `rewardIdx`   .rodata@0x6fecbe
- [CA] `rewarddetail`   .rodata@0x6fe9d2
- [CA] `rightinfo`   .rodata@0x6fe354
- [CA] `robotIdx`   .rodata@0x6fdd28
- [CA] `roleTypes`   .rodata@0x6fe8b5
- [CA] `room`   .rodata@0x6fee2e
- [CA] `roundFinish`   .rodata@0x6fd7d0
- [CA] `roundId`   .rodata@0x6fd7e2
- [CA] `roundNum`   .rodata@0x6feee3
- [CA] `roundinfo`   .rodata@0x6ff141
- [CA] `rowCount`   .rodata@0x6fdacb
- [CA] `rowNum`   .rodata@0x6fd530
- [CA] `rowStart`   .rodata@0x6fd527
- [CA] `salaryAt`   .rodata@0x6fd190
- [CA] `samples`   .rodata@0x6ff0cc
- [CA] `saveLineup`   .rodata@0x6ff2b5
- [CA] `search`   .rodata@0x6fd68d
- [CA] `searchType`   .rodata@0x6ff04c
- [CA] `searchapprbyuid`   .rodata@0x6fe622
- [CA] `searchbyuid`   .rodata@0x6fd69c
- [CA] `searchmaster`   .rodata@0x6fe615
- [CA] `selfdevelop`   .rodata@0x6fe4a3
- [CA] `selfdone`   .rodata@0x6fe4c4
- [CA] `selfspeedup`   .rodata@0x6fe4af
- [CA] `selftake`   .rodata@0x6fe4bb
- [CA] `sellPrice`   .rodata@0x6fd117
- [CA] `sellcar`   .rodata@0x6fedb3
- [CA] `sendverifymail`   .rodata@0x6ff11b
- [CA] `serverOpen`   .rodata@0x6fdc22
- [CA] `sessionToken`   .rodata@0x6ff35e
- [CA] `setinviter`   .rodata@0x6fe5e1
- [CA] `sharefriend`   .rodata@0x6fe997
- [CA] `shareworld`   .rodata@0x6fe98c
- [CA] `showsuitableapprs`   .rodata@0x6fe603
- [CA] `sig`   .rodata@0x6fd458
- [CA] `size`   .rodata@0x6fd016
- [CA] `skinType`   .rodata@0x6feffc
- [CA] `slogan`   .rodata@0x6fe27d
- [CA] `socialId`   .rodata@0x6fd26c
- [CA] `sourceGoods`   .rodata@0x6fdceb
- [CA] `sourceType`   .rodata@0x6fe5c9
- [CA] `specialParam`   .rodata@0x6febff
- [CA] `speedPoint`   .rodata@0x6feacb
- [CA] `spouseId`   .rodata@0x6fde78
- [CA] `stallId`   .rodata@0x6feb38
- [CA] `store`   .rodata@0x6ff2e4
- [CA] `storeBuy`   .rodata@0x6ff2f2
- [CA] `storeEnergy`   .rodata@0x6feb59
- [CA] `storeId`   .rodata@0x6fed98
- [CA] `storebuy`   .rodata@0x6fed0a
- [CA] `strengthPoint`   .rodata@0x6feab2
- [CA] `subId`   .rodata@0x6fd49c
- [CA] `success`   .rodata@0x6ff3a1
- [CA] `switching`   .rodata@0x6fe548
- [CA] `systemEstate`   .rodata@0x6fd0be
- [CA] `take`   .rodata@0x6fe480
- [CA] `taobao`   .rodata@0x6fd725
- [CA] `targetGoods`   .rodata@0x6fdcf7
- [CA] `targetRank`   .rodata@0x6fe4f1
- [CA] `targetType`   .rodata@0x6fe530
- [CA] `testmatch`   .rodata@0x6fed3a
- [CA] `theme`   .rodata@0x6fd469
- [CA] `themeinfo`   .rodata@0x6fefc1
- [CA] `threadId`   .rodata@0x6fd3af
- [CA] `throwOutId`   .rodata@0x6fe2b4
- [CA] `throwout`   .rodata@0x6fe2bf
- [CA] `time`   .rodata@0x6fe7aa
- [CA] `titlelist`   .rodata@0x6fe30f
- [CA] `toBag`   .rodata@0x6fdc73
- [CA] `toPlace`   .rodata@0x6ff2ea
- [CA] `toWarehouse`   .rodata@0x6fe080
- [CA] `token`   .rodata@0x6fd43b
- [CA] `tools`   .rodata@0x6ff259
- [CA] `toolsAmount`   .rodata@0x6ff25f
- [CA] `traitor`   .rodata@0x6fe63c
- [CA] `transtoolId`   .rodata@0x6ff034
- [CA] `twitterId`   .rodata@0x6fd1cc
- [CA] `unequip`   .rodata@0x6ff022
- [CA] `unionkingfightresult`   .rodata@0x6fe392
- [CA] `upHousecarl`   .rodata@0x6ff305
- [CA] `update`   .rodata@0x6fe80f
- [CA] `updatefactorylevel`   .rodata@0x6fe485
- [CA] `updateganglevel`   .rodata@0x6fd6bb
- [CA] `updatesamplestatus`   .rodata@0x6ff0d4
- [CA] `upgradestore`   .rodata@0x6feb7a
- [CA] `useGoods`   .rodata@0x6ff32d
- [CA] `useMoney`   .rodata@0x6fec26
- [CA] `useTimeMachine`   .rodata@0x6fd931
- [CA] `usebomb`   .rodata@0x6febeb
- [CA] `userId`   .rodata@0x6fe7e3
- [CA] `version`   .rodata@0x6fd320
- [CA] `viewmerevents`   .rodata@0x6ff3c8
- [CA] `vipexpired`   .rodata@0x6fd73a
- [CA] `vote`   .rodata@0x6febc1
- [CA] `votelist`   .rodata@0x6febe2
- [CA] `wake`   .rodata@0x6fec6c
- [CA] `washprop`   .rodata@0x6feba5
- [CA] `weekplayers`   .rodata@0x6fdb00
- [CA] `weiboId`   .rodata@0x6fd1ee
- [CA] `withPitInfo`   .rodata@0x6ff276
- [CA] `word`   .rodata@0x6fde2a
- [CA] `worldsharelist`   .rodata@0x6fe962

## Parser classes (Cxxx) and their response-decode methods

Static cross-reference from the .dynsym table — these are the C++ methods the client calls per HTTP response. To know what fields a given endpoint must contain, disassemble its `OnReceiveResponse(int, void*)` or `ParseXxx(void*)` method and read the .rodata field-name strings loaded via `add ip, pc, #X` instructions.

## Mission system — fully reversed (client-side data path)

The mascot bubble and mission objective text come from **assets/mission.city + assets/ar**, NOT a server endpoint. CPlayer.missionId is the only input the server provides.

| id  | tutorialId | type | tarProgress | rewardExp | missionTip (ar)               |
|----:|-----------:|-----:|------------:|----------:|:-------------------------------|
|   1 |          1 |    4 |           5 |       100 | `اوجد وظيفة مناسبة` |
|   2 |          2 |    5 |           5 |       200 | `اشترى ادوات الجريمة` |
|   3 |          3 |    4 |           5 |       200 | `ابحث فى الشوارع مرة واحدة` |
|   4 |          4 |    3 |          10 |       300 | `اذهب الى الجيم` |
|   5 |          6 |    7 |          20 |       500 | `اهجم و اشرق السيدة` |
|   6 |          7 |    3 |          20 |      1000 | `اشترى شقة` |
|   7 |          9 |    7 |          20 |       500 | `اهجم ماك فلاى و اهرب` |
|   8 |         10 |    3 |          20 |       500 | `مستشفى للعلاج` |
|   9 |         11 |    6 |          30 |       500 | `اهجم على فاتسو` |
|  10 |         12 |    3 |          30 |       500 | `خد علاج` |
|  11 |         13 |    5 |          30 |       500 | `اشترى سلاح` |
|  12 |         14 |    3 |          30 |       200 | `اعداد السلاح` |
|  13 |         15 |    5 |          50 |       500 | `اشترى درع` |
|  14 |         16 |    3 |          50 |       200 | `اعداد الدرع` |
|  15 |         17 |    7 |          50 |      1000 | `أعق فاتسو` |
|  16 |          5 |    5 |          50 |      1000 | `اشترى ادوات استعادة الطاقة` |
|  17 |         18 |    7 |          70 |       500 | `قم بتحسبن بروفايلك` |
|  18 |         19 |    4 |          70 |       100 | `قوى نفسك حتى يصل الضوء الى اللون الاخضر` |
|  19 |         20 |    7 |          70 |      1000 | `اهجم على بيترس كا` |
|  20 |         21 |    4 |          70 |      1000 | `استخدم مزايا` |
|  21 |         22 |    2 |          70 |      1000 | `اتكلم فى مكبر الصوت` |
|  22 |         25 |    5 |         200 |      1000 | `بيع الادوات فى محلك` |
|  23 |         26 |    2 |         150 |      1000 | `احرق 20 سعر من الطاقة فى الجيم` |
|  26 |         23 |    4 |         150 |      1000 | `اوصل للمستوى 10` |
|  27 |         24 |    4 |         150 |      1000 | `قم بقياس قوتك ضد لاعبين اخرين` |
|  28 |         27 |    4 |         350 |      1000 | `ارتكب 5 جرايم` |
|  31 |          8 |    4 |          35 |       500 | `تحرك الى شقة جديدة` |
|  30 |         28 |    4 |         800 |      7500 | `اوصل للمستوى 15` |
|  35 |         29 |    4 |         800 |     10000 | `اوصل مستوى 20` |

## server.py current route registry

Explicitly handled endpoints (everything else falls through to the /city/<path:cmd> or root catch-all):

- `GET,POST,PUT,DELETE,PATCH /<path:path>`
- `GET,POST,PUT /api/authplayerkey`
- `GET,POST,PUT /api/connect`
- `GET,POST,PUT /api/getallserver`
- `GET,POST,PUT /checkversion`
- `GET,POST,PUT /city/<path:cmd>`
- `GET,POST,PUT /city/chat/<path:cmd>`
- `GET,POST,PUT /city/chat/gettopmsgs`
- `GET,POST,PUT /city/connect/connect`
- `GET,POST,PUT /city/connect/create`
- `GET,POST,PUT /city/connect/getplayerlist`
- `GET,POST,PUT /city/estate/buy`
- `GET,POST,PUT /city/estate/listestates`
- `GET,POST,PUT /city/fight/randomfighters`
- `GET,POST,PUT /city/goods/getcitygoods`
- `GET,POST,PUT /city/impart`
- `GET,POST,PUT /city/player/introplayers`
- `GET /debug/history`
- `GET /debug/probe`

