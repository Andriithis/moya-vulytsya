# -*- coding: utf-8 -*-
"""Крок 6, спільна частина: дані, обчислення й оболонка сторінки.

Тексти самих документів — у step6_research.py і step6_state.py, точка входу —
у step6_docs.py. Поділ суто технічний: файл із текстами вийшов завеликий.

Вихідний опис:

Три файли на кожну версію сайту:
  doslidzhennya.html — повне дослідження ризиків: джерела, методика, результати,
                       перевірка й поіменний розбір кожної ризикованої вулиці;
  rezyume.html       — те саме на одну сторінку, без таблиць;
  analiz.html        — загальний аналіз поточного стану: що показують дані,
                       де концентрація, коли і де саме, з можливими причинами
                       (тільки викладацька версія).

Жодного тексту не написано «наперед» під конкретні цифри: усі числа беруться
з engine_report.json, risk.json, network.json, factors.json і бази подій, а
формулювання добираються від самих чисел. Тому після кожного щотижневого
запуску документи оновлюються разом із картою.
"""
import os, sys, json, math, gzip, csv, sqlite3, collections, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import labels as L

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
SITE = os.path.join(ROOT, 'site')

COURTS = {'Golosiivskyi': 'Голосіївський', 'Darnytskyi': 'Дарницький',
          'Desnianskyi': 'Деснянський', 'Dniprovskyi': 'Дніпровський',
          'Obolonskyi': 'Оболонський', 'Pecherskyi': 'Печерський',
          'Podilskyi': 'Подільський', 'Sviatoshynskyi': 'Святошинський',
          'Solomianskyi': "Солом'янський", 'Shevchenkivskyi': 'Шевченківський'}

TRAIN_Y, TEST_Y = '2024', ('2025', '2026')
TOPSTREETS = 400          # скільки вулиць кожної теми розбираємо поіменно
NEAR_R     = 250          # радіус «що поруч» для розбору вулиці

# ---------------------------------------------------------------- геометрія
def mdeg(lat):
    return 111320.0, 111320.0 * math.cos(math.radians(lat))

class PtGrid:
    """той самий пошук у радіусі, що й у кроці 4 — щоб числа збігалися"""
    def __init__(s, pts, cell=0.0025):
        s.c = cell
        s.g = collections.defaultdict(list)
        for p in pts:
            s.g[(int(p[0] / cell), int(p[1] / cell))].append(p)
    def count(s, la, lo, rad):
        my, mx = mdeg(la)
        n = int(max(rad / my, rad / mx) / s.c) + 1
        ci, cj = int(la / s.c), int(lo / s.c)
        k = 0
        for i in range(ci - n, ci + n + 1):
            for j in range(cj - n, cj + n + 1):
                for p in s.g.get((i, j), ()):
                    if math.hypot((p[0] - la) * my, (p[1] - lo) * mx) <= rad:
                        k += 1
        return k

def in_ring(la, lo, ring):
    inside = False
    n = len(ring); j = n - 1
    for i in range(n):
        yi, xi = ring[i]; yj, xj = ring[j]
        if (yi > la) != (yj > la):
            xx = xi + (la - yi) * (xj - xi) / ((yj - yi) or 1e-12)
            if lo < xx: inside = not inside
        j = i
    return inside

def esc(t):
    return (str(t).replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))

def num(n):
    return f'{int(n):,}'.replace(',', ' ')

# ---------------------------------------------------- розбір назви ознаки
def parse_factor(name):
    """'ринки_250м × житло_100м' -> [('ринки',250), ('житло',100)]

    Ознаки без радіуса ('смуг', 'клас_дороги', 'проникність', 'прохідність'…)
    повертають порожній список: для них немає об'єктів, які можна показати.
    """
    out = []
    for part in str(name).split(' × '):
        part = part.strip()
        if '_' in part and part.endswith('м'):
            base, _, r = part.rpartition('_')
            if r[:-1].isdigit():
                out.append((base, int(r[:-1])))
    return out

