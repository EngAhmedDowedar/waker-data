"""
Waker (وكر الاوغاد) - Local Server Emulator (Python Flask)

Emulates the game's HTTP API server (port 8080) and TCP keepalive server.
Allows the game client to boot and function with a private local backend.

Based on reverse engineering of libcity_ar.so and smali analysis.

Usage:
    pip install -r requirements.txt
    python server.py
"""

import os
import json
import time
import random
import string
import socket
import threading
import io
from collections import deque
from datetime import datetime
from flask import Flask, request, jsonify, redirect

# =============================================================================
# CONFIGURATION
# =============================================================================

HTTP_PORT = 8080
TCP_PORT = 9090      # keepLiveServerPort
STAT_PORT = 8992     # Analytics stat server

# Public IP/LAN IP that clients use to connect.
# Set via environment variable or defaults to 127.0.0.1.
# For LAN play: set SERVER_IP=192.168.x.x before starting.
SERVER_IP = os.environ.get('SERVER_IP', '127.0.0.1')

# Protocol dump log: full request/response bodies written to file for analysis
PROTOCOL_DUMP = os.environ.get('PROTOCOL_DUMP', '1') == '1'
DUMP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'protocol_dump.log')
_dump_lock = threading.Lock()

# ---------------------------------------------------------------------------
# CLIENT CIPHER (recovered 2026-05-28 via known-plaintext on the captured
# /checkversion request). Wire body = base64( XOR(json_utf8, XOR_KEY) ).
# XOR_KEY is the 107-byte repeating-XOR key embedded in libcity_ar.so .rodata
# (the full LOTR verse incl. trailing period). XOR is symmetric, so the same
# routine decodes requests and encodes responses.
# ---------------------------------------------------------------------------
import base64 as _b64
XOR_KEY = (b"One ring to rule them all, one ring to find them, "
           b"one ring to bring them all and in the darkness bind them.")
ENCODE_RESPONSES = os.environ.get('ENCODE_RESPONSES', '1') == '1'

def _xor_bytes(data):
    k = XOR_KEY; n = len(k)
    return bytes(data[i] ^ k[i % n] for i in range(len(data)))

def cipher_encode(plain_bytes):
    """plaintext -> base64(XOR(plain, KEY)) ASCII bytes (wire form)."""
    return _b64.b64encode(_xor_bytes(plain_bytes))

def cipher_decode(wire_bytes):
    """wire base64(XOR(...)) -> plaintext bytes."""
    return _xor_bytes(_b64.b64decode(wire_bytes))


def dump_log(entry):
    """Append a full protocol entry to the dump file."""
    if not PROTOCOL_DUMP:
        return
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    with _dump_lock:
        with open(DUMP_FILE, 'a', encoding='utf-8') as f:
            f.write(f"\n{'='*80}\n[{ts}] {entry}\n")

# =============================================================================
# REQUEST HISTORY (for debugging)
# =============================================================================
request_history = deque(maxlen=200)


# =============================================================================
# WSGI MIDDLEWARE: Normalize HTTP methods
# =============================================================================
# The game client sends PUT for all API calls via NGHttpSession.doPut().
# Flask routes only declare GET/POST, so PUT returns 405 Method Not Allowed.
# This middleware converts PUT/DELETE/PATCH → POST before Flask routing.

class MethodNormalizerMiddleware:
    """Convert non-standard HTTP methods to POST so all Flask routes match."""
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app
    def __call__(self, environ, start_response):
        original = environ.get('REQUEST_METHOD', 'GET')
        environ['ORIGINAL_HTTP_METHOD'] = original
        if original in ('PUT', 'DELETE', 'PATCH'):
            environ['REQUEST_METHOD'] = 'POST'
        return self.wsgi_app(environ, start_response)

# =============================================================================
# GAME STATE
# =============================================================================

next_player_id = 100001
players = {}
sessions = {}


def generate_token():
    chars = string.ascii_lowercase + string.digits
    return 'tok_' + ''.join(random.choices(chars, k=24)) + hex(int(time.time()))[2:]


def generate_session_id():
    chars = string.ascii_lowercase + string.digits
    return 'sess_' + ''.join(random.choices(chars, k=16))


def create_default_player(player_id, name=None):
    return {
        "playerId": player_id,
        "userId": player_id,
        "name": name or f"Player_{player_id}",
        "level": 1,
        "exp": 0,
        "vipLevel": 0,
        "gold": 100000,
        "cash": 5000,
        "diamond": 1000,
        "energy": 100,
        "maxEnergy": 100,
        "nerve": 50,
        "maxNerve": 50,
        "blood": 100,
        "maxBlood": 100,
        "strength": 10,
        "defense": 10,
        "speed": 10,
        "agile": 10,
        "gender": 1,
        "cityId": 1,
        "jobId": 1,
        "factionId": 0,
        "factionName": "",
        "avatar": "default_avatar",
        "signature": "",
        "loginContinuousDays": 1,
        "createTime": int(time.time() * 1000),
        "lastLoginTime": int(time.time() * 1000),
        "statusAt": 0,
        "statusDuration": 0,
        "statusExpiredAt": 0,
        "hostId": 1,
        "hostName": "Local Server",
        "merits": 0,
        "fansNum": 0,
        "marked": 0,
        "emotion": 0,
        "isVip": False,
        "weapon": 0,
        "armor": 0,
        "mount": 0,
        "buildings": [],
        "goods": [],
        "friends": [],
        "missions": [],
        "skills": [],
    }


# =============================================================================
# HELPERS
# =============================================================================

def get_param(key, default=None):
    """Get parameter from form data, JSON body, or query string."""
    val = request.form.get(key)
    if val is not None:
        return val
    if request.is_json:
        val = request.json.get(key)
        if val is not None:
            return val
    val = request.args.get(key)
    return val if val is not None else default


def get_player_id():
    pid = get_param('playerId')
    if pid:
        return int(pid)
    return 100001


def success_response(data=None):
    return jsonify({
        "result": 0,
        "code": 200,
        "data": data or {},
        "errorMsg": "",
        "status": "ok"
    })


def error_response(code, msg):
    return jsonify({
        "result": code,
        "code": code,
        "data": {},
        "errorMsg": msg,
        "status": "error"
    })


# =============================================================================
# HTTP API SERVER (Port 8080) - Main Game Server
# =============================================================================

app = Flask(__name__)
app.wsgi_app = MethodNormalizerMiddleware(app.wsgi_app)


@app.before_request
def log_request():
    original_method = request.environ.get('ORIGINAL_HTTP_METHOD', request.method)
    # Capture full body (no truncation for dump)
    raw_body = ""
    if request.form:
        raw_body = "&".join(f"{k}={v}" for k, v in request.form.items())
    elif request.is_json and request.json:
        raw_body = json.dumps(request.json)
    elif request.data:
        raw_body = request.data.decode('utf-8', errors='replace')
    ts = datetime.now().strftime('%H:%M:%S.%f')[:-3]
    method_note = f" (orig:{original_method})" if original_method != request.method else ""
    print(f"[HTTP {ts}] {original_method} {request.path}{method_note}")
    if raw_body:
        print(f"  Body: {raw_body[:200]}")
    if request.args:
        print(f"  Query: {dict(request.args)}")
    # Full protocol dump
    headers_str = "\n".join(f"    {k}: {v}" for k, v in request.headers)
    query_str = f"?{'&'.join(f'{k}={v}' for k,v in request.args.items())}" if request.args else ""
    dump_log(
        f"REQUEST {original_method} {request.path}{query_str}\n"
        f"  Headers:\n{headers_str}\n"
        f"  Body: {raw_body}"
    )
    # Store body for response logging
    request.environ['_DUMP_BODY'] = raw_body
    # Track for debug endpoint
    request_history.append({
        "time": ts,
        "method": original_method,
        "path": request.path,
        "body": raw_body[:500],
        "query": dict(request.args) if request.args else {},
        "headers": {k: v for k, v in list(request.headers)[:10]}
    })


