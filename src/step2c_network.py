# -*- coding: utf-8 -*-
"""Крок 2c. Модель пішохідного потоку.

Замість випадкової вибірки маршрутів — повний перебір: кожен житловий будинок
прокладає шлях до найближчих цілей свого типу. Потоки рахуються окремо
для шкіл, транспорту й торгівлі, бо вони діють у різний час і по-різному.

Основа: Davies & Bishop (2014), betweenness як предиктор ризику.
"""
import os, sys, json, math, time, heapq, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
RAW  = os.path.join(DATA, 'osm_risks_raw.json')
OUT  = os.path.join(DATA, 'network.json')

SNAP   = 5
MAX_M  = int(os.environ.get('MAXWALK', '1200'))   # межа пішої ходьби
NEAR_N = 2                                        # скільки найближчих цілей на будинок
# Цілі потоків — категорії з osm_risks_raw.json (крок 2b).
# ВИПРАВЛЕНО 2026-08: категорія 'transit' містить лише метро, вокзали й
# автостанції, тому кінцеві тролейбусів і звичайні зупинки давали НУЛЬ потоку
# (перевірено на вул. Кадетський Гай: потік до транспорту = 0 при наявній
# кінцевій). Так само 'shop24' — це магазини біля дому й фастфуд, без
# супермаркетів і ТЦ, тож великі об'єкти торгівлі не притягували маршрутів.
FLOWS = {
    'school':  ('school',),                       # школи й садки
    'transit': ('transit', 'busstop'),            # метро, вокзали + зупинки наземного транспорту
    'shop':    ('alcohol', 'shop24', 'market'),   # магазини біля дому, супермаркети, ТЦ, ринки
}

def mdeg(lat): return 111320.0, 111320.0 * math.cos(math.radians(lat))
def dist_m(a, b):
    my, mx = mdeg((a[0] + b[0]) / 2)
    return math.hypot((a[0]-b[0]) * my, (a[1]-b[1]) * mx)
def key(lat, lon): return (round(lat, SNAP), round(lon, SNAP))

def build_graph(ways):
    adj = collections.defaultdict(list); seg = {}
    for w in ways:
        g = w.get('geometry')
        if not g or len(g) < 2: continue
        t = w.get('tags', {}); nm = t.get('name', ''); wid = w.get('id')
        pts = [key(p['lat'], p['lon']) for p in g]
        for u, v in zip(pts, pts[1:]):
            if u == v: continue
            d = dist_m(u, v)
            if d <= 0: continue
            adj[u].append((v, d)); adj[v].append((u, d))
            seg[(u, v)] = seg[(v, u)] = (wid, nm)
    return adj, seg

class Grid:
    def __init__(s, pts, cell=0.0015):
        s.c = cell; s.g = collections.defaultdict(list)
        for p in pts: s.g[(int(p[0]/cell), int(p[1]/cell))].append(p)
    def nearest(s, la, lo, rad=200):
        my, mx = mdeg(la)
        n = int(max(rad/my, rad/mx)/s.c) + 1
        ci, cj = int(la/s.c), int(lo/s.c)
        best, bd = None, 1e18
        for i in range(ci-n, ci+n+1):
            for j in range(cj-n, cj+n+1):
                for p in s.g.get((i, j), ()):
                    d = math.hypot((p[0]-la)*my, (p[1]-lo)*mx)
                    if d < bd: bd, best = d, p
        return best if bd <= rad else None
    def within(s, la, lo, rad):
        my, mx = mdeg(la)
        n = int(max(rad/my, rad/mx)/s.c) + 1
        ci, cj = int(la/s.c), int(lo/s.c); out = []
        for i in range(ci-n, ci+n+1):
            for j in range(cj-n, cj+n+1):
                for p in s.g.get((i, j), ()):
                    d = math.hypot((p[0]-la)*my, (p[1]-lo)*mx)
                    if d <= rad: out.append((d, p))
        out.sort(); return out

