# -*- coding: utf-8 -*-
"""ZAVDANNYA-69, крок 3: дані табло, «Місць довкола» й нижніх розділів звіту адреси (як у 64) для кількох адрес.

  set DANI_EDRSR=<тека з кодом dani-edrsr і data/ (див. skargy69.py)>
  python zvit_adresy/dani69.py <тека виходу tmp/zvit-v69> <випуск events-*.db>

Читає: <вихід>/adresy.json (приватний список адрес), <вихід>/kesh/osm.pkl (osm69.py), <вихід>/kesh/skargy.json
(skargy69.py), межі районів data/borders.json з DANI_EDRSR. Пише <вихід>/dani/<slug>.json і <вихід>/dani/_baza.json.
Усі правила й пороги — у `docs/ZVIT-ADRESY-69.md` (розд. «Як рахувалось»); тут — лише код.
"""
import os, sys, re, json, math, pickle, random, sqlite3, statistics, collections, datetime
import numpy as np
import shapely
from shapely.geometry import Point, Polygon, box
from shapely.strtree import STRtree
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
from scipy.stats import binomtest

DE = os.environ.get('DANI_EDRSR')
sys.path.insert(0, os.path.join(DE, 'src'))
import adr_kliuch as AK  # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'brend'))
import hrupy as HRP  # noqa: E402  групи подій — один словник (MV-116)

# ------------------------------------------------------------------ сталі методики (документ, розд. «Як рахувалось»)
VID, DO = '2024-01-01', '2026-11-05'          # події випуску з датою й точкою
OSTANNII_MIS = '2026-10'                         # останній повний місяць
M12 = ('2025-11-01', '2026-10-31')               # «останні 12 міс.»
P12 = ('2024-11-01', '2025-10-31')               # «попередні 12 міс.»
PISHKY_M = 800                                   # 10 хв пішки ≈ 800 м по вулицях
KLITYNKA = 20                                    # м, клітинка ділянки
VID_MEREZHI = 60                                 # м: клітинка належить ділянці, якщо до вузла мережі ≤ 60 м
VYBIRKA = 250                                    # житлових будинків на район для бази «довкола»
R_MALYI = {'shkola': 150, 'sadok': 100}          # «біля об'єкта»: як karta-kyiv mistse_zvit (R_MISTSE 50, R_SHKOLA 150)
R_MALYI_INSHI = 50
R_VELYKYI = 250                                  # більший радіус — квартал довкола
R_VUL = 400                                      # м: адреса вулиці далі від її осі — однойменна вулиця деінде
PORIH_SKUP = 5                                   # скупчення — адреса з ≥ 5 подій (MV-76)
# ваги груп (brend/hrupy.json): насильство й грабежі > крадіжки > порядок, наркотики, алкоголь > дорога
VAHY = {'nas': 4, 'kra': 3, 'nar': 2, 'por': 2, 'alk': 2, 'vod': 1, 'dtp': 1}
DOROZHNI = {'ДТП', 'ДОР'}
NE_PRO_MISTSE = 'не про місце'
G_VUL = ['дороги, тротуари, ліхтарі', 'паркування й покинуті авто', 'торгівля з рук і МАФи', 'шум і незручності від закладів',
         'сусіди й порядок', 'безпритульні', 'сміття, прибирання, сніг', 'двір, дерева, майданчики', 'інше про місце']
SEZON_TEPLO = {10, 11, 12, 1, 2, 3, 4}           # «тепло» — лише в опалювальний сезон
MASOVYI_RAZ = 3.0                                # масовий місяць: частка будинків району > 3× медіани місяців (як 66)
POVERKHY = [(1, 5), (6, 9), (10, 16), (17, 999)]
KROKY = ['значно менше', 'менше', 'як зазвичай', 'більше', 'значно більше']
MEZHI = (0.10, 0.35, 0.65, 0.90)                 # перцентилі району для 5 кроків
MIN_BAZA = 30                                    # менше одиниць у базі — «рано казати»
TYPY_OB = {'metro': 'метро', 'shkola': 'школа', 'sadok': 'садок', 'tts': 'ТЦ', 'rynok': 'ринок', 'alko': 'заклад з алкоголем',
           'park': 'парк чи сквер', 'zupynka': 'зупинка'}

LAT0 = LON0 = KX = KY = None


def xy(lat, lon):
    return ((lon - LON0) * KX, (lat - LAT0) * KY)


def pasmo(rivni):
    if not rivni:
        return None
    for a, b in POVERKHY:
        if a <= rivni <= b:
            return f'{a}–{b}' if b < 999 else f'{a}+'
    return None


def krok(x, baza, min_rizn=3.0, min_baza=MIN_BAZA):
    """-> dict(k — 0..4 або None «рано казати», pr — середній ранг у районі, med — у типового, n — скільки в базі)."""
    baza = [b for b in baza if b is not None]
    if len(baza) < min_baza or x is None:
        return dict(k=None, pr=None, med=statistics.median(baza) if baza else None, n=len(baza))
    a = np.asarray(baza, dtype=float)
    pr = float((a < x).mean() + 0.5 * (a == x).mean())
    med = float(np.median(a))
    k = 0 if pr < MEZHI[0] else 1 if pr < MEZHI[1] else 2 if pr <= MEZHI[2] else 3 if pr <= MEZHI[3] else 4
    # мала різниця з типовим — «як зазвичай»: 1–2 події за 3 роки не роблять будинок «іншим»
    if k > 2 and x - med < min_rizn:
        k = 2
    if k < 2 and med - x < min_rizn:
        k = 2
    return dict(k=k, pr=round(pr, 3), med=med, n=len(baza))


# ------------------------------------------------------------------ завантаження
def zavantazhyty(vykhid, db):
    global LAT0, LON0, KX, KY
    O = pickle.load(open(os.path.join(vykhid, 'kesh', 'osm.pkl'), 'rb'))
    LAT0, LON0, KX, KY = O['LAT0'], O['LON0'], O['KX'], O['KY']
    S = json.load(open(os.path.join(vykhid, 'kesh', 'skargy.json'), encoding='utf-8'))
    borders = json.load(open(os.path.join(DE, 'data', 'borders.json'), encoding='utf-8'))
    raiony = {n: Polygon([xy(a, b) for a, b in ring]).buffer(0) for n, ring in borders.items()}
    return O, S, raiony


