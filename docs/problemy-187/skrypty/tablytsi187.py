import json, collections, sys
sys.path.insert(0, '/home/user/work'); from tablytsi import chyste
C = json.load(open('/home/user/work/out/chutlyvist.json')); MZ = json.load(open('/home/user/work/out/marzha.json'))
BAZ = 'базовий (8 кв., 5 подій, 3 кв., 40/60 м, P 0,05, 1 справа)'; b = C[BAZ]['kandydativ']
VY = ['ДТП на дорозі', 'ДТП', 'ДОР', 'МАЙ', 'ГП', 'НАР', 'АЛК', 'НАС']
r = ['| Варіант (змінено один параметр) | Кандидатів | Зміна | ' + ' | '.join(VY) + ' | ≈ проблем | Як оцінено |', '|' + '---|' * (len(VY) + 5)]
for n, x in C.items():
    if n.startswith('_'): continue
    m = MZ.get(n) or {}
    jak = ('частка «проблем» у вибірці 183 (повтор)' if n == BAZ else
           (f"+ {m['marzha']['dodano']} доданих: у вибірці {m['marzha']['problem']} з {m['marzha']['vybirka']} — проблеми" if m.get('marzha') else
            ('центри місць інші — частки бази (наближено)' if '100' in n else 'частки вибірки, що лишилась у варіанті')))
    r.append(f"| {n} | {x['kandydativ']} | {round(100 * (x['kandydativ'] - b) / b):+d} % | " + ' | '.join(str(x['za_vydom'].get(v, 0)) for v in VY) +
             f" | {m.get('problem_otsinka', '—')} | {jak} |")
open('/home/user/moya-vulytsya/docs/problemy-187/chutlyvist.md', 'w').write(
    '# ZAVDANNYA-187 — чутливість сита MV-195 (без ШІ)\n\nВипуск `vypusk-kyiv-2026-11-21` (зріз 2026-11-10), код `dani-edrsr#103`. Змінювався один параметр, решта — як у базовому. '
    f"Поправка Бенджаміні–Гохберга: {C['_bh']['testiv']} перевірок (усі вікна всіх місць, що повторювались), поріг P ≤ {C['_bh']['porih']:.4f}. "
    'Скрипт — `skrypty/chutlyvist.py`, оцінка проблем — `skrypty/marzha.py`.\n\n' + '\n'.join(r) + '\n')
# згода
K = json.load(open('/home/user/work/z187/kappa.json')); O = json.load(open('/home/user/work/z187/otsinky.json'))
nm = {'A_sonnet_1': 'Sonnet, прогін 2', 'B_sonnet_2': 'Sonnet, прогін 3', 'C_opus': 'Opus', '183': 'Sonnet, прогін 1 (183)'}
r = ['| Пара | Кандидатів | Збіг | Каппа Коена | Проблема/проблема | Лише в першому | Лише в другому |', '|---|---|---|---|---|---|---|']
for k, x in K.items():
    if '~' not in k: continue
    a, bb = k.split('~'); t = dict((tuple(p), c) for p, c in x['tablytsia'])
    pp = t.get(('проблема', 'проблема'), 0); l1 = sum(c for p, c in t.items() if p[0] == 'проблема' and p[1] != 'проблема'); l2 = sum(c for p, c in t.items() if p[1] == 'проблема' and p[0] != 'проблема')
    r.append(f"| {nm[a]} — {nm[bb]} | {x['n']} | {round(100 * x['zbih'])} % | {x['kappa']:.2f} | {pp} | {l1} | {l2} |")
rz = json.load(open('/home/user/work/z187/rozbizhnosti.json'))
r2 = ['| Вид | Місце | Подій | Sonnet 2 | Sonnet 3 | Opus |', '|---|---|---|---|---|---|']
for o in rz:
    f = lambda v: f"**{v['r']}** ({round(100 * (v['ch'] or 0))} %): {chyste(v['nz'])[:110]}" + (f" — {chyste(v['zn'])}" if v['zn'] else '') + (f" — вада: {'; '.join(v['vady'])}" if v['vady'] else '')
    r2.append(f"| {o['vyd']} | {chyste(o['mistse'])} | {o['n']} | {f(o['A_sonnet_1'])} | {f(o['B_sonnet_2'])} | {f(o['C_opus'])} |")
r3 = ['| Правило | ≈ проблем на Київ |', '|---|---|'] + [f'| {k} | {v} |' for k, v in O.items()]
open('/home/user/moya-vulytsya/docs/problemy-187/zghoda.md', 'w').write(
    '# ZAVDANNYA-187 — згода моделей ШІ\n\n122 кандидати сита MV-195, пропорційно за видами (сталий вибір за хешем — підмножина вибірки 183). Інструкція `config/problemy-shi.md` '
    '(183.2), перевірка відповіді — `problemy_shi.pereviryty`. «Вада» прирівняна до «скупчення» (так робить і програма). Прогін 1 — таблиця `dani-edrsr/perevirka/problemy-183.md`, '
    'прогони 2–3 і Opus — ця робота (`claude -p`, окремий кеш на кожен прогін). Скрипти — `skrypty/zghoda.py`, `skrypty/kappa.py`, `skrypty/otsinky.py`.\n\n## Попарна згода\n\n'
    + '\n'.join(r) + '\n\n## Усі 15 розбіжностей (прогони 2, 3 і Opus)\n\nУ дужках — частка описів картини, яку порахувала програма.\n\n' + '\n'.join(r2) +
    '\n\n## Оцінка проблем на Київ за різних правил\n\n' + '\n'.join(r3) + '\n')
print('ok')
