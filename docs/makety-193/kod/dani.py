"""Дані для макетів ZAVDANNYA-193: одні й ті самі числа для всіх стилів (випуск vypusk-kyiv-2026-11-21)."""
import sqlite3, json, math, sys, collections
import h3
sys.path.insert(0, '/home/user/dani-edrsr/src')
import hrupy as HR, labels as L
D = '/tmp/claude-0/-home-user/97326387-a0cb-5f2b-94fd-02e550169a0b/scratchpad/d/'
c = sqlite3.connect(D + 'vuzkyi.db')
BORD = json.load(open('/home/user/moya-vulytsya/data/borders.json'))
NAZVY = {}
for kod, (v, s) in L.CODE.items():
    st, _, t = s.partition(' · ')
    if t: NAZVY.setdefault(st, t)

def inpoly(lat, lon, poly):
    ins = False; j = len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i]; yj, xj = poly[j]
        if ((yi > lat) != (yj > lat)) and lon < (xj - xi) * (lat - yi) / (yj - yi + 1e-12) + xi: ins = not ins
        j = i
    return ins

def rayon(lat, lon):
    for r, p in BORD.items():
        if inpoly(lat, lon, p): return r
    return None

rows = c.execute("""select e.vyd, e.stattia, e.data_podii, e.chas, l.lat, l.lon, l.location_id from event e join location l using(location_id)
 where e.pokaz='карта' and e.chutlyva=0 and e.doc_id not in (select doc_id from withdrawal)""").fetchall()
ev = []
for vyd, st, d, chas, lat, lon, lid in rows:
    g = HR.hrupa(vyd, st)
    if not g or not d or len(d) < 4: continue
    ev.append((g, st, int(d[:4]), chas, lat, lon, lid))
VID = [e for e in ev if 2024 <= e[2] <= 2026]
print('усього з точкою', len(ev), 'відкритих', len(VID))

def soty(res):
    cnt = collections.Counter(h3.latlng_to_cell(e[4], e[5], res) for e in VID)
    vals = sorted(cnt.values())
    # частки 20/20/20/28/12 (MV-55)
    q = [vals[int(len(vals) * p)] for p in (0.2, 0.4, 0.6, 0.88)]
    feats = []
    for k, n in cnt.items():
        cl = 1 + sum(n > t for t in q)
        b = [[lon, lat] for lat, lon in h3.cell_to_boundary(k)]
        b.append(b[0])
        feats.append({'type': 'Feature', 'properties': {'n': n, 'c': cl, 'h': k},
                      'geometry': {'type': 'Polygon', 'coordinates': [b]}})
    return {'type': 'FeatureCollection', 'features': feats}, cnt

S7, c7 = soty(7)
S8, c8 = soty(8)
out = {'vsogo': len(VID), 'soty7': S7, 'soty8': S8}
out['hrupy'] = [dict(k=k, nazva=n, slovo=s, svitla=a, temna=b) for k, n, s, a, b in HR.HRUPY]
out['misto_hrupy'] = collections.Counter(e[0] for e in VID)

# Проблеми (без насильства — лише числом, як на сайті)
pr = c.execute("select problem_id, vyd, mekhanizm, status, lat, lon, podii from problem").fetchall()
out['problemy'] = [dict(id=a, vyd=b, nazva=m, status=s, lat=la, lon=lo, n=n) for a, b, m, s, la, lo, n in pr if b != 'НАС']
print('проблем', len(pr), 'показ', len(out['problemy']), collections.Counter(p[3] for p in pr))

# Райони: межі й центри підписів
out['rayony'] = {r: {'mezha': [[lo, la] for la, lo in p]} for r, p in BORD.items()}
for r, p in BORD.items():
    out['rayony'][r]['tsentr'] = [sum(x[1] for x in p) / len(p), sum(x[0] for x in p) / len(p)]

