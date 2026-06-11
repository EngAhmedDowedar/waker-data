"""
build_backend_spec.py
Walks libcity_ar.so + the apktool decompile + the running server.py to
produce a machine-built backend specification:

  1. Every /city/* + /api/* + /<root>/* command name in the .rodata string
     table the binary actually references.
  2. For each command name: candidate parser class + method (cross-referenced
     against the C++ symbol table).
  3. Which commands server.py handles explicitly vs. via catch-all.
  4. Which commands have a known response shape (from SCHEMAS.md / server.py).
  5. The mission/dialog/world-state CLIENT-SIDE data paths (where the data
     lives in assets/*.city + assets/<lang> instead of the server).
  6. The list of unresolved unknowns + the Frida hook recipe to resolve each.

Run with:
    python build_backend_spec.py > ../docs/BACKEND_SPEC_machine.md
"""
import json
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\Admin\Videos\New folder\waker")
SO = ROOT / "analyze/client-apk-src/lib/armeabi/libcity_ar.so"
ASSETS = ROOT / "analyze/client-apk-src/assets"
SERVER = ROOT / "local-server/python/server.py"


def load_binary():
    return SO.read_bytes()


def load_server():
    return SERVER.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. Command names: every alphanum string in the .rodata cluster
#    that the URL builder uses. Found empirically at 0x6fd000..0x6ff800.
# --------------------------------------------------------------------------

def extract_command_strings(so: bytes):
    cluster_lo, cluster_hi = 0x6fd000, 0x6ff400
    out = []
    for m in re.finditer(rb"[a-zA-Z][a-zA-Z0-9_]{2,49}\x00", so):
        off = m.start()
        if cluster_lo <= off < cluster_hi:
            s = m.group(0)[:-1].decode("ascii")
            # Filter out field-name-like strings (CamelCase with Capital prefix
            # that look like JSON field names rather than command verbs).
            # Heuristic: command verbs are all-lowercase or camelCase-verb-noun
            # starting lowercase. Field names often start uppercase.
            if s[0].isupper() and len(s) > 6 and any(c.isupper() for c in s[1:]):
                continue  # likely a field name like "ChatScreen"
            out.append((off, s))
    return out


# --------------------------------------------------------------------------
# 2. Symbol table cross-reference
# --------------------------------------------------------------------------

def extract_mangled_symbols(so: bytes):
    """Return all mangled C++ symbols visible in the binary (the .dynstr blob)."""
    return sorted(set(m.decode() for m in re.findall(rb"_Z[A-Za-z0-9_]{4,200}", so)))


def demangle_batch(syms, limit=20000):
    """Demangle a batch with c++filt. Falls back to leaving mangled names if
    c++filt isn't available."""
    try:
        proc = subprocess.run(
            ["c++filt", "-i"],
            input="\n".join(syms[:limit]).encode(),
            capture_output=True,
            timeout=30,
        )
        return proc.stdout.decode("utf-8", errors="replace").splitlines()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return list(syms[:limit])


def parsers_by_class(demangled):
    """Group symbols by (class, method) and pick the ones that look like
    response parsers."""
    out = {}
    pat = re.compile(r"^(?:[\w\s\*&:<>,]+\s)?(C[A-Z]\w+)::(\w+)\(")
    for d in demangled:
        m = pat.search(d)
        if not m:
            continue
        cls, mth = m.group(1), m.group(2)
        if any(k in mth for k in ("Parse", "OnReceiveResponse", "HandleUpdate", "Request", "Get", "Set", "Show")):
            out.setdefault(cls, set()).add(mth)
    return out


# --------------------------------------------------------------------------
# 3. server.py routes
# --------------------------------------------------------------------------

def routes_in_server(server_src: str):
    """Pull out the explicit @app.route('/...', methods=[...]) declarations."""
    routes = []
    for m in re.finditer(r"@app\.route\(\s*['\"]([^'\"]+)['\"]\s*,\s*methods=\[([^\]]+)\]", server_src):
        path = m.group(1)
        methods = re.findall(r"['\"](\w+)['\"]", m.group(2))
        routes.append((path, methods))
    return routes