def raion_tochok(raiony, X, Y):
    out = np.array([''] * len(X), dtype=object)
    for n, p in raiony.items():
        m = shapely.contains_xy(p, X, Y)
        out[m] = n
    return out


def podii(db):
    c = sqlite3.connect(db)
    rows = c.execute('''select e.event_id, e.doc_id, e.data_podii, e.chas, e.vyd, e.stattia, e.fabula, l.adresa, l.tochnist,
                               l.lat, l.lon, d.url, d.forma
                        from event e join document d using(doc_id) left join location l using(location_id)
                        where e.vyd != 'ПОЗА' ''').fetchall()
    chutlyvi = c.execute("select count(*) from event where chutlyva = 1 and data_podii >= ?", (VID,)).fetchone()[0]
    problemy = c.execute('select problem_id, riven, vyd, mekhanizm, status, lat, lon, podii, natovp, masshtab from problem').fetchall()
    pe = c.execute('select problem_id, event_id from problem_event').fetchall()
    versiia = c.execute('select versiia from release').fetchone()[0]
    return rows, chutlyvi, problemy, pe, versiia


def zvesty_podii(rows):
    """Подія = одне місце + одна дата + одна група (кілька рішень про один випадок — одна подія, як у 64)."""
    po = collections.OrderedDict()
    bez_tochky = []
    for (eid, doc, data, chas, vyd, st, fab, adr, toch, lat, lon, url, forma) in rows:
        if not data or not (VID <= data <= DO):
            continue
        if lat is None:
            bez_tochky.append(dict(id=eid, data=data, vyd=vyd, hr=HRP.hrupa(vyd, st), st=st or '', fab=fab or '', url=url))
            continue
        k = (round(lat, 6), round(lon, 6), data, vyd)
        e = po.get(k)
        if e is None:
            x, y = xy(lat, lon)
            e = po[k] = dict(id=eid, data=data, chas=chas, vyd=vyd, hr=HRP.hrupa(vyd, st), st=st or '', fab=fab or '', adr=adr or '', toch=toch,
                             x=x, y=y, rishennia=[])
        e['rishennia'].append(dict(doc=doc, url=url, st=st or '', forma=forma))
    return list(po.values()), bez_tochky


# ------------------------------------------------------------------ вулиці
def vul_z_adresy(adr):
    """адреса події -> ключі вулиць (для перехрестя «A / B» — обидві), номер або ''"""
    if not adr:
        return [], ''
    if ' / ' in adr:
        return [AK.skey(p.strip()) for p in adr.split(' / ') if p.strip()], ''
    v, _, h = adr.rpartition(',')
    if not v:
        return [AK.skey(adr)], ''
    return [AK.skey(v.strip())], h.strip()


def dovzhyna(geom):
    """довжина вулиці по осі: смуга 40 м / 40 — двосмуговий проспект не рахується двічі"""
    return geom.buffer(20).area / 40.0


