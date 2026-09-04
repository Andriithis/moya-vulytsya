# -*- coding: utf-8 -*-
"""Крок 2b. Шар РИЗИКІВ з OpenStreetMap: об'єкти + відсутності."""
import os, sys, json, time, math, urllib.request, urllib.parse, urllib.error, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
RAW  = os.path.join(DATA, 'osm_risks_raw.json')
OUT  = os.path.join(DATA, 'risks.json')

# overpass.osm.ch виключено: стабільно повертає порожню відповідь замість помилки
ENDPOINTS = ['https://overpass-api.de/api/interpreter',
             'https://overpass.kumi.systems/api/interpreter',
             'https://overpass-api.de/api/interpreter',
             'https://overpass.kumi.systems/api/interpreter']

AREA = 'area["boundary"="administrative"]["admin_level"="4"]["name"="Київ"]->.k;'

# лёгкі шари - одним запитом; важкі - плитками
LIGHT = {
 # --- атрактори за літературою ---
 'alcohol': '(nwr["amenity"~"^(bar|pub|nightclub|biergarten)$"](area.k);'
            'nwr["shop"~"^(alcohol|wine|beverages)$"](area.k););out tags center;',
 'bar_on':  '(nwr["amenity"~"^(bar|pub|nightclub|biergarten)$"](area.k););out tags center;',
 'bar_off': '(nwr["shop"~"^(alcohol|wine|beverages)$"](area.k););out tags center;',
 'shop24':  '(nwr["shop"="convenience"](area.k);'
            'nwr["amenity"="fast_food"](area.k););out tags center;',
 'finance': '(nwr["shop"~"^(pawnbroker|money_lender)$"](area.k);'
            'nwr["amenity"~"^(bureau_de_change|money_transfer)$"](area.k);'
            'nwr["amenity"="atm"](area.k);node["amenity"="atm"](area.k););out tags center;',
 'gambling':'(nwr["amenity"~"^(casino|gambling)$"](area.k);'
            'nwr["shop"="bookmaker"](area.k);'
            'nwr["leisure"="adult_gaming_centre"](area.k););out tags center;',
 'food':    '(nwr["amenity"~"^(restaurant|cafe)$"](area.k););out tags center;',
 'fuel':    '(nwr["amenity"="fuel"](area.k););out tags center;',
 'parking': '(nwr["amenity"="parking"](area.k););out tags center;',
 # --- генератори ---
 'metro':   '(node["railway"="subway_entrance"](area.k);'
            'nwr["railway"="station"](area.k););out tags center;',
 'busstop': '(node["highway"="bus_stop"](area.k);'
            'node["public_transport"="platform"](area.k););out tags center;',
 'market':  '(nwr["amenity"="marketplace"](area.k);'
            'nwr["shop"~"^(mall|department_store|supermarket)$"](area.k););out tags center;',
 'transit': '(node["railway"="subway_entrance"](area.k);'
            'nwr["amenity"="bus_station"](area.k);'
            'nwr["railway"="station"](area.k);'
            'nwr["amenity"="marketplace"](area.k););out tags center;',
 'school':  '(nwr["amenity"~"^(school|kindergarten)$"](area.k););out tags center;',
 'univer':  '(nwr["amenity"~"^(university|college)$"](area.k););out tags center;',
 'health':  '(nwr["amenity"~"^(hospital|clinic|pharmacy)$"](area.k););out tags center;',
 # --- установи, у яких оформлюють протоколи ---
 # Відділи поліції, суди, прокуратура. Потрібні не як чинник ризику, а щоб
 # викидати їх з карти: подія, записана на адресу відділу, сталася не там.
 # Беремо саме з OSM, бо це КООРДИНАТИ — текстовий перелік адрес спіткала б
 # та сама біда, що й решту адрес тут: «вул. С. Хороброго, 9» і «вул. Святослава
 # Хороброго, 9» різні рядки, а будівля одна.
 'ustanovy':'(nwr["amenity"~"^(police|courthouse|prosecutor)$"](area.k);'
            'nwr["government"~"^(police|prosecutor)$"](area.k););out tags center;',
 # --- занедбаність ---
 'abandon': '(nwr["building"~"^(ruins|abandoned|construction)$"](area.k);'
            'nwr["abandoned"="yes"](area.k);nwr["ruins"="yes"](area.k);'
            'nwr["disused"="yes"](area.k););out tags center;',
 # --- благоустрій, "очі на вулиці" ---
  'play':    '(nwr["leisure"~"^(playground|fitness_station)$"](area.k););out tags center;',
  # --- зелень: крони і трава ОКРЕМО (у літературі знаки різні) ---
  'park':    '(nwr["leisure"~"^(park|garden)$"](area.k););out tags center;',
  # --- інфраструктура руху ---
 'lamps':   '(node["highway"="street_lamp"](area.k););out skel;',
 'cross':   '(node["highway"="crossing"](area.k);node["crossing"~"."](area.k););out skel;',
 'calming': '(node["traffic_calming"~"."](area.k);'
            'node["highway"="traffic_signals"](area.k););out skel;',
}
HEAVY = {
 'roads':  'way["highway"~"^(residential|tertiary|secondary|unclassified|living_street)$"]',
 'foot':   'way["highway"~"^(footway|path|pedestrian)$"]',
 'houses': 'way["building"~"^(apartments|residential|house|dormitory)$"]',
}
BBOX = (50.21, 30.24, 50.59, 30.83)
TILES = 3