@app.after_request
def log_response(response):
    original_method = request.environ.get('ORIGINAL_HTTP_METHOD', request.method)
    if response.status_code != 200:
        print(f"  ⚠ Response: {response.status_code} for {original_method} {request.path}")
    # Dump full response body
    resp_body = ""
    try:
        resp_body = response.get_data(as_text=True)
    except Exception:
        resp_body = "<binary>"
    dump_log(
        f"RESPONSE {response.status_code} for {original_method} {request.path}\n"
        f"  Content-Type: {response.content_type}\n"
        f"  Body: {resp_body}"
    )
    # Encode the response with the client's cipher so the game's response
    # decoder accepts it (base64(XOR(body,KEY))). Plaintext was already dumped
    # above. Skip /debug endpoints and empty/non-200 bodies.
    if (ENCODE_RESPONSES and not request.path.startswith('/debug')
            and response.status_code == 200):
        try:
            body = response.get_data()
            if body:
                # ngHttpClient::HandleUpdate (0x5cfac8) reads a root-level int
                # "timestamp" via ngInteger::IntValue() with NO null check, so
                # every response MUST carry it or the GL thread null-derefs
                # (null+0x10) ~instantly. Inject it at the root if absent.
                try:
                    import json as _json, time as _tm
                    obj = _json.loads(body)
                    if isinstance(obj, dict):
                        # ngHttpClient::HandleUpdate reads these ROOT fields with
                        # NO null check (crashes otherwise): timestamp (int,
                        # ngInteger::IntValue), errorMessage (str,
                        # ngStringV2::GetCString), data (object). "error" is
                        # null-checked (absent => no-error path => proceed).
                        changed = False
                        # "error" is a STRING compared to "0" (.rodata 0x6f780f);
                        # "0" == success path. Absent => null => GetCString crash.
                        if 'error' not in obj:
                            obj['error'] = "0"; changed = True
                        if 'timestamp' not in obj:
                            obj['timestamp'] = int(_tm.time()); changed = True
                        if 'errorMessage' not in obj:
                            obj['errorMessage'] = ""; changed = True
                        if 'data' not in obj:
                            obj['data'] = {}; changed = True
                        if changed:
                            body = _json.dumps(obj).encode('utf-8')
                except Exception:
                    pass
                response.set_data(cipher_encode(body))
                dump_log(f"  [cipher] response re-encoded base64(XOR), {len(body)}->{len(response.get_data())} bytes")
        except Exception as _e:
            print(f"  [cipher] encode skipped for {request.path}: {_e}")
    return response


# ---- DEBUG: Request history viewer ----
@app.route('/debug/history', methods=['GET', 'POST'])
def debug_history():
    return jsonify({"requests": list(request_history), "total": len(request_history)})


# ---- DEBUG: pin the /checkversion probe variant for the next boot
# 0=plain JSON (apk versionName "1.1.38"), 1=echo form-urlencoded,
# 2=echo octet+checksum, 3=echo no-content-type, 4=V4 URL source probe,
# 5=VERSION_MATCH_BUILD (engine build version "39.0" hypothesis test),
# 6=FULL_SCHEMA_FROM_BINARY (every field the opcode-0x80 handler actually
#   reads: time / majorUpgrade* / minorUpgrade / isForceUpgrade / loading*),
# 7=V6_WITH_MAJORUPGRADEURL_PLACEHOLDER (identical to v6 except
#   majorUpgradeUrl="http://127.0.0.1:8080/noop"; single-variable test
#   to identify whether the render-loop launchUrl consumer is reading
#   majorUpgradeUrl specifically) — RESULT: launchUrl arg unchanged,
#   field ruled out as consumer.
# 8=V6_WITH_MAJORUPGRADETEXT_PLACEHOLDER (identical to v6 except
#   majorUpgradeText="ok"; next single-variable test of the empty-string
#   consumer hypothesis)
@app.route('/debug/probe', methods=['GET'])
def debug_probe_set():
    v = request.args.get('variant')
    if v is not None:
        _checkversion_probe_idx['n'] = int(v)
    return jsonify({"next_variant": _checkversion_probe_idx['n']})


# ---- VERSION CHECK ----
# CHttpClient::CheckVersion() / CLoadingScreen::DoCheckVersion()
# Game sends: PUT /checkversion
#
# EXPERIMENT: probe whether response decode path mirrors request encode path.
# Rotates four response variants per call so a single boot tests all of them.
# Variant labels show up in protocol_dump.log; pair with logcat to see which
# variant (if any) advances the boot flow to /server_list (DoGetServerInfo).
_checkversion_probe_idx = {'n': 0}
import hashlib as _hashlib


def _encoded_envelope_response(req_body_bytes):
    """Return a payload structurally identical to a request body.

    The client itself produced this envelope, so it IS a valid XOR+base64
    blob under the client's own cipher. Decoding it on the client side
    yields the form-encoded request fields, not a JSON response — but if
    the response decoder is engaged, we'll see a *different* failure mode
    in logcat (decode-then-parse-fail) vs. the JSON path (parse-fail-early).
    """
    return req_body_bytes  # already base64 ASCII bytes from the wire


