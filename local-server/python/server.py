"""
Waker (وكر الاوغاد) — Local Server Emulator
============================================

Reproduces enough of the original game's HTTP backend to boot the dead-server
Arabic gangster game `com.anansimobile.city_ar` (v1.1.38) from title to the
main city screen, on a lightly patched client APK. See RUN_SERVER.md to run,
STATUS.md for what works, analyze/docs/SCHEMAS.md for the recovered schemas.

All three subsystems run on one Flask app, bound to 0.0.0.0:

    8080  /checkversion + /api/*   "game API"            (HTTP, cipher'd)
    9090  /city/*                  "keepLiveServer"      (HTTP, cipher'd)
    8992  catch-all                 analytics / ignored

WIRE PROTOCOL (recovered)
-------------------------
Every request and response on 8080/9090 is:

    body = base64( XOR(json_utf8, XOR_KEY) )

XOR_KEY is the 107-byte LOTR verse embedded in libcity_ar.so .rodata. XOR is
symmetric, so the same routine decodes requests and encodes responses.

The `_log_and_encode_response` after_request hook transparently re-encodes
outbound JSON to the wire form, and ALSO injects the four root fields the
native handler `ngHttpClient::HandleUpdate` reads with no null check:
    error        — string compared to "0" (success path; .rodata 0x6f780f)
    timestamp    — int via ngInteger::IntValue
    errorMessage — string via ngStringV2::GetCString
    data         — object/array (passed to the per-command parser)
Without these, the client null-derefs on the very first response.

KEY SYSTEMS POPULATED & STABILIZED
----------------------------------
* /checkversion          Full variant-6 schema with all upgrade fields, a
                         `lastLoginPlayer` OBJECT (a string crashes
                         ParseLastLoginPlayerInfo), and a `servers:[…]` entry.
                         Less than this crash-loops the version-check screen.

* /api/connect,          Login + cached-resume + server-selection. The
  /api/authplayerkey,    resume path stalls at "step 10" (binary keepalive
  /api/getallserver      not implemented) — clear state to force direct login.

* CPlayer (168 fields)   `_make_player()` — drives the HUD. Critical fields:
                         `newPlayer:0` disables the new-player tour (which
                         crashes the market/estate tutorial screens),
                         `missionId:100` parks past `mission.city`'s 29 entries
                         ("no active mission") because a real mission triggers
                         a chain of stubbed endpoints,
                         `avatarAt>0` suppresses the photo-picker overlay,
                         resource bars: the *Up field IS the max,
                         `playerStatus` MUST be an OBJECT (ParseStatus).

* CHouse (estate)        `_make_house()` with a valid `estateType` (CaoPeng=800
                         from property.city) so GetPrice's GetById resolves.

* CCitier (fight target) `_make_fighter()` — "random fighter" / role schema.

* /city/chat/gettopmsgs  A few paced messages stop the per-frame poll. The
                         per-frame poll itself was also killed by a .so patch
                         (file_off 0x59190d  DC→E0); both fixes ship.

* /city/goods/getcitygoods   `{goodsList:[]}` — a typed empty array (NOT `{}`;
                         empty object null-derefs MarketCateScreen render).

* /city/player/introplayers, /city/connect/getplayerlist
                         `data:[]` (array, not object) — ParseChilds /
                         ParseRoleList iterate begin/next and null-deref on
                         a non-array root.

CONNECTIVITY
------------
`SERVER_HOST` env var (or legacy `SERVER_IP`) is the host/IP advertised
back to the client. Must match the address the phone uses to reach this
machine. Default 127.0.0.1 only works for on-device testing.
"""

import base64
import json
import os
import threading
import time
from collections import deque
from datetime import datetime

from flask import Flask, jsonify, make_response, request

import city_loader


# =============================================================================
# Configuration
# =============================================================================

HTTP_PORT = 8080      # game API
TCP_PORT  = 9090      # "keepLiveServerPort" — actually HTTP under the same cipher
STAT_PORT = 8992      # analytics; ignored

# Host/IP advertised back to the client in server-list and keepalive responses.
# Must match whatever the client is configured to connect to. With the
# DNS-based setup (APK patched to `waker.local`), set this to the hostname or
# IP that resolves to this machine from the phone's perspective.
#
# Accepts SERVER_HOST (preferred) or legacy SERVER_IP.
SERVER_HOST = os.environ.get('SERVER_HOST') or os.environ.get('SERVER_IP', '127.0.0.1')

# Set ENCODE_RESPONSES=0 to disable the XOR+base64 wrapper on responses (for
# raw debugging from a desktop browser; the game itself will not accept it).
ENCODE_RESPONSES = os.environ.get('ENCODE_RESPONSES', '1') == '1'

PROTOCOL_DUMP = os.environ.get('PROTOCOL_DUMP', '1') == '1'
DUMP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'protocol_dump.log')
_dump_lock = threading.Lock()