# ---------------------------------------------------------------- дані
def load():
    D = {}
    def js(n):
        p = os.path.join(DATA, n)
        return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None
    D['ER']   = js('engine_report.json') or {}
    D['RK']   = js('risk.json') or {}
    D['NET']  = js('network.json') or {}
    D['FACT'] = js('factors.json') or {}
    D['BORD'] = js('borders.json') or {}
    D['POP']  = js('population.json') or {}
    D['events'] = load_events()
    return D

def load_events():
    """(court, cat, date, street, house, tm) — з бази, а якщо її нема, зі знімка"""
    db = os.path.join(DATA, 'events.db')
    if os.path.exists(db):
        try:
            c = sqlite3.connect(db)
            rows = c.execute('SELECT court, cat, date, street, house, tm '
                             'FROM events').fetchall()
            c.close()
            if rows: return rows
        except Exception as e:
            print('   базу подій не прочитано:', e)
    snap = os.path.join(DATA, 'events.csv.gz')
    if not os.path.exists(snap): return []
    out = []
    with gzip.open(snap, 'rt', encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f, delimiter='\t'):
            out.append((r.get('court', ''), r.get('cat', ''), r.get('date', ''),
                        r.get('street', ''), r.get('house', ''), r.get('tm', '')))
    return out

# --------------------------------------------------------- спільна оболонка
CSS = """
*{box-sizing:border-box}
body{margin:0;background:#0f1117;color:#e8eaf0;font:15px/1.62 system-ui,-apple-system,sans-serif;
 padding:0 20px 80px}
.wrap{max-width:900px;margin:0 auto}
a{color:#7cb2ff}
header{padding:30px 0 18px;border-bottom:1px solid #232838;margin-bottom:26px}
.back{font-size:13px;color:#79839a;text-decoration:none}
.back:hover{color:#c4cbd8}
h1{font-size:26px;letter-spacing:-.02em;margin:14px 0 6px}
h2{font-size:19px;letter-spacing:-.01em;margin:38px 0 10px;padding-top:12px;
 border-top:1px solid #1d2230}
h3{font-size:15.5px;margin:24px 0 6px;color:#dbe2f0}
h4{font-size:14px;margin:16px 0 4px;color:#c4cbd8;font-weight:600}
.sub{color:#79839a;font-size:13.5px}
p{margin:9px 0}
ul,ol{margin:9px 0;padding-left:22px}
li{margin:4px 0}
table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}
th,td{padding:6px 9px;text-align:left;border-bottom:1px solid #1d2230;vertical-align:top}
th{color:#79839a;font-weight:500;font-size:11.5px;text-transform:uppercase;
 letter-spacing:.04em;position:sticky;top:0;background:#0f1117}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
tr:hover td{background:#151a25}
.box{background:#151a22;border:1px solid #232838;border-radius:9px;padding:14px 16px;margin:14px 0}
.box.warn{border-left:3px solid #e0533d}
.box.ok{border-left:3px solid #22c55e}
.box h4{margin-top:0}
.k{display:inline-block;background:#1c2230;border-radius:5px;padding:1px 7px;
 font-size:12px;color:#c4cbd8;margin:0 3px 3px 0;font-variant-numeric:tabular-nums}
.muted{color:#79839a;font-size:12.5px}
.big{font-size:30px;font-weight:600;letter-spacing:-.02em;line-height:1.1}
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:11px;margin:14px 0}
.card{background:#151a22;border:1px solid #232838;border-radius:9px;padding:13px 14px}
.card .lab{color:#79839a;font-size:11.5px;margin-bottom:5px}
.bar{height:6px;background:#232838;border-radius:3px;overflow:hidden;min-width:52px}
.bar i{display:block;height:100%;background:#7cb2ff}
.tw{max-height:70vh;overflow:auto;border:1px solid #1d2230;border-radius:9px;margin:12px 0}
.tw table{margin:0}
.src{font-size:12.5px;color:#8b95a8;line-height:1.7}
.src li{margin:7px 0}
.toc{background:#151a22;border:1px solid #232838;border-radius:9px;padding:12px 16px;margin:16px 0}
.toc a{display:block;padding:3px 0;font-size:13.5px;text-decoration:none}
.toc a:hover{text-decoration:underline}
input.f{background:#151a22;border:1px solid #2b3244;color:#e8eaf0;border-radius:7px;
 padding:7px 11px;font:13.5px system-ui,sans-serif;width:260px;max-width:100%}
mark{background:#3a3410;color:#f5d76e;border-radius:3px;padding:0 2px}
tr.hl td{background:#22283a !important;box-shadow:inset 3px 0 0 #f59e0b}
@media print{body{background:#fff;color:#111}.tw{max-height:none}}
"""

