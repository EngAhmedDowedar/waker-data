/**
 * Waker (وكر الاوغاد) - Local Server Emulator
 *
 * Emulates the game's HTTP API server (port 8080) and TCP keepalive server.
 * Allows the game client to boot and function with a private local backend.
 *
 * Based on reverse engineering of libcity_ar.so and smali analysis.
 */

const express = require('express');
const bodyParser = require('body-parser');
const net = require('net');

const HTTP_PORT = 8080;
const TCP_PORT = 9090;  // keepLiveServerPort
const STAT_PORT = 8992; // Analytics stat server

// Public IP/LAN IP that clients use to connect.
// Set via environment variable or defaults to 127.0.0.1.
// For LAN play: set SERVER_IP=192.168.x.x before starting.
const SERVER_IP = process.env.SERVER_IP || '127.0.0.1';

// ============================================================================
// GAME STATE
// ============================================================================

let nextPlayerId = 100001;
let players = {};
let sessions = {};

function generateToken() {
    return 'tok_' + Math.random().toString(36).substr(2, 24) + Date.now().toString(36);
}

function generateSessionId() {
    return 'sess_' + Math.random().toString(36).substr(2, 16);
}

function createDefaultPlayer(playerId, name) {
    return {
        playerId: playerId,
        userId: playerId,
        name: name || `Player_${playerId}`,
        level: 1,
        exp: 0,
        vipLevel: 0,
        gold: 100000,
        cash: 5000,
        diamond: 1000,
        energy: 100,
        maxEnergy: 100,
        nerve: 50,
        maxNerve: 50,
        blood: 100,
        maxBlood: 100,
        strength: 10,
        defense: 10,
        speed: 10,
        agile: 10,
        gender: 1,
        cityId: 1,
        jobId: 1,
        factionId: 0,
        factionName: "",
        avatar: "default_avatar",
        signature: "",
        loginContinuousDays: 1,
        createTime: Date.now(),
        lastLoginTime: Date.now(),
        statusAt: 0,
        statusDuration: 0,
        statusExpiredAt: 0,
        hostId: 1,
        hostName: "Local Server",
        merits: 0,
        fansNum: 0,
        marked: 0,
        emotion: 0,
        isVip: false,
        // Equipment
        weapon: 0,
        armor: 0,
        mount: 0,
        // Buildings
        buildings: [],
        // Inventory
        goods: [],
        // Friends
        friends: [],
        // Missions
        missions: [],
        // Skills
        skills: [],
    };
}

// ============================================================================
// HTTP API SERVER (Port 8080) - Main Game Server
// ============================================================================

const app = express();

// Parse both URL-encoded and JSON bodies
app.use(bodyParser.urlencoded({ extended: true }));
app.use(bodyParser.json());

// Log all requests for debugging
app.use((req, res, next) => {
    console.log(`[HTTP] ${req.method} ${req.url}`);
    if (Object.keys(req.body).length > 0) {
        console.log(`  Body: ${JSON.stringify(req.body).substring(0, 200)}`);
    }
    if (Object.keys(req.query).length > 0) {
        console.log(`  Query: ${JSON.stringify(req.query).substring(0, 200)}`);
    }
    next();
});

// ---- Utility response helpers ----

function successResponse(data = {}) {
    return {
        result: 0,
        code: 200,
        data: data,
        errorMsg: "",
        status: "ok"
    };
}

function errorResponse(code, msg) {
    return {
        result: code,
        code: code,
        data: {},
        errorMsg: msg,
        status: "error"
    };
}

// ---- VERSION CHECK ----
// CHttpClient::CheckVersion() / CLoadingScreen::DoCheckVersion()
// Game sends: PUT /checkversion
app.all('/checkversion', (req, res) => {
    console.log('[API] Version check (PUT /checkversion)');
    res.json({
        result: 0,
        code: 200,
        data: {
            version: "1.1.38",
            versionCode: 2090800068,
            forceUpdate: false,
            updateUrl: "",
            description: "",
            needUpdate: false
        },
        errorMsg: ""
    });
});