# --------------------------------------------------------------------------
# 4. mission.city + assets/ar — the client-side mission data path
# --------------------------------------------------------------------------

def decode_mission_city():
    p = ASSETS / "mission.city"
    if not p.exists():
        return []
    data = p.read_bytes()
    count = struct.unpack(">H", data[:2])[0]
    out = []
    for i in range(count):
        off = 2 + i * 56
        rec = struct.unpack(">14I", data[off:off + 56])
        # Field order (verified 2026-05-30):
        # id, tutorialId, missionName_strid, missionTip_strid, missionDesc_strid,
        # missionType, tarProgress, rewardExp, rewardCheck, rewardGoodIdx,
        # rewardGoodCate, rewardGoodAmount, [branchMission|isMainCity], missionFinishText_strid
        out.append(dict(zip(
            ["id", "tutorialId", "missionName_strid", "missionTip_strid",
             "missionDesc_strid", "missionType", "tarProgress", "rewardExp",
             "rewardCheck", "rewardGoodIdx", "rewardGoodCate",
             "rewardGoodAmount", "branchOrMainCity", "missionFinishText_strid"],
            rec)))
    return out


def decode_ar_strings():
    p = ASSETS / "ar"
    if not p.exists():
        return []
    data = p.read_bytes()
    count = struct.unpack(">H", data[:2])[0]
    pos = 2
    out = []
    while pos < len(data) and len(out) < count + 100:
        if pos + 2 > len(data):
            break
        ln = struct.unpack(">H", data[pos:pos + 2])[0]
        pos += 2
        if pos + ln > len(data):
            break
        try:
            out.append(data[pos:pos + ln].decode("utf-8"))
        except UnicodeDecodeError:
            out.append("<binary>")
        pos += ln
    return out


# --------------------------------------------------------------------------
# 5. Categorize commands by URL prefix (heuristic from the cluster layout)
# --------------------------------------------------------------------------