@app.route('/checkversion', methods=['GET', 'POST', 'PUT'])
def checkversion():
    from flask import make_response
    idx = _checkversion_probe_idx['n']
    # Variant 6 (FULL_SCHEMA + servers + lastLoginPlayer object) is the known-good
    # response. Do NOT auto-rotate: the game re-sends checkversion on every boot/
    # restart, and rotating would feed a different (broken) variant each time,
    # causing inconsistent crashes. Stay on whatever /debug/probe pinned.

    # Capture the exact bytes the client sent (its own envelope)
    req_body_bytes = request.get_data() or b''
    body_md5 = _hashlib.md5(req_body_bytes).hexdigest() if req_body_bytes else ''

    # Schema reconstructed from libcity_ar.so .rodata cluster around "checkversion":
    # the strings the binary actually references are version / reviewVersion /
    # majorVersion / isReview. The doc-supplied needUpdate/forceUpdate/updateUrl
    # are NOT present in the binary and were speculative.
    plain_json = json.dumps({
        "result": 0,
        "code": 200,
        "data": {
            "version": "1.1.38",
            "majorVersion": "1",
            "reviewVersion": "1.1.38",
            "isReview": False
        },
        "errorMsg": "",
        "status": "ok"
    }).encode('utf-8')

    variant = idx % 15
    label = [
        'PLAIN_JSON',
        'ECHO_FORM_URLENCODED',
        'ECHO_OCTET_STREAM_W_CHECKSUM',
        'ECHO_NO_CONTENT_TYPE',
        'V4_URL_SOURCE_PROBE',
        'VERSION_MATCH_BUILD',
        'FULL_SCHEMA_FROM_BINARY',
        'V6_WITH_MAJORUPGRADEURL_PLACEHOLDER',
        'V6_WITH_MAJORUPGRADETEXT_PLACEHOLDER',
        'CMD_HEADER_DATA_IN_COMMAND',
        'CMD_HEADER_TOPLEVEL_STATUS',
        'CMD_ONLY',
        'SERVERS_IN_COMMAND',
        'SERVERS_TOPLEVEL',
        'SERVERS_IN_DATA',
    ][variant]
    print(f'[API] /checkversion probe #{idx} variant={label}')
    dump_log(f'PROBE /checkversion #{idx} variant={label}')

    if variant == 0:
        # Baseline: plain JSON (the current behavior — known to stall)
        resp = make_response(plain_json, 200)
        resp.headers['Content-Type'] = 'application/json'
    elif variant == 1:
        # Echo the request envelope; declare it as form-urlencoded (same as request)
        resp = make_response(req_body_bytes, 200)
        resp.headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif variant == 2:
        # Echo + treat as opaque binary + mirror checksum header
        resp = make_response(req_body_bytes, 200)
        resp.headers['Content-Type'] = 'application/octet-stream'
        if body_md5:
            resp.headers['X-Game-Checksum'] = body_md5
    elif variant == 3:
        # Echo with NO Content-Type (closest to what request headers showed)
        resp = make_response(req_body_bytes, 200)
        # Flask sets a default — strip it
        resp.headers.pop('Content-Type', None)
    elif variant == 4:
        # Variant 4: URL-source-field identification probe.
        # Plain JSON + corrected schema; each candidate URL field gets a
        # uniquely-tagged marker URL. Whichever marker surfaces in
        # NGDevice.launchUrl (captured by tools/frida_url_hooks.js) names
        # the actual source field. Pair the field tag in the URL path with
        # the [URL] line emitted by the hook.
        v4_payload = json.dumps({
            "result": 0,
            "code": 200,
            "data": {
                "version": "1.1.38",
                "majorVersion": "1",
                "reviewVersion": "1.1.38",
                "isReview": False,
                "url":         "http://wakr.local/V4-from-url",
                "updateUrl":   "http://wakr.local/V4-from-updateUrl",
                "apkUrl":      "http://wakr.local/V4-from-apkUrl",
                "downloadUrl": "http://wakr.local/V4-from-downloadUrl",
                "patchUrl":    "http://wakr.local/V4-from-patchUrl",
                "redirectUrl": "http://wakr.local/V4-from-redirectUrl"
            },
            "errorMsg": "",
            "status": "ok"
        }).encode('utf-8')
        resp = make_response(v4_payload, 200)
        resp.headers['Content-Type'] = 'application/json'
    elif variant == 5:
        # Variant 5: VERSION_MATCH_BUILD.
        # Hypothesis: the native version-comparison gate compares against the
        # engine build version "39", not the APK versionName "1.1.38". If
        # boot progresses past the version-check screen on this variant,
        # the gate is confirmed to be native version comparison rather than
        # connectivity or checksum validation.
        v5_payload = json.dumps({
            "result": 0,
            "code": 200,
            "data": {
                "version":       "39.0",
                "majorVersion":  "39",
                "reviewVersion": "39.0",
                "isReview":      False
            },
            "errorMsg": "",
            "status":   "ok"
        }).encode('utf-8')
        resp = make_response(v5_payload, 200)
        resp.headers['Content-Type'] = 'application/json'
    elif variant == 6:
        # Variant 6: FULL_SCHEMA_FROM_BINARY.
        # Every field that CLoadingScreen::OnReceiveResponse (opcode 0x80
        # CheckVersion handler) reads from the response, as resolved from
        # libcity_ar.so static analysis (.rodata cluster 0x700d74..0x700e6c).
        # Field-by-field provenance:
        #   time             -> first lookup, stored in sp+0x18 then later at
        #                       a global slot helperA+0x1bd8 (used by state
        #                       machine entered at 0x6a8c9c on function exit).
        #   majorUpgradeUrl  -> URL string for major-version upgrade flow.
        #   majorUpgrade     -> bool flag.
        #   loadingDoAllStep -> loading config int.
        #   loadingForceDeaf -> loading config bool.
        #   loadingTimeOut   -> loading config int (seconds).
        #   minorUpgrade     -> bool flag.
        #   majorUpgradeText -> upgrade prompt body text.
        #   isForceUpgrade   -> bool; parsed value is written directly to
        #                       (CLoadingScreen* this)+0x2AC = the state byte
        #                       gating CheckUpdate's update-route branch at
        #                       va 0x48f910.
        # Absence is NOT equivalent to false: vtable[16] returns 0 on
        # absence which short-circuits the strb and leaves the fallback
        # global path uninitialized. All fields are therefore present
        # explicitly with safe-default values.
        import time as _t
        v6_payload = json.dumps({
            "result": 0,
            "code": 200,
            "status": "ok",
            "errorMsg": "",
            "data": {
                "version":          "1.1.38",
                "majorVersion":     "1",
                "reviewVersion":    "1.1.38",
                "isReview":         False,

                "time":             int(_t.time()),
                "majorUpgrade":     False,
                "majorUpgradeUrl":  "",
                "majorUpgradeText": "",
                "minorUpgrade":     False,
                "isForceUpgrade":   False,
                "loadingDoAllStep": 0,
                "loadingForceDeaf": False,
                "loadingTimeOut":   60,
                "minorVersion":     "1.1.38",
                "inReview":         False,
                "contentUrlPrefix": "",
                "upgradeVersionFile": "",
                "enableCP":         False,
                "serverCtrlDebugSwitch": 0,
                # CLoadingScreen::ParseLastLoginPlayerInfo @0x490418 treats this
                # as an OBJECT (node+4 -> hash, GetNode); a string crashes it.
                # Fields: type(int), name(str), password(str, read if type!=0).
                "lastLoginPlayer":  {"type": 0, "name": "", "password": ""},
                "encryptMethod":    0,
                "preServerIdx":     0,
                "servers": [{
                    "idx": 1, "status": 1, "port": 9090, "recommend": 1,
                    "register": 0, "mergeServer": 0, "name": "Waker",
                    "url": "192.168.1.4", "comment": "", "bucket": 0,
                    "displayIdx": 1, "useHttps": 0, "crossPlatCode": "android"
                }]
            }
        }).encode('utf-8')
        resp = make_response(v6_payload, 200)
        resp.headers['Content-Type'] = 'application/json'
    elif variant == 7:
        # Variant 7: V6_WITH_MAJORUPGRADEURL_PLACEHOLDER.
        # Identical to variant 6 except majorUpgradeUrl is a non-empty
        # placeholder. Single-variable test: does the render-loop launchUrl
        # consumer pick up this exact string? If launchUrl now fires with
        # "http://127.0.0.1:8080/noop" (instead of "" as under v6), the
        # consumer field is identified.
        import time as _t
        v7_payload = json.dumps({
            "result": 0,
            "code": 200,
            "status": "ok",
            "errorMsg": "",
            "data": {
                "version":          "1.1.38",
                "majorVersion":     "1",
                "reviewVersion":    "1.1.38",
                "isReview":         False,

                "time":             int(_t.time()),
                "majorUpgrade":     False,
                "majorUpgradeUrl":  "http://127.0.0.1:8080/noop",
                "majorUpgradeText": "",
                "minorUpgrade":     False,
                "isForceUpgrade":   False,
                "loadingDoAllStep": 0,
                "loadingForceDeaf": False,
                "loadingTimeOut":   60
            }
        }).encode('utf-8')
        resp = make_response(v7_payload, 200)
        resp.headers['Content-Type'] = 'application/json'
    elif variant == 8:
        # Variant 8: V6_WITH_MAJORUPGRADETEXT_PLACEHOLDER.
        # Identical to variant 6 except majorUpgradeText is "ok" instead
        # of empty. Single-variable test for the next candidate consumer
        # field after majorUpgradeUrl was ruled out by variant 7.
        # If launchUrl now fires with "ok" (not ""), text field is the
        # consumer. If launchUrl("") persists, neither URL nor text is
        # the source and we move on to other string-valued fields the
        # post-CheckVersion code path reads.
        import time as _t
        v8_payload = json.dumps({
            "result": 0,
            "code": 200,
            "status": "ok",
            "errorMsg": "",
            "data": {
                "version":          "1.1.38",
                "majorVersion":     "1",
                "reviewVersion":    "1.1.38",
                "isReview":         False,

                "time":             int(_t.time()),
                "majorUpgrade":     False,
                "majorUpgradeUrl":  "",
                "majorUpgradeText": "ok",
                "minorUpgrade":     False,
                "isForceUpgrade":   False,
                "loadingDoAllStep": 0,
                "loadingForceDeaf": False,
                "loadingTimeOut":   60
            }
        }).encode('utf-8')
        resp = make_response(v8_payload, 200)
        resp.headers['Content-Type'] = 'application/json'
    elif variant in (9, 10, 11):
        # Envelope-shape probes: the wire request the client sent decodes to
        # {"command":{...},"header":{...}} (confirmed by cracking the cipher),
        # and ngHttpClient response handling references "command"/"header" keys
        # (libcity_ar .rodata 0x7051a5/0x70424f). The prior {"result","data"}
        # envelope let boot past checkversion but crashed in TCP-connect setup
        # (null+0x10) — likely a partial parse. These mirror the request shape.
        import time as _t
        _cmd = {
            "version":          "1.1.38",
            "majorVersion":     "1",
            "reviewVersion":    "1.1.38",
            "isReview":         False,
            "time":             int(_t.time()),
            "majorUpgrade":     False,
            "majorUpgradeUrl":  "",
            "majorUpgradeText": "",
            "minorUpgrade":     False,
            "isForceUpgrade":   False,
            "loadingDoAllStep": 0,
            "loadingForceDeaf": False,
            "loadingTimeOut":   60,
        }
        if variant == 9:
            env = {"command": _cmd,
                   "header": {"result": 0, "errorMsg": "", "code": 200, "status": "ok"}}
        elif variant == 10:
            env = {"result": 0, "code": 200, "status": "ok", "errorMsg": "",
                   "command": _cmd, "header": {}}
        else:  # variant == 11
            env = {"command": _cmd}
        resp = make_response(json.dumps(env).encode('utf-8'), 200)
        resp.headers['Content-Type'] = 'application/json'
    elif variant in (12, 13, 14):
        # ROOT-CAUSE FIX probe: the checkversion response must carry a "servers"
        # array (+ preServerIdx) or CServerMnger stays empty and
        # CServerMnger::GetCurrentServer @0x56f028 returns NULL -> caller derefs
        # null+0x10 -> GLThread SIGSEGV. CServer::Parse @0x56de78 fields:
        #   ints:  idx,status,port,recommend,register,mergeServer,bucket,displayIdx,useHttps
        #   strs:  name,url,comment,crossPlatCode
        import time as _t
        _server = {
            "idx": 1, "status": 1, "port": 9090, "recommend": 1, "register": 0,
            "mergeServer": 0, "name": "Waker", "url": "192.168.1.4", "comment": "",
            "bucket": 0, "displayIdx": 1, "useHttps": 0, "crossPlatCode": "android",
        }
        _full = {
            "version": "1.1.38", "majorVersion": "1", "reviewVersion": "1.1.38",
            "minorVersion": "1.1.38", "isReview": False, "inReview": False,
            "time": int(_t.time()),
            "majorUpgrade": False, "majorUpgradeUrl": "", "majorUpgradeText": "",
            "minorUpgrade": False, "isForceUpgrade": False,
            "loadingDoAllStep": 0, "loadingForceDeaf": False, "loadingTimeOut": 60,
            "contentUrlPrefix": "", "upgradeVersionFile": "", "minorVersionFile": "",
            "enableCP": False, "serverCtrlDebugSwitch": 0, "lastLoginPlayer": "",
            "encryptMethod": 0,
            "servers": [_server],
            "preServerIdx": 0,
        }
        if variant == 12:
            env = {"command": _full,
                   "header": {"result": 0, "errorMsg": "", "code": 200, "status": "ok"}}
        elif variant == 13:
            env = dict(_full); env.update({"result": 0, "code": 200, "status": "ok", "errorMsg": ""})
        else:  # variant == 14
            env = {"result": 0, "code": 200, "status": "ok", "errorMsg": "", "data": _full}
        resp = make_response(json.dumps(env).encode('utf-8'), 200)
        resp.headers['Content-Type'] = 'application/json'
    return resp