app.all('/check_version', (req, res) => {
    console.log('[API] Version check');
    res.json({
        result: 0,
        code: 200,
        data: {
            version: "1.1.38",
            versionCode: 2090800068,
            forceUpdate: false,
            updateUrl: "",
            description: "",
            needUpdate: false
        },
        errorMsg: ""
    });
});

app.all('/api/check_version', (req, res) => {
    res.json({
        result: 0, code: 200,
        data: { version: "1.1.38", forceUpdate: false, needUpdate: false },
        errorMsg: ""
    });
});

// ---- MAINTENANCE CHECK ----
// CHttpClient::CheckMaintenance()
app.all('/check_maintenance', (req, res) => {
    console.log('[API] Maintenance check');
    res.json({
        result: 0,
        code: 200,
        data: { maintenance: false, message: "" },
        errorMsg: ""
    });
});

app.all('/api/check_maintenance', (req, res) => {
    res.json({ result: 0, code: 200, data: { maintenance: false }, errorMsg: "" });
});

// ---- SERVER LIST ----
// CServerMnger::ParseServerList() / CLoadingScreen::DoGetServerInfo()
app.all('/server_list', (req, res) => {
    console.log('[API] Server list request');
    res.json({
        result: 0,
        code: 200,
        data: {
            servers: [
                {
                    id: 1,
                    serverId: 1,
                    displayId: 1,
                    name: "Local Server",
                    host: SERVER_IP,
                    port: HTTP_PORT,
                    status: 1,  // 1 = open
                    isNew: false,
                    isFull: false,
                    isRecommend: true,
                    platCode: "android",
                    showIdx: 1,
                    keepLiveServerHost: SERVER_IP,
                    keepLiveServerPort: TCP_PORT
                }
            ],
            suggestServer: 1,
            crossPlatCode: "android"
        },
        errorMsg: ""
    });
});

app.all('/api/server_list', (req, res) => {
    res.redirect('/server_list');
});

app.all('/servers', (req, res) => {
    res.redirect('/server_list');
});

// ---- GUEST REGISTRATION ----
// CHttpClient::GuestRegister() / CHttpClient::GuestRegisterPlayerServer()
app.all('/guest/register', (req, res) => {
    const pid = nextPlayerId++;
    const token = generateToken();
    const sessionId = generateSessionId();

    players[pid] = createDefaultPlayer(pid);
    sessions[sessionId] = { playerId: pid, token: token };

    console.log(`[API] Guest register -> playerId: ${pid}`);
    res.json({
        result: 0,
        code: 200,
        data: {
            playerId: pid,
            userId: pid,
            token: token,
            sessionId: sessionId,
            isNew: true,
            serverId: 1,
            serverName: "Local Server"
        },
        errorMsg: ""
    });
});

// ---- PLAYER AUTH ----
// CHttpClient::PlayerAuth()
app.all('/player/auth', (req, res) => {
    const pid = parseInt(req.body.playerId || req.query.playerId) || nextPlayerId++;
    const token = generateToken();
    const sessionId = generateSessionId();

    if (!players[pid]) {
        players[pid] = createDefaultPlayer(pid);
    }
    sessions[sessionId] = { playerId: pid, token: token };

    console.log(`[API] Player auth -> playerId: ${pid}`);
    res.json({
        result: 0,
        code: 200,
        data: {
            playerId: pid,
            userId: pid,
            token: token,
            sessionId: sessionId,
            isNew: false
        },
        errorMsg: ""
    });
});

// ---- FACEBOOK LOGIN ----
// CHttpClient::PlayerConnectFacebook()
app.all('/connect/facebook', (req, res) => {
    const pid = nextPlayerId++;
    const token = generateToken();

    players[pid] = createDefaultPlayer(pid);

    console.log(`[API] Facebook connect -> playerId: ${pid}`);
    res.json({
        result: 0, code: 200,
        data: { playerId: pid, userId: pid, token: token, isNew: true },
        errorMsg: ""
    });
});

app.all('/connectFacebook', (req, res) => {
    res.redirect(307, '/connect/facebook');
});

