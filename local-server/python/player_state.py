"""
player_state.py — single-player mutable state + JSON persistence for the Waker
local server (Phase 1: Estate, Goods, Job, Crime).

Source of truth: analyze/docs/PLAYER_STATE_IMPLEMENTATION_PLAN.md §0. Only the
fields that action endpoints mutate are stored here; catalog data (prices,
rewards) stays read-only in server.GAMEDATA (the decoded .city tables).

The state is one dict persisted to player_state.json next to this file, loaded
once at import, mutated in-place by endpoints, and saved after each mutation.
"""
import json
import os
import time
import threading

_HERE = os.path.dirname(os.path.abspath(__file__))
_STATE_FILE = os.path.join(_HERE, 'player_state.json')
_lock = threading.RLock()
_player = None


def now():
    return int(time.time())


def default_state():
    """Seed values mirror the boot-safe _make_player() defaults."""
    t = now()
    return {
        # identity
        'id': 1, 'name': 'Abu Hassan', 'level': 20, 'exp': 0,
        # currencies
        'money': 5000000, 'cheque': 5000, 'gold': 100000,
        # mission (scalar)
        'missionId': 1, 'missionProgress': 0,
        # resources
        'energy': 100, 'energyUp': 100,
        'blood': 100, 'bloodUp': 100,
        'happy': 100, 'happyUp': 100,
        # status / cooldown
        'coolingTime': 0,
        'playerStatus': {'cityId': 1, 'status': 0, 'statusAt': 0,
                         'statusDuration': 0, 'statusExtra': 0,
                         'statusExtraDesc': '', 'noFightedExpireAt': 0},
        # inventory (arrays of CGoods)
        'goods': [], 'bags': [],
        # estates (array of CHouse)
        'estates': [], 'liveEstate': 0,
        # job state
        'jobCategory': {}, 'salaryAt': 0,
        # crime state
        'crimeSkills': [], 'crimeSuccess': 0, 'crimeTimes': 0,
        'thriceNum': 0, 'jailHalved': 0,
        # id allocators
        '_next_house_id': 1, '_next_goods_id': 1,
    }


def load():
    """Return the live player dict (loaded from disk on first call)."""
    global _player
    with _lock:
        if _player is None:
            if os.path.exists(_STATE_FILE):
                try:
                    _player = json.load(open(_STATE_FILE, encoding='utf-8'))
                    # backfill any keys added since the file was written
                    for k, v in default_state().items():
                        _player.setdefault(k, v)
                except Exception:
                    _player = default_state()
            else:
                _player = default_state()
        return _player


def save():
    with _lock:
        if _player is not None:
            tmp = _STATE_FILE + '.tmp'
            json.dump(_player, open(tmp, 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
            os.replace(tmp, _STATE_FILE)


def reset():
    """Reset to defaults (test helper)."""
    global _player
    with _lock:
        _player = default_state()
        save()
        return _player


# --- element builders (verified shapes from the subsystem reports) ----------

def make_goods(gtype, amount, category=0, bought_price=0, gid=None):
    """CGoods (CGoods::Parse): id,type,amount,category,boughtPrice,canUseTime,convertGoods."""
    p = load()
    if gid is None:
        gid = p['_next_goods_id']
        p['_next_goods_id'] += 1
    return {'id': gid, 'type': gtype, 'amount': amount, 'category': category,
            'boughtPrice': bought_price, 'canUseTime': 0, 'convertGoods': 0}


def make_house(estate_type, owner_id=1, owner_name='Abu Hassan', hid=None,
               sell_price=1000, rent_price=100):
    """CHouse (CHouse::Parse, 22 keys). estate_type MUST be a property.city id
    (800-817) or GetById null-derefs (fault 0x84)."""
    p = load()
    if hid is None:
        hid = p['_next_house_id']
        p['_next_house_id'] += 1
    return {'id': hid, 'estateType': estate_type, 'systemEstate': 0,
            'decoration1': 0, 'decoration2': 0, 'decoration3': 0,
            'maid1': 0, 'maid1ExpireAt': 0, 'maid2': 0, 'maid2ExpireAt': 0,
            'ownerId': owner_id, 'renterId': 0, 'renterName': '',
            'ownerName': owner_name, 'status': 1,
            'sellPrice': sell_price, 'rentPrice': rent_price,
            'rentExpireAt': 0, 'rentDays': 0, 'maintainExpireAt': 0,
            'customHouseAt': 0, 'customHouseTag': ''}


def add_crime_skill(crime_idx):
    """Increment per-crime experience (crimeSkills[] = [{crimeIdx,crimeNum}])."""
    p = load()
    for e in p['crimeSkills']:
        if e['crimeIdx'] == crime_idx:
            e['crimeNum'] += 1
            return e
    e = {'crimeIdx': crime_idx, 'crimeNum': 1}
    p['crimeSkills'].append(e)
    return e