# -----------------------------------------------------------------------------
# Asset-driven game data — the decoded .city catalog tables (see
# analyze/docs/ASSET_SCHEMA.md). Loaded once at import. Set CITY_ASSETS_DIR to a
# live `.city` assets folder to parse fresh; otherwise the committed gamedata/
# JSON snapshot is used. Endpoints below pull REAL ids/values from GAMEDATA
# instead of empty stubs.
# -----------------------------------------------------------------------------
GAMEDATA = city_loader.load_catalogs()

# Opt-in: serve real asset-sourced records from gameplay endpoints. Default OFF
# so the committed default stays byte-identical to the frozen-safe boot baseline.
# Populated responses are to be validated on real ARM hardware (not the emulator,
# where the layout/GC path is unreliable under Houdini).
SERVE_ASSET_DATA = os.environ.get('SERVE_ASSET_DATA', '0') == '1'


def _catalog(name):
    """Return a Catalog or None; never raises so endpoints degrade gracefully."""
    return GAMEDATA.get(name)


# =============================================================================
# Wire cipher
# Symmetric repeating-key XOR with the LOTR verse from libcity_ar.so .rodata,
# then base64. Recovered by cracking a captured request body against the
# known plaintext fields the client sends at boot.
# =============================================================================

XOR_KEY = (b"One ring to rule them all, one ring to find them, "
           b"one ring to bring them all and in the darkness bind them.")


def _xor_bytes(buf):
    k = XOR_KEY
    n = len(k)
    return bytes(buf[i] ^ k[i % n] for i in range(len(buf)))


def cipher_encode(plain):
    """Plaintext bytes -> base64( XOR(plain, KEY) ) (the wire form)."""
    return base64.b64encode(_xor_bytes(plain))


def cipher_decode(wire):
    """Wire base64( XOR(...) ) -> plaintext bytes."""
    return _xor_bytes(base64.b64decode(wire))


# =============================================================================
# Logging
# =============================================================================

def dump_log(entry):
    """Append a full protocol entry to protocol_dump.log (for offline analysis)."""
    if not PROTOCOL_DUMP:
        return
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    with _dump_lock, open(DUMP_FILE, 'a', encoding='utf-8') as f:
        f.write(f"\n{'=' * 80}\n[{ts}] {entry}\n")


request_history = deque(maxlen=200)


# =============================================================================
# Flask app + middleware
# The client always sends PUT (NGHttpSession.doPut). Flask routes are simpler
# when we normalize to POST before dispatch; we still log the ORIGINAL method.
# =============================================================================

class MethodNormalizerMiddleware:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        original = environ.get('REQUEST_METHOD', 'GET')
        environ['ORIGINAL_HTTP_METHOD'] = original
        if original in ('PUT', 'DELETE', 'PATCH'):
            environ['REQUEST_METHOD'] = 'POST'
        return self.wsgi_app(environ, start_response)


app = Flask(__name__)
app.wsgi_app = MethodNormalizerMiddleware(app.wsgi_app)


@app.before_request
def _log_request():
    original = request.environ.get('ORIGINAL_HTTP_METHOD', request.method)
    raw_body = ''
    if request.form:
        raw_body = '&'.join(f'{k}={v}' for k, v in request.form.items())
    elif request.is_json and request.json:
        raw_body = json.dumps(request.json)
    elif request.data:
        raw_body = request.data.decode('utf-8', errors='replace')
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    method_note = f' (orig:{original})' if original != request.method else ''
    print(f'[HTTP {ts}] {original} {request.path}{method_note}')
    if raw_body:
        print(f'  Body: {raw_body[:200]}')
    if request.args:
        print(f'  Query: {dict(request.args)}')
    headers = '\n'.join(f'    {k}: {v}' for k, v in request.headers)
    query = ('?' + '&'.join(f'{k}={v}' for k, v in request.args.items())
             if request.args else '')
    dump_log(f'REQUEST {original} {request.path}{query}\n'
             f'  Headers:\n{headers}\n  Body: {raw_body}')
    request_history.append({'time': ts, 'method': original,
                            'path': request.path, 'body': raw_body[:500]})


@app.after_request
def _log_and_encode_response(response):
    """Inject the four required root fields, then cipher-encode the body.

    See module docstring (WIRE PROTOCOL) for why these are mandatory. Routes
    can pre-set `error`/`errorMessage`/`data` in their JSON; only missing keys
    are filled. /debug paths and non-200 responses are exempt (developer aids).
    """
    original = request.environ.get('ORIGINAL_HTTP_METHOD', request.method)
    try:
        body_text = response.get_data(as_text=True)
    except Exception:
        body_text = '<binary>'
    dump_log(f'RESPONSE {response.status_code} for {original} {request.path}\n'
             f'  Content-Type: {response.content_type}\n  Body: {body_text}')

    if (ENCODE_RESPONSES and response.status_code == 200
            and not request.path.startswith('/debug')):
        try:
            body = response.get_data()
            if body:
                try:
                    obj = json.loads(body)
                    if isinstance(obj, dict):
                        changed = False
                        for k, default in (('error', '0'),
                                           ('timestamp', int(time.time())),
                                           ('errorMessage', ''),
                                           ('data', {})):
                            if k not in obj:
                                obj[k] = default
                                changed = True
                        if changed:
                            body = json.dumps(obj).encode('utf-8')
                except Exception:
                    # Non-JSON body — encode as-is. The client rejects it; we
                    # only see this when a route returns raw bytes deliberately.
                    pass
                response.set_data(cipher_encode(body))
        except Exception as e:
            print(f'  [cipher] encode skipped for {request.path}: {e}')
    return response


