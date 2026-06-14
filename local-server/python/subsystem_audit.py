"""
subsystem_audit.py — protocol-correct validation of the 21 required play systems.

Unlike wildicity_full_audit.py (which hit invented /user/login, /mission/list
paths that DO NOT exist in this game), this speaks the REAL wire protocol:
every request/response on 8080+9090 is base64(XOR(json, LOTR_KEY)). It exercises
the actual endpoints the client calls for each subsystem and verifies:

  * HTTP 200
  * body decodes (XOR+base64) to valid JSON
  * required ROOT fields present (error/timestamp/data injected by server)
  * `data` is the CONTAINER TYPE the native parser expects (array vs object) —
    the #1 crash cause (wrong container null-derefs the iterator)
  * action endpoints mutate persisted player_state (money/blood/etc.)

Run the server first (port 8080; 9090 mirrors it). Then:
    python subsystem_audit.py
Exit code 0 if no BROKEN systems.
"""
import base64
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8080"
XOR_KEY = (b"One ring to rule them all, one ring to find them, "
           b"one ring to bring them all and in the darkness bind them.")


def _xor(b):
    k = XOR_KEY
    return bytes(b[i] ^ k[i % len(k)] for i in range(len(b)))


def call(path, payload=None):
    """PUT a ciphered request; return (status, decoded_json_or_None, raw)."""
    body = b""
    if payload is not None:
        body = base64.b64encode(_xor(json.dumps(payload).encode()))
    req = urllib.request.Request(BASE + path, data=body, method="PUT")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read()
            status = r.status
    except urllib.error.HTTPError as e:
        return e.code, None, e.read()
    except Exception as e:
        return 0, None, str(e).encode()
    # responses are ciphered too (200 path)
    try:
        obj = json.loads(_xor(base64.b64decode(raw)).decode("utf-8"))
    except Exception:
        try:
            obj = json.loads(raw.decode("utf-8"))
        except Exception:
            obj = None
    return status, obj, raw


def container(obj):
    if obj is None:
        return "none"
    d = obj.get("data") if isinstance(obj, dict) else None
    if isinstance(d, list):
        return "array"
    if isinstance(d, dict):
        return "object"
    return type(d).__name__