// ---- ROLE/PLAYER LIST ----
// CServerMnger::ParseRoleList() / CLoadingScreen::DoGetPlayerList()
app.all('/player/list', (req, res) => {
    const pid = parseInt(req.body.playerId || req.query.playerId) || Object.keys(players)[0] || 100001;
    const player = players[pid] || createDefaultPlayer(pid);

    console.log(`[API] Player list for pid: ${pid}`);
    res.json({
        result: 0,
        code: 200,
        data: {
            roleList: [
                {
                    playerId: player.playerId,
                    name: player.name,
                    level: player.level,
                    gender: player.gender,
                    avatar: player.avatar,
                    serverId: 1,
                    serverName: "Local Server",
                    cityId: player.cityId
                }
            ],
            canCreate: true
        },
        errorMsg: ""
    });
});

app.all('/role/list', (req, res) => {
    res.redirect('/player/list');
});

// ---- CREATE PLAYER ----
// CLoadingScreen::DoCreateUser() / CHttpClient::UserCreate()
app.all('/player/create', (req, res) => {
    const pid = parseInt(req.body.playerId || req.query.playerId) || nextPlayerId++;
    const name = req.body.name || req.query.name || `Player_${pid}`;
    const gender = parseInt(req.body.gender || req.query.gender) || 1;

    players[pid] = createDefaultPlayer(pid, name);
    players[pid].gender = gender;

    console.log(`[API] Create player: ${name} (pid: ${pid})`);
    res.json({
        result: 0, code: 200,
        data: { playerId: pid, name: name, created: true },
        errorMsg: ""
    });
});

app.all('/user/create', (req, res) => {
    res.redirect(307, '/player/create');
});

// ---- PLAYER INFO / CONNECT ----
// CLoadingScreen::DoConnectPlayerInfo() / CHttpClient::Connect()
app.all('/connect', (req, res) => {
    const pid = parseInt(req.body.playerId || req.query.playerId) || 100001;
    let player = players[pid];
    if (!player) {
        player = createDefaultPlayer(pid);
        players[pid] = player;
    }
    player.lastLoginTime = Date.now();

    console.log(`[API] Connect player: ${pid}`);
    res.json({
        result: 0,
        code: 200,
        data: {
            ...player,
            keepLiveServerHost: SERVER_IP,
            keepLiveServerPort: TCP_PORT,
            serverTime: Math.floor(Date.now() / 1000),
            loginGifts: [],
            loginRewardList: [],
            windowConfigs: [],
            announcements: [],
            errorMsg: ""
        },
        errorMsg: ""
    });
});

app.all('/connect/', (req, res) => {
    res.redirect(307, '/connect');
});

// ---- PLAYER INFO ----
app.all('/player/info', (req, res) => {
    const pid = parseInt(req.body.playerId || req.query.playerId) || 100001;
    const player = players[pid] || createDefaultPlayer(pid);

    res.json({ result: 0, code: 200, data: player, errorMsg: "" });
});

// ---- PLAYER RATING ----
app.all('/player/rating', (req, res) => {
    res.json({
        result: 0, code: 200,
        data: { rating: 1000, rank: 1, totalPlayers: 1 },
        errorMsg: ""
    });
});

// ---- PLAYER UPDATE ----
// CHttpClient::UpdatePlayerInfo()
app.all('/player/update', (req, res) => {
    const pid = parseInt(req.body.playerId || req.query.playerId) || 100001;
    if (players[pid]) {
        Object.assign(players[pid], req.body);
    }
    res.json(successResponse({ updated: true }));
});

// ---- CHAT ----
// CHttpClient::ChatGetMessage() / ChatPostMessage() / ChatGetSysMsg()
app.all('/chat/get', (req, res) => {
    res.json({ result: 0, code: 200, data: { msgs: [], msgType: 0 }, errorMsg: "" });
});

app.all('/chat/post', (req, res) => {
    res.json(successResponse({ sent: true }));
});

app.all('/chat/sys', (req, res) => {
    res.json({ result: 0, code: 200, data: { msgs: [] }, errorMsg: "" });
});

app.all('/chat/top', (req, res) => {
    res.json({ result: 0, code: 200, data: { msgs: [] }, errorMsg: "" });
});

// ---- MAIL ----
app.all('/mail/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { mails: [] }, errorMsg: "" });
});

