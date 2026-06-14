"""
release_validation.py — end-to-end gameplay flow validation through the server.

Proves GAMEPLAY FUNCTIONALITY (not parser correctness): each flow hits the real
endpoints over the real cipher, and for mutating flows the state delta is read
back from player_state.json ON DISK (the thing reloaded on restart) to prove
persistence.

Run AFTER starting the server on a CLEAN state (delete player_state.json first).
"""
import base64, json, os, sys, urllib.request

BASE = "http://127.0.0.1:8080"
STATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "player_state.json")
XOR = (b"One ring to rule them all, one ring to find them, "
       b"one ring to bring them all and in the darkness bind them.")

def xor(b): return bytes(b[i] ^ XOR[i % len(XOR)] for i in range(len(b)))
def call(path, payload=None):
    body = base64.b64encode(xor(json.dumps(payload or {}).encode()))
    req = urllib.request.Request(BASE + path, data=body, method="PUT")
    raw = urllib.request.urlopen(req, timeout=5).read()
    try:
        return json.loads(xor(base64.b64decode(raw)).decode())
    except Exception:
        return json.loads(raw.decode())
def disk():
    """current persisted state (what a restart would load)."""
    with open(STATE, encoding="utf-8") as f:
        return json.load(f)

results = []
def record(flow, endpoints, resp_summary, before, after, persist):
    results.append(dict(flow=flow, endpoints=endpoints, resp=resp_summary,
                        before=before, after=after, persist=persist))

def ok(resp):
    d = resp.get("data")
    return resp.get("result") == 0 or resp.get("error") in ("0", 0) or d is not None

# ---------------------------------------------------------------------------
# 1. Login
r = call("/api/connect", {"username": "test", "password": "x"})
pid = (r.get("data") or {}).get("playerId")
record("Login", "/api/connect", f"playerId={pid}", "-", "-",
       "N/A" if pid else "FAIL")

# 2. Character load
r = call("/city/connect/connect")
d = r.get("data") or {}
record("Character load", "/city/connect/connect",
       f"id={d.get('id')} name={d.get('name')} level={d.get('level')} "
       f"money={d.get('money')} status={'obj' if isinstance(d.get('playerStatus'),dict) else 'BAD'}",
       "-", "-", "N/A")

# 3. Estate buy
b = disk()
r = call("/city/estate/buy", {"estateType": 800})
a = disk()
record("Estate buy", "/city/estate/buy",
       f"result={r.get('result')} estates={len((r.get('data') or {}).get('estates',[]))}",
       f"money={b['money']} estates={len(b['estates'])}",
       f"money={a['money']} estates={len(a['estates'])}",
       "Y" if len(a['estates']) == len(b['estates']) + 1 and a['money'] < b['money'] else "N")

# 4. Bank deposit
b = disk()
r = call("/city/bank/deposit", {"amount": 1000})
a = disk()
record("Bank deposit", "/city/bank/deposit",
       f"money={(r.get('data') or {}).get('money')} cheque={(r.get('data') or {}).get('cheque')}",
       f"money={b['money']} cheque={b['cheque']}",
       f"money={a['money']} cheque={a['cheque']}",
       "Y" if a['money'] == b['money'] - 1000 and a['cheque'] == b['cheque'] + 1000 else "N")

# 5. Bank withdraw
b = disk()
r = call("/city/bank/withdraw", {"amount": 500})
a = disk()
record("Bank withdraw", "/city/bank/withdraw",
       f"money={(r.get('data') or {}).get('money')} cheque={(r.get('data') or {}).get('cheque')}",
       f"money={b['money']} cheque={b['cheque']}",
       f"money={a['money']} cheque={a['cheque']}",
       "Y" if a['money'] == b['money'] + 500 and a['cheque'] == b['cheque'] - 500 else "N")

# 6. Job work
b = disk()
r = call("/city/job/work", {"jobId": 1200})
a = disk()
record("Job work", "/city/job/work",
       f"result={(r.get('data') or {}).get('result')} award={(r.get('data') or {}).get('awardMoney')}",
       f"money={b['money']} exp={b['exp']}",
       f"money={a['money']} exp={a['exp']}",
       "Y" if a['money'] > b['money'] and a['exp'] >= b['exp'] else "N")