@app.route('/check_version', methods=['GET', 'POST', 'PUT'])
def check_version():
    print('[API] Version check')
    return jsonify({
        "result": 0,
        "code": 200,
        "data": {
            "version": "1.1.38",
            "versionCode": 2090800068,
            "forceUpdate": False,
            "updateUrl": "",
            "description": "",
            "needUpdate": False
        },
        "errorMsg": ""
    })


@app.route('/api/check_version', methods=['GET', 'POST', 'PUT'])
def api_check_version():
    return jsonify({
        "result": 0, "code": 200,
        "data": {"version": "1.1.38", "forceUpdate": False, "needUpdate": False},
        "errorMsg": ""
    })


# ---- MAINTENANCE CHECK ----
# CHttpClient::CheckMaintenance()
@app.route('/check_maintenance', methods=['GET', 'POST'])
def check_maintenance():
    print('[API] Maintenance check')
    return jsonify({
        "result": 0, "code": 200,
        "data": {"maintenance": False, "message": ""},
        "errorMsg": ""
    })


@app.route('/api/check_maintenance', methods=['GET', 'POST'])
def api_check_maintenance():
    return jsonify({"result": 0, "code": 200, "data": {"maintenance": False}, "errorMsg": ""})


# ---- SERVER LIST ----
# CServerMnger::ParseServerList() / CLoadingScreen::DoGetServerInfo()
@app.route('/server_list', methods=['GET', 'POST'])
def server_list():
    print('[API] Server list request')
    return jsonify({
        "result": 0,
        "code": 200,
        "data": {
            "servers": [
                {
                    "id": 1,
                    "serverId": 1,
                    "displayId": 1,
                    "name": "Local Server",
                    "host": SERVER_IP,
                    "port": HTTP_PORT,
                    "status": 1,
                    "isNew": False,
                    "isFull": False,
                    "isRecommend": True,
                    "platCode": "android",
                    "showIdx": 1,
                    "keepLiveServerHost": SERVER_IP,
                    "keepLiveServerPort": TCP_PORT
                }
            ],
            "suggestServer": 1,
            "crossPlatCode": "android"
        },
        "errorMsg": ""
    })


@app.route('/api/server_list', methods=['GET', 'POST'])
def api_server_list():
    return redirect('/server_list')


@app.route('/servers', methods=['GET', 'POST'])
def servers():
    return redirect('/server_list')


# ---- STEP-10 STAGE: getallserver + connect (reversed from libcity_ar.so) ----
def _server_entry():
    # CServer::Parse @0x56de78 schema: ints idx/status/port/recommend/register/
    # mergeServer/bucket/displayIdx/useHttps; strings name/url/comment/crossPlatCode.
    return {
        "idx": 1, "status": 1, "port": TCP_PORT, "recommend": 1, "register": 0,
        "mergeServer": 0, "name": "Waker", "url": SERVER_IP, "comment": "",
        "bucket": 0, "displayIdx": 1, "useHttps": 0, "crossPlatCode": "android",
    }


@app.route('/api/getallserver', methods=['GET', 'POST', 'PUT'])
def api_getallserver():
    # CHttpClient::GetAllServer @0x453044 (opcode 0xe4); response parsed by
    # CServerMnger::ParseServerList -> CServer::Parse over data.servers[].
    print('[API] /api/getallserver')
    # CServerMnger::ParseServerList @0x56eb4c iterates `data` AS AN ARRAY (same
    # [data+4].begin() pattern as ParseChilds), CServer::Parse on each element,
    # then hashes the server (by name/url) into a map. data must be the server
    # ARRAY directly — an object wrapper makes it parse a null-named server and
    # ContainsKey(null) -> strlen(NULL) crash on the resume (getallserver) path.
    return jsonify({"result": 0, "code": 200, "errorMsg": "",
                    "data": [_server_entry()], "preServerIdx": 0, "suggestServer": 0})


def _login_success_payload():
    pid = "1001"
    return {
        "playerId": pid, "uid": pid, "userId": pid, "id": pid,
        "key": "waker-key", "sessionKey": "waker-key", "token": "waker-key",
        "name": "Player", "serverId": 1,
        "keepLiveServerHost": SERVER_IP, "keepLiveServerPort": TCP_PORT,
    }


@app.route('/api/connect', methods=['GET', 'POST', 'PUT'])
def api_connect():
    # CHttpClient::PlayerLogin @0x44e9b8 (opcode 0x78, command "connect").
    # On success -> CLoadingScreen::OnLoginSuccess(playerId, key).
    print('[API] /api/connect (PlayerLogin)')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": _login_success_payload()})


@app.route('/api/authplayerkey', methods=['GET', 'POST', 'PUT'])
def api_authplayerkey():
    # Cached-key RESUME path (relaunch without re-entering credentials). The
    # client does checkversion -> authplayerkey; if it doesn't get a valid login
    # session it loops at the title. Mirror the connect login-success payload so
    # the resume path proceeds to getplayerlist/connect like a fresh login.
    print('[API] /api/authplayerkey (cached resume login)')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": _login_success_payload()})


# ---- PORT 9090 ("keepLiveServerPort") IS HTTP, same base64+XOR cipher ----
# The client connects to 9090 and sends PUT /city/<cmd> with a cipher'd body
# (NOT an RC4 binary frame). /city/impart = game-config (CImpart) fetch at
# LoadingMnger step 10. Served by the same Flask app on port 9090 (see __main__).
@app.route('/city/impart', methods=['GET', 'POST', 'PUT'])
def city_impart():
    print('[9090] /city/impart (game config)')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": {}})


@app.route('/city/connect/getplayerlist', methods=['GET', 'POST', 'PUT'])
def city_getplayerlist():
    # CServerMnger::ParseRoleList @0x56f19a iterates an ARRAY node (vtable[0x14]
    # begin / [8] hasNext / [0xc] next), allocating a 1384-byte role per element
    # and parsing via 0x693ecc. An EMPTY array iterates nothing (no crash) and
    # means "no character on this server" -> char-creation path. Cover all
    # candidate root keys (players/playerList) at both root and data level.
    print('[9090] /city/connect/getplayerlist')
    # ParseResponse passes the response "data" node DIRECTLY to ParseRoleList
    # (no sub-key lookup), so data must BE the role ARRAY. Empty [] iterates
    # to nothing => no crash => "no character" / char-creation path.
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": []})