# =============================================================================
# Game-data builders — schemas recovered from libcity_ar.so static analysis.
# Field name/offset provenance is in analyze/docs/SCHEMAS.md.
# =============================================================================

def _server_entry():
    """One CServer (CServer::Parse @0x56de78).

    Fields read by name: ints idx/status/port/recommend/register/mergeServer/
    bucket/displayIdx/useHttps; strings name/url/comment/crossPlatCode.
    `url` and `keepLiveServer*` must point at SERVER_HOST — the address the
    client uses to reach this machine.
    """
    return {
        'idx': 1, 'status': 1, 'port': TCP_PORT, 'recommend': 1, 'register': 0,
        'mergeServer': 0, 'name': 'Waker', 'url': SERVER_HOST, 'comment': '',
        'bucket': 0, 'displayIdx': 1, 'useHttps': 0, 'crossPlatCode': 'android',
    }


def _login_success_payload():
    """Login envelope returned by /api/connect and /api/authplayerkey.
    `keepLiveServerHost`/`keepLiveServerPort` tell the client where to reach
    the 9090 channel (the same SERVER_HOST, served by this same Flask app).
    """
    pid = '1001'
    return {
        'playerId': pid, 'uid': pid, 'userId': pid, 'id': pid,
        'key': 'waker-key', 'sessionKey': 'waker-key', 'token': 'waker-key',
        'name': 'Player', 'serverId': 1,
        'keepLiveServerHost': SERVER_HOST, 'keepLiveServerPort': TCP_PORT,
    }


def _make_house(hid=1, estate_type=800, owner_id=1, owner_name='Player'):
    """One CHouse (CHouse::Parse @0x4498d8).

    `estateType` must be a valid property.city id (the loader's first BE32
    per record). 800 = CaoPeng, the first table entry — guaranteed to exist.
    GetById(estateType) inside CHouse::GetPrice null-derefs (fault 0x84) if
    the id isn't in the table.
    """
    return {
        'id': hid, 'estateType': estate_type, 'systemEstate': 0,
        'decoration1': 0, 'decoration2': 0, 'decoration3': 0,
        'maid1': 0, 'maid1ExpireAt': 0, 'maid2': 0, 'maid2ExpireAt': 0,
        'ownerId': owner_id, 'renterId': 0, 'renterName': '',
        'ownerName': owner_name, 'status': 1,
        'sellPrice': 1000, 'rentPrice': 100,
        'rentExpireAt': 0, 'rentDays': 0, 'maintainExpireAt': 0,
        'customHouseAt': 0, 'customHouseTag': '',
    }


def _make_fighter(fid=2001, name='Rival', level=18):
    """One CCitier (CCitier::Parse @0x34df98).

    A "random fighter" is a full other-player record (1384 bytes, same parser
    as getplayerlist roles via thunk 0x693ecc). `liveEstateObj` = the
    fighter's house, which the city map uses for placement.

    /city/fight/randomfighters returning [] leaves the active mission's
    fight target absent → ngGameMapSpriteLayer::HandleRender null-derefs on
    a null sprite. We serve a valid pair so that path can render when a
    mission is active (the rest of the mission chain is still unimplemented;
    see STATUS.md "active missions crash").
    """
    now = int(time.time())
    return {
        'id': fid, 'uid': fid, 'playerType': 0, 'name': name, 'level': level,
        'blood': 100, 'bloodUp': 100, 'status': 0, 'statusAt': 0,
        'statusDuration': 0, 'statusExtra': 0, 'statusExtraDesc': '',
        'rankPos': 0, 'rankScore': 0, 'cityId': 1, 'avatarAt': 0,
        'online': 1, 'vip': 0, 'gangFlag': 0, 'gangId': 0, 'title': 0,
        'prestige': 0, 'contribution': 0, 'gangMemberRelationId': 0,
        'relation': 0, 'lastOnlineAt': now, 'playerRole': 1, 'wantedId': 0,
        'wantedOwnerId': 0, 'rewardMoney': 0, 'content': '', 'gender': 1,
        'maritalStatus': 0, 'merits': 0, 'createdAt': now - 86400 * 60,
        'bailCostMoney': 0, 'signature': '', 'battlePrestige': 0,
        'guardRelation': 0, 'popular': 0, 'noChat': 0, 'disable': 0,
        'serverIdx': 1, 'locale': 'en', 'remark': '',
        'liveEstateObj': _make_house(hid=9001, owner_id=fid, owner_name=name),
    }