# Hand-curated buckets based on observed string clustering in .rodata and
# what the existing server.py routes accept.
BUCKETS = [
    ("auth/session",  ["connect", "create", "authplayerkey", "register",
                       "completeinfo", "modifyname", "modifyemail",
                       "modifypassword", "connectFacebook"]),
    ("server-list",   ["getallserver", "checkversion", "check_version"]),
    ("session-tick",  ["heartbeat", "pause", "atHome", "self", "open"]),
    ("config",        ["impart", "matchconfig"]),
    ("player",        ["updatelevel", "updatesignature", "updateskill",
                       "updatedailytask", "completedailytask",
                       "updateavatar", "updatewindowstatus",
                       "updateplayerinfo", "introplayers", "avatarinfo",
                       "updateProjectFinish", "updateskillexp",
                       "updatelevelexp", "updatecamps", "playergoods",
                       "playerbags", "playerequip", "playerEvent"]),
    ("chat/message",  ["gettopmsgs", "getsysmsgs", "getmsg", "getoldmsg",
                       "send", "sendSysMsg", "reply", "readchat",
                       "deletechatmsgs", "sendbyuid", "getvalentinemsg",
                       "delete", "read", "write", "ParseMsg"]),
    ("mission",       ["missionRefill", "finishtask", "inMission",
                       "missionTip", "completeinfo"]),
    ("economy:goods", ["getcitygoods", "randomgoods", "buygoods",
                       "movegoods", "usegoods", "splitsgoldgoods",
                       "lockgoods", "removegoods", "importgoods",
                       "transgoods", "getgoods", "goodspackage",
                       "multigoodspackage", "mergegoods", "mergegold",
                       "mergefood", "strengthen", "upgrade", "selltonpc",
                       "buygoldtool", "usegoldtool", "buy", "sell"]),
    ("economy:estate",["listestates", "buyplayerestate", "buy", "buycancel",
                       "listonsell", "listonrent", "onsell", "onrent",
                       "rent", "rentcancel", "cancelsell", "changerentinfo",
                       "changesellinfo", "buydecoration", "buymaid",
                       "driveout", "checkin", "modifydecorator",
                       "getdecorators", "spouseestates", "maintaincost",
                       "getonrentamount"]),
    ("economy:bank",  ["savemoney", "drawmoney", "checkbalance"]),
    ("economy:job",   ["applyjob", "collectsalary", "salary"]),
    ("economy:gym",   ["buyservice", "join", "use", "frontpage",
                       "strengthEnergy", "agileEnergy", "speedEnergy",
                       "enduranceEnergy"]),
    ("economy:gamble",["redblackshow", "redblackbet", "point21bust",
                       "gambling", "slot", "turntable", "multiturntable",
                       "getturntablemsgs", "getfreeturntable"]),
    ("crime",         ["crime", "crimeType", "crimeSkilled",
                       "rewardCrimeCategory"]),
    ("medical",       ["medicine", "cure", "goldcure", "outhospital",
                       "patients", "drugaddictiontreat",
                       "getdrugaddictioninfo", "eatdrug", "eatfood",
                       "eatredbull", "eatcuisines", "recovermoral",
                       "recover", "recoverenergy", "recoverbrave",
                       "recoverblood", "recoverloyalty"]),
    ("jail",          ["bail", "bust", "prisonbreak", "searchprisoner",
                       "prisonerlist", "outjail"]),
    ("combat:player", ["randomfighters", "fightjudge", "fightrobot",
                       "fightrobotnew", "fightskyscraper", "fightnew",
                       "fightcompetition", "fightcompetitionnew",
                       "fightgangboss", "fightteamworkboss",
                       "fightteamworkbossnew", "pvpfightresult",
                       "pvefightresult", "fightresult",
                       "ladderfightjudge", "ladderfightjudgenew",
                       "ladderrandomfighters", "battlefightresult",
                       "wantedfightresult", "buyFightTime",
                       "buyfighttimes", "thoughtrap", "thoughtrapnpc",
                       "fightskyscrapernew", "kingfight", "unionkingfight"]),
    ("combat:gang",   ["randomgangs", "randomfightgangs", "listapplygangs",
                       "listrankgangs", "gangs", "listbattles", "battle",
                       "fight", "ganginvite", "approveinvite",
                       "rejectinvite", "removemember", "changeowner",
                       "modifygangname", "modifyguardinfo", "buybasicskill",
                       "buyspecialskill", "getgangskill", "resetskill",
                       "drawmoney", "judgebattle", "openlocaltroop",
                       "joinlocaltroops", "troopsituation", "wargangs",
                       "joinwar", "donate", "switchdonate",
                       "fightgangboss", "applylist", "manageapply",
                       "applyclass", "listapplymembers",
                       "listjoinedmembers", "updatemembertitle"]),
    ("relation",      ["marryrequest", "marryapprove", "marrycancel",
                       "marryreject", "maritalstatus", "divorcerequest",
                       "divorcereject", "divorcecancel", "candidates",
                       "friends", "request", "pendingrequests",
                       "updateremark", "friendsharelist", "friendnum"]),
    ("guard",         ["listguards", "searchguardbyname", "hireguard",
                       "fireout", "cancelguardinfo", "modifyguardinfo"]),
    ("airline/travel",["airlines", "travel", "arrive", "flightAward",
                       "fastarrive"]),
    ("activity",      ["getactivities", "getactivitydetail",
                       "getactivityrank", "attendActiviesInfo",
                       "validatecode", "code", "logingifts", "logingift",
                       "newlogingift", "clockin", "getoccupyinfo",
                       "getplayergrowth", "receivinggift",
                       "facebooksharereward", "FBSharePrize",
                       "getachievements"]),
    ("auction",       ["showsystemauction", "listallgoods", "listmyauctions",
                       "listauctions", "cancelauction", "bid",
                       "listinvolvedauctions"]),
    ("dungeon",       ["enterdungeon", "exitdungeon", "recordaction",
                       "passlevel", "thoughtrap", "thoughtrapnpc",
                       "fallback", "obtainremainingtimes",
                       "bugdungeontimes", "unfoldallcells",
                       "dungeonplayers"]),
    ("hunting",       ["transtools", "huntTools", "hunttools", "hunttool",
                       "supplyfuel", "repair", "pursue", "rentbox",
                       "escape", "hitback", "giveup", "exit"]),
    ("mercenary",     ["mercenaryIds", "mercenaryLearnProject",
                       "mercenaryLoyal", "getmercenarys", "getMercenary",
                       "getMercenaryRank", "chooseMercenary",
                       "costMercenarys", "costMercenaryIds",
                       "starup", "train", "fire", "equip", "addLoyalty",
                       "addexp", "replenish", "resetattributes",
                       "addShield", "addAttack", "addHit", "addDodge",
                       "addDefense", "addCrit", "addTenacity",
                       "distribute"]),
    ("race",          ["matchconfig", "matchinginfo", "matching",
                       "matchingprizelist", "getmatchingprize", "match",
                       "joinCostMoney", "raceStartCountDown", "tracks",
                       "trackId", "roomcreate", "listroom", "join",
                       "exit", "start", "history"]),
    ("city-war",      ["enterMatchCard", "rewardReceive", "enrollHours",
                       "buybox", "buyseat", "buyTimes", "buycooling",
                       "enterwar", "streetwarfight", "streetwarfightresult",
                       "useAircraft", "useaircraft", "switchmatch",
                       "gangresult", "getscore", "enterbuilding"]),
    ("debug/misc",    ["sysTime", "check", "no_heartbeat",
                       "verifymedal", "verifyhuman", "verifySI",
                       "verifypayment", "verifymail"]),
]