@app.route('/city/chat/gettopmsgs', methods=['GET', 'POST', 'PUT'])
def city_gettopmsgs():
    # Rolling-text ticker: CTopScreen::ParseMsg @0x592fb4 iterates data as an
    # ARRAY of {senderName,content,createdAt,id}; OnRollingOneTime @0x593374
    # displays one at a time then RequestMsg re-polls when empty. Empty [] =>
    # instant exhaustion => busy-loop => ANR. Provide a few msgs to pace it.
    import time as _t
    now = int(_t.time())
    msgs = [{"senderName": "System", "content": "Welcome to Waker", "createdAt": now, "id": 1},
            {"senderName": "System", "content": "Server online", "createdAt": now, "id": 2},
            {"senderName": "System", "content": "Have fun", "createdAt": now, "id": 3}]
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": msgs})


@app.route('/city/chat/<path:cmd>', methods=['GET', 'POST', 'PUT'])
def city_chat_cmd(cmd):
    # Chat endpoints are message LISTS. CTopScreen::ParseSysMsg @0x59318c (and
    # gettopmsgs) iterate response "data" as an ARRAY (begin-iter vtbl+0x14);
    # sys-msg entry fields = senderName(str), content(str), createdAt(int), id(int).
    # Empty [] = no messages, no crash.
    print(f'[9090] /city/chat/{cmd}')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": []})


@app.route('/city/player/introplayers', methods=['GET', 'POST', 'PUT'])
def city_introplayers():
    # Routed to CFeedbackScreen::OnReceiveResponse (code 0xe0) -> ParseChilds
    # @0x3ea612, which iterates "data" as an ARRAY (begin-iter vtbl+0x14). An
    # object/{} makes begin() return null -> ldr [r5] null-deref (GLThread SIGSEGV).
    # Empty [] -> valid end-iterator, count==0 -> clean epilogue.
    print('[9090] /city/player/introplayers')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": []})


def _make_player():
    # CPlayer::Parse @0x5140bc (168 fields, see SCHEMAS.md). Provide a NON-new,
    # established player so the new-player guided tour (job->gym->market, which
    # crashes CMarketCateScreen) does not run and the game lands on CMainScreen.
    # Fields read by name; omitted ones default. Keep complex arrays/objects out
    # (they default to empty) to avoid type-mismatch crashes in the parser.
    import time as _t
    now = int(_t.time())
    return {
        # --- identity / profile ---
        "id": 1, "uid": 1, "name": "Player", "level": 20, "exp": 0,
        # avatarAt>0 = avatar already set (avatarAt:0 pops the photo-picker dialog).
        "gender": 1, "playerRole": 1, "avatarAt": now - 86400, "signature": "Welcome to Waker",
        "createdAt": now - 86400 * 30, "playerKey": "waker-key",
        "maritalStatus": 0, "spouseName": "",
        # newPlayer=0 = minimal tutorial-disable. missionId is intentionally past
        # the 29 mission.city entries ("no active mission") so the mascot doesn't
        # force-open (and crash) a mission target screen; player lands on the city
        # view. A real active mission needs its full endpoint chain (getmsg +
        # randomfighters + randomgangs) populated — see STATUS.md.
        "newPlayer": 0, "missionId": 100, "missionProgress": 0,
        "loginGift": 0, "loginContinuousDays": 1, "firstPayed": 0, "firstPayGifted": 0,
        # --- currencies (CPlayer names: gold/money/cheque, NOT cash/diamond) ---
        "gold": 100000, "money": 5000000, "cheque": 5000,
        "merits": 1000, "totalMerits": 1000,
        "vip": 0, "vipExpireAt": 0, "payed": 0, "payLevel": 0,
        # --- combat stats (base + basic) ---
        "strength": 50, "endurance": 50, "speed": 50, "agile": 50,
        "basicStrength": 50, "basicEndurance": 50, "basicSpeed": 50, "basicAgile": 50,
        "defense": 20, "hornNum": 5, "bigHornNum": 2,
        # --- resource bars: "current/max" where the *Up field IS the max
        #     (verified on-device: current=80/Up=100 rendered "80/100"). Full bars. ---
        "energy": 100, "energyUp": 100, "energyAt": now, "boughtRecoverEnergy": 0,
        "storedEnergy": 0, "maxPlayerEnergy": 100,
        "blood": 100, "bloodUp": 100,
        "happy": 100, "happyUp": 100,
        "brave": 100, "braveUp": 100,
        "moral": 100, "moralUp": 100, "moralAt": now,
        # --- sizes / counters ---
        "warehouseSize": 50, "bagMaxSize": 50, "dealMaxSize": 20, "friendNum": 0,
        "fightTimes": 0, "jailTimes": 0, "hospitalTimes": 0, "crimeTimes": 0,
        "thriceNum": 0, "crimeSuccess": 0,
        # --- typed objects/arrays (only the VERIFIED-safe shapes; CPlayer::Parse
        #     crashes if an array/object field is given the wrong container type,
        #     so other account collections are left absent => default empty). ---
        #     playerStatus -> CPlayer::ParseStatus @0x516254 (object; status=0=normal).
        #     goods/bags -> arrays of CGoods; estates -> array of CHouse.
        "playerStatus": {"cityId": 1, "status": 0, "statusAt": 0, "statusDuration": 0,
                         "statusExtra": 0, "statusExtraDesc": "", "noFightedExpireAt": 0},
        "goods": [], "bags": [], "estates": [],
    }


def _make_fighter(fid=2001, name="Rival", level=18):
    # CCitier::Parse @0x34df98 (55 fields). A "random fighter" is a full CCitier
    # (other-player/role, 1384B, same parser as getplayerlist roles via 0x693ecc ->
    # CCitier::Parse). /city/fight/randomfighters returns an ARRAY of these; an
    # empty/object response = zero fighters => the mission fight-target is absent =>
    # the city map places a null target sprite -> ngGameMapSpriteLayer::HandleRender
    # null-deref. liveEstateObj = the fighter's house (its map placement).
    import time as _t
    now = int(_t.time())
    return {
        "id": fid, "uid": fid, "playerType": 0, "name": name, "level": level,
        "blood": 100, "bloodUp": 100, "status": 0, "statusAt": 0, "statusDuration": 0,
        "statusExtra": 0, "statusExtraDesc": "", "rankPos": 0, "rankScore": 0,
        "cityId": 1, "avatarAt": 0, "online": 1, "vip": 0, "gangFlag": 0, "gangId": 0,
        "title": 0, "prestige": 0, "contribution": 0, "gangMemberRelationId": 0,
        "relation": 0, "lastOnlineAt": now, "playerRole": 1, "wantedId": 0,
        "wantedOwnerId": 0, "rewardMoney": 0, "content": "", "gender": 1,
        "maritalStatus": 0, "merits": 0, "createdAt": now - 86400 * 60,
        "bailCostMoney": 0, "signature": "", "battlePrestige": 0, "guardRelation": 0,
        "popular": 0, "noChat": 0, "disable": 0, "serverIdx": 1, "locale": "en",
        "remark": "", "liveEstateObj": _make_house(hid=9001, owner_id=fid, owner_name=name),
    }


@app.route('/city/fight/randomfighters', methods=['GET', 'POST', 'PUT'])
def city_randomfighters():
    print('[9090] /city/fight/randomfighters -> [CCitier] array (mission fight target)')
    return jsonify({"result": 0, "code": 200, "errorMsg": "",
                    "data": [_make_fighter(2001, "Rival", 18), _make_fighter(2002, "Thug", 17)]})


@app.route('/city/connect/connect', methods=['GET', 'POST', 'PUT'])
def city_connect_connect():
    print('[9090] /city/connect/connect -> non-new CPlayer (stop new-player tour)')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": _make_player()})


@app.route('/city/connect/create', methods=['GET', 'POST', 'PUT'])
def city_connect_create():
    print('[9090] /city/connect/create -> non-new CPlayer')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": _make_player()})