def _make_player():
    """The self-player object (CPlayer::Parse @0x5140bc, 168 fields).

    Returned by /city/connect/connect — drives the HUD and world state.

    Choices that matter:
      * newPlayer:0   — skips the new-player guided tour (job→gym→market,
                       which crashes the market and estate tutorial screens).
      * missionId:100 — past mission.city's 29 entries ("no active mission").
                       A real id activates the mission chain (getmsg +
                       randomfighters + randomgangs) which is only partly
                       built and crashes the city-map sprite render.
      * avatarAt>0    — avatar "already set" — suppresses the on-boot
                       photo-picker dialog overlay.
      * Resource bars: the *Up field IS the max (verified on-device:
                       current=80, energyUp=100 renders as "80/100").
      * playerStatus  — MUST be an object (CPlayer::ParseStatus @0x516254
                       reads sub-fields; a scalar crashes ParseStatus+0x40).
      * goods / bags / estates — must be ARRAYS when present. Other complex
                       sub-objects are omitted entirely so CPlayer::Parse
                       falls through their accessors with no type mismatch.
    """
    now = int(time.time())
    # CLASS B CRASH INVESTIGATION (2026-06-11): Full 65-field response causes
    # deterministic SEGV_ACCERR at 0x756f707b (Dalvik GC guard) in
    # ngHashMap→ngLinkedList during JSON tree cleanup. Testing minimal set
    # to bisect the trigger. Original full set preserved below in comment.
    return {
        'id': 1, 'uid': 1, 'name': 'Abu Hassan', 'level': 20, 'exp': 0,
        'gender': 1, 'playerRole': 1, 'avatarAt': now - 86400,
        'signature': '',
        'createdAt': now - 86400 * 30, 'playerKey': 'waker-key',
        'newPlayer': 0, 'missionId': 1, 'missionProgress': 0,
        'loginGift': 0, 'loginContinuousDays': 1,
        'gold': 100000, 'money': 5000000, 'cheque': 5000,
        'energy': 100, 'energyUp': 100, 'energyAt': now,
        'blood': 100, 'bloodUp': 100,
        'happy': 100, 'happyUp': 100,
        'brave': 100, 'braveUp': 100,
        'moral': 100, 'moralUp': 100, 'moralAt': now,
        'playerStatus': {'cityId': 1, 'status': 0, 'statusAt': 0,
                         'statusDuration': 0, 'statusExtra': 0,
                         'statusExtraDesc': '', 'noFightedExpireAt': 0},
        'goods': [], 'bags': [], 'estates': [],
    }
    # ORIGINAL FULL SET (pre-bisect):
    # 'maritalStatus': 0, 'spouseName': '',
    # 'firstPayed': 0, 'firstPayGifted': 0,
    # 'merits': 1000, 'totalMerits': 1000,
    # 'vip': 0, 'vipExpireAt': 0, 'payed': 0, 'payLevel': 0,
    # 'strength': 50, 'endurance': 50, 'speed': 50, 'agile': 50,
    # 'basicStrength': 50, 'basicEndurance': 50,
    # 'basicSpeed': 50, 'basicAgile': 50,
    # 'defense': 20, 'hornNum': 5, 'bigHornNum': 2,
    # 'boughtRecoverEnergy': 0, 'storedEnergy': 0, 'maxPlayerEnergy': 100,
    # 'warehouseSize': 50, 'bagMaxSize': 50, 'dealMaxSize': 20,
    # 'friendNum': 0,
    # 'fightTimes': 0, 'jailTimes': 0, 'hospitalTimes': 0,
    # 'crimeTimes': 0, 'thriceNum': 0, 'crimeSuccess': 0,


# =============================================================================
# Routes — VERSION CHECK (port 8080)
# CHttpClient::CheckVersion / CLoadingScreen::DoCheckVersion → opcode 0x80.
# CLoadingScreen::OnReceiveResponse reads every field in `data` below; their
# offsets and consumers were resolved from .rodata 0x700d74..0x700e6c.
# Critically: `lastLoginPlayer` is parsed as an OBJECT
# (CLoadingScreen::ParseLastLoginPlayerInfo @0x490418 — node+4 → hash,
# GetNode); a string crashes it. And a `servers:[…]` entry must be present
# so CServerMnger isn't empty when DoGetServerInfo runs.
# =============================================================================

@app.route('/checkversion', methods=['GET', 'POST', 'PUT'])
def checkversion():
    payload = {
        'result': 0, 'code': 200, 'status': 'ok', 'errorMsg': '',
        'data': {
            'version':          '1.1.38',
            'majorVersion':     '1',
            'reviewVersion':    '1.1.38',
            'minorVersion':     '1.1.38',
            'isReview':         False,
            'inReview':         False,
            'time':             int(time.time()),
            # All upgrade fields explicit: vtable[16] returns 0 on absence
            # and leaves the fallback global path uninitialized.
            'majorUpgrade':     False,
            'majorUpgradeUrl':  '',
            'majorUpgradeText': '',
            'minorUpgrade':     False,
            'isForceUpgrade':   False,   # parsed value is written to
                                         # CLoadingScreen+0x2AC — the state
                                         # byte gating CheckUpdate at va 0x48f910.
            'loadingDoAllStep': 0,
            'loadingForceDeaf': False,
            'loadingTimeOut':   60,
            'contentUrlPrefix': '',
            'upgradeVersionFile': '',
            'enableCP':         False,
            'serverCtrlDebugSwitch': 0,
            'encryptMethod':    0,
            'lastLoginPlayer':  {'type': 0, 'name': '', 'password': ''},
            'preServerIdx':     0,
            'servers':          [_server_entry()],
        },
    }
    resp = make_response(json.dumps(payload).encode('utf-8'), 200)
    resp.headers['Content-Type'] = 'application/json'
    return resp


