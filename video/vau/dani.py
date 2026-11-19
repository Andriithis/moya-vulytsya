"""Дані для роликів рушія «Вау» (ZAVDANNYA-127) — з випуску events-<дата>.db (приватний dani-edrsr).

Правила тут, а не в сценаріях (AGENTS.md розд. 4–8, MV-25, MV-60, MV-69):
- насильство (НАС), чутливі справи й «поза Києвом» у ролики не йдуть узагалі — ні точкою, ні числом;
- адреса — лише вулиця без номера будинку (`adresa_pokazu.bez_nomera`); номер — тільки в публічних місць, яким
  сценарій сам дає назву (ТЦ, ринок, вокзал), і ніколи — житлового будинку;
- кожна подія має посилання на рішення (без нього запису у випуску немає).

Модуль нічого не пише в git: великі набори точок кладе в кеш `video/vyhid/kesh/` (у .gitignore).
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
sys.path.insert(0, str(KORIN / 'brend'))
from adresa_pokazu import bez_nomera, chutlyva  # noqa: E402

NE_V_ROLYKY = {'НАС', 'ПОЗА'}

# Групи подій → короткий підпис і колір у ролику (без червоного — MV-58; колір = вид, не небезпека).
HRUPY = {
    'ДТП': ('ДТП', '#66E6BA'),
    'ДОР': ('порушення на дорозі', '#9C9DF0'),
    'ГП': ('громадський порядок', '#F2C46D'),
    'НАР': ('наркотики', '#6CC9F2'),
    'МАЙ': ('крадіжки й майно', '#D79CF5'),
    'АЛК': ('торгівля з рук', '#B8E07A'),
}

# Номер статті → короткий підпис для мітки над точкою (читається за пів секунди).
KOROTKO = {
    '124': 'ДТП', '122-4': 'поїхав з місця ДТП', '286': 'ДТП з травмами',
    '130': "п'яний за кермом", '126': 'без прав', '122-2': 'не зупинився', '139': 'пошкодив дорогу',
    '121': 'несправне авто', '122': 'правила руху', '140': 'ремонт дороги', '123': 'переїзд',
    '309': 'наркотики', '44': 'наркотики', '307': 'збут наркотиків', '308': 'наркотики',
    '51': 'дрібна крадіжка', '185': 'крадіжка', '190': 'шахрайство', '186': 'грабіж', '187': 'розбій',
    '289': 'угон', '194': 'знищення майна',
    '173': 'хуліганство', '296': 'хуліганство', '178': 'розпивання', '175-1': 'куріння', '181': 'азартні ігри',
    '263': 'зброя', '154': 'тварини', '174': 'стрільба', '345': 'опір поліції',
    '160': 'торгівля з рук', '156': 'алкоголь і тютюн',
}

STATTIA = re.compile(r'ст\.\s*([\d\-]+)\s*(КК|КУпАП)?')


def korotko(stattia: str | None, vyd: str) -> str:
    m = STATTIA.search(stattia or '')
    if m:
        n = m.group(1)
        if vyd == 'ГП' and n == '185':
            return 'непокора поліції'
        if n in KOROTKO:
            return KOROTKO[n]
    t = (stattia or '').split('·', 1)[-1].strip()
    if 'тварин' in t or 'рослин' in t:
        return 'продаж риби чи рослин'
    return (t[:22] if t else HRUPY.get(vyd, (vyd,))[0])


def vulytsia(adresa: str) -> str:
    """«вул. Хрещатик, 17» → «вул. Хрещатик»; перехрестя «А / Б» → «А / Б» (номерів там немає)."""
    return bez_nomera(adresa or '').strip()


@dataclass
class Podiia:
    id: str
    data: str | None
    chas: str | None
    vyd: str
    stattia: str
    fabula: str | None
    lat: float
    lon: float
    adresa: str          # повна, лише для внутрішніх обчислень — у кадр не йде
    tochnist: str
    url: str

    @property
    def rik(self):
        return int(self.data[:4]) if self.data and self.data[:4].isdigit() else None

    @property
    def hodyna(self):
        return int(self.chas[:2]) if self.chas and self.chas[:2].isdigit() else None

    @property
    def vul(self):
        return vulytsia(self.adresa)

    @property
    def mitka(self):
        return korotko(self.stattia, self.vyd)

    @property
    def nomer_rishennia(self):
        return self.id.split('-')[0]


class Vypusk:
    def __init__(self, baza: Path, borders: Path | None = None):
        self.baza = Path(baza)
        self.con = sqlite3.connect(f'file:{self.baza.as_posix()}?mode=ro', uri=True)
        self.versiia = self.con.execute('SELECT versiia FROM release').fetchone()[0]
        self.borders = borders or (KORIN / 'data' / 'borders.json')

    @cached_property
    def podii(self) -> list[Podiia]:
        rows = self.con.execute('''
            SELECT e.event_id, e.data_podii, e.chas, e.vyd, e.stattia, e.fabula, e.chutlyva,
                   l.lat, l.lon, l.adresa, l.tochnist, d.url
            FROM event e JOIN location l ON l.location_id = e.location_id
            JOIN document d ON d.doc_id = e.doc_id
            WHERE e.doc_id NOT IN (SELECT doc_id FROM withdrawal)
            ORDER BY e.data_podii, e.chas, e.event_id''').fetchall()
        vykhid = []
        for (eid, data, chas, vyd, st, fab, chut, lat, lon, adr, toch, url) in rows:
            if vyd in NE_V_ROLYKY or chut or chutlyva(st or ''):
                continue
            if not url or not url.startswith('https://'):
                continue
            vykhid.append(Podiia(eid, data, chas, vyd, st or '', fab, lat, lon, adr or '', toch or '', url))
        return vykhid

    @cached_property
    def rayony(self):
        import importlib.util
        sys.path.insert(0, str(KORIN / 'site' / 'sait'))
        sys.path.insert(0, str(KORIN / 'site'))
        spec = importlib.util.spec_from_file_location('sait_dani', KORIN / 'site' / 'sait' / 'dani.py')
        m = importlib.util.module_from_spec(spec)
        sys.modules['sait_dani'] = m
        spec.loader.exec_module(m)   # site/sait/dani.py: межі районів (ім'я модуля збігається з цим, тож — напряму)
        return m.Rayony(self.borders)

    def rayon(self, p: Podiia):
        return self.rayony.rayon(p.lat, p.lon)

    def po_vulytsi(self) -> dict[str, list[Podiia]]:
        d = defaultdict(list)
        for p in self.podii:
            if p.tochnist == 'house' and p.vul and '/' not in p.vul:
                d[p.vul].append(p)
        return d

    def problemy(self):
        rows = self.con.execute('SELECT problem_id, riven, vyd, mekhanizm, status, lat, lon, podii, natovp, masshtab '
                                'FROM problem ORDER BY podii DESC').fetchall()
        vykhid = []
        for r in rows:
            if r[2] in NE_V_ROLYKY:
                continue
            m = json.loads(r[9]) if r[9] else {}
            n = json.loads(r[8]) if r[8] else {}
            vykhid.append({'id': r[0], 'riven': r[1], 'vyd': r[2], 'mekhanizm': r[3], 'status': r[4], 'lat': r[5],
                           'lon': r[6], 'podii': r[7], 'natovp': n, 'masshtab': m})
        return vykhid

    def podii_problemy(self, problem_id: str) -> list[Podiia]:
        ids = {r[0] for r in self.con.execute('SELECT event_id FROM problem_event WHERE problem_id = ?', (problem_id,))}
        return [p for p in self.podii if p.id in ids]


# ------------------------------------------------------------------ формати для сцени

def tochky(podii: list[Podiia], chasy: list[float] | None = None, mitky: bool = False) -> dict:
    """Компактний набір для сцени: x, y (lon, lat × 1e5), група, час появи (с) і, за потреби, мітка."""
    hrupy = list(HRUPY)
    xs, ys, gs, ts, ms = [], [], [], [], []
    # кілька подій в одному місці — «соняшником» довкола нього (крок ≈ 7 м), інакше зливаються в одну цятку
    skilky = Counter()
    for i, p in enumerate(podii):
        k = (round(p.lat, 5), round(p.lon, 5))
        n = skilky[k]
        skilky[k] += 1
        dlat = dlon = 0.0
        if n:
            r = 7.0 * math.sqrt(n)
            a = n * 2.39996
            dlat = r * math.sin(a) / 111_320
            dlon = r * math.cos(a) / (111_320 * math.cos(math.radians(p.lat)))
        xs.append(round((p.lon + dlon) * 1e5))
        ys.append(round((p.lat + dlat) * 1e5))
        gs.append(hrupy.index(p.vyd) if p.vyd in hrupy else 0)
        ts.append(round(chasy[i], 3) if chasy else 0)
        if mitky:
            ms.append(p.mitka)
    d = {'x': xs, 'y': ys, 'g': gs, 't': ts}
    if mitky:
        d['m'] = ms
    return d


def kolory_hrup() -> list[str]:
    return [c for _, c in HRUPY.values()]


def soty(podii: list[Podiia], riven: int = 8, verkh: float = 0.12, min_chastka: float = 0.0, min_n: int = 1) -> dict:
    """Соти H3 як на сайті: клас кольору 1–5 за місцем серед сот (шкала частками, MV-55), висота — лише верхнім 12 %.

    min_chastka, min_n — «менше сот» (MV-151): нижня частка сот і соти з кількома подіями в ролик не йдуть, інакше
    на темній карті дрібні соти зливаються з вулицями («мурашник»). Клас кольору рахується по всіх сотах, як на сайті."""
    import h3
    lich = Counter(h3.latlng_to_cell(p.lat, p.lon, riven) for p in podii)
    if not lich:
        return {'type': 'FeatureCollection', 'features': []}
    poriadok = sorted(lich.values())
    n = len(poriadok)
    maks = poriadok[-1]
    porih = poriadok[int(n * (1 - verkh))] if n > 4 else maks
    feats = []
    for k, c in lich.items():
        chastka = sum(1 for v in poriadok if v < c) / n  # місце серед сот
        if chastka < min_chastka or c < min_n:
            continue
        klas = min(5, 1 + int(chastka * 5))
        kontur = [[round(lon, 6), round(lat, 6)] for lat, lon in h3.cell_to_boundary(k)]
        kontur.append(kontur[0])
        lat, lon = h3.cell_to_latlng(k)
        vys = 0.0
        if c >= porih:
            vys = 0.15 + 0.85 * (math.log1p(c - porih) / math.log1p(max(1, maks - porih)))
        feats.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [kontur]},
                      # h — висота для стилю «стовпчики» (кожна сота, за числом; ZAVDANNYA-138)
                      'properties': {'n': c, 'k': klas, 'v': round(vys, 3), 'h': round(math.log1p(c) / math.log1p(maks), 3), 'cx': round(lon, 6), 'cy': round(lat, 6),
                                     'id': k}})
    return {'type': 'FeatureCollection', 'features': feats}


def adresy(podii: list[Podiia], chasy: list[float] | None = None, min_n: int = 1) -> dict:
    """Адреси для роликів (В3): місце (координата точки) → скільки подій. Як карта підписника, але в кадрі — лише число,
    ніколи не адреса чи номер будинку (MV-25, MV-60). t — коли місце з'являється (найраніша поява його подій)."""
    mista: dict = {}
    for i, p in enumerate(podii):
        k = (round(p.lat, 5), round(p.lon, 5))
        t = chasy[i] if chasy else 0.0
        if k in mista:
            mista[k][0] += 1
            mista[k][1] = min(mista[k][1], t)
        else:
            mista[k] = [1, t]
    feats = [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [lon, lat]},
              'properties': {'n': n, 't': round(t, 3)}}
             for (lat, lon), (n, t) in sorted(mista.items(), key=lambda x: x[1][0]) if n >= min_n]
    return {'type': 'FeatureCollection', 'features': feats}


def soty_z_podiiamy(podii: list[Podiia], riven: int) -> dict[str, list[int]]:
    import h3
    d = defaultdict(list)
    for i, p in enumerate(podii):
        d[h3.latlng_to_cell(p.lat, p.lon, riven)].append(i)
    return d


def chyslo(n: int) -> str:
    return f'{n:,}'.replace(',', ' ')


def vidminok(n: int, formy: tuple) -> str:
    o, d = n % 10, n % 100
    return formy[0] if o == 1 and d != 11 else formy[1] if 2 <= o <= 4 and not 12 <= d <= 14 else formy[2]


def vidstan_m(a_lat, a_lon, b_lat, b_lon) -> float:
    k = math.cos(math.radians((a_lat + b_lat) / 2))
    return math.hypot((a_lat - b_lat) * 111_320, (a_lon - b_lon) * 111_320 * k)