@app.route('/city/goods/getcitygoods', methods=['GET', 'POST', 'PUT'])
def city_getcitygoods():
    # CMarketCateScreen::ParseGoodsAmount @0x4c2fe8 reads data.goodsList (array);
    # each entry has {category, type, amount} (type -> product.city id). With the
    # catch-all data:{} (no goodsList) the goods model is null -> the cate table
    # renders a null cell -> CMarketCateCellRender::SetValue null-deref. Provide
    # the field as an empty array so the model is non-null and renders 0 cells.
    print('[9090] /city/goods/getcitygoods')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": {"goodsList": []}})


def _make_house(hid=1, estate_type=800, owner_id=1, owner_name="Player"):
    # CHouse::Parse @0x4498d8 schema. estateType -> property.city id (CaoPeng=800,
    # the first record / table key read by the CProperty loader). GetById(estateType)
    # in CHouse::GetPrice must resolve, else null-deref (fault 0x84).
    return {
        "id": hid, "estateType": estate_type, "systemEstate": 0,
        "decoration1": 0, "decoration2": 0, "decoration3": 0,
        "maid1": 0, "maid1ExpireAt": 0, "maid2": 0, "maid2ExpireAt": 0,
        "ownerId": owner_id, "renterId": 0, "renterName": "", "ownerName": owner_name,
        "status": 1, "sellPrice": 1000, "rentPrice": 100,
        "rentExpireAt": 0, "rentDays": 0, "maintainExpireAt": 0,
        "customHouseAt": 0, "customHouseTag": "",
    }


@app.route('/city/estate/listestates', methods=['GET', 'POST', 'PUT'])
def city_listestates():
    # Array of houses (each parsed by CHouse::Parse). One owned estate.
    print('[9090] /city/estate/listestates')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": [_make_house()]})


@app.route('/city/estate/buy', methods=['GET', 'POST', 'PUT'])
def city_estate_buy():
    # cmd 0x13b -> CPropertyListCateScreen builds ONE CHouse from data (object),
    # then CHouse::GetPrice -> GetById(estateType). Provide a fully-populated house
    # object with a valid estateType so the config lookup resolves.
    print('[9090] /city/estate/buy -> valid CHouse(estateType=800)')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": _make_house()})


@app.route('/city/<path:cmd>', methods=['GET', 'POST', 'PUT'])
def city_cmd(cmd):
    print(f'[9090] /city/{cmd}')
    return jsonify({"result": 0, "code": 200, "errorMsg": "", "data": {}})


# ---- GUEST REGISTRATION ----
# CHttpClient::GuestRegister() / CHttpClient::GuestRegisterPlayerServer()
@app.route('/guest/register', methods=['GET', 'POST'])
def guest_register():
    global next_player_id
    pid = next_player_id
    next_player_id += 1
    token = generate_token()
    session_id = generate_session_id()

    players[pid] = create_default_player(pid)
    sessions[session_id] = {"playerId": pid, "token": token}

    print(f'[API] Guest register -> playerId: {pid}')
    return jsonify({
        "result": 0,
        "code": 200,
        "data": {
            "playerId": pid,
            "userId": pid,
            "token": token,
            "sessionId": session_id,
            "isNew": True,
            "serverId": 1,
            "serverName": "Local Server"
        },
        "errorMsg": ""
    })


# ---- PLAYER AUTH ----
# CHttpClient::PlayerAuth()
@app.route('/player/auth', methods=['GET', 'POST'])
def player_auth():
    global next_player_id
    pid_str = get_param('playerId')
    pid = int(pid_str) if pid_str else next_player_id
    if not pid_str:
        next_player_id += 1
    token = generate_token()
    session_id = generate_session_id()

    if pid not in players:
        players[pid] = create_default_player(pid)
    sessions[session_id] = {"playerId": pid, "token": token}

    print(f'[API] Player auth -> playerId: {pid}')
    return jsonify({
        "result": 0,
        "code": 200,
        "data": {
            "playerId": pid,
            "userId": pid,
            "token": token,
            "sessionId": session_id,
            "isNew": False
        },
        "errorMsg": ""
    })


# ---- FACEBOOK LOGIN ----
# CHttpClient::PlayerConnectFacebook()
@app.route('/connect/facebook', methods=['GET', 'POST'])
def connect_facebook():
    global next_player_id
    pid = next_player_id
    next_player_id += 1
    token = generate_token()
    players[pid] = create_default_player(pid)

    print(f'[API] Facebook connect -> playerId: {pid}')
    return jsonify({
        "result": 0, "code": 200,
        "data": {"playerId": pid, "userId": pid, "token": token, "isNew": True},
        "errorMsg": ""
    })


@app.route('/connectFacebook', methods=['GET', 'POST'])
def connect_facebook_alt():
    return redirect('/connect/facebook', code=307)


# ---- ROLE/PLAYER LIST ----
# CServerMnger::ParseRoleList() / CLoadingScreen::DoGetPlayerList()
@app.route('/player/list', methods=['GET', 'POST'])
def player_list():
    pid = get_player_id()
    player = players.get(pid, create_default_player(pid))

    print(f'[API] Player list for pid: {pid}')
    return jsonify({
        "result": 0,
        "code": 200,
        "data": {
            "roleList": [
                {
                    "playerId": player["playerId"],
                    "name": player["name"],
                    "level": player["level"],
                    "gender": player["gender"],
                    "avatar": player["avatar"],
                    "serverId": 1,
                    "serverName": "Local Server",
                    "cityId": player["cityId"]
                }
            ],
            "canCreate": True
        },
        "errorMsg": ""
    })


@app.route('/role/list', methods=['GET', 'POST'])
def role_list():
    return redirect('/player/list')


# ---- CREATE PLAYER ----
# CLoadingScreen::DoCreateUser() / CHttpClient::UserCreate()
@app.route('/player/create', methods=['GET', 'POST'])
def player_create():
    global next_player_id
    pid_str = get_param('playerId')
    pid = int(pid_str) if pid_str else next_player_id
    if not pid_str:
        next_player_id += 1
    name = get_param('name', f'Player_{pid}')
    gender = int(get_param('gender', '1'))

    players[pid] = create_default_player(pid, name)
    players[pid]["gender"] = gender

    print(f'[API] Create player: {name} (pid: {pid})')
    return jsonify({
        "result": 0, "code": 200,
        "data": {"playerId": pid, "name": name, "created": True},
        "errorMsg": ""
    })


@app.route('/user/create', methods=['GET', 'POST'])
def user_create():
    return redirect('/player/create', code=307)


# ---- PLAYER INFO / CONNECT ----
# CLoadingScreen::DoConnectPlayerInfo() / CHttpClient::Connect()
@app.route('/connect', methods=['GET', 'POST'])
def connect():
    pid = get_player_id()
    if pid not in players:
        players[pid] = create_default_player(pid)
    players[pid]["lastLoginTime"] = int(time.time() * 1000)

    print(f'[API] Connect player: {pid}')
    data = dict(players[pid])
    data.update({
        "keepLiveServerHost": SERVER_IP,
        "keepLiveServerPort": TCP_PORT,
        "serverTime": int(time.time()),
        "loginGifts": [],
        "loginRewardList": [],
        "windowConfigs": [],
        "announcements": [],
    })
    return jsonify({
        "result": 0, "code": 200,
        "data": data,
        "errorMsg": ""
    })


@app.route('/connect/', methods=['GET', 'POST'])
def connect_slash():
    return redirect('/connect', code=307)


# ---- PLAYER INFO ----
@app.route('/player/info', methods=['GET', 'POST'])
def player_info():
    pid = get_player_id()
    player = players.get(pid, create_default_player(pid))
    return jsonify({"result": 0, "code": 200, "data": player, "errorMsg": ""})


# ---- PLAYER RATING ----
@app.route('/player/rating', methods=['GET', 'POST'])
def player_rating():
    return jsonify({
        "result": 0, "code": 200,
        "data": {"rating": 1000, "rank": 1, "totalPlayers": 1},
        "errorMsg": ""
    })


# ---- PLAYER UPDATE ----
@app.route('/player/update', methods=['GET', 'POST'])
def player_update():
    pid = get_player_id()
    if pid in players:
        if request.form:
            players[pid].update(dict(request.form))
        elif request.is_json and request.json:
            players[pid].update(request.json)
    return success_response({"updated": True})


# ---- CHAT ----
@app.route('/chat/get', methods=['GET', 'POST'])
def chat_get():
    return jsonify({"result": 0, "code": 200, "data": {"msgs": [], "msgType": 0}, "errorMsg": ""})