# =============================================================================
# Routes — LOGIN (port 8080)
# =============================================================================

@app.route('/api/connect', methods=['GET', 'POST', 'PUT'])
def api_connect():
    """CHttpClient::PlayerLogin @0x44e9b8 (opcode 0x78, command "connect").
    On success → CLoadingScreen::OnLoginSuccess(playerId, key)."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _login_success_payload()})


@app.route('/api/authplayerkey', methods=['GET', 'POST', 'PUT'])
def api_authplayerkey():
    """Cached-key resume login (relaunch without re-entering credentials).
    Without a valid session here, the client loops at the title. Mirrors
    /api/connect's success payload so the resume path proceeds the same."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _login_success_payload()})


@app.route('/api/getallserver', methods=['GET', 'POST', 'PUT'])
def api_getallserver():
    """CHttpClient::GetAllServer @0x453044 (opcode 0xe4).

    `data` MUST be the server ARRAY directly. CServerMnger::ParseServerList
    @0x56eb4c uses the same `[data+4].begin()` pattern as ParseChilds, iterates
    elements, and hashes by name/url. An object wrapper makes the parser
    create a null-named server → ContainsKey(null) → strlen(NULL) crash.
    """
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': [_server_entry()],
                    'preServerIdx': 0, 'suggestServer': 0})


# =============================================================================
# Routes — CITY (the same Flask app also serves these on port 9090).
# 9090 is the "keepLiveServer" port but it's plain HTTP under the same
# XOR+base64 cipher; the binary/RC4 keepalive channel is unimplemented (the
# resume-path "step 10" stall).
# =============================================================================

@app.route('/city/impart', methods=['GET', 'POST', 'PUT'])
def city_impart():
    """CImpart — game-config fetch at LoadingMnger step 10.

    The full 201-key config schema is documented in SCHEMAS.md. We serve
    `data:{}` because the boot path's lookups all fall through to the
    bundled `.city` assets the client ships with; populating impart matters
    for feature screens (see STATUS.md "Suggested next steps").
    """
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': {}})


@app.route('/city/connect/getplayerlist', methods=['GET', 'POST', 'PUT'])
def city_getplayerlist():
    """CServerMnger::ParseRoleList @0x56f19a iterates `data` as an ARRAY of
    role objects (1384B each, allocator @0x693ecc → CCitier::Parse).
    Empty [] = "no character on this server" → character-creation path."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/connect/connect', methods=['GET', 'POST', 'PUT'])
def city_connect_connect():
    """Full CPlayer object — drives the HUD."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


@app.route('/city/connect/create', methods=['GET', 'POST', 'PUT'])
def city_connect_create():
    """Create-role: same CPlayer shape as connect/connect."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


# ----- city DATA endpoints --------------------------------------------------
# Each must return the right CONTAINER TYPE; mismatched containers null-deref
# the parser. The exact-type notes are inline.

@app.route('/city/player/introplayers', methods=['GET', 'POST', 'PUT'])
def city_introplayers():
    """CFeedbackScreen::ParseChilds @0x3ea612 iterates `data` as an array
    (begin-iter vtbl+0x14). An object/{} makes begin() return null →
    ldr [r5] null-deref. Empty [] = valid end-iterator."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/goods/getcitygoods', methods=['GET', 'POST', 'PUT'])
def city_getcitygoods():
    """CMarketCateScreen::ParseGoodsAmount @0x4c2fe8 reads data.goodsList
    (array of {category, type, amount}). The catch-all `data:{}` shape
    leaves the goods model null → SetValue null-deref on the cate table.

    ASSET-BACKED: with SERVE_ASSET_DATA=1, `type` is a real product.city id
    (194 goods, ids 600+). Default OFF keeps the verified-safe empty baseline;
    the populated path is to be validated on ARM hardware, not the emulator
    (see ASSET_ENDPOINT_MAPPING.md)."""
    goods_list = []
    if SERVE_ASSET_DATA:
        prod = _catalog('product')
        if prod:
            # category 0 = single shop tab (category→tab mapping unverified);
            # type = product id (the GetById key); amount = nominal stock.
            goods_list = [{'category': 0, 'type': pid, 'amount': 99}
                          for pid in prod.ids()]
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {'goodsList': goods_list}})