# Вибрана сота (картка на карті): найбільша сота рівня 8 у Подільському
pod = BORD['Подільський']
k8 = max((k for k in c8 if inpoly(*h3.cell_to_latlng(k), pod)), key=lambda k: c8[k])
evk = [e for e in ev if h3.latlng_to_cell(e[4], e[5], 8) == k8]
vk = [e for e in evk if 2024 <= e[2] <= 2026]
hod = collections.Counter(int(e[3][:2]) // 3 for e in vk if e[3] and e[3][:2].isdigit() and int(e[3][:2]) < 24)
med = sorted(c8.values())[len(c8) // 2]
out['sota'] = {'h': k8, 'tsentr': h3.cell_to_latlng(k8), 'n': len(vk), 'raz': round(len(vk) / med, 1),
               'hrupy': collections.Counter(e[0] for e in vk).most_common(),
               'roky': {r: sum(1 for e in evk if e[2] == r) for r in range(2016, 2027)},
               'pik': hod.most_common(1)[0][0] * 3 if hod else None,
               'problemy': [p['nazva'] + ' (' + (p['status'] or '') + ')' for p in out['problemy']
                            if h3.latlng_to_cell(p['lat'], p['lon'], 8) == k8]}
print('сота', out['sota'])

# Будинок: Вишгородська вулиця, 33 (номер у макеті закрито)
B = json.load(open(D + 'budynky.json'))
bud = next(b for b in B['budynky'] if b['vulytsia'] == 'Вишгородська вулиця' and b['nomer'] == '33')
lid = c.execute("select location_id from location where adresa='вул. Вишгородська, 33'").fetchone()[0]
be = [e for e in ev if e[6] == lid]
roky = {r: bud['podii'].get(str(r), {}) for r in (2024, 2025, 2026)}
out['budynok'] = {'vulytsia': 'Вишгородська вулиця', 'rayon': 'Подільський', 'lat': bud['lat'], 'lon': bud['lon'],
                  'skarhy': sorted(bud['skarhy'].items(), key=lambda x: -x[1]), 'susidy': bud.get('susidy', {}),
                  'susidiv': bud.get('susidiv'), 'roky': roky, 'vsogo': sum(sum(v.values()) for v in roky.values()),
                  'vse': len(be)}
print('будинок', out['budynok']['vsogo'], sum(bud['skarhy'].values()), roky)

# Район: Подільський (за точкою, як на сайті)
re_ = [e for e in ev if inpoly(e[4], e[5], pod)]
rv = [e for e in re_ if 2024 <= e[2] <= 2026]
hr = []
for k in HR.KLIUCHI:
    g = [e for e in rv if e[0] == k]
    vydy = collections.Counter(NAZVY.get(e[1], HR.NAZVA[k]) for e in g).most_common(2)
    hr.append({'k': k, 'n': len(g), 'ostanniy': sum(1 for e in g if e[2] == 2025),
               'roky': [sum(1 for e in re_ if e[0] == k and e[2] == r) for r in range(2016, 2027)],
               'vydy': [(v, round(100 * n / max(1, len(g)))) for v, n in vydy]})
sk = collections.Counter()
nb = 0
for b in B['budynky']:
    if b.get('skarhy') and inpoly(b['lat'], b['lon'], pod):
        sk.update(b['skarhy']); nb += 1
prd = [p for p in pr if inpoly(p[4], p[5], pod)]
out['rayon'] = {'nazva': 'Подільський', 'vsogo': len(rv), 'hrupy': hr, 'skarhy': sk.most_common(6), 'budynkiv': nb,
                'roky': [sum(1 for e in re_ if e[2] == r) for r in range(2016, 2027)],
                'problemy': collections.Counter(p[3] for p in prd), 'problem_n': len(prd),
                'problemy_nazvy': [p[2] for p in prd if p[1] != 'НАС'][:6]}
print('район', len(rv), [(h['k'], h['n'], h['vydy']) for h in hr], out['rayon']['problemy'], out['rayon']['roky'])
# Вектори для «Вектор · рух»: зміна 2024 -> 2025 у кожній соті рівня 7 (лише минуле, не прогноз)
v7 = collections.defaultdict(lambda: [0, 0])
for e in VID:
    if e[2] in (2024, 2025):
        v7[h3.latlng_to_cell(e[4], e[5], 7)][e[2] - 2024] += 1
cls7 = {f['properties']['h']: f['properties']['c'] for f in S7['features']}
out['vektory7'] = [dict(h=k, lat=h3.cell_to_latlng(k)[0], lon=h3.cell_to_latlng(k)[1], a=a, b=b, c=cls7.get(k, 1))
                   for k, (a, b) in v7.items() if a + b >= 6]
cls8 = {f['properties']['h']: f['properties']['c'] for f in S8['features']}
v8 = collections.defaultdict(lambda: [0, 0])
for e in VID:
    if e[2] in (2024, 2025):
        v8[h3.latlng_to_cell(e[4], e[5], 8)][e[2] - 2024] += 1
out['vektory8'] = [dict(h=k, lat=h3.cell_to_latlng(k)[0], lon=h3.cell_to_latlng(k)[1], a=a, b=b, c=cls8.get(k, 1))
                   for k, (a, b) in v8.items() if a + b >= 6]
out['sota7'] = h3.cell_to_parent(k8, 7)
out['misiatsi_1551'] = B['skarhy_misiatsi']
json.dump(out, open('dani.json', 'w'), ensure_ascii=False)