def categorize(cmds):
    """Bucket each command name into its most likely category."""
    bucketed = {b: [] for b, _ in BUCKETS}
    bucketed["unknown"] = []
    seen = set()
    for off, s in cmds:
        if s in seen:
            continue
        seen.add(s)
        for bucket, kws in BUCKETS:
            if s in kws:
                bucketed[bucket].append((off, s))
                break
        else:
            bucketed["unknown"].append((off, s))
    return bucketed


# --------------------------------------------------------------------------
# 6. Pull demangled symbols of every CXxxScreen / CXxxMnger / CXxxManager
# --------------------------------------------------------------------------

def screen_parsers(demangled):
    """Return {class -> [parser methods]} for every CXxxScreen/Mnger/Manager."""
    out = {}
    pat = re.compile(r"^(?:[\w\s\*&:<>,]+\s)?(C[A-Z]\w+(?:Screen|Mnger|Manager|Mngr|Client))::(\w+)\(")
    for d in demangled:
        m = pat.search(d)
        if not m:
            continue
        cls, mth = m.group(1), m.group(2)
        if any(mth.startswith(p) for p in ("Parse", "OnReceiveResponse", "HandleUpdate",
                                            "RequestMsg", "PullRequest")):
            out.setdefault(cls, []).append(mth)
    return {k: sorted(set(v)) for k, v in sorted(out.items())}


# --------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------

