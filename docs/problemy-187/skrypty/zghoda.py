# -*- coding: utf-8 -*-
"""ZAVDANNYA-187, п. 2–3: згода моделей. 120 кандидатів сита MV-195 пропорційно за видами (той самий сталий вибір за хешем,
що в perevirka/problemy_183.py, тож це підмножина вибірки 183). Прогони: A — Sonnet (кеш повтору 183), B — Sonnet ще раз
(окремий кеш = новий виклик), C — Opus. Запуск: python zghoda.py <kand.pkl> <kesh_A> <тека> [моделі]"""
import sys, os, json, pickle, collections
sys.path.insert(0, '/home/user/d103/src'); sys.path.insert(0, '/home/user/d103/perevirka')
import problemy_shi as PS, problemy_183 as K
kand = pickle.load(open(sys.argv[1], 'rb')); keshA, out = sys.argv[2], sys.argv[3]
os.makedirs(out, exist_ok=True)
vyb, po = K.vybirka(kand, 120)
usi = [k for v in vyb.values() for k in v]
print('вибірка', len(usi), {t: len(v) for t, v in vyb.items()}, flush=True)
instr = open(PS.INSTRUKTSIIA, encoding='utf-8').read()
zz = [PS.zapyt(k, instr) for k in usi]
log = lambda *x: print(*x, flush=True)
progony = [('A_sonnet_1', 'sonnet', keshA), ('B_sonnet_2', 'sonnet', os.path.join(out, 'kesh_B')),
           ('C_opus', 'opus', os.path.join(out, 'kesh_C'))]
if len(sys.argv) > 4: progony = [p for p in progony if p[0] in sys.argv[4].split(',')]
for nazva, model, kesh in progony:
    vk = PS.Vyklyky(kesh, 8, log)
    tt = vk(model, [q['tekst'] for q in zz], nazva)
    r = []
    for k, q, t in zip(usi, zz, tt):
        v, vady = PS.pereviryty(t, q)
        r.append(dict(id=PS.kliuch(k), vyd=K.vyd(k), mistse=K.bez_nomera(k['mistse']), n=k['n'],
                      rishennia=('вада' if vady else (v or {}).get('rishennia')), shi=(v or {}).get('nazva_shi') or (v or {}).get('nazva'),
                      spilne=(v or {}).get('spilne'), znizheno=(v or {}).get('znizheno'), vady=vady, opysy=(v or {}).get('opysy'),
                      chastka=(v or {}).get('chastka'), politsiia=(v or {}).get('politsiia'), syre=t))
    json.dump(dict(model=model, stat=vk.stat(), vidpovidi=r), open(os.path.join(out, f'zghoda-{nazva}.json'), 'w'), ensure_ascii=False, indent=1)
    print(nazva, collections.Counter(x['rishennia'] for x in r), vk.stat(), flush=True)