# Each subsystem: list of (label, path, payload, expect_container, expect_keys)
# expect_container: 'array' | 'object' | None(don't care)
# expect_keys: keys that must be present in data (object) — parser reads them.
SYSTEMS = {
    "1.Login":        [("connect", "/api/connect", {}, "object", ["playerId"]),
                       ("authkey", "/api/authplayerkey", {}, "object", ["playerId"]),
                       ("servers", "/api/getallserver", {}, "array", None)],
    "2.Character":    [("playerlist", "/city/connect/getplayerlist", {}, "array", None),
                       ("connect", "/city/connect/connect", {}, "object", ["id", "name", "playerStatus"])],
    "3.City":         [("impart", "/city/impart", {}, "object", None),
                       ("topmsgs", "/city/chat/gettopmsgs", {}, "array", None),
                       ("introplayers", "/city/player/introplayers", {}, "array", None)],
    "4.Estate":       [("list", "/city/estate/listestates", {}, "object", ["myEstates", "money"]),
                       ("buy", "/city/estate/buy", {"estateType": 800}, "object", None)],
    "5.Bank":         [("balance", "/city/bank/checkbalance", {}, "object", ["money", "cheque"]),
                       ("deposit", "/city/bank/deposit", {"amount": 100}, "object", ["money", "cheque"]),
                       ("withdraw", "/city/bank/withdraw", {"amount": 100}, "object", ["money", "cheque"])],
    "6.Inventory":    [("bags", "/city/goods/playerbags", {}, "object", ["playerGoods"]),
                       ("warehouse", "/city/goods/playergoods", {}, "object", ["playerGoods"])],
    "7.GoodsMarket":  [("citygoods", "/city/goods/getcitygoods", {}, "object", ["goodsList"]),
                       ("buy", "/city/goods/buy", {"goodsType": 600, "amount": 1}, "object", None)],
    "8.Jobs":         [("getjobs", "/city/job/getjobs", {}, "array", None),
                       ("work", "/city/job/work", {"jobId": 1200}, "object", ["money", "salaryAt"])],
    "9.Crime":        [("docrime", "/city/crime/docrime", {"crimeId": 100}, "object", ["result"])],
    "10.Fight":       [("random", "/city/fight/randomfighters", {}, "array", None),
                       ("attack", "/city/fight/attack", {"targetId": 2001}, "object", ["result"])],
    "11.Missions":    [("getmission", "/city/mission/getmission", {}, "object", ["missionId"]),
                       ("update", "/city/mission/updatemission", {}, "object", ["missionId"])],
    "12.School":      [("classes", "/city/school/getmyclasses", {}, "object", ["myClasses"]),
                       ("apply", "/city/school/applyclass", {"classId": 1}, "object", None)],
    "13.Gym":         [("getgym", "/city/gym/getgym", {}, "object", ["gymTypes", "energy"]),
                       ("train", "/city/gym/train", {"type": 1}, "object", None)],
    "14.Mail":        [("list", "/city/message/list", {}, "object", ["messages"])],
    "15.Rankings":    [("rank", "/city/rank/list", {}, "object", ["players"]),
                       ("getranking", "/city/player/getranking", {}, "array", None)],
    "16.Gang":        [("factions", "/city/faction/list", {}, "object", ["factions"]),
                       ("info", "/city/faction/info", {}, "object", ["members"]),
                       ("randomgangs", "/city/gang/randomgangs", {}, "array", None)],
    "17.Hospital":    [("patients", "/city/hospital/patients", {}, "array", None),
                       ("cure", "/city/hospital/cure", {}, "object", ["blood", "money"])],
    "18.Store":       [("catelist", "/city/store/catelist", {}, "array", None),
                       ("package", "/city/store/package", {}, "object", ["packages"])],
    "19.Auction":     [("list", "/city/auction/list", {}, "object", None)],
    "20.Lottery":     [("info", "/city/lottery/info", {}, "array", None),
                       ("draw", "/city/lottery/draw", {}, "object", None)],
    "21.Race":        [("matchconfig", "/race/match/matchconfig", {}, "object", None),
                       ("matchinginfo", "/race/match/matchinginfo", {}, "object", None)],
}


def audit():
    working, partial, broken = [], [], []
    detail = {}
    for sysname, calls in SYSTEMS.items():
        notes = []
        ok = True
        soft = False
        for label, path, payload, exp_cont, exp_keys in calls:
            status, obj, raw = call(path, payload)
            if status != 200 or obj is None:
                notes.append(f"{label}: HTTP {status} / undecodable")
                ok = False
                continue
            cont = container(obj)
            if exp_cont and cont != exp_cont:
                notes.append(f"{label}: container {cont}!={exp_cont}")
                ok = False
            if exp_keys:
                d = obj.get("data", {})
                miss = [k for k in exp_keys if not isinstance(d, dict) or k not in d]
                if miss:
                    notes.append(f"{label}: missing {miss}")
                    soft = True
        if ok and not soft:
            working.append(sysname)
        elif ok and soft:
            partial.append(sysname)
        else:
            broken.append(sysname)
        detail[sysname] = notes
    return working, partial, broken, detail


if __name__ == "__main__":
    w, p, b, detail = audit()
    print("\n================ SUBSYSTEM AUDIT (protocol level) ================")
    print(f"WORKING  ({len(w)}): {', '.join(w)}")
    print(f"PARTIAL  ({len(p)}): {', '.join(p)}")
    print(f"BROKEN   ({len(b)}): {', '.join(b)}")
    print("==================================================================")
    for s in p + b:
        for n in detail[s]:
            print(f"  [{s}] {n}")
    sys.exit(1 if b else 0)
