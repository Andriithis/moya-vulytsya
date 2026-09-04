# -*- coding: utf-8 -*-
"""Відбір проблем і обрізання карти до району.

«Проблема» — не будь-яке скупчення, а пара «адреса + механізм», яка подолала
поріг однорідних епізодів. Інцидент стався раз випадково; проблема повторюється
роками, і причина в місці. Тут же збирається аналітична частина картки — роки,
розклад доби, підказка моделі ризику — і паспорт для SARA.

Далі: районна карта обрізає точки, межі, населення й лічильники до одного
району, бо дільничний працює районом, а не містом.

Шари під подіями — у map_layers.
"""
import os, sys, json, collections
import labels as L
import mech as M
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

BORD  = os.path.join(DATA, 'borders.json')

# ---- ВІДБІР ПРОБЛЕМ (п.7.3) ----
MIN_EPISODES = 15   # мінімум однорідних епізодів (за групою подібності, п.7.2) на адресу
GUARANTEE    = 2    # обов'язкових проблем з кожного району
CITYWIDE     = 30   # + найгостріших по місту понад гарантовані

# Квота за напрямком (теми). На реальних даних дорожній рух — 85% усіх кандидатів
# (утричі більше подій за наступну тему), тож без обмежень він займав 48 з 50 місць,
# а насильство/середовище не потрапляли жодного разу. Квота дорожнього руху свідомо
# більша за інші — це найчисельніша тема, і повне вирівнювання було б нечесним щодо
# реальності. Якщо в темі просто немає кандидатів (як у насильства чи середовища),
# її квота лишається незаповненою — місця йдуть наступним найгострішим, а не пропадають.
CAP_THEME   = {'ДОР': 18}
CAP_DEFAULT = 10

COURTS = {'Golosiivskyi':'Голосіївський','Darnytskyi':'Дарницький','Desnianskyi':'Деснянський',
 'Dniprovskyi':'Дніпровський','Obolonskyi':'Оболонський','Pecherskyi':'Печерський',
 'Podilskyi':'Подільський','Sviatoshynskyi':'Святошинський','Solomianskyi':"Солом'янський",
 'Shevchenkivskyi':'Шевченківський'}

# латинські ярлики — для якорів у doslidzhennya.html (крок 6).
# Кирилиця у фрагменті URL працює, але ламається при копіюванні посилання,
# тому анкори латинські. ЄДИНЕ ДЖЕРЕЛО — mech.py: раніше цей словник жив
# у трьох файлах і вони встигли розійтися.
THSLUG = M.THSLUG

# Короткі ярлики районів для адреси сторінки: kyiv.html#desna. Живуть тут,
# бо ними користуються і карта (перехід по районах), і крок 5 (плитки).
SLUG = {'Голосіївський':'golosiiv','Дарницький':'darnytsia','Деснянський':'desna',
        'Дніпровський':'dnipro','Оболонський':'obolon','Печерський':'pechersk',
        'Подільський':'podil','Святошинський':'sviatoshyn',"Солом'янський":'solomianka',
        'Шевченківський':'shevchenkivsk'}

def in_ring(la, lo, ring):
    """чи точка всередині багатокутника (промінь праворуч)"""
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        yi, xi = ring[i]; yj, xj = ring[j]
        if (yi > la) != (yj > la):
            xx = xi + (la - yi) * (xj - xi) / ((yj - yi) or 1e-12)
            if lo < xx: inside = not inside
        j = i
    return inside


THEME_SKEW = {
 'ГП': 'громадського порядку', 'АЛК': "пов'язаних з алкоголем", 'НАР': 'наркотичних',
 'НАС': 'насильства', 'МАЙ': 'майнових', 'ДОР': 'дорожніх', 'СЕР': 'середовища громади',
}



# ---- ВІДБІР У МЕЖАХ РАЙОНУ ----
# Міський список — 50 найгостріших на все місто, і тихому району в ньому
# дістається дві-три позиції. Дільничному цього мало: він працює районом,
# і найгірше місце Деснянського для нього важливіше за десяте місце Києва.
# Тому для кожного району складається СВІЙ перелік з тим самим порогом
# MIN_EPISODES — визначення проблеми не пом'якшується. Де кандидатів менше
# за DISTRICT_TOP, показуємо скільки є: це теж відповідь.
DISTRICT_TOP = 10        # скільки проблем показувати всередині району
CAP_D_THEME  = {'ДОР': 4}   # квота теми в межах району
CAP_D_DEF    = 3