def dijkstra_multi(adj, src, targets, limit):
    """шлях від src до НАЙБЛИЖЧОЇ з targets (за мережею, не по прямій)"""
    tset = set(targets)
    if not tset: return None
    dist = {src: 0.0}; prev = {}
    pq = [(0.0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e18): continue
        if u in tset:
            path, cur = [], u
            while cur != src:
                p = prev[cur]; path.append((p, cur)); cur = p
            return path
        if d > limit: break
        for v, w in adj[u]:
            nd = d + w
            if nd < dist.get(v, 1e18):
                dist[v] = nd; prev[v] = u
                heapq.heappush(pq, (nd, v))
    return None

def centers(els):
    out = []
    for el in els:
        la = el.get('lat') or (el.get('center') or {}).get('lat')
        lo = el.get('lon') or (el.get('center') or {}).get('lon')
        if la and lo: out.append((la, lo))
    return out

def main():
    if not os.path.exists(RAW):
        print('немає data/osm_risks_raw.json — спершу 2b-RISKS'); sys.exit(1)
    raw = json.load(open(RAW, encoding='utf-8'))
    roads, foot = raw.get('roads', []), raw.get('foot', [])
    houses = centers(raw.get('houses', []))
    print(f'дороги {len(roads):,}   пішохідні {len(foot):,}   будинки {len(houses):,}')
    print(f'межа ходьби: {MAX_M} м')

    # --- ВАГА БУДИНКІВ ЗА НАСЕЛЕННЯМ ---
    popw = None
    ppath = os.path.join(DATA, 'population.json')
    if os.path.exists(ppath):
        P = json.load(open(ppath, encoding='utf-8'))['items']
        pcell = 0.0045                       # ~500 м, під розмір шестикутника Kontur
        pg = collections.defaultdict(list)
        for la, lo, n in P:
            pg[(int(la/pcell), int(lo/pcell))].append((la, lo, n))
        hcnt = collections.Counter()
        hkey = {}
        for idx, h in enumerate(houses):
            ci, cj = int(h[0]/pcell), int(h[1]/pcell)
            best, bd = None, 1e18
            for di in (-1, 0, 1):
                for dj in (-1, 0, 1):
                    for la, lo, n in pg.get((ci+di, cj+dj), ()):
                        d = dist_m(h, (la, lo))
                        if d < bd: bd, best = d, (round(la,5), round(lo,5), n)
            if best and bd <= 600:
                hkey[idx] = best; hcnt[best] += 1
        popw = {}
        for idx, k in hkey.items():
            popw[idx] = max(1.0, k[2] / max(hcnt[k], 1))   # мешканців на будинок
        if popw:
            vals = sorted(popw.values())
            print(f'   населення підключено: {len(popw):,} будинків, '
                  f'медіана {vals[len(vals)//2]:.0f} осіб на будинок')
    else:
        print('   population.json відсутній — усі будинки важать однаково')

    print('1) граф пішохідної мережі...')
    adj, seg = build_graph(roads + foot)
    print(f'   вузлів {len(adj):,}   ребер {len(seg)//2:,}')
    # --- ДІАГНОСТИКА ЗВ'ЯЗНОСТІ ---
    seen = set(); comps = []
    for st in adj:
        if st in seen: continue
        stack = [st]; comp = 0; seen.add(st)
        while stack:
            u = stack.pop(); comp += 1
            for v, _ in adj[u]:
                if v not in seen:
                    seen.add(v); stack.append(v)
        comps.append(comp)
    comps.sort(reverse=True)
    big = comps[0] if comps else 0
    print(f'   компонент зв\'язності: {len(comps):,}, найбільша {big:,} вузлів '
          f'({100*big/max(len(adj),1):.0f}% мережі)')
    # прив'язуємось лише до вузлів найбільшої компоненти
    seen3 = set(); mainnodes = None
    for st in adj:
        if st in seen3: continue
        stack = [st]; grp = [st]; seen3.add(st)
        while stack:
            u = stack.pop()
            for v, _ in adj[u]:
                if v not in seen3:
                    seen3.add(v); stack.append(v); grp.append(v)
        if len(grp) == big: mainnodes = set(grp)
    ngrid = Grid(list(mainnodes) if mainnodes else list(adj))

    if big / max(len(adj), 1) < 0.7:
        print('   !!! УВАГА: мережа сильно розірвана — імовірно, неповні дані foot/roads.')
        print('   !!! Перезапустіть 2b-RISKS, видаливши data/osm_risks_raw.json')
    # до якої компоненти належить перевірювана вулиця
    if len(sys.argv) > 1 and sys.argv[1].strip():
        q0 = sys.argv[1].strip().lower()
        mainset = None
        for st in adj:
            pass
        # позначаємо вузли найбільшої компоненти
        seen2 = set()
        for st in adj:
            if st in seen2: continue
            stack = [st]; group = [st]; seen2.add(st)
            while stack:
                u = stack.pop()
                for v, _ in adj[u]:
                    if v not in seen2:
                        seen2.add(v); stack.append(v); group.append(v)
            if len(group) == big: mainset = set(group); break
        inmain = out = 0
        for wq in roads:
            nm = (wq.get('tags', {}) or {}).get('name', '')
            if q0 in nm.lower():
                for pnt in wq.get('geometry', []):
                    k = key(pnt['lat'], pnt['lon'])
                    if mainset and k in mainset: inmain += 1
                    else: out += 1
        if inmain or out:
            print(f'   "{sys.argv[1]}": вузлів у головній мережі {inmain}, поза нею {out}')
            if out and not inmain:
                print('   !!! ця вулиця ВІДРІЗАНА від мережі — маршрути через неї неможливі')

    # прив'язка будинків до мережі — один раз
    print('2) прив\'язую будинки до мережі...')
    hnodes = []
    for i, h in enumerate(houses):
        if i and i % 4000 == 0: print(f'   {i:,} / {len(houses):,}', flush=True)
        n = ngrid.nearest(*h, rad=300)
        if n: hnodes.append((h, n, (popw or {}).get(i, 1.0)))
    print(f'   прив\'язано {len(hnodes):,}')

    total = collections.defaultdict(float)
    per_flow = {}
    for fname, keys in FLOWS.items():
        tg = []
        for k in keys: tg += centers(raw.get(k, []))
        if not tg:
            print(f'   потік {fname}: цілей немає, пропускаю'); continue
        tgrid = Grid(tg)
        tnodes = {}
        for t in tg:
            n = ngrid.nearest(*t, rad=400)
            if n: tnodes[t] = n
        print(f'3) потік "{fname}": цілей {len(tg):,}, з них у мережі {len(tnodes):,}')

        load = collections.defaultdict(float); ok = 0; t0 = time.time()
        no_t = no_p = 0
        for i, (h, hn, wgt) in enumerate(hnodes):
            if i and i % 2000 == 0:
                print(f'   {i:,} / {len(hnodes):,}   маршрутів {ok:,}   {time.time()-t0:.0f} c', flush=True)
            near = tgrid.within(*h, MAX_M)[:NEAR_N]
            if not near:
                nb = tgrid.nearest(*h, rad=MAX_M)
                near = [(0, nb)] if nb else []
            if not near: no_t += 1; continue
            tn = [tnodes[p] for d, p in near if p in tnodes]
            if not tn: no_t += 1; continue
            path = dijkstra_multi(adj, hn, tn, MAX_M * 1.5)
            if not path: no_p += 1; continue
            ok += 1
            for e in path: load[e] += wgt
        print(f'   маршрутів прокладено: {ok:,}   без цілі поблизу: {no_t:,}   шлях не знайдено: {no_p:,}')
        per_flow[fname] = load
        for e, c in load.items(): total[e] += c

    if not total:
        print('жодного маршруту — перевірте дані'); sys.exit(1)

    print('4) зводжу по вулицях...')
    # Навантаження вулиці = СЕРЕДНЄ по її власних відрізках, зважене на довжину.
    # Пішохідна доріжка враховується, якщо йде впритул уздовж дороги (коридор),
    # але кожна вулиця збирає лише свій слід — без запозичення в сусідів.
    road_nm = {w['id']: (w.get('tags', {}) or {}).get('name', '') for w in roads}
    road_ids = set(road_nm)

    # 1) слід кожного ребра прив'язуємо до найближчої ДОРОГИ (не далі 35 м)
    CELL = 0.0006
    rgrid = collections.defaultdict(list)
    for w in roads:
        g = w.get('geometry') or []
        for a, b in zip(g, g[1:]):
            mla, mlo = (a['lat'] + b['lat']) / 2, (a['lon'] + b['lon']) / 2
            rgrid[(int(mla / CELL), int(mlo / CELL))].append((mla, mlo, w['id']))

    def owner(la, lo, rad=35.0):
        my, mx = mdeg(la)
        ci, cj = int(la / CELL), int(lo / CELL)
        best, bd = None, 1e18
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for pa, po, wid_ in rgrid.get((ci + di, cj + dj), ()):
                    d = math.hypot((pa - la) * my, (po - lo) * mx)
                    if d < bd: bd, best = d, wid_
        return best if bd <= rad else None

    own_cache = {}
    def by_way(load):
        acc = collections.defaultdict(float)   # сума (навантаження × довжина)
        ln  = collections.defaultdict(float)   # сума довжин
        for e, c in load.items():
            if e not in seg: continue
            wid, nm = seg[e]
            if wid not in road_ids:
                (la1, lo1), (la2, lo2) = e
                mk = (round((la1 + la2) / 2, 5), round((lo1 + lo2) / 2, 5))
                if mk in own_cache: wid = own_cache[mk]
                else: wid = own_cache[mk] = owner(*mk)
                if wid is None: continue
            d_ = dist_m(e[0], e[1]) or 1.0
            acc[wid] += c * d_
            ln[wid] += d_
        out = {}
        for wid in acc:
            out[wid] = [int(round(acc[wid] / max(ln[wid], 1))), road_nm.get(wid, '')]
        return out

    tot_w = by_way(total)
    flow_w = {f: by_way(l) for f, l in per_flow.items()}

    geo = {}
    for w in roads:
        g = w.get('geometry')
        if g and w.get('id') in tot_w:
            st = max(1, len(g)//10)
            geo[w['id']] = [[round(p['lat'],5), round(p['lon'],5)] for p in g[::st]]

    items = []
    for wid, (c, nm) in tot_w.items():
        if wid in geo and c > 0:
            sch = flow_w.get('school', {}).get(wid, [0, ''])[0]
            trn = flow_w.get('transit', {}).get(wid, [0, ''])[0]
            shp = flow_w.get('shop', {}).get(wid, [0, ''])[0]
            # 7-й елемент — id відрізка OSM. Потрібен кроку 4, щоб брати потік
            # ПО ВІДРІЗКУ, а не максимум по назві вулиці (див. коментар там).
            items.append([geo[wid], nm, c, sch, trn, shp, wid])
    # ---- ГЕОМЕТРІЯ МЕРЕЖІ: проникність, перехрестя, звивистість ----
    # Johnson & Bowers (2014), "Examining the Relationship Between Road Structure and
    # Burglary Risk Via Quantitative Network Analysis", J. of Quantitative Criminology
    # 30(2). (У попередній редакції коду рік було вказано помилково — 2010.)
    print('5) геометрія мережі...')
    deg = collections.Counter()
    for u in adj: deg[u] = len(set(v for v, _ in adj[u]))
    netgeo = {}
    for w in roads:
        g = w.get('geometry')
        if not g or len(g) < 2: continue
        pts = [key(p['lat'], p['lon']) for p in g]
        ends = [pts[0], pts[-1]]
        # тип кінців: 1 = тупик, 2 = продовження, 3 = T-подібне, 4+ = хрестоподібне
        dg = [deg.get(e, 1) for e in ends]
        cross4 = sum(1 for d in dg if d >= 4)
        cross3 = sum(1 for d in dg if d == 3)
        dead = sum(1 for d in dg if d <= 1)
        # проникність: скільки різних напрямків доступно з кінців
        perm = sum(dg)
        # звивистість: відношення довжини по осі до прямої
        L = sum(dist_m(a, b) for a, b in zip(pts, pts[1:]))
        straight = dist_m(pts[0], pts[-1]) or 1.0
        sinuo = L / straight
        # щільність перехресть уздовж відрізка
        inner = sum(1 for p in pts[1:-1] if deg.get(p, 2) >= 3)
        netgeo[w['id']] = dict(perm=perm, cross4=cross4, cross3=cross3, dead=dead,
                               sinuo=round(sinuo, 3), inner=inner, length=round(L))
    json.dump(netgeo, open(os.path.join(DATA, 'netgeo.json'), 'w', encoding='utf-8'),
              separators=(',', ':'))
    dd = collections.Counter()
    for v in netgeo.values():
        dd['тупики' if v['dead'] else ('хрестоподібні' if v['cross4'] else
            ('T-подібні' if v['cross3'] else 'прості'))] += 1
    for k, v in dd.most_common(): print(f'   {k}: {v:,}')
    print(f'   -> data/netgeo.json ({len(netgeo):,} відрізків)')

    items.sort(key=lambda x: -x[2])
    json.dump({'title': 'Модельована пішохідна прохідність', 'items': items},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',',':'))
    print(f'   відрізків {len(items):,} -> data/network.json')

    def rank_of(items, idx, title):
        agg = collections.Counter()
        for it in items:
            if it[1]: agg[it[1]] = max(agg[it[1]], it[idx])
        r = [(n, c) for n, c in agg.most_common() if c > 0]
        print(f'\n=== ТОП-20: {title} ===')
        for i, (n, c) in enumerate(r[:20], 1): print(f'   {i:3}. {c:6}  {n}')
        return r

    rank_all = rank_of(items, 2, 'загальна прохідність')
    rank_sch = rank_of(items, 3, 'ПОТІК ДО ШКІЛ І САДКІВ')

    if len(sys.argv) > 1 and sys.argv[1].strip():
        q = sys.argv[1].strip().lower()
        print(f'\n=== ПЕРЕВІРКА: "{sys.argv[1]}" ===')
        for label, r in (('загальна', rank_all), ('до шкіл', rank_sch)):
            hit = [(i, n, c) for i, (n, c) in enumerate(r, 1) if q in n.lower()]
            if not hit:
                print(f'   {label}: не знайдено')
            for i, n, c in hit:
                print(f'   {label}: місце {i} з {len(r)} (верхні {100*i/len(r):.1f}%)  навантаження {c}  — {n}')

if __name__ == '__main__':
    main()
