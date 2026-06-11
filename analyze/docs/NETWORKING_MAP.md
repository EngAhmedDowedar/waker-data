# Waker (وكر الاوغاد) - Complete Networking Map

## Network Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    ANDROID DEVICE                                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Game Client (APK)                                        │   │
│  │  ┌─────────────────┐  ┌────────────────┐                │   │
│  │  │ Java Layer       │  │ Native Layer   │                │   │
│  │  │ (smali/dex)      │  │ (libcity_ar.so)│                │   │
│  │  │                  │  │                │                │   │
│  │  │ - Main.smali     │  │ - CHttpClient  │                │   │
│  │  │ - RootActivity   │──│ - CTcpClient   │                │   │
│  │  │ - NextGenEngine  │  │ - CServerMnger │                │   │
│  │  │ - NGHttpSession  │  │ - CHeartBeat   │                │   │
│  │  │ - Analytics SDKs │  │ - ngRC4Mnger   │                │   │
│  │  └─────────────────┘  └───┬────┬───────┘                │   │
│  └───────────────────────────┼────┼──────────────────────────┘   │
│                              │    │                              │
└──────────────────────────────┼────┼──────────────────────────────┘
                               │    │
              HTTP POST :8080  │    │  TCP :9090 (RC4 encrypted)
              (JSON responses) │    │  (heartbeat, chat, poker)
                               │    │
