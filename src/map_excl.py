# -*- coding: utf-8 -*-
"""Адреси установ: суди, відділи поліції, місця оформлення протоколів.

Такі адреси дають сотні подій, яких там насправді не сталося, і без вилучення
вони очолюють будь-який список. Виявляються автоматично за часткою подій свого
району; результат пишеться в data/vykluchennya.txt — це РЕЗУЛЬТАТ, не вхід,
інакше адреса, раз потрапивши туди, лишалася б виключеною назавжди.

Власний список користувача — data/vykluchennya_moyi.txt — автоматика ніколи
не перезаписує.
"""
import os, sys, json, collections
import labels as L
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

EXCL = os.path.join(DATA, 'vykluchennya.txt')           # формується автоматично
MANUAL = os.path.join(DATA, 'vykluchennya_moyi.txt')    # ваш список, ніколи не перезаписується
REVIEW = os.path.join(DATA, 'top100_dlya_pereviryky.txt')

SHARE_LIMIT = 0.015      # частка подій свого району, за якою адреса вважається установою
ABS_LIMIT   = 90         # або стільки подій незалежно від частки

# ---- ДРУГА ОЗНАКА: ПРОФІЛЬ СТАТЕЙ ----
# Знайдено 3 вересня: вул. Святослава Хороброго, 9 — відділ поліції — давала
# 50 подій, тобто 0,68% свого району. Обидва пороги вище вона не перетинала й
# лишалася на карті як скупчення ДТП.
#
# Але місце оформлення протоколів видно не обсягом, а СКЛАДОМ. Керування у
# стані сп'яніння (ст.130) і залишення місця ДТП (ст.122-4) — це те, що
# оформлюють у відділі, а не там, де сталося. Справжній небезпечний перехрестя
# дає ст.124, і майже не дає ст.130.
#
# На всьому місті ця ознака ловить вісім адрес — рівно тих, що й мала.
PROC_MIN   = 20          # хоча б стільки подій на адресі
PROC_SHARE = 0.5         # і стільки маркерних статей серед них
MARKERS = {k for k, v in L.CODE.items()
           if v[1].startswith('ст.130 ') or v[1].startswith('ст.122-4 ')}

# Список «це справжня адреса, не чіпати». Потрібен тому, що автоматичний файл
# перезаписується щоразу: викреслити з нього рядок назавжди неможливо.
KEEP = os.path.join(DATA, 'vykluchennya_ne.txt')

# ---- ПЕРША ОЗНАКА, НАЙНАДІЙНІША: БУДІВЛЯ УСТАНОВИ ----
# Відділи поліції, суди й прокуратура з OpenStreetMap (крок 2b). Порівнюємо
# КООРДИНАТИ, а не рядки: текстовий перелік адрес спіткала б та сама біда,
# що й решту адрес у цих даних — «вул. С. Хороброго, 9» і «вул. Святослава
# Хороброго, 9» різні рядки, а будівля одна.
#
# Радіус малий навмисно. Геокодування ставить усі події адреси в одну точку,
# тож 60 метрів це «та сама будівля», а не «той самий квартал»: інакше разом
# із відділом вилітали б сусідні будинки, де події справжні.
USTANOVY = os.path.join(DATA, 'ustanovy.json')
NEAR_M = 60
_MLAT = 111320.0                    # метрів в одному градусі широти
_MLON = 111320.0 * 0.6374           # ...і довготи на широті Києва

def load_ustanovy():
    """координати установ; порожньо, якщо крок 2b ще не збирав їх"""
    if not os.path.exists(USTANOVY):
        return []
    try:
        return [(float(x[0]), float(x[1])) for x in
                json.load(open(USTANOVY, encoding='utf-8'))]
    except Exception as e:
        print('   не прочитав data/ustanovy.json:', e)
        return []


def load_keep():
    """адреси, які НЕ виключати, хоч би що вирішила автоматика"""
    if not os.path.exists(KEEP):
        with open(KEEP, 'w', encoding='utf-8') as f:
            f.write('# Адреси, які НЕ треба виключати з карти,\n')
            f.write('# навіть якщо автоматика вважає їх установою.\n')
            f.write('# Автоматика цей файл НІКОЛИ не перезаписує.\n')
            f.write('# Один рядок = одна адреса, точно як у vykluchennya.txt\n\n')
    keep = set()
    for ln in open(KEEP, encoding='utf-8'):
        ln = ln.split('#')[0].strip()
        if ln: keep.add(ln.lower())
    return keep


def load_excl():
    man = set()
    if not os.path.exists(MANUAL):
        with open(MANUAL, 'w', encoding='utf-8') as f:
            f.write('# ВАШ список адрес, які треба виключити з карти.\n')
            f.write('# Цей файл автоматика НІКОЛИ не перезаписує.\n')
            f.write('# Один рядок = одна адреса, точно як у vykluchennya.txt\n\n')
    # ЧИТАЄМО ЛИШЕ РУЧНИЙ файл. Автоматичний (EXCL) — це результат, не вхід:
    # інакше адреса, раз потрапивши туди, лишалась би виключеною назавжди.
    if os.path.exists(MANUAL):
        for ln in open(MANUAL, encoding='utf-8'):
            ln = ln.split('#')[0].strip()
            if ln: man.add(ln.lower())
    return man