@app.route('/chat/post', methods=['GET', 'POST'])
def chat_post():
    return success_response({"sent": True})


@app.route('/chat/sys', methods=['GET', 'POST'])
def chat_sys():
    return jsonify({"result": 0, "code": 200, "data": {"msgs": []}, "errorMsg": ""})


@app.route('/chat/top', methods=['GET', 'POST'])
def chat_top():
    return jsonify({"result": 0, "code": 200, "data": {"msgs": []}, "errorMsg": ""})


# ---- MAIL ----
@app.route('/mail/list', methods=['GET', 'POST'])
def mail_list():
    return jsonify({"result": 0, "code": 200, "data": {"mails": []}, "errorMsg": ""})


# ---- FRIENDS ----
@app.route('/friend/list', methods=['GET', 'POST'])
def friend_list():
    return jsonify({"result": 0, "code": 200, "data": {"friends": []}, "errorMsg": ""})


@app.route('/friend/add', methods=['GET', 'POST'])
def friend_add():
    return success_response()


@app.route('/friend/delete', methods=['GET', 'POST'])
def friend_delete():
    return success_response()


@app.route('/friend/approve', methods=['GET', 'POST'])
def friend_approve():
    return success_response()


# ---- ENEMY ----
@app.route('/enemy/get', methods=['GET', 'POST'])
def enemy_get():
    return jsonify({"result": 0, "code": 200, "data": {"enemies": []}, "errorMsg": ""})


@app.route('/enemy/add', methods=['GET', 'POST'])
def enemy_add():
    return success_response()


@app.route('/enemy/delete', methods=['GET', 'POST'])
def enemy_delete():
    return success_response()


# ---- FACTION/GANG ----
@app.route('/faction/list', methods=['GET', 'POST'])
def faction_list():
    return jsonify({"result": 0, "code": 200, "data": {"factions": []}, "errorMsg": ""})


@app.route('/faction/info', methods=['GET', 'POST'])
def faction_info():
    return jsonify({"result": 0, "code": 200, "data": {"factionId": 0}, "errorMsg": ""})


@app.route('/faction/create', methods=['GET', 'POST'])
def faction_create():
    name = get_param('name', 'Gang')
    return success_response({"factionId": 1, "name": name})


@app.route('/faction/apply', methods=['GET', 'POST'])
def faction_apply():
    return success_response()


@app.route('/faction/approve', methods=['GET', 'POST'])
def faction_approve():
    return success_response()


# ---- BUILDINGS / HOUSE ----
@app.route('/house/buy', methods=['GET', 'POST'])
def house_buy():
    return success_response({"houseId": 1})


@app.route('/house/info', methods=['GET', 'POST'])
def house_info():
    return jsonify({"result": 0, "code": 200, "data": {"houses": []}, "errorMsg": ""})


@app.route('/house/decorate', methods=['GET', 'POST'])
def house_decorate():
    return success_response()


# ---- MARKET / STORE ----
@app.route('/market/list', methods=['GET', 'POST'])
def market_list():
    return jsonify({"result": 0, "code": 200, "data": {"items": []}, "errorMsg": ""})


@app.route('/market/sell', methods=['GET', 'POST'])
def market_sell():
    return success_response()


@app.route('/market/buy', methods=['GET', 'POST'])
def market_buy():
    return success_response()


@app.route('/store/buy', methods=['GET', 'POST'])
def store_buy():
    return success_response()


# ---- CRIME / WORK / MISSIONS ----
@app.route('/crime/do', methods=['GET', 'POST'])
def crime_do():
    return jsonify({
        "result": 0, "code": 200,
        "data": {"success": True, "exp": 10, "gold": 100, "energy": -5},
        "errorMsg": ""
    })


@app.route('/work/do', methods=['GET', 'POST'])
def work_do():
    return jsonify({
        "result": 0, "code": 200,
        "data": {"success": True, "exp": 5, "gold": 50, "energy": -3},
        "errorMsg": ""
    })


@app.route('/mission/list', methods=['GET', 'POST'])
def mission_list():
    return jsonify({"result": 0, "code": 200, "data": {"missions": []}, "errorMsg": ""})


@app.route('/mission/update', methods=['GET', 'POST'])
def mission_update():
    return success_response()


# ---- DAILY / LOGIN GIFTS ----
@app.route('/daily/gift', methods=['GET', 'POST'])
def daily_gift():
    return jsonify({
        "result": 0, "code": 200,
        "data": {
            "loginContinuousDays": 1,
            "loginGifts": [],
            "loginRewardList": [],
            "loginGiftGoldToolRatio": 1
        },
        "errorMsg": ""
    })


@app.route('/login/gift', methods=['GET', 'POST'])
def login_gift():
    return jsonify({"result": 0, "code": 200, "data": {"gifts": []}, "errorMsg": ""})


# ---- BANK ----
@app.route('/bank/balance', methods=['GET', 'POST'])
def bank_balance():
    return jsonify({"result": 0, "code": 200, "data": {"balance": 0, "deposit": 0}, "errorMsg": ""})


@app.route('/bank/deposit', methods=['GET', 'POST'])
def bank_deposit():
    return success_response()


@app.route('/bank/withdraw', methods=['GET', 'POST'])
def bank_withdraw():
    return success_response()


# ---- GYM ----
@app.route('/gym/enter', methods=['GET', 'POST'])
def gym_enter():
    return success_response()


@app.route('/gym/train', methods=['GET', 'POST'])
def gym_train():
    return jsonify({"result": 0, "code": 200, "data": {"success": True, "statIncrease": 1}, "errorMsg": ""})


# ---- HOSPITAL / CURE ----
@app.route('/cure', methods=['GET', 'POST'])
def cure():
    return success_response({"blood": 100, "maxBlood": 100})


# ---- PRISON ----
@app.route('/prison/list', methods=['GET', 'POST'])
def prison_list():
    return jsonify({"result": 0, "code": 200, "data": {"prisoners": []}, "errorMsg": ""})


@app.route('/prison/bail', methods=['GET', 'POST'])
def prison_bail():
    return success_response()


@app.route('/prison/bust', methods=['GET', 'POST'])
def prison_bust():
    return success_response()


# ---- DUNGEON ----
@app.route('/dungeon/enter', methods=['GET', 'POST'])
def dungeon_enter():
    return success_response()


@app.route('/dungeon/pass', methods=['GET', 'POST'])
def dungeon_pass():
    return success_response({"exp": 50, "gold": 200})


# ---- AUCTION ----
@app.route('/auction/list', methods=['GET', 'POST'])
def auction_list():
    return jsonify({"result": 0, "code": 200, "data": {"auctions": []}, "errorMsg": ""})


@app.route('/auction/create', methods=['GET', 'POST'])
def auction_create():
    return success_response()


@app.route('/auction/bid', methods=['GET', 'POST'])
def auction_bid():
    return success_response()


# ---- SKYSCRAPER ----
@app.route('/skyscraper/enter', methods=['GET', 'POST'])
def skyscraper_enter():
    return success_response()


@app.route('/skyscraper/building', methods=['GET', 'POST'])
def skyscraper_building():
    return success_response()


# ---- EQUIPMENT / STRENGTHEN ----
@app.route('/equipment/list', methods=['GET', 'POST'])
def equipment_list():
    return jsonify({"result": 0, "code": 200, "data": {"equipment": []}, "errorMsg": ""})


@app.route('/strengthen', methods=['GET', 'POST'])
def strengthen():
    return success_response({"success": True})


# ---- DRUGS ----
@app.route('/drug/eat', methods=['GET', 'POST'])
def drug_eat():
    return success_response()


# ---- ACHIEVEMENT ----
@app.route('/achievement/list', methods=['GET', 'POST'])
def achievement_list():
    return jsonify({"result": 0, "code": 200, "data": {"achievements": []}, "errorMsg": ""})


# ---- ACTIVE / EVENTS ----
@app.route('/active/list', methods=['GET', 'POST'])
def active_list():
    return jsonify({"result": 0, "code": 200, "data": {"activities": []}, "errorMsg": ""})


# ---- RACE GAME ----
@app.route('/race/enter', methods=['GET', 'POST'])
def race_enter():
    return success_response()


# ---- KING FIGHT ----
@app.route('/kingfight/config', methods=['GET', 'POST'])
def kingfight_config():
    return jsonify({"result": 0, "code": 200, "data": {"kingFightConfig": {}}, "errorMsg": ""})


