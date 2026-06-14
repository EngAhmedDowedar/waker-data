# City-Boot Parser Dependency Graph (P4)

Parsers reached during the LoadingMnger boot sequence and the city-screen init,
with the endpoint that feeds each and the binary-extracted field contract.
All field types verified against live server JSON — **0 type mismatches** after
the four proven fixes (convertGoods, customHouseTag, bucket, flag).

Legend: ✓ = served with matching types · ∅ = endpoint returns empty (no records,
no field-type risk; container type handled separately).

```
PRE-LOAD  (version / server select)
└── /checkversion
    ├── CServer::Parse @0x56de78         servers[]          ✓ (bucket: string)
    │     fields: idx,status,port,recommend,register,mergeServer,bucket,displayIdx,
    │             useHttps(int)  name,url,comment,crossPlatCode,bucket(string)
    └── CLoadingScreen::ParseLastLoginPlayerInfo @0x490418  lastLoginPlayer{}  ✓
          fields: name(string), type(int)

step10  LoadingMnger — config + server list
├── /city/impart            CImpart::Parse @0x468d00        data:{}  ∅ (no fields read on empty)
└── /api/getallserver       CServer::Parse @0x56de78        servers[]  ✓

step11  character list / create
└── /city/connect/getplayerlist   CServerMnger::ParseRoleList → CCitier::Parse @0x34df98
        data:[]  ∅  (empty ⇒ character-creation path)

step12  player object (drives HUD)
└── /city/connect/connect (and /connect/create)   CPlayer::Parse @0x5140bc  (169 fields) ✓
    │   ALL fields null-checked (cmp r0,#0; beq) ⇒ MISSING is safe; only WRONG-TYPE crashes.
    ├── CPlayer::ParseStatus @0x516254     playerStatus{}   ✓ (6 fields)
    ├── CPlayer::ParseGoods  → CGoods::Parse @0x40cc70   goods[]   ✓ (7 fields; convertGoods omitted)
    ├── CPlayer::ParseBags   → CGoods::Parse             bags[]    ✓
    └── CPlayer::ParseHouses → CHouse::Parse @0x4498d8   estates[] ✓ (21 fields; customHouseTag: int)

step13  city screen init  (CMainScreen / CTopScreen)
├── /city/chat/gettopmsgs   CTopScreen::ParseMsg @0x592fb4    msgs[]  ✓ (senderName,content:string; createdAt,id:int)
├── /city/goods/getcitygoods  CMarketCateScreen::ParseGoodsAmount   goodsList:[]  ∅
├── /city/chat/getmsg       CChatScreen::ParseMsg @0x347edc   msgs[]  ✓ (10 fields)
└── (if mission active)
    ├── /city/fight/randomfighters  CCitier::Parse @0x34df98   data[]  ✓ (54 fields)
    └── /city/gang/randomgangs      CFaction::Parse @0x3ce220  data[]  ✓ (flag: string)

ON-DEMAND feature screens (not boot; audited for completeness — endpoints empty ⇒ ∅)
├── CFaction::Parse     /city/faction/info        ✓ (flag: string)
├── CGym::Parse         /city/gym/getgym          ✓ (4 gymTypes)
├── CFight::Parse       /city/fight/statistics    ∅
├── CCrime::Parse       /city/crime/list          ∅
├── CJob::Parse         /city/job/getjobs         ∅
├── CMessage::Parse     /city/message/list        ∅
└── CSubject::Parse     /city/school/subjects     ∅
```

## Proven fixes applied (parser + field + payload evidence each)

| Field | Parser | Read site | Expected | Was sent | Endpoint(s) |
|-------|--------|-----------|----------|----------|-------------|
| convertGoods | CGoods::Parse | 0x40cd40 nested-iterate | object (omit) | int 0 | connect, playerbags |
| customHouseTag | CHouse::Parse | 0x449b96 int veneer | int | string '' | connect.estates, listestates |
| bucket | CServer::Parse | 0x56dfde string path | string | int 0 | checkversion, getallserver |
| flag | CFaction::Parse | 0x3ce2ec string path | string | int 1 | faction/list, faction/info, randomgangs |

## Key invariant (why missing ≠ crash)

CPlayer::Parse and all per-record parsers null-check every field
(`GetNode → cmp r0,#0 → beq skip`). A MISSING field is skipped (safe). Only a
field that is PRESENT with the WRONG TYPE crashes (node passes the null-check,
then the typed extractor mis-reads it: int-veneer on a string → IntValue-null
0x10; string-path on an int → bad char* deref). Therefore the audit only needs
to verify TYPES of fields actually sent — done, 0 mismatches.

Tooling: `analyze/parser_contract_audit.py` (re-runnable against a live server).
Full output: `analyze/docs/PARSER_CONTRACT_AUDIT.txt`.
