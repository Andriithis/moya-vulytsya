# -*- coding: utf-8 -*-
"""Крок 2d. Межі районів Києва з OpenStreetMap — щоб різати карту географічно."""
import os, sys, json, time, urllib.request, urllib.parse, urllib.error

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT  = os.path.join(DATA, 'borders.json')

ENDPOINTS = ['https://overpass-api.de/api/interpreter',
             'https://overpass.kumi.systems/api/interpreter'] * 2

# райони в містах України мають admin_level=9 (8 — це міста й громади).
# Пробуємо кілька варіантів, доки не знайдемо всі десять.
# Пошук ПРЯМО ЗА НАЗВАМИ у прямокутнику Києва.
# Фільтр (area.k) для відношень-меж ненадійний: площа Києва будується
# з тих самих меж, тому вкладені відношення в неї часто не потрапляють.
NAMES_Q = '|'.join([
    'Голосіївський район', 'Дарницький район', 'Деснянський район',
    'Дніпровський район', 'Оболонський район', 'Печерський район',
    'Подільський район', 'Святошинський район',
    "Солом'янський район", 'Солом’янський район', 'Шевченківський район',
])
BB = '50.20,30.22,50.60,30.86'
QUERIES = [
 f'[out:json][timeout:300];'
 f'relation["boundary"="administrative"]["name"~"^({NAMES_Q})$"]({BB});out geom;',

 f'[out:json][timeout:300];'
 f'relation["boundary"="administrative"]["admin_level"~"^(7|8|9)$"]({BB});out geom;',

 f'[out:json][timeout:300];'
 f'relation["place"="borough"]({BB});'
 f'relation["boundary"="administrative"]["name"~"район"]({BB});out geom;',
]

# як райони називаються в OSM -> як у нас
ALIAS = {
    'голосіївський': 'Голосіївський', 'дарницький': 'Дарницький',
    'деснянський': 'Деснянський', 'дніпровський': 'Дніпровський',
    'оболонський': 'Оболонський', 'печерський': 'Печерський',
    'подільський': 'Подільський', 'святошинський': 'Святошинський',
    "солом'янський": "Солом'янський", 'солом’янський': "Солом'янський",
    'шевченківський': 'Шевченківський',
}

def norm(nm):
    n = (nm or '').lower().replace('район', '').replace('ʼ', "'").replace('’', "'").strip()
    return ALIAS.get(n)

def rings(el):
    """збирає зовнішні кільця з членів relation"""
    segs = []
    for m in el.get('members', []):
        if m.get('role') not in ('outer', ''): continue
        g = m.get('geometry')
        if g and len(g) > 1:
            segs.append([(p['lat'], p['lon']) for p in g])
    out, used = [], [False] * len(segs)
    for i, s0 in enumerate(segs):
        if used[i]: continue
        used[i] = True
        ring = list(s0)
        changed = True
        while changed:
            changed = False
            for j, sj in enumerate(segs):
                if used[j]: continue
                if abs(ring[-1][0]-sj[0][0]) < 1e-7 and abs(ring[-1][1]-sj[0][1]) < 1e-7:
                    ring += sj[1:]; used[j] = True; changed = True
                elif abs(ring[-1][0]-sj[-1][0]) < 1e-7 and abs(ring[-1][1]-sj[-1][1]) < 1e-7:
                    ring += list(reversed(sj))[1:]; used[j] = True; changed = True
        if len(ring) > 3: out.append(ring)
    return out

def main():
    os.makedirs(DATA, exist_ok=True)
    if os.path.exists(OUT):
        print('межі вже завантажені (видаліть data/borders.json щоб оновити)')
        return
    els = None
    for qi, q in enumerate(QUERIES, 1):
        data = urllib.parse.urlencode({'data': q}).encode()
        for ep in ENDPOINTS:
            try:
                print(f'   спроба {qi}, {ep.split("/")[2]} ...', end=' ', flush=True)
                rq = urllib.request.Request(ep, data=data, headers={'User-Agent': 'edrsr-academy/5.0'})
                with urllib.request.urlopen(rq, timeout=320) as r:
                    js = json.loads(r.read().decode())
            except Exception as e:
                print(f'{type(e).__name__} — пауза 20 c'); time.sleep(20); continue
            got = js.get('elements', [])
            named = [e for e in got if norm((e.get('tags') or {}).get('name'))]
            print(f'знайдено {len(got)}, з них наших районів {len(named)}')
            if got and not named:
                ex = [(e.get('tags') or {}).get('name') for e in got[:6]]
                lv = sorted({(e.get('tags') or {}).get('admin_level') for e in got})
                print(f'      приклади назв: {ex}')
                print(f'      рівні: {lv}')
            if len(named) >= 8:
                els = got; break
            if named and (els is None or len(named) > len(els)):
                els = got
        if els and len([e for e in els if norm((e.get('tags') or {}).get('name'))]) >= 8:
            break
    if not els:
        print('не вдалось завантажити межі — карта районів будуватиметься за судом')
        sys.exit(1)

    res = {}
    for el in els:
        nm = norm((el.get('tags') or {}).get('name'))
        if not nm: continue
        rr = rings(el)
        if not rr: continue
        rr.sort(key=len, reverse=True)
        # прорідження: кожна межа до ~400 точок
        big = rr[0]
        step = max(1, len(big) // 400)
        res[nm] = [[round(a, 5), round(b, 5)] for a, b in big[::step]]
    json.dump(res, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f'\n=== ГОТОВО === {len(res)} районів -> data/borders.json')
    for k, v in sorted(res.items()): print(f'   {k}: {len(v)} точок')

if __name__ == '__main__':
    main()