# ---- STREET WAR ----
@app.route('/streetwar/enter', methods=['GET', 'POST'])
def streetwar_enter():
    return success_response()


# ---- RANK / LEADERBOARD ----
@app.route('/rank/list', methods=['GET', 'POST'])
def rank_list():
    return jsonify({"result": 0, "code": 200, "data": {"ranks": [], "weekRank": []}, "errorMsg": ""})


# ---- SHOWCASE ----
@app.route('/showcase/list', methods=['GET', 'POST'])
def showcase_list():
    return jsonify({"result": 0, "code": 200, "data": {"showcases": []}, "errorMsg": ""})


# ---- HUNT ----
@app.route('/hunt/enter', methods=['GET', 'POST'])
def hunt_enter():
    return success_response()


# ---- AIRLINE ----
@app.route('/airline/get', methods=['GET', 'POST'])
def airline_get():
    return jsonify({"result": 0, "code": 200, "data": {"arrived": True}, "errorMsg": ""})


# ---- MASTER / APPRENTICE ----
@app.route('/master/info', methods=['GET', 'POST'])
def master_info():
    return jsonify({"result": 0, "code": 200, "data": {"master": None, "children": []}, "errorMsg": ""})


# ---- PAYMENT VERIFICATION (Stub) ----
@app.route('/verify/payment', methods=['GET', 'POST'])
def verify_payment():
    return success_response({"verified": True})


@app.route('/store/vip', methods=['GET', 'POST'])
def store_vip():
    return success_response({"vipLevel": 0})


# ---- PUSH NOTIFICATION TOKEN ----
@app.route('/push/token', methods=['GET', 'POST'])
def push_token():
    return success_response()


# ---- ADVERTISES ----
@app.route('/advertises', methods=['GET', 'POST'])
def advertises():
    return jsonify({"result": 0, "code": 200, "data": {"ads": []}, "errorMsg": ""})


# ---- SIGNATURE UPDATE ----
@app.route('/signature/update', methods=['GET', 'POST'])
def signature_update():
    return success_response()


# ---- WINDOWS/POPUP CONFIG ----
@app.route('/window/config', methods=['GET', 'POST'])
def window_config():
    return jsonify({"result": 0, "code": 200, "data": {"windowConfigs": []}, "errorMsg": ""})


@app.route('/window/status', methods=['GET', 'POST'])
def window_status():
    return success_response()


# ---- PASSWORD RESET PAGE (web) ----
@app.route('/page/pwdreset', methods=['GET'])
def pwd_reset():
    return '<html><body><h1>Password Reset</h1><p>Local server - no password reset needed.</p></body></html>'


# ---- STATISTICS / ANALYTICS (stub) ----
@app.route('/logevent/weightevent', methods=['GET', 'POST'])
def logevent():
    return jsonify({"result": 0})


# ---- CROSS SERVER ----
@app.route('/cross/fight', methods=['GET', 'POST'])
def cross_fight():
    return success_response()


@app.route('/cross/ladder', methods=['GET', 'POST'])
def cross_ladder():
    return jsonify({"result": 0, "code": 200, "data": {"fighters": []}, "errorMsg": ""})


# ---- YB (Faction Factory/Force) ----
@app.route('/yb/store', methods=['GET', 'POST'])
def yb_store():
    return jsonify({"result": 0, "code": 200, "data": {"items": []}, "errorMsg": ""})


@app.route('/yb/battle', methods=['GET', 'POST'])
def yb_battle():
    return success_response()


# ---- DEAL / TRADE ----
@app.route('/deal/list', methods=['GET', 'POST'])
def deal_list():
    return jsonify({"result": 0, "code": 200, "data": {"deals": []}, "errorMsg": ""})


@app.route('/deal/create', methods=['GET', 'POST'])
def deal_create():
    return success_response()


@app.route('/deal/buy', methods=['GET', 'POST'])
def deal_buy():
    return success_response()


# ---- WORLD BOSS ----
@app.route('/worldboss/detail', methods=['GET', 'POST'])
def worldboss_detail():
    return jsonify({"result": 0, "code": 200, "data": {"boss": None}, "errorMsg": ""})


# ---- HEARTBEAT (HTTP fallback) ----
@app.route('/heartbeat', methods=['GET', 'POST'])
def heartbeat():
    return jsonify({"result": 0, "code": 200, "data": {"serverTime": int(time.time())}, "errorMsg": ""})


# ---- CHECKSUM ----
@app.route('/checksum', methods=['GET', 'POST'])
def checksum():
    return jsonify({"result": 0, "code": 200, "data": {"valid": True}, "errorMsg": ""})


# =============================================================================
# CATCH-ALL: Return generic success for any unhandled API call
# =============================================================================

@app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def catch_all(path):
    print(f'[API] UNHANDLED: {request.method} /{path}')
    if request.form:
        print(f'  Body: {dict(request.form)}')
    return jsonify({
        "result": 0,
        "code": 200,
        "data": {},
        "errorMsg": "",
        "status": "ok"
    })


# =============================================================================
# TCP KEEPALIVE SERVER (Port 9090)
# =============================================================================

def tcp_keepalive_server():
    """TCP keep-alive server for real-time features (chat, poker, notifications).
    Uses RC4 encryption via ngRC4Mnger. We accept connections and respond to heartbeats."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', TCP_PORT))
    server.listen(5)
    print(f'[TCP]  KeepAlive server running on port {TCP_PORT}')

    while True:
        try:
            client, addr = server.accept()
            print(f'[TCP] Client connected: {addr}')
            t = threading.Thread(target=handle_tcp_client, args=(client, addr), daemon=True)
            t.start()
        except Exception as e:
            print(f'[TCP] Accept error: {e}')


def handle_tcp_client(client, addr):
    """Handle a single TCP keepalive client connection."""
    pkt_count = 0
    try:
        while True:
            data = client.recv(4096)
            if not data:
                break
            pkt_count += 1
            print(f'[TCP] Data from {addr}: {len(data)} bytes (pkt #{pkt_count})')
            print(f'  Hex: {data.hex()[:200]}')

            # Dump full TCP packet to protocol log
            dump_log(
                f"TCP RECV from {addr} ({len(data)} bytes, pkt #{pkt_count})\n"
                f"  Hex: {data.hex()}\n"
                f"  Raw: {data!r}"
            )

            # Send simple acknowledgment (4 bytes: packet length = 0)
            try:
                client.send(b'\x00\x00\x00\x00')
            except Exception as e:
                print(f'[TCP] Error sending ack: {e}')
                break
    except Exception as e:
        print(f'[TCP] Client error ({addr}): {e}')
    finally:
        try:
            client.close()
        except:
            pass
        print(f'[TCP] Client disconnected: {addr} (total packets: {pkt_count})')


# =============================================================================
# ANALYTICS/STAT SERVER (Port 8992)
# =============================================================================

stat_app = Flask('stat_server')


@stat_app.route('/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE'])
@stat_app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def stat_catch_all(path):
    print(f'[STAT] {request.method} /{path} (ignored)')
    return jsonify({"result": 0})


def run_stat_server():
    stat_app.run(host='0.0.0.0', port=STAT_PORT, debug=False, use_reloader=False)


# =============================================================================
# START ALL SERVERS
# =============================================================================

if __name__ == '__main__':
    print('=' * 44)
    print('  Waker Local Server - وكر الاوغاد')
    print('=' * 44)

    # Port 9090 ("keepLiveServerPort") is actually HTTP with the same cipher
    # (client sends PUT /city/impart with base64(XOR(json))), NOT an RC4 binary
    # socket. Serve the same Flask app there so /city/* + the cipher encoder work.
    game9090 = threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=TCP_PORT, debug=False,
                               use_reloader=False, threaded=True),
        daemon=True)
    game9090.start()

    # Start stat server in background thread
    stat_thread = threading.Thread(target=run_stat_server, daemon=True)
    stat_thread.start()

    print(f'[HTTP] Game API server running on port {HTTP_PORT}')
    print(f'       URL: http://{SERVER_IP}:{HTTP_PORT}/')
    print(f'[STAT] Analytics server running on port {STAT_PORT}')
    print('=' * 44)
    print('Ready! Configure your device to point to this server.')
    print('=' * 44)

    # Start main HTTP API server (blocking)
    app.run(host='0.0.0.0', port=HTTP_PORT, debug=False, use_reloader=False)