// ---- FRIENDS ----
app.all('/friend/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { friends: [] }, errorMsg: "" });
});

app.all('/friend/add', (req, res) => {
    res.json(successResponse());
});

app.all('/friend/delete', (req, res) => {
    res.json(successResponse());
});

app.all('/friend/approve', (req, res) => {
    res.json(successResponse());
});

// ---- ENEMY ----
app.all('/enemy/get', (req, res) => {
    res.json({ result: 0, code: 200, data: { enemies: [] }, errorMsg: "" });
});

app.all('/enemy/add', (req, res) => {
    res.json(successResponse());
});

app.all('/enemy/delete', (req, res) => {
    res.json(successResponse());
});

// ---- FACTION/GANG ----
app.all('/faction/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { factions: [] }, errorMsg: "" });
});

app.all('/faction/info', (req, res) => {
    res.json({ result: 0, code: 200, data: { factionId: 0 }, errorMsg: "" });
});

app.all('/faction/create', (req, res) => {
    res.json(successResponse({ factionId: 1, name: req.body.name || "Gang" }));
});

app.all('/faction/apply', (req, res) => {
    res.json(successResponse());
});

app.all('/faction/approve', (req, res) => {
    res.json(successResponse());
});

// ---- BUILDINGS / HOUSE ----
app.all('/house/buy', (req, res) => {
    res.json(successResponse({ houseId: 1 }));
});

app.all('/house/info', (req, res) => {
    res.json({ result: 0, code: 200, data: { houses: [] }, errorMsg: "" });
});

app.all('/house/decorate', (req, res) => {
    res.json(successResponse());
});

// ---- MARKET / STORE ----
app.all('/market/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { items: [] }, errorMsg: "" });
});

app.all('/market/sell', (req, res) => {
    res.json(successResponse());
});

app.all('/market/buy', (req, res) => {
    res.json(successResponse());
});

app.all('/store/buy', (req, res) => {
    res.json(successResponse());
});

// ---- CRIME / WORK / MISSIONS ----
app.all('/crime/do', (req, res) => {
    res.json({
        result: 0, code: 200,
        data: { success: true, exp: 10, gold: 100, energy: -5 },
        errorMsg: ""
    });
});

app.all('/work/do', (req, res) => {
    res.json({
        result: 0, code: 200,
        data: { success: true, exp: 5, gold: 50, energy: -3 },
        errorMsg: ""
    });
});

app.all('/mission/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { missions: [] }, errorMsg: "" });
});

app.all('/mission/update', (req, res) => {
    res.json(successResponse());
});

// ---- DAILY / LOGIN GIFTS ----
app.all('/daily/gift', (req, res) => {
    res.json({
        result: 0, code: 200,
        data: {
            loginContinuousDays: 1,
            loginGifts: [],
            loginRewardList: [],
            loginGiftGoldToolRatio: 1
        },
        errorMsg: ""
    });
});

app.all('/login/gift', (req, res) => {
    res.json({ result: 0, code: 200, data: { gifts: [] }, errorMsg: "" });
});

// ---- BANK ----
app.all('/bank/balance', (req, res) => {
    res.json({ result: 0, code: 200, data: { balance: 0, deposit: 0 }, errorMsg: "" });
});

app.all('/bank/deposit', (req, res) => {
    res.json(successResponse());
});

app.all('/bank/withdraw', (req, res) => {
    res.json(successResponse());
});

// ---- GYM ----
app.all('/gym/enter', (req, res) => {
    res.json(successResponse());
});

app.all('/gym/train', (req, res) => {
    res.json({ result: 0, code: 200, data: { success: true, statIncrease: 1 }, errorMsg: "" });
});

// ---- HOSPITAL / CURE ----
app.all('/cure', (req, res) => {
    res.json(successResponse({ blood: 100, maxBlood: 100 }));
});

// ---- PRISON ----
app.all('/prison/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { prisoners: [] }, errorMsg: "" });
});

app.all('/prison/bail', (req, res) => {
    res.json(successResponse());
});

app.all('/prison/bust', (req, res) => {
    res.json(successResponse());
});