def fetch(name, body, label='', allow_empty=False):
    q = '[out:json][timeout:600];' + AREA + body
    data = urllib.parse.urlencode({'data': q}).encode()
    for attempt, ep in enumerate(ENDPOINTS * 2):
        try:
            print(f'   {name:8}{label:8} <- {ep.split("/")[2]:22}', end=' ', flush=True)
            rq = urllib.request.Request(ep, data=data, headers={'User-Agent': 'edrsr-academy/3.0'})
            with urllib.request.urlopen(rq, timeout=650) as r:
                raw = r.read().decode('utf-8', 'replace')
            try:
                js = json.loads(raw)
            except Exception:
                msg = ' '.join(raw.split())[:200]
                print(f'НЕ JSON: {msg}')
                time.sleep(8); continue
            els = js.get('elements', [])
            n = len(els)
            if n == 0 and not allow_empty:
                print('0 — підозріло, пробую інший сервер')
                time.sleep(20); continue
            print(f'{n:,}')
            return els
        except urllib.error.HTTPError as e:
            wait = 45 if e.code in (429, 504) else 10
            print(f'HTTP {e.code} — пауза {wait} c')
            time.sleep(wait)
        except Exception as e:
            print(f'збій {type(e).__name__}: {str(e)[:70]}')
            time.sleep(15)
    print(f'   !!! {name}{label} НЕ ЗАВАНТАЖЕНО')
    return None

def center(el):
    if 'lat' in el: return el['lat'], el['lon']
    c = el.get('center')
    if c: return c['lat'], c['lon']
    g = el.get('geometry')
    if g: return sum(p['lat'] for p in g)/len(g), sum(p['lon'] for p in g)/len(g)
    return None

# --- геометрія ---
def m_per_deg(lat): return 111320.0, 111320.0 * math.cos(math.radians(lat))

def seg_len_m(geom):
    t = 0
    for a, b in zip(geom, geom[1:]):
        my, mx = m_per_deg((a['lat']+b['lat'])/2)
        t += math.hypot((a['lat']-b['lat'])*my, (a['lon']-b['lon'])*mx)
    return t

class Grid:
    """проста сітка для пошуку найближчих точок"""
    def __init__(self, pts, cell=0.0025):
        self.c = cell; self.g = collections.defaultdict(list)
        for la, lo in pts: self.g[(int(la/cell), int(lo/cell))].append((la, lo))
    def near(self, la, lo, rad_m):
        my, mx = m_per_deg(la)
        r = max(rad_m/my, rad_m/mx)
        n = int(r/self.c)+1
        ci, cj = int(la/self.c), int(lo/self.c)
        for i in range(ci-n, ci+n+1):
            for j in range(cj-n, cj+n+1):
                for pa, po in self.g.get((i, j), ()):
                    if math.hypot((pa-la)*my, (po-lo)*mx) <= rad_m: return True
        return False