@app.route('/city/estate/listestates', methods=['GET', 'POST', 'PUT'])
def city_listestates():
    """Array of CHouse — the player's owned estates.
    NOTE: returning the full 20-field _make_house() causes a heap corruption
    crash in ngHashMap→ngLinkedList during JSON tree cleanup (fault addr
    0x756f707b in Dalvik GC guard memory). Empty array avoids the crash;
    re-enable with minimal fields once the safe set is identified."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': []})


@app.route('/city/estate/buy', methods=['GET', 'POST', 'PUT'])
def city_estate_buy():
    """Buy = one CHouse (cmd 0x13b). CPropertyListCateScreen builds one
    CHouse from `data` and calls CHouse::GetPrice → needs a valid estateType."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_house()})


@app.route('/city/fight/randomfighters', methods=['GET', 'POST', 'PUT'])
def city_randomfighters():
    """Array of CCitier — fight targets. See _make_fighter() docstring for
    why this matters (and why it's only half the active-mission fix)."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': [_make_fighter(2001, 'Rival', 18),
                             _make_fighter(2002, 'Thug', 17)]})


# ----- city CHAT ------------------------------------------------------------

@app.route('/city/chat/gettopmsgs', methods=['GET', 'POST', 'PUT'])
def city_gettopmsgs():
    """CTopScreen rolling-text ticker. ParseMsg @0x592fb4 iterates `data`
    as an array of {senderName, content, createdAt, id}; OnRollingOneTime
    @0x593374 displays one at a time then RequestMsg re-polls when empty.
    Empty [] → instant exhaustion → busy-loop → ANR.

    A parallel .so patch (file_off 0x59190d  DC→E0) turns the poll-gate's
    `bgt` into an unconditional `b`, killing the per-frame request flood
    even when this endpoint is reachable. Both fixes ship.
    """
    now = int(time.time())
    # Arabic-locale system ticker: a small in-character roster so the marquee
    # has texture, not just placeholders. CTopScreen renders these one at a
    # time and re-polls when empty.
    msgs = [
        {'senderName': 'النظام', 'content': 'مرحباً بك في الوكر — جولة سعيدة',
         'createdAt': now,        'id': 1},
        {'senderName': 'النظام', 'content': 'الخادم متصل — الإصدار 1.1.38',
         'createdAt': now - 10,   'id': 2},
        {'senderName': 'الزعيم', 'content': 'حافظ على هدوئك في الشارع',
         'createdAt': now - 60,   'id': 3},
        {'senderName': 'النظام', 'content': 'فعاليات اليوم متاحة الآن',
         'createdAt': now - 300,  'id': 4},
        {'senderName': 'الزعيم', 'content': 'العدو يتربص — كن جاهزاً',
         'createdAt': now - 900,  'id': 5},
    ]
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': msgs})


@app.route('/city/chat/getmsg', methods=['GET', 'POST', 'PUT'])
def city_getmsg():
    """Active mission dialogue and global chat.
    CChatScreen::ParseMsg expects a root object containing a 'msgs' array.
    The previous catch-all returned a flat array [], causing a native crash.
    """
    msg_obj = {
        'roomId': 0,
        'worldFlag': 0,
        'specialFlag': 0,
        'msgType': 1,             # Standard message type
        'senderName': 'الزعيم',   # "The Boss" (Arabic locale)
        'senderId': 2001,
        'playerRole': 1,
        'serverIdx': 1,
        'showType': 1,
        'jsonContent': 'Mission initialized. Watch your back out there.', 
        'packetId': 1,
        'note': '',
        'packetType': 1
    }
    
    return jsonify({
        'result': 0, 
        'code': 200, 
        'errorMsg': '', 
        'data': {
            'msgs': [msg_obj]
        }
    })


@app.route('/city/chat/<path:cmd>', methods=['GET', 'POST', 'PUT'])
def city_chat_other(cmd):
    """Other chat endpoints — message LISTS. ParseSysMsg @0x59318c iterates
    response `data` as an array; empty [] = no messages, no crash."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


# ----- GANG ----------------------------------------------------------------

@app.route('/city/gang/randomgangs', methods=['GET', 'POST', 'PUT'])
def city_randomgangs():
    """Array of gang objects for the mission fight-target picker.
    The parser iterates `data` as an array (same pattern as randomfighters);
    `data:{}` from the catch-all causes a null-deref in the array iterator."""
    now = int(time.time())
    gang = {
        'id': 1, 'name': 'عصابة الشارع', 'level': 5,
        'leaderId': 2001, 'leaderName': 'Rival',
        'memberCount': 10, 'maxMember': 50,
        'prestige': 500, 'money': 100000,
        'notice': '', 'createdAt': now - 86400 * 90,
        'flag': 1, 'status': 0,
    }
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': [gang]})


# ----- MISSION -------------------------------------------------------------

@app.route('/city/mission/updatemission', methods=['GET', 'POST', 'PUT'])
def city_updatemission():
    """Mission progress update — returns the updated CPlayer."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


@app.route('/city/mission/getmission', methods=['GET', 'POST', 'PUT'])
def city_getmission():
    """Mission info fetch — returns mission state as object."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {'missionId': 1, 'missionProgress': 0,
                             'missionStatus': 0}})