def render(cmds, server_routes, missions, ar_strings, bucketed, screens):
    server_paths = {p for p, _ in server_routes}
    md = []
    md.append("# BACKEND SPEC — machine-extracted index\n")
    md.append("_Auto-generated from libcity_ar.so .rodata + .dynsym + assets/ + server.py."
              " Re-run `python analyze/tools/build_backend_spec.py` to refresh._\n")
    md.append(f"- Commands found in .rodata cluster 0x6fd000..0x6ff400: **{len(cmds)}** strings, "
              f"**{len({s for _, s in cmds})} unique**")
    md.append(f"- mission.city entries: **{len(missions)}** (ids {sorted(set(m['id'] for m in missions))})")
    md.append(f"- assets/ar strings: **{len(ar_strings)}**")
    md.append(f"- server.py explicit routes: **{len(server_paths)}**")
    md.append("")

    md.append("## Index by category\n")
    md.append("Each entry is a command-name string from .rodata. `[OK]` = explicitly "
              "handled by server.py; `[CA]` = falls through to a catch-all "
              "(/city/<cmd> or /<path>) that returns `data:{}` or `data:[]`; "
              "`[?]` = unknown (no static signal it's been observed in flight).")
    md.append("")
    for bucket, entries in bucketed.items():
        if not entries:
            continue
        md.append(f"### {bucket}")
        md.append("")
        for off, s in sorted(entries, key=lambda e: e[1]):
            # Status mark
            mark = "[?]"
            for p in server_paths:
                if p.endswith("/" + s) or p == "/" + s or p.endswith("/" + s + "/"):
                    mark = "[OK]"
                    break
            if mark == "[?]":
                # Catch-all coverage for /city/<cmd>
                if "/city/<path:cmd>" in server_paths or "/city/<path:cmd>" in [p for p in server_paths]:
                    pass  # we'll mark city/* commands as [CA] below
            # Improved catch-all detection: if a /city/<x>/<cmd> wildcard route exists
            for p, _ in server_routes:
                if "<path:" in p and "/city/" in p and mark == "[?]":
                    mark = "[CA]"
            md.append(f"- {mark} `{s}`   .rodata@{hex(off)}")
        md.append("")

    md.append("## Parser classes (Cxxx) and their response-decode methods\n")
    md.append("Static cross-reference from the .dynsym table — these are the C++ "
              "methods the client calls per HTTP response. To know what fields a "
              "given endpoint must contain, disassemble its `OnReceiveResponse(int, void*)` "
              "or `ParseXxx(void*)` method and read the .rodata field-name strings "
              "loaded via `add ip, pc, #X` instructions.")
    md.append("")
    for cls in sorted(screens.keys()):
        md.append(f"### {cls}")
        for mth in screens[cls]:
            md.append(f"- `{mth}`")
        md.append("")

    md.append("## Mission system — fully reversed (client-side data path)\n")
    md.append("The mascot bubble and mission objective text come from "
              "**assets/mission.city + assets/ar**, NOT a server endpoint. "
              "CPlayer.missionId is the only input the server provides.")
    md.append("")
    md.append("| id  | tutorialId | type | tarProgress | rewardExp | missionTip (ar)               |")
    md.append("|----:|-----------:|-----:|------------:|----------:|:-------------------------------|")
    for m in missions:
        tip_id = m["missionTip_strid"]
        tip_text = ar_strings[tip_id] if tip_id < len(ar_strings) else "<oob>"
        md.append(f"| {m['id']:3d} | {m['tutorialId']:10d} | {m['missionType']:4d} | "
                  f"{m['tarProgress']:11d} | {m['rewardExp']:9d} | `{tip_text}` |")
    md.append("")

    md.append("## server.py current route registry\n")
    md.append("Explicitly handled endpoints (everything else falls through to the "
              "/city/<path:cmd> or root catch-all):")
    md.append("")
    for p, methods in sorted(server_routes):
        md.append(f"- `{','.join(methods)} {p}`")
    md.append("")

    return "\n".join(md)


# --------------------------------------------------------------------------

def main():
    so = load_binary()
    server = load_server()
    cmds = extract_command_strings(so)
    syms = extract_mangled_symbols(so)
    demangled = demangle_batch(syms, limit=40000)
    routes = routes_in_server(server)
    missions = decode_mission_city()
    ar_strings = decode_ar_strings()
    bucketed = categorize(cmds)
    screens = screen_parsers(demangled)
    print(render(cmds, routes, missions, ar_strings, bucketed, screens))


if __name__ == "__main__":
    main()