# ------------------------------------------------------------------ мережа й ділянка 10 хв
class Merezha:
    def __init__(s, O):
        xyv = np.asarray(O['xy'], dtype=float)
        s.xy = xyv
        r = np.asarray(O['rebra'], dtype=float)
        i, j, w = r[:, 0].astype(np.int64), r[:, 1].astype(np.int64), np.maximum(r[:, 2], 0.01)
        n = len(xyv)
        s.G = csr_matrix((np.concatenate([w, w]), (np.concatenate([i, j]), np.concatenate([j, i]))), shape=(n, n))
        # лише вузли, з яких можна йти: проїжджа частина з `foot=no` є в малюнку карти, але не в мережі
        deg = np.diff(s.G.indptr)
        s.pishi = np.where(deg > 0)[0]
        s.kd = cKDTree(xyv[s.pishi])
        x0, y0 = xyv.min(0) - 1000
        x1, y1 = xyv.max(0) + 1000
        s.x0, s.y0 = x0, y0
        s.nx, s.ny = int((x1 - x0) / KLITYNKA) + 1, int((y1 - y0) / KLITYNKA) + 1
        cx = x0 + (np.arange(s.nx) + 0.5) * KLITYNKA
        cy = y0 + (np.arange(s.ny) + 0.5) * KLITYNKA
        XX, YY = np.meshgrid(cx, cy)               # [ny, nx]
        d, idx = s.kd.query(np.c_[XX.ravel(), YY.ravel()], distance_upper_bound=VID_MEREZHI + 1, workers=-1)
        s.c_vuzol = np.where(np.isfinite(d), s.pishi[np.minimum(idx, len(s.pishi) - 1)], -1).astype(np.int64)
        s.c_vidst = np.where(np.isfinite(d), d, 1e9)
        s.cx, s.cy = XX.ravel(), YY.ravel()

    def najblyzhchyi(s, x, y):
        d, k = s.kd.query((x, y))
        return d, int(s.pishi[k])

    def klitynka(s, X, Y):
        i = ((np.asarray(Y) - s.y0) // KLITYNKA).astype(np.int64)
        j = ((np.asarray(X) - s.x0) // KLITYNKA).astype(np.int64)
        ok = (i >= 0) & (i < s.ny) & (j >= 0) & (j < s.nx)
        return np.where(ok, i * s.nx + j, -1)

    def dilianka(s, poly):
        """-> (масив клітинок ділянки, відстані до вузлів мережі, джерела) від контуру будинку"""
        mezha = poly.exterior if hasattr(poly, 'exterior') else poly.convex_hull.exterior
        pts = [mezha.interpolate(t, normalized=True) for t in np.linspace(0, 1, 24, endpoint=False)]
        dzh = set()
        for p in pts:
            for k in s.kd.query_ball_point((p.x, p.y), 40):
                dzh.add(int(s.pishi[k]))
        if not dzh:
            c = poly.representative_point()
            dzh = {int(s.najblyzhchyi(c.x, c.y)[1])}
        dist = dijkstra(s.G, indices=sorted(dzh), min_only=True, limit=PISHKY_M)
        c = poly.representative_point()
        r = PISHKY_M + VID_MEREZHI + KLITYNKA
        i0, i1 = int((c.y - r - s.y0) // KLITYNKA), int((c.y + r - s.y0) // KLITYNKA)
        j0, j1 = int((c.x - r - s.x0) // KLITYNKA), int((c.x + r - s.x0) // KLITYNKA)
        ii, jj = np.meshgrid(np.arange(max(i0, 0), min(i1, s.ny - 1) + 1), np.arange(max(j0, 0), min(j1, s.nx - 1) + 1), indexing='ij')
        cl = (ii * s.nx + jj).ravel()
        v = s.c_vuzol[cl]
        ok = v >= 0
        cl, v = cl[ok], v[ok]
        dd = dist[v] + s.c_vidst[cl]
        m = dd <= PISHKY_M
        return cl[m], dist


# ------------------------------------------------------------------ головне
def main():
    vykhid, db = sys.argv[1], sys.argv[2]
    ADR = json.load(open(os.path.join(vykhid, 'adresy.json'), encoding='utf-8'))
    O, S, raiony = zavantazhyty(vykhid, db)
    rows, chutlyvi, problemy_db, pe, versiia = podii(db)
    P, bez_tochky = zvesty_podii(rows)
    print(f'подій з точкою {len(P)}, без точки {len(bez_tochky)}, чутливих без адреси {chutlyvi}')
    PX = np.array([e['x'] for e in P]); PY = np.array([e['y'] for e in P])
    PR = raion_tochok(raiony, PX, PY)
    for e, r in zip(P, PR):
        e['raion'] = r
    PV = np.array([e['vyd'] for e in P]); PD = np.array([e['data'] for e in P])
    kd_p = cKDTree(np.c_[PX, PY])
    ne_dor = np.array([v not in DOROZHNI for v in PV])
    m_last = (PD >= M12[0]) & (PD <= M12[1]); m_prev = (PD >= P12[0]) & (PD <= P12[1])

    # --- будинки
    B = O['budynky']
    BG = [b['poly'] for b in B]
    tree_b = STRtree(BG)
    BX = np.array([b['x'] for b in B]); BY = np.array([b['y'] for b in B])
    BR = raion_tochok(raiony, BX, BY)
    zhytlo = np.array([b['typ'] in ('apartments', 'residential', 'house', 'detached', 'terrace', 'semidetached_house') for b in B])
    # база — будинки того самого класу: багатоквартирні (apartments, residential) окремо від садиб (house…):
    # інакше в районі з приватним сектором «типова ділянка» — це садиби на околиці
    BK = np.array(['bagatokv' if b['typ'] in ('apartments', 'residential') else 'sadyba' for b in B])

    def budynok_tochky(X, Y, maks=25):
        """точки -> індекс будинку (у контурі або найближчий до maks м), -1 — немає"""
        pts = shapely.points(X, Y)
        out = np.full(len(X), -1, dtype=np.int64)
        ii, bb = tree_b.query(pts, predicate='within')
        out[ii] = bb
        rest = np.where(out < 0)[0]
        if len(rest):
            ii2, bb2 = tree_b.query_nearest(pts[rest], max_distance=maks, all_matches=False)
            out[rest[ii2]] = bb2
        return out

    P_bud = budynok_tochky(PX, PY)
    bud_podii = collections.Counter(P_bud[P_bud >= 0].tolist())

    # --- скарги 1551
    hrupy = S['hrupy']; hi = {h: i for i, h in enumerate(hrupy)}
    mis = S['misiatsi']
    SB = S['budynky']
    SX = np.array([xy(b[1], b[2])[0] for b in SB]); SY = np.array([xy(b[1], b[2])[1] for b in SB])
    S_raion = [b[3] for b in SB]
    S_bud = budynok_tochky(SX, SY)
    S_pasmo = [pasmo(B[k]['rivni']) if k >= 0 else None for k in S_bud]
    m12 = set(f'2025-{m:02d}' for m in (11, 12)) | set(f'2026-{m:02d}' for m in range(1, 11))
    # масові місяці: (район, група, місяць), коли скаржилася незвично велика частка будинків району
    po_r = collections.Counter(S_raion)
    skarzh = collections.Counter()
    for bi, gi, mi, n in S['bgm']:
        skarzh[(S_raion[bi], gi, mi)] += 1
    masovi = set()
    for rn in po_r:
        for gi in range(len(hrupy)):
            ch = [skarzh[(rn, gi, mi)] / po_r[rn] for mi in range(len(mis))]
            med = statistics.median(ch) or 1e-9
            for mi, c in enumerate(ch):
                if c > MASOVYI_RAZ * med:
                    masovi.add((rn, gi, mi))
    # скарги за 12 міс. без масових місяців і «тепла» поза сезоном: (будинок 1551) -> Counter(група)
    sk12 = collections.defaultdict(collections.Counter)
    sk12_mis = collections.defaultdict(set)
    sk_masovi = collections.defaultdict(collections.Counter)   # що відкинуто як масове — для дрібного рядка
    for bi, gi, mi, n in S['bgm']:
        ym = mis[mi]
        if ym not in m12:
            continue
        h = hrupy[gi]
        if h == NE_PRO_MISTSE:
            continue
        if h == 'тепло' and int(ym[5:]) not in SEZON_TEPLO:
            continue
        if (S_raion[bi], gi, mi) in masovi:
            sk_masovi[bi][(h, ym)] += n
            continue
        sk12[bi][h] += n
        sk12_mis[(bi, h)].add(ym)
    S_vse = np.array([sum(sk12[i].values()) for i in range(len(SB))])
    S_vul = np.array([sum(sk12[i][h] for h in G_VUL) for i in range(len(SB))])
    S_kliuch = {b[0]: i for i, b in enumerate(SB)}

    # --- мережа, клітинки
    MZ = Merezha(O)
    ncl = MZ.nx * MZ.ny
    print(f'мережа: {len(MZ.xy)} вузлів; клітинок {ncl}')
    P_cl = MZ.klitynka(PX, PY)
    S_cl = MZ.klitynka(SX, SY)

    def sumy_klitynok(cl, vagy=None):
        a = np.zeros(ncl, dtype=np.float64)
        ok = cl >= 0
        np.add.at(a, cl[ok], 1 if vagy is None else vagy[ok])
        return a
    C_ne_dtp = sumy_klitynok(P_cl, (PV != 'ДТП').astype(float))
    C_dtp = sumy_klitynok(P_cl, (PV == 'ДТП').astype(float))
    C_last = sumy_klitynok(P_cl, m_last.astype(float))
    C_prev = sumy_klitynok(P_cl, m_prev.astype(float))
    C_skvul = sumy_klitynok(S_cl, S_vul.astype(float))
    # зелень
    Z = np.zeros(ncl, dtype=bool)
    for g in O['zelen']:
        x0, y0, x1, y1 = g.bounds
        i0, i1 = max(int((y0 - MZ.y0) // KLITYNKA), 0), min(int((y1 - MZ.y0) // KLITYNKA), MZ.ny - 1)
        j0, j1 = max(int((x0 - MZ.x0) // KLITYNKA), 0), min(int((x1 - MZ.x0) // KLITYNKA), MZ.nx - 1)
        if i1 < i0 or j1 < j0:
            continue
        ii, jj = np.meshgrid(np.arange(i0, i1 + 1), np.arange(j0, j1 + 1), indexing='ij')
        cl = (ii * MZ.nx + jj).ravel()
        Z[cl[shapely.contains_xy(g, MZ.cx[cl], MZ.cy[cl])]] = True
    print('зелень: клітинок', int(Z.sum()))

    def dilianka_metryky(poly):
        cl, dist = MZ.dilianka(poly)
        return dict(cl=cl, dist=dist, ne_dtp=int(C_ne_dtp[cl].sum()), dtp=int(C_dtp[cl].sum()),
                    last=int(C_last[cl].sum()), prev=int(C_prev[cl].sum()), skvul=int(C_skvul[cl].sum()),
                    zelen=round(100.0 * Z[cl].mean(), 1) if len(cl) else 0.0, ploshcha=len(cl) * KLITYNKA ** 2)

    # --- бази району «довкола»: випадкові житлові будинки
    rnd = random.Random(69)
    baza_dov = collections.defaultdict(list)
    for rn in sorted(raiony):
        ids = sorted(int(i) for i in np.where(zhytlo & (BR == rn) & (BK == 'bagatokv'))[0])
        for i in rnd.sample(ids, min(VYBIRKA, len(ids))):
            m = dilianka_metryky(BG[i])
            m.pop('cl'); m.pop('dist')
            baza_dov[rn].append(m)
        print('база довкола:', rn, len(baza_dov[rn]))
    # тренд району: усі події району, останні 12 проти попередніх 12
    tr_raion = {rn: (int((m_last & (PR == rn)).sum()), int((m_prev & (PR == rn)).sum())) for rn in raiony}

    # --- бази вулиць: подій і скарг на 100 м
    vul_geom = collections.defaultdict(list)
    for nm, linii in O['vulytsi'].items():
        k = AK.skey(nm)
        if k:
            for l in linii:
                if len(l) >= 2:
                    vul_geom[k].append(shapely.LineString(l))
    vul_nazva = {}
    for nm in O['vulytsi']:
        k = AK.skey(nm)
        if k and (k not in vul_nazva or len(nm) < len(vul_nazva[k])):
            vul_nazva[k] = nm
    # написання з ініціалом («З.Гайдай», «З. Гайдай») -> ключ вулиці OSM, якщо такий один (прізвище збігається,
    # решта слів — початки слів ключа OSM)
    po_slovu = collections.defaultdict(set)
    for k in vul_geom:
        for w in k.split():
            po_slovu[w].add(k)
    kanon = {}

    def kanonichnyi(k):
        if k in vul_geom or not k:
            return k
        if k in kanon:
            return kanon[k]
        ws = k.split()
        dov = max(ws, key=len)
        kand = [c for c in po_slovu.get(dov, ()) if all(any(t.startswith(w) for t in c.split()) for w in ws)]
        kanon[k] = kand[0] if len(kand) == 1 else k
        return kanon[k]
    P_vul = collections.defaultdict(list)
    for i, e in enumerate(P):
        for k in vul_z_adresy(e['adr'])[0]:
            k = kanonichnyi(k)
            if k:
                P_vul[k].append(i)
    S_vulk = collections.defaultdict(list)
    for i, b in enumerate(SB):
        S_vulk[b[0].split('|')[0]].append(i)

    def vulytsia_metryky(k, blyzko_xy=None):
        ls = vul_geom.get(k)
        if not ls:
            return None
        g = shapely.union_all(ls)
        if blyzko_xy is not None:   # однойменні вулиці: лише частини в межах 4 км від будинку, зв'язні з ним
            parts = [p for p in getattr(g, 'geoms', [g]) if p.distance(Point(blyzko_xy)) < 4000]
            g = shapely.union_all(parts) if parts else g
        L = dovzhyna(g)
        if L < 1:
            return None
        ii = P_vul.get(k, [])
        n_p = int(shapely.dwithin(g, shapely.points(PX[ii], PY[ii]), R_VUL).sum()) if ii else 0
        jj = S_vulk.get(k, [])
        n_s = int(sum(S_vul[j] for j, ok in zip(jj, shapely.dwithin(g, shapely.points(SX[jj], SY[jj]), R_VUL)) if ok)) if jj else 0
        c = g.representative_point()
        return dict(L=L, podii=n_p, skargy=n_s, na100=100 * n_p / L, sk100=100 * n_s / L, geom=g, x=c.x, y=c.y)

    baza_vul = collections.defaultdict(list)
    for k in vul_geom:
        m = vulytsia_metryky(k)
        if not m or m['L'] < 300:
            continue
        rn = raion_tochok(raiony, np.array([m['x']]), np.array([m['y']]))[0]
        if rn:
            baza_vul[rn].append((m['na100'], m['sk100']))
    print('база вулиць:', {r: len(v) for r, v in baza_vul.items()})

    # --- бази будинку
    baza_bud_podii = collections.defaultdict(list)
    for i in np.where(zhytlo & (BK == 'bagatokv'))[0]:
        if BR[i]:
            baza_bud_podii[BR[i]].append(bud_podii.get(int(i), 0))
    baza_bud_sk = collections.defaultdict(list)          # (район, пасмо) -> [скарг]
    baza_bud_hr = collections.defaultdict(lambda: collections.defaultdict(list))
    for i in range(len(SB)):
        for key in ((S_raion[i], S_pasmo[i]), (S_raion[i], None)):
            baza_bud_sk[key].append(int(S_vse[i]))
            for h in hrupy:
                if h != NE_PRO_MISTSE:
                    baza_bud_hr[key][h].append(sk12[i][h])

    # --- об'єкти: дублікати (точка й контур того самого) — один
    obiekty = []
    for o in sorted(O['obiekty'], key=lambda o: o['poly'] is None):
        if any(p['typ'] == o['typ'] and math.hypot(p['x'] - o['x'], p['y'] - o['y']) < 120 and
               (p['nazva'] == o['nazva'] or not o['nazva'] or not p['nazva']) for p in obiekty[-400:]):
            continue
        obiekty.append(o)
    OX = np.array([o['x'] for o in obiekty]); OY = np.array([o['y'] for o in obiekty])
    OR = raion_tochok(raiony, OX, OY)
    kd_ne_dor = cKDTree(np.c_[PX[ne_dor], PY[ne_dor]])
    idx_ne_dor = np.where(ne_dor)[0]

    def podii_bilia(o, r, lyshe_ne_dor=True):
        """індекси подій у r м від об'єкта (контур — від межі)"""
        if o['poly'] is not None:
            g = o['poly']
            x0, y0, x1, y1 = g.bounds
            rr = r + math.hypot(x1 - x0, y1 - y0) / 2
            c = ((x0 + x1) / 2, (y0 + y1) / 2)
        else:
            g = None; rr = r; c = (o['x'], o['y'])
        if lyshe_ne_dor:
            kand = idx_ne_dor[kd_ne_dor.query_ball_point(c, rr)]
        else:
            kand = np.asarray(kd_p.query_ball_point(c, rr), dtype=np.int64)
        if g is not None and len(kand):
            kand = kand[shapely.dwithin(g, shapely.points(PX[kand], PY[kand]), r)]
        return kand

    rozpodil_typiv = {}
    for t in TYPY_OB:
        ms, mv = [], []
        for o, rn in zip(obiekty, OR):
            if o['typ'] != t or not rn:
                continue
            ms.append(len(podii_bilia(o, R_MALYI.get(t, R_MALYI_INSHI))))
            mv.append(len(podii_bilia(o, R_VELYKYI)))
        rozpodil_typiv[t] = (ms, mv)
    print('об\'єктів Києва за типами:', {t: len(v[0]) for t, v in rozpodil_typiv.items()})

    # --- проблеми випуску
    pe_po = collections.defaultdict(list)
    for pid, eid in pe:
        pe_po[pid].append(eid)
    data_po_id = {}
    for (eid, doc, data, *_r) in rows:
        data_po_id[eid] = data

    # --- адреса за адресою
    sys.path.insert(0, os.path.join(DE, 'src'))
    os.chdir(DE)
    import budynky_1551 as BU
    Dv = BU.Dovidnyk()
    os.makedirs(os.path.join(vykhid, 'dani'), exist_ok=True)
    zvedennia = []
    for A in ADR:
        bk, pravylo, pt, pidpys = Dv(*[x.strip() for x in A['adresa_1551'].rsplit(',', 1)])
        if not bk:
            print('НЕ ЗНАЙДЕНО', A['slug'], pravylo); continue
        hx, hy = xy(*pt)
        bi = int(budynok_tochky(np.array([hx]), np.array([hy]))[0])
        poly = BG[bi]
        bud = B[bi]
        rn = raion_tochok(raiony, np.array([hx]), np.array([hy]))[0]
        ps = pasmo(bud['rivni'])
        vk = bk.split('|')[0]
        out = dict(slug=A['slug'], nazva=A['nazva'], raion=rn, kliuch=bk, x=hx, y=hy, typ=bud['typ'], rivni=bud['rivni'],
                   pasmo=ps, osm=bud['osm'], versiia=versiia, chutlyvi_bez_adresy=chutlyvi)

        # ряд 1: будинок
        dim_idx = [int(i) for i in np.where(P_bud == bi)[0]]
        n_dim = len(dim_idx)
        si = S_kliuch.get(bk)
        sk_dim = int(S_vse[si]) if si is not None else 0
        key = (rn, ps) if ps and len(baza_bud_sk[(rn, ps)]) >= MIN_BAZA else (rn, None)
        hr_rows = []
        if si is not None:
            for h in hrupy:
                if h == NE_PRO_MISTSE or not sk12[si][h]:
                    continue
                kk = krok(sk12[si][h], baza_bud_hr[key][h])
                hr_rows.append(dict(h=h, n=sk12[si][h], mis=len(sk12_mis[(si, h)]), krok=kk))
        hr_rows.sort(key=lambda r: (-(r['krok']['pr'] or 0), -r['n']))
        # головна тема: найвищий крок шкали, далі — у скількох місяцях скаржилися, далі — скільки скарг
        hr_rows.sort(key=lambda r: (-(r['krok']['k'] if r['krok']['k'] is not None else -1), -r['mis'], -r['n']))
        tema = next((r for r in hr_rows if r['n'] >= 5 and (r['krok']['k'] or 0) >= 3), None)
        masovi_bud = collections.Counter()
        if si is not None:
            for (h, ym), n in sk_masovi[si].items():
                masovi_bud[(h, ym)] += n
        out['budynok'] = dict(
            podii=n_dim, podii_krok=krok(n_dim, baza_bud_podii[rn]),
            skargy=sk_dim, skargy_krok=krok(sk_dim, baza_bud_sk[key], min_rizn=5),
            skargy_baza='та сама поверховість' if key[1] else 'усі будинки району (поверховість невідома)',
            skargy_baza_n=len(baza_bud_sk[key]), hrupy=hr_rows[:8], tema=tema,
            zmist=S['zmist'].get(bk, [])[:6] if si is not None else [],
            masovi=[dict(h=h, ym=ym, n=n) for (h, ym), n in masovi_bud.most_common(4)])

        # ряд 2: вулиця
        vm = vulytsia_metryky(vk, (hx, hy))
        if vm:
            bv = baza_vul.get(rn, [])
            out['vulytsia'] = dict(nazva=vul_nazva.get(vk, ''), dovzhyna=round(vm['L']), podii=vm['podii'],
                                   skargy=vm['skargy'], na100=round(vm['na100'], 2), sk100=round(vm['sk100'], 2),
                                   podii_krok=krok(vm['na100'], [a for a, b in bv], min_rizn=300 / vm['L']),
                                   skargy_krok=krok(vm['sk100'], [b for a, b in bv], min_rizn=500 / vm['L']), baza_n=len(bv))
            vgeom = vm['geom']
        else:
            out['vulytsia'] = None
            vgeom = None

        # ряд 3–5: довкола
        dm = dilianka_metryky(poly)
        bd = baza_dov[rn]
        out['dovkola'] = dict(
            ploshcha_ga=round(dm['ploshcha'] / 1e4, 1), podii=dm['ne_dtp'], skargy=dm['skvul'], zelen=dm['zelen'],
            podii_krok=krok(dm['ne_dtp'], [m['ne_dtp'] for m in bd]), skargy_krok=krok(dm['skvul'], [m['skvul'] for m in bd], min_rizn=10),
            zelen_krok=krok(dm['zelen'], [m['zelen'] for m in bd], min_rizn=5), baza_n=len(bd))
        out['doroga'] = dict(dtp=dm['dtp'], krok=krok(dm['dtp'], [m['dtp'] for m in bd]))
        L_, P_ = dm['last'], dm['prev']
        rl, rp = tr_raion[rn]
        p0 = rl / (rl + rp)
        if L_ + P_ >= 20:
            t = binomtest(L_, L_ + P_, p0)
            ind = L_ / (L_ + P_)
            baza_ind = [m['last'] / (m['last'] + m['prev']) for m in bd if m['last'] + m['prev'] >= 20]
            kk = krok(ind, baza_ind, min_rizn=0)
            if t.pvalue >= 0.05:
                kk['k'] = 2
            slovo = 'без помітних змін' if kk['k'] == 2 else ('більшає' if ind > p0 else 'меншає')
            out['zminy'] = dict(ostanni=L_, poperedni=P_, raion_ostanni=rl, raion_poperedni=rp, p=round(t.pvalue, 4),
                                krok=kk, slovo=slovo, tut_pct=round(100 * (L_ - P_) / P_) if P_ else None,
                                raion_pct=round(100 * (rl - rp) / rp))
        else:
            out['zminy'] = dict(ostanni=L_, poperedni=P_, raion_ostanni=rl, raion_poperedni=rp, krok=dict(k=None, med=None),
                                slovo='рано казати', tut_pct=None, raion_pct=round(100 * (rl - rp) / rp))

        # --- «Місця довкола»
        cl_set = set(dm['cl'].tolist())
        dist = dm['dist']

        def merezhna(px, py, poly_=None):
            """відстань по вулицях від будинку до точки чи контуру, м (None — поза 10 хв)"""
            if poly_ is not None:
                mezha = poly_.exterior if hasattr(poly_, 'exterior') else poly_.convex_hull.exterior
                pts = [mezha.interpolate(t, normalized=True) for t in np.linspace(0, 1, 40, endpoint=False)]
            else:
                pts = [Point(px, py)]
            best = None
            for p in pts:
                d, k = MZ.najblyzhchyi(p.x, p.y)
                if d <= VID_MEREZHI and np.isfinite(dist[k]):
                    v = dist[k] + d
                    best = v if best is None else min(best, v)
            return best

        mistsia = []
        # 1-й прохід: кандидати подій біля кожного об'єкта; 2-й: кожна подія — лише найближчому об'єкту
        # (ТЦ, бар у ньому й зупинка біля входу не отримують ту саму крадіжку тричі)
        kand = []
        for o in obiekty:
            if math.hypot(o['x'] - hx, o['y'] - hy) > PISHKY_M + 200:
                continue
            d = merezhna(o['x'], o['y'], o['poly'])
            if d is None:
                continue
            rm = R_MALYI.get(o['typ'], R_MALYI_INSHI)
            ii = [int(i) for i in podii_bilia(o, rm) if int(i) not in dim_idx]
            g = o['poly'] if o['poly'] is not None else Point(o['x'], o['y'])
            kand.append((o, d, rm, {i: g.distance(Point(P[i]['x'], P[i]['y'])) for i in ii}))
        vlasnyk = {}
        for k, (o, d, rm, dd_) in enumerate(kand):
            for i, v in dd_.items():
                if i not in vlasnyk or v < vlasnyk[i][0]:
                    vlasnyk[i] = (v, k)
        vzhe = set(vlasnyk)
        for k, (o, d, rm, dd_) in enumerate(kand):
            ii = [i for i in dd_ if vlasnyk[i][1] == k]
            hrr = collections.Counter(P[i]['hr'] for i in ii)
            ms, mv = rozpodil_typiv[o['typ']]
            porivn = None
            # розрахунок як у карті Києва — лише коли тип міряний (≥ 20 об'єктів у місті) і подій достатньо (≥ 5 своїх)
            if o['typ'] in ('metro', 'shkola', 'sadok', 'alko', 'tts', 'rynok', 'zupynka') and len(ms) >= 20 and len(ii) >= 5:
                syri = len(dd_)
                ivel = podii_bilia(o, R_VELYKYI)
                porivn = dict(r_malyi=rm, malyi=syri, malyi_typovo=float(np.median(ms)), malyi_krok=krok(syri, ms),
                              r_velykyi=R_VELYKYI, velykyi=len(ivel), velykyi_typovo=float(np.median(mv)),
                              velykyi_krok=krok(len(ivel), mv), obiektiv=len(ms))
            mistsia.append(dict(rid='o' + o['osm'], vid='obiekt', typ=o['typ'], typ_n=TYPY_OB[o['typ']], nazva=o['nazva'],
                                x=round(o['x'] - hx), y=round(o['y'] - hy), d=round(d), r=rm, podii=len(ii), spilni=len(dd_) - len(ii),
                                hrupy=dict(hrr), vaha=sum(VAHY.get(v, 0) * n for v, n in hrr.items()), ids=[P[i]['id'] for i in ii],
                                roky=dict(collections.Counter(P[i]['data'][:4] for i in ii)),
                                ostannia=max((P[i]['data'] for i in ii), default=None), porivn=porivn))
        # скупчення без об'єкта
        lok = collections.defaultdict(list)
        for i in kd_p.query_ball_point((hx, hy), PISHKY_M + 100):
            if i in dim_idx:
                continue
            e = P[i]
            if MZ.klitynka(np.array([e['x']]), np.array([e['y']]))[0] not in cl_set:
                continue
            lok[(round(e['x'], 1), round(e['y'], 1))].append(i)
        for (lx, ly), ii in lok.items():
            ii = [i for i in ii if i not in vzhe]
            if len(ii) < PORIH_SKUP:
                continue
            d = merezhna(lx, ly)
            if d is None:
                continue
            adr = P[ii[0]]['adr']
            hrr = collections.Counter(P[i]['hr'] for i in ii)
            mistsia.append(dict(rid=f's{len(mistsia)}', vid='skupchennia', typ='skup', typ_n='скупчення', nazva=adr,
                                toch=P[ii[0]]['toch'], x=round(lx - hx), y=round(ly - hy), d=round(d), r=0, podii=len(ii),
                                hrupy=dict(hrr), vaha=sum(VAHY.get(v, 0) * n for v, n in hrr.items()), ids=[P[i]['id'] for i in ii],
                                roky=dict(collections.Counter(P[i]['data'][:4] for i in ii)),
                                ostannia=max(P[i]['data'] for i in ii), porivn=None))
        # скарги «вуличних» груп біля місця (у тих самих r, для скупчення — 50 м)
        kd_s = cKDTree(np.c_[SX, SY])
        for m in mistsia:
            r = m['r'] or R_MALYI_INSHI
            jj = kd_s.query_ball_point((m['x'] + hx, m['y'] + hy), r + (60 if m['typ'] in ('park', 'shkola', 'sadok', 'tts', 'rynok') else 0))
            c = collections.Counter()
            for j in jj:
                for h in G_VUL:
                    c[h] += sk12[j][h]
            m['skargy'] = sum(c.values())
            m['skargy_hr'] = c.most_common(2)
            # стан (MV-74, Г.3): дані з 2024, тож «затихло» (2 повні роки без подій) і «росте» (3 повні роки) ще неможливі
            if not m['podii']:
                m['stan'] = None
            elif m['ostannia'] >= M12[0]:
                m['stan'] = 'нове' if min(m['roky']) >= '2025' and m['podii'] >= PORIH_SKUP else 'триває'
            else:
                m['stan'] = 'рано казати'
        out['mistsia_vsi'] = len(mistsia)
        out['mistsia'] = mistsia

        # --- нижні розділи (як у 64)
        def ev(i, d):
            e = P[i]
            return dict(id=e['id'], data=e['data'], chas=e['chas'], vyd=e['vyd'], st=e['st'], fab=e['fab'][:1200],
                        adr=e['adr'], x=[round(e['x'] - hx, 1), round(e['y'] - hy, 1)], d=round(d, 1), rishennia=e['rishennia'])
        bil = kd_p.query_ball_point((hx, hy), 300)
        dim_s = set(dim_idx)
        dd = {i: poly.distance(Point(P[i]['x'], P[i]['y'])) for i in bil}
        out['dim'] = [ev(i, 0) for i in dim_idx]
        out['p100'] = [ev(i, dd[i]) for i in bil if i not in dim_s and dd[i] <= 100]
        out['p300'] = [ev(i, dd[i]) for i in bil if i not in dim_s and 100 < dd[i] <= 300]
        # вулиця за адресами
        vl = collections.defaultdict(list)
        for i in P_vul.get(vk, []):
            if vgeom is not None and vgeom.distance(Point(P[i]['x'], P[i]['y'])) <= R_VUL:
                ks, nom = vul_z_adresy(P[i]['adr'])
                vl[AK.nh(nom) if nom else 'перехрестя'].append(i)
        nom_bud = bk.split('|')[1]
        vul_list = []
        for n, ii in vl.items():
            vul_list.append(dict(n=n, k=len(ii), hr=collections.Counter(HRP.NAZVA.get(P[i]['hr'], 'інше') for i in ii).most_common(),
                                 x=[round(P[ii[0]]['x'] - hx, 1), round(P[ii[0]]['y'] - hy, 1)], skup=len(ii) >= PORIH_SKUP and n != 'перехрестя',
                                 ty=(n == nom_bud), roky=dict(collections.Counter(P[i]['data'][:4] for i in ii)),
                                 ostannia=max(P[i]['data'] for i in ii)))
        out['vul_list'] = sorted(vul_list, key=lambda v: -v['k'])
        out['vul_k'] = sum(v['k'] for v in vul_list)
        # без точного номера: подія без точки, фабула називає вулицю (характерне слово назви)
        slova = [w for w in re.findall(r'[А-ЯІЇЄҐ][а-яіїєґʼ\'-]{3,}', out['vulytsia']['nazva'] if out['vulytsia'] else '')]
        if slova:
            rx = re.compile(r'\b' + r'\w*\s+'.join(re.escape(w[:-1]) for w in slova[-2:]) + r'\w*', re.I) if len(slova) > 1 \
                else re.compile(r'\b' + re.escape(slova[0][:-1]) + r'\w*', re.I)
            out['bez_nom'] = sum(1 for e in bez_tochky if rx.search(e['fab'] or ''))
        else:
            out['bez_nom'] = 0
        # проблеми випуску в 1,5 км
        pr = []
        for (pid, riv, vyd, mekh, status, la, lo, pod, natovp, mass) in problemy_db:
            if la is None:
                continue
            px, py = xy(la, lo)
            d = math.hypot(px - hx, py - hy)
            if d > 1500:
                continue
            ds = sorted(x for x in (data_po_id.get(e) for e in pe_po[pid]) if x)
            pr.append(dict(id=pid, riven=riv, vyd=vyd, mekh=mekh, status=status, x=[round(px - hx), round(py - hy)], d=round(d),
                           podii=pod, roky=dict(collections.Counter(x[:4] for x in ds)), ostannia=ds[-1] if ds else None,
                           masshtab=json.loads(mass) if mass else None))
        out['problemy'] = sorted(pr, key=lambda p: p['d'])
        # найрідша справа району поруч
        st_r = collections.Counter(P[i]['st'].split('·')[0].strip() for i in np.where(PR == rn)[0])
        ridki = [i for i in np.where(PR == rn)[0] if st_r[P[i]['st'].split('·')[0].strip()] == 1]
        ridki.sort(key=lambda i: math.hypot(P[i]['x'] - hx, P[i]['y'] - hy))
        out['ridki'] = [ev(int(i), math.hypot(P[i]['x'] - hx, P[i]['y'] - hy)) for i in ridki[:3]]
        k300 = [i for i in bil if dd[i] <= 300]
        out['roky'] = dict(collections.Counter(P[i]['data'][:4] for i in k300))
        out['hr300'] = collections.Counter(HRP.NAZVA.get(P[i]['hr'], 'інше') for i in k300).most_common()
        out['st300'] = collections.Counter(P[i]['st'] for i in k300).most_common(10)
        ri = np.where(PR == rn)[0]
        out['ob_h'] = collections.Counter(HRP.NAZVA.get(P[i]['hr'], 'інше') for i in ri).most_common()
        out['ob_n'] = len(ri)
        out['ob_roky'] = dict(collections.Counter(P[i]['data'][:4] for i in ri))
        # медіана подій у 300 м навколо житлових будинків району (та сама вибірка, що для «довкола»)
        rnd2 = random.Random(64)
        ids = sorted(int(i) for i in np.where(zhytlo & (BR == rn) & (BK == 'bagatokv'))[0])
        smp = rnd2.sample(ids, min(1000, len(ids)))
        out['ob_med'] = float(np.median([len(kd_p.query_ball_point((BX[i], BY[i]), 300)) for i in smp]))
        out['k300'] = len(k300)

        # --- карта: будинки, зелень, дороги в 1 км; контур ділянки
        R = 1100
        win = box(hx - R, hy - R, hx + R, hy + R)

        def lin(c):
            return [[round(x - hx), round(-(y - hy))] for x, y in c]
        bud_m = []
        for j in tree_b.query(win):
            g = BG[j]
            for p in getattr(g, 'geoms', [g]):
                bud_m.append(dict(p=lin(p.exterior.coords), ty=int(j) == bi))
        zel_m = []
        for g in O['zelen']:
            if g.intersects(win):
                g2 = g.intersection(win)
                for p in getattr(g2, 'geoms', [g2]):
                    if p.geom_type == 'Polygon' and p.area > 200:
                        zel_m.append(lin(p.simplify(3).exterior.coords))
        dor_m = []
        for klas, nm, l in O['dorogy']:
            if any(abs(x - hx) < R and abs(y - hy) < R for x, y in l[::max(1, len(l) // 6)] + [l[-1]]):
                dor_m.append(dict(k=klas, n=nm, p=lin(l)))
        cl = dm['cl']
        sq = [box(MZ.cx[c] - KLITYNKA / 2 - 0.5, MZ.cy[c] - KLITYNKA / 2 - 0.5, MZ.cx[c] + KLITYNKA / 2 + 0.5, MZ.cy[c] + KLITYNKA / 2 + 0.5) for c in cl]
        kont = shapely.union_all(sq).simplify(12)
        kont_m = [lin(p.exterior.coords) for p in getattr(kont, 'geoms', [kont]) if p.area > 5000]
        vul_m = [lin(l.coords) for l in getattr(vgeom, 'geoms', [vgeom])] if vgeom is not None else []
        out['mapa'] = dict(bud=bud_m, zel=zel_m, dor=dor_m, kontur=kont_m, vul=vul_m)
        out['podii_tochky'] = [dict(x=round(P[i]['x'] - hx), y=round(-(P[i]['y'] - hy)), vyd=P[i]['vyd'], data=P[i]['data'])
                               for i in kd_p.query_ball_point((hx, hy), R)]
        json.dump(out, open(os.path.join(vykhid, 'dani', A['slug'] + '.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, separators=(',', ':'), default=lambda o: o if not isinstance(o, np.generic) else o.item())
        zvedennia.append((A['slug'], rn, n_dim, sk_dim, out['vulytsia'] and out['vulytsia']['podii'], dm['ne_dtp'], dm['dtp'],
                          dm['zelen'], out['zminy']['slovo'], len(mistsia)))
        print('готово', zvedennia[-1])

    # бази — для документа
    json.dump(dict(
        dovkola={rn: {k: dict(med=float(np.median([m[k] for m in v])), p10=float(np.percentile([m[k] for m in v], 10)),
                              p90=float(np.percentile([m[k] for m in v], 90)), n=len(v))
                      for k in ('ne_dtp', 'dtp', 'skvul', 'zelen', 'last', 'prev')} for rn, v in baza_dov.items()},
        vulytsi={rn: dict(n=len(v), med_na100=float(np.median([a for a, b in v])), p90_na100=float(np.percentile([a for a, b in v], 90)),
                          med_sk100=float(np.median([b for a, b in v]))) for rn, v in baza_vul.items()},
        budynky_podii={rn: dict(n=len(v), nul=round(sum(1 for x in v if x == 0) / len(v), 3), p90=float(np.percentile(v, 90)),
                                p99=float(np.percentile(v, 99))) for rn, v in baza_bud_podii.items()},
        trend_raion=tr_raion, typy={t: dict(n=len(v[0]), med_malyi=float(np.median(v[0])) if v[0] else None,
                                            p90_malyi=float(np.percentile(v[0], 90)) if v[0] else None,
                                            med_velykyi=float(np.median(v[1])) if v[1] else None) for t, v in rozpodil_typiv.items()},
        masovi=len(masovi), zvedennia=zvedennia), open(os.path.join(vykhid, 'dani', '_baza.json'), 'w', encoding='utf-8'),
        ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