# ----- PLAYER ---------------------------------------------------------------

@app.route('/city/player/updatelevel', methods=['GET', 'POST', 'PUT'])
def city_updatelevel():
    """Level-up response — returns full CPlayer."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


@app.route('/city/player/pause', methods=['GET', 'POST', 'PUT'])
def city_player_pause():
    """Player pause/resume notification — ack with empty object."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': {}})


# ----- HEARTBEAT / MAINTENANCE ----------------------------------------------

@app.route('/city/heartbeat', methods=['GET', 'POST', 'PUT'])
def city_heartbeat():
    """Periodic keepalive from the client."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {'time': int(time.time())}})


@app.route('/game/maintenance/check', methods=['GET', 'POST', 'PUT'])
def game_maintenance_check():
    """Maintenance-mode check — always return not-in-maintenance."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {'maintenance': False, 'msg': ''}})


# ----- JOB / GYM / CRIME (mission-1 = "find a job") -------------------------

@app.route('/city/job/getjobs', methods=['GET', 'POST', 'PUT'])
def city_getjobs():
    """Job listings — array of job objects. Mission 1 sends the player to
    the job screen; the parser iterates data as an array."""
    jobs = [
        {'id': 1, 'jobType': 1, 'name': 'عامل نظافة', 'level': 1,
         'salary': 500, 'exp': 10, 'energy': 5, 'duration': 60,
         'status': 0, 'playerId': 0},
        {'id': 2, 'jobType': 2, 'name': 'حارس', 'level': 5,
         'salary': 1000, 'exp': 20, 'energy': 8, 'duration': 120,
         'status': 0, 'playerId': 0},
    ]
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': jobs})


@app.route('/city/job/work', methods=['GET', 'POST', 'PUT'])
def city_job_work():
    """Start working — returns updated CPlayer."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


@app.route('/city/gym/getgym', methods=['GET', 'POST', 'PUT'])
def city_getgym():
    """Gym info — object with gym state."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {'gymTypes': [], 'gymServiceDetails': []}})


@app.route('/city/gym/train', methods=['GET', 'POST', 'PUT'])
def city_gym_train():
    """Gym training — returns updated CPlayer."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


@app.route('/city/crime/docrime', methods=['GET', 'POST', 'PUT'])
def city_docrime():
    """Crime action — returns updated CPlayer."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


@app.route('/city/player/getplayerinfo', methods=['GET', 'POST', 'PUT'])
def city_getplayerinfo():
    """Full player info fetch — same CPlayer shape."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': _make_player()})


@app.route('/city/friend/getfriends', methods=['GET', 'POST', 'PUT'])
def city_getfriends():
    """Friends list — array."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/player/getranking', methods=['GET', 'POST', 'PUT'])
def city_getranking():
    """Ranking list — array."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


# ----- GOODS / INVENTORY (mission chain may open market) --------------------

@app.route('/city/goods/playerbags', methods=['GET', 'POST', 'PUT'])
def city_playerbags():
    """Player inventory bags — array."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {'bags': [], 'goods': []}})