┌──────────────────────────────┼────┼──────────────────────────────┐
│               LOCAL SERVER (127.0.0.1)                            │
│  ┌───────────────────────────┴────┴──────────────────────────┐   │
│  │                                                           │   │
│  │  ┌─────────────────┐  ┌──────────────┐  ┌─────────────┐  │   │
│  │  │ HTTP API :8080   │  │ TCP KA :9090 │  │ Stats :8992 │  │   │
│  │  │ (Express/Flask)  │  │ (net/socket) │  │ (stub)      │  │   │
│  │  │                  │  │              │  │             │  │   │
│  │  │ ~60+ endpoints   │  │ heartbeat    │  │ /logevent/* │  │   │
│  │  │ JSON responses   │  │ ack packets  │  │ always OK   │  │   │
│  │  └─────────────────┘  └──────────────┘  └─────────────┘  │   │
│  └───────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Connection Flow Diagram

```
Game Boot → CLoadingScreen::ViewDidLoad
    │
    ▼
[1] DoCheckVersion ─────────────────► POST /check_version
    │                                  Response: {version: "1.1.38", needUpdate: false}
    ▼
[2] CheckMaintenance ───────────────► POST /check_maintenance
    │                                  Response: {maintenance: false}
    ▼
[3] DoGetServerInfo ────────────────► POST /server_list
    │                                  Response: {servers: [{id:1, host:"127.0.0.1",
    │                                    port:8080, keepLiveServerHost:"127.0.0.1",
    │                                    keepLiveServerPort:9090}]}
    ▼
[4] DoChooseGameServer ─────────────► (client-side selection, no HTTP call)
    │                                  Selects server from list
    ▼
[5] GuestRegister ──────────────────► POST /guest/register
    │  OR DoFacebookLogin               Response: {playerId, token, sessionId}
    │  OR PlayerAuth
    ▼
[6] OnLoginSuccess ─────────────────► (client-side, stores token)
    │
    ▼
[7] DoGetPlayerList ────────────────► POST /player/list
    │                                  Response: {roleList: [{playerId, name, level}]}
    ▼
[8] DoChooseUser ───────────────────► (client-side selection)
    │  OR DoCreateUser ─────────────► POST /player/create
    │                                  Response: {playerId, name, created: true}
    ▼
[9] DoConnectPlayerInfo ────────────► POST /connect
    │                                  Response: {full player data, keepLiveServer*}
    ▼
[10] TCP KeepAlive Connect ─────────► TCP connect to 127.0.0.1:9090
    │                                  RC4 encrypted heartbeat packets
    ▼
[11] DoEnterGame ───────────────────► (enters main game screen)
    │
    ▼
[GAME RUNNING] ─── periodic ────────► POST /heartbeat (HTTP fallback)
                                      TCP heartbeat (CHeartBeat)
                                      Various API calls as player acts
```

## Protocol Details

### HTTP Protocol

| Property | Value |
|----------|-------|
| **Method** | POST (primarily), GET accepted |
| **Content-Type** | `application/x-www-form-urlencoded` |
| **Response Format** | JSON |
| **Port** | 8080 |
| **SSL/TLS** | None (plain HTTP) |
| **Authentication** | Token-based (received after login) |

### Standard Response Format

```json
{
    "result": 0,        // 0 = success, non-zero = error code
    "code": 200,        // HTTP-like status code
    "data": { ... },    // Response payload
    "errorMsg": "",     // Error message (empty on success)
    "status": "ok"      // "ok" or "error"
}
```

### TCP Keep-Alive Protocol

| Property | Value |
|----------|-------|
| **Port** | 9090 (from `keepLiveServerPort` field) |
| **Encryption** | RC4 via `ngRC4Mnger` |
| **Format** | Binary with `ngByteBuffer` |
| **Packet Header** | 4-byte length prefix |
| **Heartbeat** | `CHeartBeat::SendHeartBeat()` periodic |
| **Features** | Chat, Poker (Texas Hold'em), Notifications, Street War |

### Analytics/Stats Protocol

| Property | Value |
|----------|-------|
| **Port** | 8992 |
| **Endpoint** | `/logevent/weightevent` |
| **Purpose** | Game analytics, event logging |
| **Required** | No (can return empty success) |

## Server Endpoints by Category

### Boot/Init Sequence (CRITICAL)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/check_version` | POST | Version check (must return needUpdate=false) |
| `/check_maintenance` | POST | Maintenance check (must return maintenance=false) |
| `/server_list` | POST | Server list with keepalive info |
| `/guest/register` | POST | Guest account creation |
| `/player/auth` | POST | Existing player authentication |
| `/connect/facebook` | POST | Facebook login |
| `/player/list` | POST | Get player/role list for server |
| `/player/create` | POST | Create new character |
| `/connect` | POST | Full player data load + enter game |

### Player Management
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/player/info` | POST | Get player details |
| `/player/update` | POST | Update player info |
| `/player/rating` | POST | Get player rating/rank |
| `/signature/update` | POST | Update player signature |

### Social
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/chat/get` | POST | Get chat messages |
| `/chat/post` | POST | Send chat message |
| `/chat/sys` | POST | System messages |
| `/chat/top` | POST | Top/pinned messages |
| `/mail/list` | POST | Get mailbox |
| `/friend/list` | POST | Friends list |
| `/friend/add` | POST | Add friend |
| `/friend/delete` | POST | Remove friend |
| `/friend/approve` | POST | Accept friend request |
| `/enemy/get` | POST | Enemies list |
| `/enemy/add` | POST | Add enemy |
| `/enemy/delete` | POST | Remove enemy |

### Faction/Gang
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/faction/list` | POST | List factions |
| `/faction/info` | POST | Faction details |
| `/faction/create` | POST | Create faction |
| `/faction/apply` | POST | Apply to faction |
| `/faction/approve` | POST | Approve faction member |
| `/yb/store` | POST | Faction store |
| `/yb/battle` | POST | Faction battle |

### Game Actions
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/crime/do` | POST | Commit crime |
| `/work/do` | POST | Do work |
| `/mission/list` | POST | Mission list |
| `/mission/update` | POST | Update mission |
| `/gym/enter` | POST | Enter gym |
| `/gym/train` | POST | Train stats |
| `/cure` | POST | Hospital heal |
| `/drug/eat` | POST | Use drugs |

### Economy
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/bank/balance` | POST | Bank balance |
| `/bank/deposit` | POST | Deposit gold |
| `/bank/withdraw` | POST | Withdraw gold |
| `/market/list` | POST | Market listings |
| `/market/buy` | POST | Buy from market |
| `/market/sell` | POST | Sell on market |
| `/store/buy` | POST | Buy from store |
| `/store/vip` | POST | VIP store |
| `/deal/list` | POST | Trade listings |
| `/deal/create` | POST | Create trade |
| `/deal/buy` | POST | Accept trade |
| `/auction/list` | POST | Auction listings |
| `/auction/create` | POST | Create auction |
| `/auction/bid` | POST | Bid on auction |

### Combat/PvP
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/prison/list` | POST | Prison inmates |
| `/prison/bail` | POST | Bail out |
| `/prison/bust` | POST | Bust out |
| `/dungeon/enter` | POST | Enter dungeon |
| `/dungeon/pass` | POST | Complete dungeon |
| `/race/enter` | POST | Enter race |
| `/kingfight/config` | POST | King fight config |
| `/streetwar/enter` | POST | Street war |
| `/cross/fight` | POST | Cross-server fight |
| `/cross/ladder` | POST | Cross-server ladder |
| `/worldboss/detail` | POST | World boss |
| `/hunt/enter` | POST | Enter hunt |

### Buildings/City
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/house/buy` | POST | Buy house |
| `/house/info` | POST | House details |
| `/house/decorate` | POST | Decorate house |
| `/skyscraper/enter` | POST | Enter skyscraper |
| `/skyscraper/building` | POST | Skyscraper building |
| `/airline/get` | POST | Travel/airline |

### Progress/Ranking
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/equipment/list` | POST | Equipment list |
| `/strengthen` | POST | Strengthen equipment |
| `/achievement/list` | POST | Achievements |
| `/active/list` | POST | Events/activities |
| `/rank/list` | POST | Leaderboards |
| `/showcase/list` | POST | Showcase |
| `/master/info` | POST | Master/apprentice |

### System
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/heartbeat` | POST | HTTP heartbeat |
| `/checksum` | POST | Data checksum |
| `/daily/gift` | POST | Daily login gifts |
| `/login/gift` | POST | Login rewards |
| `/window/config` | POST | UI popup config |
| `/window/status` | POST | Window status |
| `/push/token` | POST | Push notification token |
| `/advertises` | POST | Ad config |
| `/verify/payment` | POST | Payment verification |
| `/page/pwdreset` | GET | Password reset page |
| `/logevent/weightevent` | POST | Analytics (stub) |

## Original Server Domains (ALL DEAD)

| Domain | Port | Purpose | Redirected To |
|--------|------|---------|---------------|
| `city-arab.anansigame.org` | 8080 | Main game API | `127.0.0.1:8080` |
| `city-arab.anansigame.org` | 2095 | Password reset | `127.0.0.1:8080` |
| `appstat.anansicorp.org` | 8992 | Analytics | `127.0.0.1:8992` |
| `city.wiyun.com` | 80 | FAQ/Help | `127.0.0.1:8080` |
| `s3.amazonaws.com` | 443 | Resources/Policy | `127.0.0.1:8080` |
| `www.sakhabgame.com` | 80 | Resource pack | `127.0.0.1:8080` |
| `alog.umeng.com` | 80 | Umeng analytics | Disabled |
| `trx.9191card.com` | 80 | Payment | N/A |

## Data Flow: Request/Response Examples

### 1. Version Check
```
REQUEST:
POST /check_version HTTP/1.1
Host: 127.0.0.1:8080
Content-Type: application/x-www-form-urlencoded

version=1.1.38&versionCode=2090800068&platform=android&channel=GooglePlayAr

RESPONSE:
HTTP/1.1 200 OK
Content-Type: application/json

{
    "result": 0,
    "code": 200,
    "data": {
        "version": "1.1.38",
        "versionCode": 2090800068,
        "forceUpdate": false,
        "needUpdate": false,
        "updateUrl": "",
        "description": ""
    },
    "errorMsg": ""
}
```

### 2. Server List
```
REQUEST:
POST /server_list HTTP/1.1
Content-Type: application/x-www-form-urlencoded

platform=android&channel=GooglePlayAr

RESPONSE:
{
    "result": 0,
    "code": 200,
    "data": {
        "servers": [{
            "id": 1,
            "serverId": 1,
            "displayId": 1,
            "name": "Local Server",
            "host": "127.0.0.1",
            "port": 8080,
            "status": 1,
            "isNew": false,
            "isFull": false,
            "isRecommend": true,
            "platCode": "android",
            "showIdx": 1,
            "keepLiveServerHost": "127.0.0.1",
            "keepLiveServerPort": 9090
        }],
        "suggestServer": 1,
        "crossPlatCode": "android"
    },
    "errorMsg": ""
}
```

### 3. Guest Registration
```
REQUEST:
POST /guest/register HTTP/1.1
Content-Type: application/x-www-form-urlencoded

deviceId=abc123&platform=android&channel=GooglePlayAr&serverId=1

RESPONSE:
{
    "result": 0,
    "code": 200,
    "data": {
        "playerId": 100001,
        "userId": 100001,
        "token": "tok_abc123def456...",
        "sessionId": "sess_xyz789...",
        "isNew": true,
        "serverId": 1,
        "serverName": "Local Server"
    },
    "errorMsg": ""
}
```

### 4. Connect (Enter Game)
```
REQUEST:
POST /connect HTTP/1.1
Content-Type: application/x-www-form-urlencoded

playerId=100001&token=tok_abc123def456...&serverId=1

RESPONSE:
{
    "result": 0,
    "code": 200,
    "data": {
        "playerId": 100001,
        "name": "Player_100001",
        "level": 1,
        "exp": 0,
        "gold": 100000,
        "cash": 5000,
        "diamond": 1000,
        "energy": 100,
        "maxEnergy": 100,
        "blood": 100,
        "maxBlood": 100,
        "strength": 10,
        "defense": 10,
        "speed": 10,
        "cityId": 1,
        "keepLiveServerHost": "127.0.0.1",
        "keepLiveServerPort": 9090,
        "serverTime": 1716700000,
        "loginGifts": [],
        "windowConfigs": [],
        "announcements": []
    },
    "errorMsg": ""
}
```

### 5. TCP Heartbeat (Binary)
```
CLIENT → SERVER:
  4 bytes: packet length (big-endian)
  N bytes: RC4-encrypted heartbeat payload

SERVER → CLIENT:
  4 bytes: 00 00 00 00 (acknowledgment, zero-length payload)
```

## Key Response Fields Reference

| Field | Type | Description |
|-------|------|-------------|
| `result` | int | 0 = success, non-zero = error |
| `code` | int | Status code (200 = OK) |
| `data` | object | Response payload |
| `errorMsg` | string | Error message |
| `status` | string | "ok" or "error" |
| `playerId` | int | Player ID |
| `token` | string | Authentication token |
| `sessionId` | string | Session identifier |
| `servers` | array | Server list |
| `roleList` | array | Player characters on server |
| `keepLiveServerHost` | string | TCP keepalive host |
| `keepLiveServerPort` | int | TCP keepalive port |
| `serverTime` | int | Unix timestamp |
| `loginGifts` | array | Login gift items |
| `windowConfigs` | array | UI popup configurations |
| `announcements` | array | Server announcements |
| `statusAt` | int | Status start time |
| `statusDuration` | int | Status duration |
| `statusExpiredAt` | int | Status expiry time |
| `msgType` | int | Message type |
| `msgs` | array | Messages |