def select(P, meta, labels, ck, ykeys, sim_of, gi_of_theme,
           district, risks, ER, FACT, theme_rgrid, pred_theme):
    """Повертає (P, POP, meta, theme_cnt)."""
    POP = []

    # ---- ВІДБІР ПРОБЛЕМ (п.7.1–7.4): інцидент / проблема. «Проблема» = членство
    # в кураторському списку ~50 адрес-напрямків. Кілька напрямків на одній
    # адресі, що подолали поріг, — кілька окремих проблем (розд.6 передачі). ----
    CORE = {'ГП', 'АЛК', 'НАР', 'НАС', 'МАЙ', 'ДОР', 'СЕР'}   # усе, крім домашнього насильства

    ALL_BORDERS = {}
    if os.path.exists(BORD):
        ALL_BORDERS = json.load(open(BORD, encoding='utf-8'))

    DNAMES = sorted(ALL_BORDERS)
    DIDX = {d: i for i, d in enumerate(DNAMES)}
    # рамка навколо кожного району: точка поза рамкою не може бути в межах,
    # і дорога перевірка променем для неї не запускається
    DBOX = {d: (min(q[0] for q in r), max(q[0] for q in r),
                min(q[1] for q in r), max(q[1] for q in r))
            for d, r in ALL_BORDERS.items()}

    def addr_district(la, lo):
        for d, ring in ALL_BORDERS.items():
            y0, y1, x0, x1 = DBOX[d]
            if la < y0 or la > y1 or lo < x0 or lo > x1: continue
            if in_ring(la, lo, ring): return d
        return None

    candidates = []
    skipped_street = 0
    for pi, p in enumerate(P):
        # Проблема — це МІСЦЕ, куди можна приїхати. Центр вулиці місцем не є:
        # там зібрані події з усієї вулиці лише тому, що будинків не знайшлося
        # в OpenStreetMap. Такі точки в кандидати не беремо — інакше кожна
        # довга вулиця автоматично ставала б «проблемою» з великим числом.
        if not p[3]:
            skipped_street += 1
            continue
        by_sim = collections.defaultdict(lambda: [0, set(), collections.Counter()])
        core_n = 0
        for e in p[4]:
            th, lbl = labels[e[1]]
            if th not in CORE: continue
            core_n += 1
            sim = sim_of[e[1]]
            rec = by_sim[sim]
            rec[0] += 1
            rec[1].add(ykeys[e[2]] if e[2] < len(ykeys) else 'раніше')
            rec[2][lbl] += 1
        if not by_sim: continue
        dist = addr_district(p[0], p[1])
        for sim, (n, yrs, arts) in by_sim.items():
            if n < MIN_EPISODES: continue
            th = sim.split('_', 1)[0]
            score = n * (1 + 0.15 * len(yrs))
            candidates.append(dict(pi=pi, sim=sim, th=th, n=n, core_n=core_n,
                                    district=dist, years=sorted(yrs),
                                    arts=arts.most_common(), score=score))
    candidates.sort(key=lambda c: -c['score'])

    chosen = {}
    used_theme = collections.Counter()   # спільний лічильник квоти по темах (п.7.3, за проханням користувача)

    def try_take(c):
        cap = CAP_THEME.get(c['th'], CAP_DEFAULT)
        if used_theme[c['th']] >= cap: return False
        key = (c['pi'], c['sim'])
        if key in chosen: return False
        chosen[key] = c; used_theme[c['th']] += 1
        return True

    for d in ALL_BORDERS:
        got = 0
        for c in candidates:
            if got >= GUARANTEE: break
            if c['district'] != d: continue
            if try_take(c): got += 1
    got = 0
    for c in candidates:
        if got >= CITYWIDE: break
        if try_take(c): got += 1

    # Кожен район добирає свій перелік із тих самих кандидатів. Спершу з квотою
    # за темами, щоб перелік не був суцільним дорожнім рухом; якщо після квоти
    # місць лишилося, добираємо найгострішим без огляду на тему — інакше в тихому
    # районі половина рядків просто не заповнилася б.
    chosen_loc = {}
    for d in ALL_BORDERS:
        pool = [c for c in candidates if c['district'] == d]
        used_d, got = collections.Counter(), 0
        for pass_ in (0, 1):
            for c in pool:
                if got >= DISTRICT_TOP: break
                key = (c['pi'], c['sim'])
                if key in chosen_loc: continue
                if pass_ == 0 and used_d[c['th']] >= CAP_D_THEME.get(c['th'], CAP_D_DEF):
                    continue
                chosen_loc[key] = c; used_d[c['th']] += 1; got += 1

    problems = sorted(chosen.values(), key=lambda c: -c['score'])
    skew = collections.Counter(c['th'] for c in problems)
    skew_txt = ''
    if problems:
        parts = [f"{n} {THEME_SKEW.get(t, L.THEMES.get(t, t))}" for t, n in skew.most_common()]
        skew_txt = f"З {len(problems)} відібраних проблем: " + ', '.join(parts) + '.'
    print(f'   відібрано проблем: {len(problems)} з {len(candidates)} кандидатів (поріг {MIN_EPISODES} епізодів)')
    if skipped_street:
        print(f'   не розглядали {skipped_street:,} центрів вулиць — це не місця, а вулиці загалом')
    if skew_txt: print('   ' + skew_txt)

    # Одна адреса-напрямок може бути і в міському переліку, і в районному,
    # і лише в одному з них. Запис зберігаємо ОДИН, а належність позначаємо
    # прапорцями: карта показує те, що доречно для поточного вигляду.
    city_keys = set(chosen)
    loc_keys = set(chosen_loc)
    merged = dict(chosen_loc); merged.update(chosen)
    merged_list = sorted(merged.values(), key=lambda c: -c['score'])

    probs_by_pi = collections.defaultdict(list)
    for c in merged_list:
        th = c['th']
        # Спершу питаємо модель ВЛАСНОГО механізму цієї проблеми, і лише якщо
        # для нього моделі немає — загальну модель теми.
        rkey = c['sim'] if c['sim'] in theme_rgrid else th
        risk_pc = pred_theme(rkey, P[c['pi']][0], P[c['pi']][1])
        d = ER.get(rkey, {})
        analysis = None
        if risk_pc > 0 and d:
            analysis = dict(pc=risk_pc, hit=round(100*d.get('hit_середовище', 0)),
                             factors=[[n_, round(float(w), 3)] for n_, w in d.get('фактори', []) if w > 0][:8],
                             train=d.get('навчання', 0), test=d.get('перевірка', 0))
        key = (c['pi'], c['sim'])
        probs_by_pi[c['pi']].append(dict(
            thi=gi_of_theme.get(th, -1),   # індекс теми — щоб картка ховалась разом із фільтром
            sim=c['sim'], theme=L.THEMES.get(th, th), mech=M.simname(c['sim']),
            n=c['n'], core_n=c['core_n'], years=c['years'], arts=c['arts'],
            d=DIDX.get(c['district'], -1),           # район адреси
            city=1 if key in city_keys else 0,       # у міському переліку
            loc=1 if key in loc_keys else 0,         # у переліку свого району
            analysis=analysis))

    for pi, p in enumerate(P):
        probs = probs_by_pi.get(pi, [])
        p.append(2 if any(q['city'] for q in probs) else 0)   # кат.: 0 інцидент, 2 проблема
        p.append(probs)
        # район точки рахуємо тут раз назавжди: далі карта перемикає райони
        # порівнянням числа, а не геометрією — інакше кожен клік коштував би
        # дванадцяти тисяч перевірок променем у браузері
        p.append(DIDX.get(addr_district(p[0], p[1]), -1))

    pp2 = os.path.join(DATA, 'population.json')
    if os.path.exists(pp2):
        POP = [[x[0], x[1], x[2]] for x in json.load(open(pp2, encoding='utf-8'))['items'] if x[2] > 30]
        print(f'населення: {len(POP):,} комірок')

    meta['skew'] = skew_txt
    meta['n_problems'] = len(problems)

    # ---- ДАНІ ДЛЯ ПЕРЕХОДУ ПО РАЙОНАХ У МЕЖАХ ОДНОГО ФАЙЛУ ----
    # Міська карта несе межі всіх районів, їхні переліки проблем і короткі
    # латинські ярлики для адреси сторінки. Районні файли цього не потребують:
    # вони вже обрізані.
    if not district and ALL_BORDERS:
        meta['dnames'] = DNAMES
        meta['dslug'] = [SLUG.get(d, d) for d in DNAMES]
        meta['borders'] = [ALL_BORDERS[d] for d in DNAMES]
        dcnt, dskew = [], []
        for d in DNAMES:
            got = [c for c in chosen_loc.values() if c['district'] == d]
            dcnt.append(len(got))
            sk = collections.Counter(c['th'] for c in got)
            dskew.append(('У районі %d %s: ' % (len(got), 'проблема' if len(got) == 1 else 'проблем')
                          + ', '.join(f'{n} {THEME_SKEW.get(t, L.THEMES.get(t, t))}'
                                      for t, n in sk.most_common()) + '.') if got else '')
        meta['dprob'] = dcnt
        meta['dskew'] = dskew
        # Події кожного району за темами — з цього крок 5 будує плитки оглядової
        # сторінки. Рахуємо тут, бо тут уже відомий район кожної точки: інакше
        # довелося б збирати десять карт лише заради десяти чисел.
        dth = [collections.Counter() for _ in DNAMES]
        for pt in P:
            di = pt[8] if len(pt) > 8 else -1
            if di < 0: continue
            for e in pt[4]: dth[di][labels[e[1]][0]] += 1
        meta['dtheme'] = [dict(x) for x in dth]
        thin = [f'{DNAMES[i]} — {n}' for i, n in enumerate(dcnt) if n < DISTRICT_TOP]
        print(f'   переліки районів: по {DISTRICT_TOP} проблем, разом {sum(dcnt)}')
        if thin:
            print('   менше за поріг набрали: ' + '; '.join(thin))

    if district:
        ring = ALL_BORDERS.get(district)
        if ring:
            # ГЕОГРАФІЧНЕ обрізання: лишаємо тільки те, що фізично в межах району
            before = len(P)
            P = [p for p in P if in_ring(p[0], p[1], ring)]
            print(f'   район {district}: {len(P):,} адрес (за межами відсіяно {before-len(P):,})')
            # Потоки тепер стислі: геометрія лежить один раз у risks['geo'],
            # а шар несе номер відрізка й число. Обрізаємо обидва види, і
            # заразом викидаємо з geo те, що за межами району.
            geo = risks.get('geo') or []
            for k, v in list(risks.get('lines', {}).items()):
                if v.get('g'):
                    v['items'] = [x for x in v['items'] if 0 <= x[0] < len(geo)
                                  and any(in_ring(q[0], q[1], ring) for q in geo[x[0]][0])]
                else:
                    v['items'] = [x for x in v['items']
                                  if any(in_ring(q[0], q[1], ring) for q in x[0])]
                if not v['items'] and not v.get('nodata'): risks['lines'].pop(k, None)
            if geo:
                keep = sorted({x[0] for v in risks['lines'].values() if v.get('g')
                               for x in v['items']})
                pos = {j: i for i, j in enumerate(keep)}
                risks['geo'] = [geo[j] for j in keep]
                for v in risks['lines'].values():
                    if v.get('g'): v['items'] = [[pos[x[0]], x[1]] for x in v['items']]
            POP = [x for x in POP if in_ring(x[0], x[1], ring)]
            for _c in FACT.get('cats', []):
                _c['pts'] = [q for q in _c['pts'] if in_ring(q[0], q[1], ring)]
            la_ = [q[0] for q in ring]; lo_ = [q[1] for q in ring]
            meta['bounds'] = [[min(la_), min(lo_)], [max(la_), max(lo_)]]
            meta['border'] = ring
        else:
            keep = {i for i, c in enumerate(ck) if COURTS.get(c, c) == district}
            P = [p for p in P if any(e[0] in keep for e in p[4])]
            for p in P: p[4] = [e for e in p[4] if e[0] in keep]
            P = [p for p in P if p[4]]
            print(f'   район {district}: {len(P):,} адрес (за судом — межі не завантажені)')
        meta['courts'] = [COURTS.get(x, x) for x in ck]
        meta['only'] = district
        if P and 'bounds' not in meta:
            meta['center'] = [round(sum(x[0] for x in P)/len(P), 5),
                              round(sum(x[1] for x in P)/len(P), 5)]

        # Лічильники бічної панелі рахувалися ДО обрізання району, тому на
        # районній карті стояли міські числа: у Деснянському було написано
        # «Дорожній рух 47 981» — це весь Київ. Перераховуємо по тому, що
        # справді лишилося на карті.
        cnt2 = collections.Counter()
        for p in P:
            for e in p[4]: cnt2[e[1]] += 1
        meta['counts'] = [cnt2.get(i, 0) for i in range(len(labels))]
        for g in meta['groups']:
            g[2] = sum(meta['counts'][i] for i in g[1])

    # Скільки подій лишилося на цій карті, за темами. Крок 5 будує з цього
    # плитки оглядової сторінки, щоб її числа збігалися з числами карти:
    # раніше плитка рахувала за судом, а карта — за географією району.
    theme_cnt = collections.Counter()
    for p in P:
        for e in p[4]: theme_cnt[labels[e[1]][0]] += 1

    return P, POP, meta, theme_cnt
