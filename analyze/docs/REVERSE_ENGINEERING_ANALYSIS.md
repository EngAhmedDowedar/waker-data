# Waker (وكر الاوغاد) - Complete Reverse Engineering Analysis

## 1. Project Overview

| Field | Value |
|-------|-------|
| **Game Name** | وكر الاوغاد (Den of Scoundrels / Wild City) |
| **Package** | `com.anansimobile.city_ar` |
| **Developer** | Anansi Mobile |
| **Version** | 1.1.38 (versionCode: 2090800068) |
| **Engine** | NextGenEngine (NGE) - Custom C++/OpenGL ES 2.0 engine |
| **Native Lib** | `libcity_ar.so` (armeabi) |
| **Min SDK** | 14 (Android 4.0) |
| **Target SDK** | 26 (Android 8.0) |
| **Market** | Google Play - Arabic region (GooglePlayAr channel) |

## 2. Architecture

### Entry Point
- **Main Activity**: `com.anansimobile.city_ar.Main` extends `com.anansimobile.nge.RootActivity`
- Loads native library: `System.loadLibrary("city_ar")`
- Uses OpenGL ES 2.0 via `NGGLSurfaceView` + `NDKRenderer`

### Engine (NGE - NextGenEngine)
- Custom C++ engine with JNI bridge to Java
- Key classes: `ngScreen`, `ngView`, `ngNode`, `ngMedia`
- Networking stack: `ngConnectionManager` → `ngConnectionSession` → `ngHttpClient`/`ngSocket`
- JSON parsing: `ngJsonRoot`, `ngJsonHash`, `ngJsonArray`, `ngJsonNode`
- Encryption: `ngRC4Mnger` (RC4 cipher for keepalive TCP packets)

### Game Flow (CLoadingScreen)
1. `ViewDidLoad` → Initialize
2. `DoCheckVersion` → Check game version against server
3. `CheckUpdate` → Verify if update needed
4. `DoGetServerInfo` → Fetch server list from main server
5. `DoChooseGameServer` → User picks server or auto-select
6. `DoFacebookLogin` OR `GuestRegister` → Authenticate
7. `OnLoginSuccess` → Receive player token
8. `DoGetPlayerList` → Get player/role list for this server
9. `DoChooseUser` / `DoCreateUser` → Select or create character
10. `DoConnectPlayerInfo` → Load full player data
11. `DoEnterGame` → Enter main game screen

## 3. Networking Analysis

### Server Domains (ALL DEAD)

| URL | Purpose | Port |
|-----|---------|------|
| `http://city-arab.anansigame.org:8080/` | **Main game API server** | 8080 |
| `http://city-arab.anansigame.org:2095/page/pwdreset` | Password reset page | 2095 |
| `http://appstat.anansicorp.org:8992/logevent/weightevent` | Analytics/stat server | 8992 |
| `http://city.wiyun.com/mobilefaq/helpfaq.html` | FAQ/Help page | 80 |
| `http://s3.amazonaws.com/anansi-bucket/police/cityarab_policy.html` | Privacy policy | 443 |
| `http://s3.amazonaws.com/anansi-bucket/cityen-download/respkg/%s` | Resource download | 443 |
| `http://www.sakhabgame.com/EN/soft/CityRes_005.zip` | Resource pack download | 80 |
| `http://trx.9191card.com/trx/paymentTrxOrder.action` | 91Card payment | 80 |
| `https://play.google.com/store/apps/details?id=com.anansimobile.city_ar` | Play Store link | 443 |
| `https://www.facebook.com/wkralawghad` | Facebook page | 443 |
| `https://twitter.com/Wild_City` | Twitter page | 443 |

### Protocol Details

#### HTTP API (Primary - Port 8080)
- **Format**: HTTP POST with `Content-Type: application/x-www-form-urlencoded`
- **Response**: JSON (`{"result": ..., "data": ..., "code": ..., "errorMsg": ...}`)
- **Client class**: `CHttpClient` (636 API methods identified)
- **URL pattern**: `http://{server_host}:{port}/{endpoint}`