def page(title, lead, body, back='index.html', script=''):
    return ('<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{esc(title)}</title><style>{CSS}</style></head><body><div class="wrap">'
            f'<header><a class="back" href="{back}">← до карт</a>'
            f'<h1>{esc(title)}</h1><div class="sub">{lead}</div></header>'
            f'{body}</div>{script}</body></html>')

def stamp():
    return datetime.datetime.utcnow().strftime('%d.%m.%Y')

# ============================================================ ОБЧИСЛЕННЯ
def analyse(D):
    """Усі числа, з яких потім складаються три документи."""
    A = {}
    ev = D['events']
    A['n_events'] = len(ev)

    by_year  = collections.Counter()
    by_theme = collections.Counter()
    by_dist  = collections.Counter()
    by_hour  = collections.Counter()
    by_wday  = collections.Counter()
    by_month = collections.Counter()
    by_art   = collections.Counter()
    addr     = collections.Counter()
    dist_th  = collections.defaultdict(collections.Counter)
    th_hour  = collections.defaultdict(collections.Counter)

    for court, cat, date, street, house, tm in ev:
        lb = L.CODE.get(str(cat))
        th = lb[0] if lb else None
        d  = COURTS.get(court, court)
        y  = (date or '')[:4]
        if y.isdigit(): by_year[y] += 1
        if th:
            by_theme[th] += 1
            dist_th[d][th] += 1
            by_art[lb[1]] += 1
        by_dist[d] += 1
        if len(date or '') >= 10:
            try:
                dt = datetime.date(int(date[:4]), int(date[5:7]), int(date[8:10]))
                by_wday[dt.weekday()] += 1
                by_month[int(date[5:7])] += 1
            except Exception:
                pass
        if tm and ':' in tm:
            h = tm.split(':')[0]
            if h.isdigit() and 0 <= int(h) <= 23:
                by_hour[int(h)] += 1
                if th: th_hour[th][int(h)] += 1
        if street and house:
            addr[(d, street.strip(), house.strip())] += 1

    A.update(by_year=by_year, by_theme=by_theme, by_dist=by_dist, by_hour=by_hour,
             by_wday=by_wday, by_month=by_month, by_art=by_art, dist_th=dist_th,
             th_hour=th_hour)

    # ---- концентрація (Weisburd 2015): яка частка адрес дає половину подій ----
    cnt = sorted(addr.values(), reverse=True)
    tot = sum(cnt)
    A['n_addr'] = len(cnt)
    A['n_addr_events'] = tot
    A['conc'] = {}
    if tot:
        run = 0
        for share in (0.25, 0.50, 0.80):
            need = share * tot
            k = 0; run = 0
            for c in cnt:
                run += c; k += 1
                if run >= need: break
            A['conc'][share] = 100.0 * k / len(cnt)
    A['top_addr'] = addr.most_common(40)
    A['addr_once'] = 100.0 * sum(1 for c in cnt if c == 1) / (len(cnt) or 1)

    # ---- населення району (щоб порівнювати райони чесно) ----
    pop = {}
    cells = (D['POP'] or {}).get('items', [])
    for dname, ring in (D['BORD'] or {}).items():
        s = 0
        for la, lo, p in cells:
            if in_ring(la, lo, ring): s += p
        pop[dname] = s
    A['pop'] = pop

    # ---- модель ----
    A['ER'] = D['ER']
    A['themes_ok'] = [t for t in L.ORDER if t in D['ER']]
    A['themes_no'] = [t for t in L.ORDER
                      if t not in D['ER'] and t != 'ДОМ' and by_theme.get(t)]

    # ---- потоки по відрізках ----
    flow_by_first, flow_rank = {}, {}
    items = (D['NET'] or {}).get('items', [])
    if items:
        order = sorted(range(len(items)), key=lambda i: -(items[i][2] or 0))
        rank = {i: r + 1 for r, i in enumerate(order)}
        for i, it in enumerate(items):
            g = it[0]
            if not g: continue
            k = (round(g[0][0], 5), round(g[0][1], 5))
            flow_by_first[k] = (it[2], it[3], it[4], it[5])
            flow_rank[k] = rank[i]
    A['n_net'] = len(items)

    # ---- сітки чинників для «що поруч» ----
    grids, catname = {}, {}
    for c in (D['FACT'] or {}).get('cats', []):
        grids[c['b']] = PtGrid([tuple(p) for p in c['pts']])
        catname[c['b']] = c['n']
    A['catname'] = catname

    # ---- поіменний розбір ризикованих вулиць ----
    streets = {}
    for th, v in (D['RK'] or {}).get('layers', {}).items():
        fac = [(n, w) for n, w in D['ER'].get(th, {}).get('фактори', []) if w > 0]
        rows = []
        it = sorted(v.get('items', []), key=lambda x: -x[2])[:TOPSTREETS]
        n = len(it)
        for i, x in enumerate(it):
            pts = x[0]
            la, lo = pts[len(pts) // 2]
            k = (round(pts[0][0], 5), round(pts[0][1], 5))
            fl = flow_by_first.get(k)
            near, seen = [], set()
            for fname, w in fac:
                for base, rad in parse_factor(fname):
                    if base in seen or base not in grids: continue
                    seen.add(base)
                    q = grids[base].count(la, lo, rad)
                    if q: near.append((catname.get(base, base), q, rad, w))
                if len(near) >= 6: break
            near.sort(key=lambda z: -z[3])
            rows.append({
                'rank': i + 1,
                'pc': int(100 * (n - i) / n),
                'name': x[1] or 'без назви',
                'score': x[2],
                'ev24': x[3],
                'lat': la, 'lon': lo,
                'flow': fl[0] if fl else None,
                'flow_rank': flow_rank.get(k),
                'fsch': fl[1] if fl else None,
                'ftrn': fl[2] if fl else None,
                'fshp': fl[3] if fl else None,
                'near': near[:5]})
        streets[th] = rows
    A['streets'] = streets

    # ---- аномалії: подій багато, а середовище їх не пояснює ----
    anom = {}
    for th, rows in streets.items():
        allrows = rows
        hi_ev = sorted((r for r in allrows if r['ev24'] > 0), key=lambda r: -r['ev24'])
        anom[th] = [r for r in hi_ev if r['rank'] > len(allrows) * 0.5][:12]
    A['anom'] = anom

    # ---- вулиці з високим ризиком і нульовою історією: де ще не фіксували ----
    fresh = {}
    for th, rows in streets.items():
        fresh[th] = [r for r in rows[:120] if r['ev24'] == 0][:12]
    A['fresh'] = fresh
    return A

WDAY = ['понеділок', 'вівторок', 'середа', 'четвер', "п'ятниця", 'субота', 'неділя']

def bar(v, mx, w=100):
    p = 0 if not mx else max(2, int(w * v / mx))
    return f'<div class="bar" style="width:{w}px"><i style="width:{p}%"></i></div>'

THSLUG = {'ГП': 'gp', 'АЛК': 'alk', 'НАР': 'nar', 'НАС': 'nas',
          'МАЙ': 'may', 'ДОР': 'dor', 'СЕР': 'ser', 'ДОМ': 'dom'}

def fac_human(name):
    """'ринки_250м × житло_100м' -> 'ринки в 250 м у поєднанні з житлом у 100 м'"""
    parts = []
    for p in str(name).split(' × '):
        p = p.strip()
        if '_' in p and p.endswith('м'):
            base, _, r = p.rpartition('_')
            if r[:-1].isdigit():
                parts.append(f'{base.replace("_", " ")} в {r[:-1]} м')
                continue
        parts.append(p.replace('_', ' '))
    return ' у поєднанні з '.join(parts)