def detect_institutional(rows, manual):
    per_court = collections.Counter(r[1] for r in rows)
    per_addr = collections.Counter()
    addr_court = {}
    for r in rows:
        if not r[5]: continue
        a = (r[5] + ', ' + r[6]) if r[6] else r[5]
        per_addr[a] += 1
        addr_court[a] = r[1]
    # склад статей кожної адреси — для ознаки «місце оформлення»
    prof_mark = collections.Counter()
    for r in rows:
        if not r[5]: continue
        if r[2] in MARKERS:
            prof_mark[(r[5] + ', ' + r[6]) if r[6] else r[5]] += 1

    # координати кожної адреси — беремо з будь-якої її події, вони спільні
    addr_pt = {}
    for r in rows:
        if not r[5]: continue
        a = (r[5] + ', ' + r[6]) if r[6] else r[5]
        if a not in addr_pt and r[7] and r[8]: addr_pt[a] = (r[7], r[8])

    ust = load_ustanovy()
    on_ust = set()
    if ust:
        # сітка на 0,001° (~110 м), щоб не міряти кожну адресу до кожної установи
        cell = collections.defaultdict(list)
        for la, lo in ust:
            cell[(int(la * 1000), int(lo * 1000))].append((la, lo))
        for a, (la, lo) in addr_pt.items():
            ci, cj = int(la * 1000), int(lo * 1000)
            near = False
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for ula, ulo in cell.get((ci + di, cj + dj), ()):
                        if ((la - ula) * _MLAT) ** 2 + ((lo - ulo) * _MLON) ** 2 <= NEAR_M ** 2:
                            near = True; break
                    if near: break
                if near: break
            if near: on_ust.add(a)
        print(f'   установ з OpenStreetMap: {len(ust)}; адрес на них: {len(on_ust)}')
    else:
        print('   data/ustanovy.json немає — установи ловляться лише за числами '
              '(запустіть 2b-RISKS, щоб додати будівлі з OpenStreetMap)')

    keep = load_keep()
    auto = {}
    for a, n in per_addr.items():
        tot = per_court[addr_court[a]] or 1
        share = n / tot
        mark = prof_mark[a] / n if n else 0
        why = ('будівля' if a in on_ust
               else 'обсяг' if (n >= ABS_LIMIT or share >= SHARE_LIMIT)
               else ('склад' if (n >= PROC_MIN and mark >= PROC_SHARE) else None))
        if why and a.lower() not in keep:
            auto[a] = (n, round(100 * share, 1), why, round(100 * mark))
    # звіт: топ-100 адрес із профілем статей, щоб можна було оцінити очима
    prof = collections.defaultdict(collections.Counter)
    for r in rows:
        if not r[5]: continue
        a = (r[5] + ', ' + r[6]) if r[6] else r[5]
        lb = L.CODE.get(r[2])
        prof[a][lb[1] if lb else r[2]] += 1
    with open(REVIEW, 'w', encoding='utf-8') as f:
        f.write('# Топ-100 адрес за кількістю подій, із профілем статей.\n')
        f.write('# Якщо бачите установу (суд, відділ поліції, місце оформлення протоколів) —\n')
        f.write('# скопіюйте її адресу у файл vykluchennya.txt окремим рядком.\n')
        f.write('# Ознака місця оформлення: майже все — ст.130, ст.126, ст.122-4.\n\n')
        for a, n in per_addr.most_common(100):
            mark = ' [ВЖЕ ВИКЛЮЧЕНО]' if a in auto else ''
            f.write(f'{n:6}  {a}{mark}\n')
            for st, k in prof[a].most_common(4):
                f.write(f'          {k:5}  {st}\n')
            f.write('\n')
    print(f'   звіт для перегляду: data/top100_dlya_pereviryky.txt')

    if auto or not os.path.exists(EXCL):
        with open(EXCL, 'w', encoding='utf-8') as f:
            f.write('# Адреси, виключені з карти як установи (суди, відділи поліції).\n')
            f.write('# Визначено автоматично за трьома ознаками:\n')
            f.write('#   будівля — адреса стоїть на відділі поліції, суді чи прокуратурі\n')
            f.write(f'#             за даними OpenStreetMap (радіус {NEAR_M} м);\n')
            # пороги підставляються з констант, щоб текст не розходився з кодом
            f.write(f'#   обсяг — понад {SHARE_LIMIT*100:g}% подій свого району або понад {ABS_LIMIT} подій;\n')
            f.write(f'#   склад — від {PROC_MIN} подій, з яких понад {PROC_SHARE*100:g}% це\n')
            f.write('#           ст.130 і ст.122-4, тобто те, що оформлюють у відділі.\n')
            f.write('#\n')
            f.write('# ЦЕЙ ФАЙЛ ПЕРЕЗАПИСУЄТЬСЯ ЩОРАЗУ. Викреслити рядок назавжди не\n')
            f.write('# вийде: якщо адреса справжня, впишіть її у vykluchennya_ne.txt.\n')
            f.write('# Один рядок = одна адреса.\n\n')
            for a, (n, pc, why, mk) in sorted(auto.items(), key=lambda x: -x[1][0]):
                tail = ({'будівля': f'{n} подій, будівля установи за OpenStreetMap',
                         'обсяг': f'{n} подій, {pc}% району'}
                        .get(why, f'{n} подій, {mk}% ст.130 і ст.122-4'))
                f.write(f'{a}   # {tail}\n')
        by_why = collections.Counter(v[2] for v in auto.values())
        print(f'   виявлено установ: {len(auto)} -> data/vykluchennya.txt  ('
              + ', '.join(f'{n} за {w}' for w, n in by_why.most_common()) + ')')
        for a, (n, pc, why, mk) in sorted(auto.items(), key=lambda x: -x[1][0])[:8]:
            print(f'     {n:5}  {pc:4}%  {a}')
    return {a.lower() for a in auto} | manual