#### TCP Keep-Alive Socket
- **Fields**: `keepLiveServerHost`, `keepLiveServerPort`
- **Encryption**: RC4 via `ngRC4Mnger`
- **Purpose**: Real-time notifications, heartbeat, chat, poker (Texas Hold'em)
- **Packet format**: Binary with `ngByteBuffer`, RC4 encrypted
- **Heartbeat**: `CHeartBeat` sends periodic keep-alive packets

#### API Endpoints (Key ones from CHttpClient)
- `guest/register` - Guest account registration
- `connect/` - Connection handshake
- `player/` - Player data
- `player/rating` - Player ratings
- `chat/` - Chat system
- `game/` - Game actions
- `api/` - General API

### 3rd Party SDKs (All can be disabled)
- **Facebook SDK** (login, sharing)
- **Firebase** (FCM push notifications)
- **Umeng** (analytics - `http://alog.umeng.com/app_logs`)
- **TalkingData** (analytics)
- **AppsFlyer** (attribution tracking)
- **Vungle** (video ads)
- **Helpshift** (customer support)
- **Payssion** (payments)
- **Google Play Billing** (IAP)

## 4. Security Analysis

### Encryption
- **RC4**: Used for TCP keep-alive packet encryption (`ngRC4Mnger`)
  - `EncryptKpAliveData` / `DecryptKpAliveData`
  - Key initialized via `InitKey()`
- **MD5/SHA1**: Used for checksum verification (resource packages)
- **No SSL pinning**: HTTP (not HTTPS) used for main API
- **No certificate validation**: Plain HTTP connection to port 8080

### Anti-Tamper
- **Google Play License Check**: `com.android.vending.CHECK_LICENSE`
- **APK Expansion File**: Version-based OBB file check
- **Base64 Public Key** for IAP verification (in `Main.smali`)
- **No root detection** observed
- **No anti-debug** observed

### IAP Public Key
```
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAgd8SYj+8N+tMCVElpVMDKTTUZONwDK4LBG3a1IuUqAj0Q+6ashOfugRlZtT6Z3C0HO5AbW55eVsQV7vGrjEz4TEsZ2fMCwLy1AETU3ufAf1RT4f+yqd3GeWjnfAxoesL0zrnwkyGSYim3WdFo/X32V63XiFca9MDW1oTDAmCoZmy3W/XsxYHgQ2IWwq1UIJy1Z7L8nAr9pEXed0MBu5NoZ7B8R5Rn905fBVr3708eDyVGFlO8qKOZJo8A8j6lbecuGR2WSNshYpTCPIY08r8SyEsRxMsqQwVSeh73kunuoemOBl4emhro/PA2t4nzF6bLPXlhkgYbXM0kzkJ6KLbeQIDAQAB
```

## 5. Version/Update System

- `CHttpClient::CheckVersion()` - Sends version to server
- `CLoadingScreen::DoCheckVersion()` - Called during startup
- `CLoadingScreen::CheckUpdate()` - Compares local vs server version
- `CLoadingScreen::AfterUpgrade()` - Post-update handler
- Resource packages downloaded from S3: `anansi-bucket/cityen-download/respkg/%s`

## 6. Native Library Analysis

### `libcity_ar.so` (armeabi)
- **Full game engine** compiled in C++
- **~636 HTTP API methods** in `CHttpClient`
- **Key manager classes**:
  - `CServerMnger` - Server list management, server selection
  - `CHttpClient` - All HTTP API calls
  - `CTcpClient` - Real-time TCP connection (poker, chat, notifications)
  - `CHeartBeat` - Keep-alive heartbeat
  - `ngRC4Mnger` - RC4 encryption for TCP packets
  - `ngConnectionManager` - HTTP connection pool (uses libcurl)
  - `CLoadingMnger` - Loading/init sequence
  - `CGameData` - Game state management
  - `CJsonHelper` / `CDZ_JsonHelper` - JSON parsing helpers

### JNI Methods
- `NextGenEngine.bitmapDataDidLoad()` - Native bitmap loading
- `NGReachability.onNetworkStatusChange()` - Network state callback
- `NGHttpSession.doPut()` - HTTP PUT helper (stub in Java, real impl in native)
- `RootActivity.HandleSystemBackEvent()` - Back button handler

## 7. Why The Game No Longer Works

**The servers are completely shut down.** All game servers at `anansigame.org` and `anansicorp.org` are offline. The game cannot:
1. Check version (fails at startup)
2. Get server list (no servers respond)
3. Authenticate (no login server)
4. Load player data (no game server)

The game was an Arabic-region online city-building/crime game by Anansi Mobile, likely shut down around 2019-2020.

## 8. Data Formats

### `.city` files - Binary game data tables
- Header: length-prefixed records with string IDs
- Contains: city names, equipment stats, quest data, etc.
- Example from `cities.city`: cities with names like "nanfei", "xianggang", "aiji", "moxige", "usa", "baxi", "riben", "uk"

### `.drf` files - Device/display configuration
- Binary format referencing image assets at different scales

### JSON - Animation/skeleton data
- DragonBones format: `*_ske.json` (skeleton), `*_tex.json` (texture atlas)

### Response Format (JSON)
```json
{
  "result": 0,
  "code": 200,
  "data": { ... },
  "errorMsg": "",
  "servers": [ ... ],
  "playerList": [ ... ],
  "token": "...",
  "playerId": 12345,
  "status": "ok"
}
```

## 9. Server Recreation Strategy

The game uses a standard HTTP REST API on port 8080 with JSON responses. The TCP keepalive is secondary and can be stubbed. The critical flow is:

1. **Version check** → Return "no update needed"
2. **Server list** → Return a single local server
3. **Guest register / Login** → Return fake credentials
4. **Player data** → Return a starter player profile
5. **All other API calls** → Return success with minimal valid data
6. **TCP keepalive** → Accept connections, respond to heartbeats

This is fully achievable with a local server.
