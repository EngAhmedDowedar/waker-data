"""
test_phase1.py — exercises Phase 1 player-state endpoints via the Flask test
client (no game, no emulator). Verifies the verified shapes and that action
endpoints mutate + persist player_state. Run: python test_phase1.py
"""
import json
import sys

import player_state
import server

server.ENCODE_RESPONSES = False  # inspect plaintext JSON


def body(resp):
    return json.loads(resp.data)['data']


def main():
    player_state.reset()
    c = server.app.test_client()
    ok = 0
    fail = 0

    def check(name, cond, detail=''):
        nonlocal ok, fail
        if cond:
            ok += 1
            print(f'  PASS {name} {detail}')
        else:
            fail += 1
            print(f'  FAIL {name} {detail}')

    print('== Estate ==')
    d = body(c.put('/city/estate/listestates'))
    check('listestates is object', isinstance(d, dict))
    check('listestates.myEstates is array', isinstance(d.get('myEstates'), list))
    check('listestates.spouseEstates is array', isinstance(d.get('spouseEstates'), list))

    before = player_state.load()['money']
    d = body(c.put('/city/estate/buy', data=json.dumps({'estateType': 800})))
    check('buy returns buy_house', isinstance(d.get('buy_house'), dict),
          f"estateType={d.get('buy_house',{}).get('estateType')}")
    check('buy returns estates array', isinstance(d.get('estates'), list)
          and len(d['estates']) == 1)
    check('buy estateType valid (800-817)', 800 <= d['buy_house']['estateType'] <= 817)
    after = player_state.load()['money']
    check('buy deducted money', after < before, f'{before}->{after}')

    d = body(c.put('/city/estate/listestates'))
    check('listestates now shows owned estate', len(d['myEstates']) == 1)

    print('== Goods ==')
    d = body(c.put('/city/goods/playerbags'))
    check('playerbags uses playerGoods key', 'playerGoods' in d)
    check('playerbags has specialities', 'specialities' in d)
    check('no legacy bags/goods keys', 'bags' not in d and 'goods' not in d)
    d = body(c.put('/city/goods/playergoods'))
    check('warehouse has playerGoods/tradeGoods/specialities',
          all(k in d for k in ('playerGoods', 'tradeGoods', 'specialities')))

    print('== Job ==')
    m0 = player_state.load()['money']
    d = body(c.put('/city/job/work', data=json.dumps({'jobId': 1200})))
    check('work returns money+salaryAt', 'money' in d and 'salaryAt' in d)
    m1 = player_state.load()['money']
    check('work awarded salary', m1 > m0, f'{m0}->{m1}')
    check('jobCategory recorded', len(player_state.load()['jobCategory']) >= 1)

    print('== Crime ==')
    cm0 = player_state.load()['money']
    results = [body(c.put('/city/crime/docrime', data=json.dumps({'crimeId': 100})))
               for _ in range(20)]
    keys = {'result', 'awardMoney', 'awardExp', 'statusDuration', 'blood',
            'lostToolFlag', 'consumeNum', 'awardGoodsType'}
    check('docrime result has all verified keys',
          all(keys <= set(r) for r in results))
    check('docrime result is object of scalars',
          all(isinstance(r, dict) and all(not isinstance(v, (list, dict))
              for v in r.values()) for r in results))
    succ = sum(1 for r in results if r['result'] == 1)
    check('crime mix of success/fail', 0 < succ < 20, f'{succ}/20 success')
    check('crimeSkills tracked',
          any(e['crimeIdx'] == 100 and e['crimeNum'] == 20
              for e in player_state.load()['crimeSkills']))
    check('cooldown set in playerStatus',
          player_state.load()['playerStatus']['statusDuration'] in (60, 300))

    print('== Persistence ==')
    player_state._player = None  # force reload from disk
    reloaded = player_state.load()
    check('state persisted to disk', reloaded['crimeTimes'] == 20
          and len(reloaded['estates']) == 1)

    print('== CPlayer payload reflects state ==')
    server.ENCODE_RESPONSES = False
    d = body(c.put('/city/connect/connect'))
    check('connect.money == persisted money', d['money'] == reloaded['money'])
    check('connect.estates is array w/ owned house', len(d['estates']) == 1)
    check('connect.goods/bags arrays', isinstance(d['goods'], list)
          and isinstance(d['bags'], list))

    print(f'\n{ok} passed, {fail} failed')
    return 1 if fail else 0


if __name__ == '__main__':
    sys.exit(main())