def main():
    os.makedirs(DATA, exist_ok=True)
    if os.path.exists(RAW):
        raw = json.load(open(RAW, encoding='utf-8'))
        miss = [k for k in LIGHT if not raw.get(k)]
        if miss:
            print(f'сирі дані є, але порожні шари: {", ".join(miss)} — докачую')
            for k in miss:
                r_ = fetch(k, LIGHT[k])
                if r_: raw[k] = r_
                time.sleep(5)
            json.dump(raw, open(RAW, 'w', encoding='utf-8'), ensure_ascii=False)
        else:
            # Докачуємо лише те, чого в кеші немає. Раніше поява нової категорії
            # означала перезавантаження всіх 25 хвилин; тепер це хвилина.
            miss = [k for k in LIGHT if k not in raw]
            if miss:
                print('докачую нові категорії:', ', '.join(miss))
                for k in miss:
                    r_ = fetch(k, LIGHT[k])
                    raw[k] = r_ if r_ is not None else []
                    time.sleep(5)
                json.dump(raw, open(RAW, 'w', encoding='utf-8'), ensure_ascii=False)
            else:
                print('сирі дані OSM вже є (видаліть data/osm_risks_raw.json щоб перезавантажити)')
    else:
        print('1) завантаження з OpenStreetMap (10-25 хв):')
        raw = {}
        for k, q in LIGHT.items():
            r_ = fetch(k, q)
            raw[k] = r_ if r_ is not None else []
            time.sleep(5)
        s_, w_, n_, e_ = BBOX
        dla, dlo = (n_ - s_) / TILES, (e_ - w_) / TILES
        for k, sel in HEAVY.items():
            acc, seen = [], set()
            outmode = 'out tags geom;' if k in ('roads', 'foot') else 'out center;'
            for i in range(TILES):
                for j in range(TILES):
                    bb = f'{s_+i*dla:.4f},{w_+j*dlo:.4f},{s_+(i+1)*dla:.4f},{w_+(j+1)*dlo:.4f}'
                    els = fetch(k, f'({sel}(area.k)({bb}););{outmode}',
                                f'{i*TILES+j+1}/{TILES*TILES}', allow_empty=True)
                    for el in (els or []):
                        if el.get('id') not in seen:
                            seen.add(el.get('id')); acc.append(el)
                    time.sleep(5)
            raw[k] = acc
            print(f'   {k}: разом {len(acc):,}')
        json.dump(raw, open(RAW, 'w', encoding='utf-8'), ensure_ascii=False)

    print('\n2) обробка')
    out = {'points': {}, 'lines': {}}

    NAMES = {'alcohol':'Алкоголь: бари, клуби, магазини','bar_on':'Заклади на місці (бари, клуби)',
             'bar_off':'Алкоголь на винос','shop24':'Магазини біля дому і фастфуд',
             'finance':'Ломбарди, обмінники, банкомати','gambling':'Гральні заклади',
             'food':'Кафе і ресторани','fuel':'Автозаправки','parking':'Паркінги',
             'metro':'Метро і вокзали','busstop':'Зупинки транспорту','market':'Ринки і ТЦ',
             'transit':'Метро, вокзали, ринки','school':'Школи і садки','univer':'ВНЗ',
             'health':'Лікарні й аптеки','abandon':'Покинуті та недобудовані',
             'bench':'Лавки й урни','play':'Дитячі майданчики','cctv':'Камери спостереження',
             'trees':'Дерева','park':'Парки і сквери','grass':'Трав\'яні ділянки'}
    for k, title in NAMES.items():
        pts = []
        for el in raw.get(k, []):
            c = center(el)
            if c:
                t = el.get('tags', {})
                pts.append([round(c[0],5), round(c[1],5), (t.get('name') or t.get('amenity') or t.get('shop') or '')[:40]])
        out['points'][k] = {'title': title, 'items': pts}
        print(f'   {title}: {len(pts):,}')

    # --- установи: окремий маленький файл для виключення з карти ---
    ust = []
    for el in raw.get('ustanovy', []):
        c = center(el)
        if c:
            t = el.get('tags', {})
            ust.append([round(c[0], 5), round(c[1], 5),
                        (t.get('name') or t.get('amenity') or '')[:60]])
    if ust:
        up = os.path.join(DATA, 'ustanovy.json')
        json.dump(ust, open(up, 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'))
        print(f'   установи (поліція, суди, прокуратура): {len(ust):,} -> data/ustanovy.json')

    # --- відсутності ---
    houses = [c for c in (center(e) for e in raw.get('houses', [])) if c]
    hg = Grid(houses)
    print(f'   житлових будинків: {len(houses):,}')

    fpts = []
    for w in raw.get('foot', []):
        for p in w.get('geometry', []) or []: fpts.append((p['lat'], p['lon']))
    fg = Grid(fpts); print(f'   точок пішохідних шляхів: {len(fpts):,}')

    lamps = [(e['lat'], e['lon']) for e in raw.get('lamps', []) if 'lat' in e]
    lg = Grid(lamps); print(f'   ліхтарів: {len(lamps):,}')
    if not lamps:
        print('   УВАГА: ліхтарі не завантажились — шар "без освітлення" буде майже порожній')

    cross = [(e['lat'], e['lon']) for e in raw.get('cross', []) if 'lat' in e]
    cg = Grid(cross); print(f'   переходів: {len(cross):,}')

    no_walk, maybe_walk, no_light, no_cross = [], [], [], []
    NOSW = {'no', 'none'}
    for w in raw.get('roads', []):
        g = w.get('geometry')
        if not g or len(g) < 2: continue
        t = w.get('tags', {})
        L = seg_len_m(g)
        if L < 80: continue
        # три контрольні точки замість однієї середини
        pts = [g[0], g[len(g)//2], g[-1]]
        if not any(hg.near(p['lat'], p['lon'], 130) for p in pts): continue
        line = [[round(p['lat'],5), round(p['lon'],5)] for p in g[::max(1, len(g)//12)]]
        nm = (t.get('name') or '')[:44]
        hw = t.get('highway', '')

        # --- 1. ЯВНО вказано, що тротуару немає ---
        sw_vals = {str(t.get(k, '')).lower() for k in
                   ('sidewalk', 'sidewalk:both', 'sidewalk:left', 'sidewalk:right')} - {''}
        explicit_no = (bool(sw_vals) and sw_vals <= NOSW) or str(t.get('foot', '')).lower() in NOSW
        has_sw = bool(sw_vals - NOSW)
        if explicit_no:
            no_walk.append([line, nm, int(L)])
            continue

        # --- 2. Тег відсутній -> лише припущення, і лише для дрібних вулиць ---
        # магістралі й проспекти виключаємо: там тротуар практично завжди є
        small = hw in ('residential', 'living_street', 'unclassified', 'service')
        bigname = any(x in nm.lower() for x in ('проспект', 'бульвар', 'набережна', 'шосе', 'площа'))
        if (not has_sw and not sw_vals and small and not bigname
                and not any(fg.near(p['lat'], p['lon'], 35) for p in pts)):
            maybe_walk.append([line, nm, int(L)])

        # --- освітлення: тільки якщо ліхтарі взагалі є в базі ---
        if str(t.get('lit', '')).lower() in NOSW:
            no_light.append([line, nm, int(L)])
        elif lamps and not t.get('lit') and not any(lg.near(p['lat'], p['lon'], 70) for p in pts):
            no_light.append([line, nm, int(L)])

        # --- розриви між переходами ---
        if L > 300 and not any(cg.near(p['lat'], p['lon'], 170) for p in pts):
            no_cross.append([line, nm, int(L)])

    # шари відсутностей прибрано: дані OSM про ВІДСУТНІСТЬ ненадійні,
    # двигун стабільно давав по них нуль
    out['lines'] = {}
    for k, v in out['lines'].items(): print(f"   {v['title']}: {len(v['items']):,}")

    json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',',':'))
    print(f"\n=== ГОТОВО === data/risks.json ({os.path.getsize(OUT)/1048576:.1f} МБ)")
    print('тепер запустіть 3-MAP')

if __name__ == '__main__':
    main()