@app.route('/city/goods/playergoods', methods=['GET', 'POST', 'PUT'])
def city_playergoods():
    """Player goods — object with goods array."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {'goods': []}})


# ----- ARRAY-EXPECTING STUBS (binary-verified: crash with data:{}) ---------

@app.route('/city/airline/airlines', methods=['GET', 'POST', 'PUT'])
def city_airline_airlines():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/chat/getsysmsgs', methods=['GET', 'POST', 'PUT'])
def city_chat_getsysmsgs():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/race/car/getcars', methods=['GET', 'POST', 'PUT'])
def race_car_getcars():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/race/car/getstoreitems', methods=['GET', 'POST', 'PUT'])
def race_car_getstoreitems():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/hospital/patients', methods=['GET', 'POST', 'PUT'])
def city_hospital_patients():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/gang/randomgangs', methods=['GET', 'POST', 'PUT'])
def city_gang_randomgangs():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/jail/prisonerlist', methods=['GET', 'POST', 'PUT'])
def city_jail_prisonerlist():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/event/list', methods=['GET', 'POST', 'PUT'])
def city_event_list():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/player/logingifts', methods=['GET', 'POST', 'PUT'])
def city_player_logingifts():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/marital/candidates', methods=['GET', 'POST', 'PUT'])
def city_marital_candidates():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


# Phase 1: all remaining CRITICAL array-iterator routes (OnReceiveResponse
# itself calls vtbl+0x14 begin() — crashes with data:{}, safe with data:[])

@app.route('/city/store/catelist', methods=['GET', 'POST', 'PUT'])
def city_store_catelist():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/showwindow/list', methods=['GET', 'POST', 'PUT'])
def city_showwindow_list():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/skyscraper/list', methods=['GET', 'POST', 'PUT'])
def city_skyscraper_list():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/lottery/info', methods=['GET', 'POST', 'PUT'])
def city_lottery_info():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/lottery/prizes', methods=['GET', 'POST', 'PUT'])
def city_lottery_prizes():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/lottery/records', methods=['GET', 'POST', 'PUT'])
def city_lottery_records():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/mercenary/helpandbattle', methods=['GET', 'POST', 'PUT'])
def city_mercenary_helpandbattle():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/mercenary/rank', methods=['GET', 'POST', 'PUT'])
def city_mercenary_rank():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/mercenary/ybclass', methods=['GET', 'POST', 'PUT'])
def city_mercenary_ybclass():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/hunt/store/list', methods=['GET', 'POST', 'PUT'])
def city_hunt_store_list():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/crossserverwar/joinlist', methods=['GET', 'POST', 'PUT'])
def city_crossserverwar_joinlist():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/race/match/maplist', methods=['GET', 'POST', 'PUT'])
def race_match_maplist():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/race/match/dungeon/info', methods=['GET', 'POST', 'PUT'])
def race_match_dungeon_info():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/race/match/record', methods=['GET', 'POST', 'PUT'])
def race_match_record():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/race/match/recorddesc', methods=['GET', 'POST', 'PUT'])
def race_match_recorddesc():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


@app.route('/city/deal/taobao', methods=['GET', 'POST', 'PUT'])
def city_deal_taobao():
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': []})


# ----- catch-alls -----------------------------------------------------------

@app.route('/city/<path:cmd>', methods=['GET', 'POST', 'PUT'])
def city_other(cmd):
    """Unrecognized /city/* — empty-object response. Accepted by every parser
    that just calls into per-screen data builders (those screens render
    "nothing", they don't crash on `data:{}`)."""
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '', 'data': {}})


# ----- debug endpoints (NOT cipher-encoded) ---------------------------------

@app.route('/debug/history', methods=['GET'])
def debug_history():
    """Last ~200 requests, JSON, in plain text — useful from a desktop browser."""
    return jsonify({'requests': list(request_history),
                    'total': len(request_history)})


@app.route('/debug/probe', methods=['GET'])
def debug_probe():
    """Compat stub for RUN_SERVER.md's "pin probe variant 6" step.

    The /checkversion response used to have 15 diagnostic variants; only
    variant 6 is the known-good response and it is now the single canonical
    handler. This endpoint is preserved so the documented curl still returns
    the expected JSON. It's a no-op.
    """
    return jsonify({'next_variant': 6})


@app.route('/debug/gamedata', methods=['GET'])
def debug_gamedata():
    """Read-only view of the loaded asset catalogs (real .city data). Plaintext,
    not ciphered — inspect from a desktop browser. `?table=job` for one table's
    full records; no arg = summary of all 93."""
    t = request.args.get('table')
    if t and t in GAMEDATA:
        c = GAMEDATA[t]
        return jsonify({'table': t, 'count': c.count, 'schema': c.schema,
                        'fields': c.fields, 'status': c.status,
                        'records': c.records})
    return jsonify({'serve_asset_data': SERVE_ASSET_DATA,
                    'tables': [{'name': c.name, 'count': c.count,
                                'status': c.status}
                               for c in sorted(GAMEDATA.values(),
                                               key=lambda x: x.name)]})


@app.route('/', defaults={'path': ''},
           methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def root_catch_all(path):
    """Anything otherwise unhandled — accepted with empty object."""
    print(f'[API] UNHANDLED: {request.method} /{path}')
    return jsonify({'result': 0, 'code': 200, 'errorMsg': '',
                    'data': {}, 'status': 'ok'})


# =============================================================================
# Analytics / stat server (port 8992) — accepted and ignored.
# =============================================================================

stat_app = Flask('stat_server')


@stat_app.route('/', defaults={'path': ''},
                methods=['GET', 'POST', 'PUT', 'DELETE'])
@stat_app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def _stat_catch_all(path):
    print(f'[STAT] {request.method} /{path} (ignored)')
    return jsonify({'result': 0})


def _run_stat_server():
    stat_app.run(host='0.0.0.0', port=STAT_PORT,
                 debug=False, use_reloader=False)


# =============================================================================
# Entry point
# 9090 ("keepLiveServer") runs the SAME Flask app in a background thread so
# /city/* + the cipher wrapper apply identically. 8080 runs in the main thread.
# =============================================================================

if __name__ == '__main__':
    print('=' * 44)
    print('  Waker Local Server - وكر الاوغاد')
    print('=' * 44)

    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=TCP_PORT,
                               debug=False, use_reloader=False,
                               threaded=True),
        daemon=True,
    ).start()

    threading.Thread(target=_run_stat_server, daemon=True).start()

    print(f'[HTTP] Game API server running on port {HTTP_PORT}')
    print(f'       URL: http://{SERVER_HOST}:{HTTP_PORT}/')
    print(f'[CITY] keepLiveServer (HTTP) on port {TCP_PORT}')
    print(f'[STAT] Analytics server running on port {STAT_PORT}')
    print('=' * 44)
    print('Ready! Configure your device to point to this server.')

    app.run(host='0.0.0.0', port=HTTP_PORT,
            debug=False, use_reloader=False)