// ---- DUNGEON ----
app.all('/dungeon/enter', (req, res) => {
    res.json(successResponse());
});

app.all('/dungeon/pass', (req, res) => {
    res.json(successResponse({ exp: 50, gold: 200 }));
});

// ---- AUCTION ----
app.all('/auction/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { auctions: [] }, errorMsg: "" });
});

app.all('/auction/create', (req, res) => {
    res.json(successResponse());
});

app.all('/auction/bid', (req, res) => {
    res.json(successResponse());
});

// ---- SKYSCRAPER ----
app.all('/skyscraper/enter', (req, res) => {
    res.json(successResponse());
});

app.all('/skyscraper/building', (req, res) => {
    res.json(successResponse());
});

// ---- EQUIPMENT / STRENGTHEN ----
app.all('/equipment/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { equipment: [] }, errorMsg: "" });
});

app.all('/strengthen', (req, res) => {
    res.json(successResponse({ success: true }));
});

// ---- DRUGS ----
app.all('/drug/eat', (req, res) => {
    res.json(successResponse());
});

// ---- ACHIEVEMENT ----
app.all('/achievement/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { achievements: [] }, errorMsg: "" });
});

// ---- ACTIVE / EVENTS ----
app.all('/active/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { activities: [] }, errorMsg: "" });
});

// ---- RACE GAME ----
app.all('/race/enter', (req, res) => {
    res.json(successResponse());
});

// ---- KING FIGHT ----
app.all('/kingfight/config', (req, res) => {
    res.json({ result: 0, code: 200, data: { kingFightConfig: {} }, errorMsg: "" });
});

// ---- STREET WAR ----
app.all('/streetwar/enter', (req, res) => {
    res.json(successResponse());
});

// ---- RANK / LEADERBOARD ----
app.all('/rank/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { ranks: [], weekRank: [] }, errorMsg: "" });
});

// ---- SHOWCASE ----
app.all('/showcase/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { showcases: [] }, errorMsg: "" });
});

// ---- HUNT ----
app.all('/hunt/enter', (req, res) => {
    res.json(successResponse());
});

// ---- AIRLINE ----
app.all('/airline/get', (req, res) => {
    res.json({ result: 0, code: 200, data: { arrived: true }, errorMsg: "" });
});

// ---- MASTER / APPRENTICE ----
app.all('/master/info', (req, res) => {
    res.json({ result: 0, code: 200, data: { master: null, children: [] }, errorMsg: "" });
});

// ---- PAYMENT VERIFICATION (Stub - always succeed) ----
app.all('/verify/payment', (req, res) => {
    res.json(successResponse({ verified: true }));
});

app.all('/store/vip', (req, res) => {
    res.json(successResponse({ vipLevel: 0 }));
});

// ---- PUSH NOTIFICATION TOKEN ----
app.all('/push/token', (req, res) => {
    res.json(successResponse());
});

// ---- ADVERTISES ----
app.all('/advertises', (req, res) => {
    res.json({ result: 0, code: 200, data: { ads: [] }, errorMsg: "" });
});

// ---- SIGNATURE UPDATE ----
app.all('/signature/update', (req, res) => {
    res.json(successResponse());
});

// ---- WINDOWS/POPUP CONFIG ----
app.all('/window/config', (req, res) => {
    res.json({ result: 0, code: 200, data: { windowConfigs: [] }, errorMsg: "" });
});

app.all('/window/status', (req, res) => {
    res.json(successResponse());
});

// ---- PASSWORD RESET PAGE (web) ----
app.get('/page/pwdreset', (req, res) => {
    res.send('<html><body><h1>Password Reset</h1><p>Local server - no password reset needed.</p></body></html>');
});

// ---- STATISTICS / ANALYTICS (stub) ----
app.all('/logevent/weightevent', (req, res) => {
    res.json({ result: 0 });
});

// ---- CROSS SERVER ----
app.all('/cross/fight', (req, res) => {
    res.json(successResponse());
});

app.all('/cross/ladder', (req, res) => {
    res.json({ result: 0, code: 200, data: { fighters: [] }, errorMsg: "" });
});

