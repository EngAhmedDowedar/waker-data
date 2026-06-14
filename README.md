# Waker — Legacy Game Server Restoration (Handover)

A Flask server that revives the dead-server Android game
`com.anansimobile.city_ar` (Arabic gangster game). The client is patched to talk
to `127.0.0.1`; this server answers its ciphered API so the game boots and plays.

## Getting Started (3 steps)

**1. Install dependencies**
```bash
cd local-server/python
pip install -r requirements.txt          # Flask 3 + Werkzeug
```

**2. Run the server**
```bash
# Windows (REQUIRED: forces UTF-8 — the startup banner has Arabic text and
# crashes on the default cp1252 console otherwise)
set PYTHONUTF8=1 && python server.py
# macOS / Linux
PYTHONUTF8=1 python server.py
```
You should see it listening on `0.0.0.0:8080` (game API), `9090` (keepalive),
`8992` (analytics). Leave it running.

**3. Connect the game client**
```bash
adb install -r client/waker-usb-signed.apk     # the 127.0.0.1 build
adb reverse tcp:8080 tcp:8080                   # tunnel device -> this PC over USB
adb reverse tcp:9090 tcp:9090
adb reverse tcp:8992 tcp:8992
adb shell pm clear com.anansimobile.city_ar     # forces the direct-login path
adb shell am start -n com.anansimobile.city_ar/.Main
```
The game boots to the city. **Every unimplemented route the client hits is auto-
captured to `discovered_apis.json`** (and prints `[RADAR] Captured /route`) while
returning a safe "Coming Soon" dialog instead of crashing — navigate the game,
then implement the captured routes in `server.py`.

## Key files
- `local-server/python/server.py` — all Flask routes (the work happens here).
- `local-server/python/player_state.py` — persisted player state (money/stats/inventory).
- `local-server/python/city_loader.py` — loads the bundled `.city` config tables.
- `local-server/python/gamedata/` — 94 decoded config tables (REQUIRED).
- `local-server/python/discovered_apis.json` — radar log of routes still to build.
- `SERVER_REQUIREMENTS.md` / `IMPLEMENTATION_PRIORITY.md` — what's left to build.

## Conventions (read before editing `server.py`)
- Requests are `base64(XOR(json))`; **always** read params via `_req_json()` /
  `_req_int()` (they decode the cipher AND lift the `command` envelope).
- **Never** return bare `{}` / `[]` for unimplemented features — it crashes the
  client parser. Return `_coming_soon()` (safe dialog) or a real typed shape.
- Any route that changes player data must `player_state.save()`.