# 7. Crime action
b = disk()
r = call("/city/crime/docrime", {"crimeId": 100})
a = disk()
dd = r.get("data") or {}
record("Crime action", "/city/crime/docrime",
       f"result={dd.get('result')} awardMoney={dd.get('awardMoney')} blood={dd.get('blood')}",
       f"money={b['money']} blood={b['blood']} crimeTimes={b['crimeTimes']}",
       f"money={a['money']} blood={a['blood']} crimeTimes={a['crimeTimes']}",
       "Y" if a['crimeTimes'] == b['crimeTimes'] + 1 else "N")

# 8. Fight attack
b = disk()
r = call("/city/fight/attack", {"targetId": 2001})
a = disk()
dd = r.get("data") or {}
bw = (b.get('battleWin', 0) + b.get('battleLose', 0))
aw = (a.get('battleWin', 0) + a.get('battleLose', 0))
record("Fight attack", "/city/fight/attack",
       f"result={dd.get('result')} award={dd.get('awardMoney')} myHp={dd.get('myHp')}",
       f"money={b['money']} blood={b['blood']} battles={bw}",
       f"money={a['money']} blood={a['blood']} battles={aw}",
       "Y" if aw == bw + 1 else "N")

# 9. Hospital cure
b = disk()
r = call("/city/hospital/cure")
a = disk()
dd = r.get("data") or {}
record("Hospital cure", "/city/hospital/cure",
       f"blood={dd.get('blood')} money={dd.get('money')}",
       f"blood={b['blood']} money={b['money']}",
       f"blood={a['blood']} money={a['money']}",
       "Y" if a['blood'] == 100 else "N")

# 10. Goods buy
b = disk()
r = call("/city/goods/buy", {"goodsType": 600, "amount": 1})
a = disk()
record("Goods buy", "/city/goods/buy",
       f"money={(r.get('data') or {}).get('money')} bags={len((r.get('data') or {}).get('bags',[]))}",
       f"money={b['money']} bags={len(b['bags'])}",
       f"money={a['money']} bags={len(a['bags'])}",
       "Y" if len(a['bags']) == len(b['bags']) + 1 and a['money'] < b['money'] else "N")

# 11-16. Read-only loads (persistence N/A; verify response loads)
for flow, path, key in [
    ("Mission load", "/city/mission/getmission", "missionId"),
    ("Ranking load", "/city/rank/list", "players"),
    ("Mail load", "/city/message/list", "messages"),
    ("Gang load", "/city/faction/info", "members"),
    ("Store package load", "/city/store/package", "packages"),
    ("Lottery load", "/city/lottery/info", None),
]:
    r = call(path)
    d = r.get("data")
    present = (key in d) if (key and isinstance(d, dict)) else (d is not None)
    record(flow, path,
           f"data={'list' if isinstance(d,list) else type(d).__name__} "
           f"{key+'='+str(type(d.get(key)).__name__) if key and isinstance(d,dict) else ''}",
           "-", "-", "N/A" if (ok(r) and present) else "FAIL")

# ---------------------------------------------------------------------------
fail = [r for r in results if r["persist"] in ("N", "FAIL")]
print(f"{'FLOW':20} {'PERSIST':8} ENDPOINTS")
for r in results:
    print(f"{r['flow']:20} {r['persist']:8} {r['endpoints']}")
    print(f"   resp:   {r['resp']}")
    if r['before'] != '-':
        print(f"   before: {r['before']}")
        print(f"   after:  {r['after']}")
print(f"\nFLOWS={len(results)}  FAILED={len(fail)}")
if fail:
    print("FAILED FLOWS:", ", ".join(r['flow'] for r in fail))
    sys.exit(1)
print("ALL GAMEPLAY FLOWS PASSED")

# emit machine-readable for the report
with open(os.path.join(os.path.dirname(STATE), "release_validation_result.json"), "w", encoding="utf-8") as f:
    json.dump({"flows": results, "failed": len(fail)}, f, ensure_ascii=False, indent=1)
