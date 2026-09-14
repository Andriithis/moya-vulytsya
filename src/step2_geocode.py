# -*- coding: utf-8 -*-
"""Крок 2. Адресна база СУВОРО в межах міста Києва + зіставлення."""
import os, re, sys, json, time, sqlite3, math, urllib.request, urllib.parse, urllib.error, collections
try:
    from .location_evidence import confirmed_rows
    from .geocode_quality import load_resolver, POLICY_VERSION, MIN_CONFIDENCE
except ImportError:
    from location_evidence import confirmed_rows
    from geocode_quality import load_resolver, POLICY_VERSION, MIN_CONFIDENCE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
DB   = os.path.join(DATA, 'events.db')
OSM  = os.path.join(DATA, 'osm_kyiv_city.json')

ENDPOINTS = ['https://overpass-api.de/api/interpreter',
             'https://overpass.kumi.systems/api/interpreter',
             'https://overpass-api.de/api/interpreter',
             'https://overpass.kumi.systems/api/interpreter']
BBOX  = (50.21, 30.24, 50.59, 30.83)
TILES = 3

QHEAD = '[out:json][timeout:600];area["boundary"="administrative"]["admin_level"="4"]["name"="Київ"]->.k;'

def _ask(body, label):
    data = urllib.parse.urlencode({'data': QHEAD + body}).encode()
    for ep in ENDPOINTS * 2:
        try:
            print(f'   {label:9} <- {ep.split("/")[2]:24}', end=' ', flush=True)
            rq = urllib.request.Request(ep, data=data, headers={'User-Agent': 'edrsr-academy/4.0'})
            with urllib.request.urlopen(rq, timeout=650) as r:
                js = json.loads(r.read().decode('utf-8', 'replace'))
            els = js.get('elements', [])
            print(f'{len(els):,}')
            return els
        except urllib.error.HTTPError as e:
            wait = 45 if e.code in (429, 504) else 10
            print(f'HTTP {e.code} — пауза {wait} c'); time.sleep(wait)
        except Exception as e:
            print(f'{type(e).__name__} — пауза 15 c'); time.sleep(15)
    print(f'   !!! {label} не завантажено')
    return None

def fetch():
    """адреси міста Києва, плитками (один великий запит сервер не витримує)"""
    if os.path.exists(OSM):
        print('   база вже завантажена (видаліть data/osm_kyiv_city.json щоб оновити)')
        return json.load(open(OSM, encoding='utf-8'))
    s_, w_, n_, e_ = BBOX
    dla, dlo = (n_ - s_) / TILES, (e_ - w_) / TILES
    out, seen, failed = [], set(), 0
    for i in range(TILES):
        for j in range(TILES):
            bb = f'{s_+i*dla:.4f},{w_+j*dlo:.4f},{s_+(i+1)*dla:.4f},{w_+(j+1)*dlo:.4f}'
            body = (f'(node["addr:housenumber"]["addr:street"](area.k)({bb});'
                    f'way["addr:housenumber"]["addr:street"](area.k)({bb}););out tags center;')
            els = _ask(body, f'{i*TILES+j+1}/{TILES*TILES}')
            if els is None:
                failed += 1; continue
            for el in els:
                identity = (el.get('type'), el.get('id'))
                if identity in seen: continue
                seen.add(identity)
                t = el.get('tags', {})
                lat = el.get('lat') or (el.get('center') or {}).get('lat')
                lon = el.get('lon') or (el.get('center') or {}).get('lon')
                if lat and lon and t.get('addr:street'):
                    out.append([t['addr:street'], t.get('addr:housenumber', ''), round(lat, 6), round(lon, 6)])
            time.sleep(4)
    if failed > TILES * TILES // 3:
        print(f'   ЗАБАГАТО невдалих плиток ({failed}) — база неповна, не зберігаю')
        return []
    if out:
        json.dump(out, open(OSM, 'w', encoding='utf-8'), ensure_ascii=False)
        print(f'   отримано {len(out):,} адрес міста Києва')
    return out

def main():
    if not os.path.exists(DB): print('спочатку крок 1'); sys.exit(1)
    conn = sqlite3.connect(DB)
    todo = confirmed_rows(conn)
    if not todo:
        conn.close()
        raise RuntimeError('Немає підтверджених місць подій. Потрібне повторне витягування з контекстом; старий CSV не є доказом.')
    # Відсутня/пошкоджена межа зупиняє крок до мережевих запитів.
    load_resolver([])
    print('1) адресна база OpenStreetMap, тільки місто Київ')
    rows = fetch()
    if not rows:
        print('   ПОМИЛКА: адресну базу не отримано. Спробуйте пізніше.')
        sys.exit(1)

    resolver = load_resolver(rows)
    out = []; st = collections.Counter()
    # DDL і всі результати змінюються разом; збій лишає попередню таблицю.
    conn.execute('BEGIN')
    try:
        conn.execute('DROP TABLE IF EXISTS geo')
        conn.execute('CREATE TABLE geo(doc_id TEXT PRIMARY KEY, lat REAL, lon REAL,\n            precision TEXT, geocode_confidence REAL NOT NULL CHECK(geocode_confidence BETWEEN 0 AND 1),\n            policy_version TEXT NOT NULL, reference_hash TEXT NOT NULL, address_key TEXT NOT NULL)')
        for doc, street, house in todo:
            hit = resolver.cached(conn, street, house)
            if hit and hit[3] >= MIN_CONFIDENCE:
                out.append((doc, *hit, POLICY_VERSION, resolver.reference_hash, resolver.key(street, house)))
                st['точний будинок'] += 1
            else:
                st['без надійної координати'] += 1
        conn.executemany('INSERT INTO geo VALUES(?,?,?,?,?,?,?,?)', out)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    print('\n=== ГОТОВО ===')
    for k, v in st.most_common():
        print(f'  {k:14} {v:8,}  {100*v/max(len(todo),1):5.1f}%')

if __name__ == '__main__':
    main()