// ---- YB (义帮 - Faction Factory/Force) ----
app.all('/yb/store', (req, res) => {
    res.json({ result: 0, code: 200, data: { items: [] }, errorMsg: "" });
});

app.all('/yb/battle', (req, res) => {
    res.json(successResponse());
});

// ---- DEAL / TRADE ----
app.all('/deal/list', (req, res) => {
    res.json({ result: 0, code: 200, data: { deals: [] }, errorMsg: "" });
});

app.all('/deal/create', (req, res) => {
    res.json(successResponse());
});

app.all('/deal/buy', (req, res) => {
    res.json(successResponse());
});

// ---- WORLD BOSS ----
app.all('/worldboss/detail', (req, res) => {
    res.json({ result: 0, code: 200, data: { boss: null }, errorMsg: "" });
});

// ---- HEARTBEAT (HTTP fallback) ----
app.all('/heartbeat', (req, res) => {
    res.json({ result: 0, code: 200, data: { serverTime: Math.floor(Date.now() / 1000) }, errorMsg: "" });
});

// ---- CHECKSUM ----
app.all('/checksum', (req, res) => {
    res.json({ result: 0, code: 200, data: { valid: true }, errorMsg: "" });
});

// ---- CATCH-ALL: Return generic success for any unhandled API call ----
app.all('*', (req, res) => {
    console.log(`[API] UNHANDLED: ${req.method} ${req.url}`);
    console.log(`  Body: ${JSON.stringify(req.body)}`);
    res.json({
        result: 0,
        code: 200,
        data: {},
        errorMsg: "",
        status: "ok"
    });
});

// ============================================================================
// TCP KEEPALIVE SERVER (Port 9090)
// ============================================================================
// The game connects via TCP for real-time features (chat, poker, notifications).
// Uses RC4 encryption via ngRC4Mnger. We accept connections and respond to heartbeats.

const tcpServer = net.createServer((socket) => {
    const clientAddr = `${socket.remoteAddress}:${socket.remotePort}`;
    console.log(`[TCP] Client connected: ${clientAddr}`);

    socket.on('data', (data) => {
        console.log(`[TCP] Data from ${clientAddr}: ${data.length} bytes`);
        console.log(`  Hex: ${data.toString('hex').substring(0, 100)}`);

        // Simple heartbeat response: echo back data or send minimal ack
        // The game expects some response to keep the connection alive
        // RC4 encrypted, but we respond with minimal valid data
        try {
            // Send a simple acknowledgment (4 bytes: packet length = 0)
            const ack = Buffer.alloc(4, 0);
            socket.write(ack);
        } catch (e) {
            console.log(`[TCP] Error sending ack: ${e.message}`);
        }
    });

    socket.on('close', () => {
        console.log(`[TCP] Client disconnected: ${clientAddr}`);
    });

    socket.on('error', (err) => {
        console.log(`[TCP] Socket error (${clientAddr}): ${err.message}`);
    });
});

// ============================================================================
// ANALYTICS/STAT SERVER (Port 8992)
// ============================================================================

const statApp = express();
statApp.use(bodyParser.urlencoded({ extended: true }));
statApp.use(bodyParser.json());

statApp.all('*', (req, res) => {
    console.log(`[STAT] ${req.method} ${req.url} (ignored)`);
    res.json({ result: 0 });
});

// ============================================================================
// START ALL SERVERS
// ============================================================================

app.listen(HTTP_PORT, '0.0.0.0', () => {
    console.log(`============================================`);
    console.log(`  Waker Local Server - وكر الاوغاد`);
    console.log(`============================================`);
    console.log(`[HTTP] Game API server running on port ${HTTP_PORT}`);
    console.log(`       URL: http://${SERVER_IP}:${HTTP_PORT}/`);
});

tcpServer.listen(TCP_PORT, '0.0.0.0', () => {
    console.log(`[TCP]  KeepAlive server running on port ${TCP_PORT}`);
});

statApp.listen(STAT_PORT, '0.0.0.0', () => {
    console.log(`[STAT] Analytics server running on port ${STAT_PORT}`);
    console.log(`============================================`);
    console.log(`Ready! Configure your device to point to this server.`);
    console.log(`============================================`);
});
