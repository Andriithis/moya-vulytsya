"""Збирає maket/m1/dani.json із пробного випуску бази: лише суми по сотах (MV-3).

Запуск:
  python maket/m1/zibraty_dani.py --baza events-2026-11-08.db --osm misto.osm.pbf

База — dani-edrsr, Releases vypusk-2026-11-08. OSM — витяг міста з того самого конвеєра,
з нього беремо лише назви станцій метро й торгових центрів для назви соти.
Сітка — та сама, що в картці сот навчальної карти Києва (hexAt у site_src/vyhlyady.js).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import osmium
from shapely.geometry import Point, Polygon, shape
from shapely.prepared import prep
from shapely.strtree import STRtree

KORIN = Path(__file__).resolve().parents[2]
VYKHID = Path(__file__).resolve().parent / 'dani.json'

MX = 111320 * math.cos(50.45 * math.pi / 180)
MY = 111320
RIVNI = {'L': 330, 'S': 130}

# Сім груп (MV-28). Кольори — приглушені тони, узгоджені з брендом; вживаються лише у вигляді В3 (М2).
HRUPY = [['dtp', 'ДТП', '#5F7F78'], ['dor', 'Дороги', '#A9A296'], ['hp', 'Громадський порядок', '#B98B5E'],
         ['mai', 'Майно', '#5E7FA3'], ['nar', 'Наркотики', '#7F749E'], ['alk', 'Алкоголь', '#3F8F88'],
         ['nas', 'Насильство', '#A8716F']]
HRUPA_VYDU = {'ДТП': 0, 'ДОР': 1, 'ГП': 2, 'МАЙ': 3, 'НАР': 4, 'АЛК': 5, 'НАС': 6}
INDEKS_NASYLSTVA = 6

# Найменша кількість подій проблеми всередині соти, щоб назвати її в картці цієї соти.
MIN_PODII_PROBLEMY = 2
# Радіус пошуку орієнтира, м: (метро, ТЦ, вулиця).
ORIYENTYR_M = {'L': (500, 350, 350), 'S': (300, 150, 200)}


def hex_at(la: float, lo: float, r: float) -> tuple[str, float, float]:
    """Шестикутник, куди потрапляє точка (порт hexAt карти Києва)."""
    w, h, x, y = math.sqrt(3) * r, 1.5 * r, lo * MX, la * MY
    r0 = round_js(y / h)
    best = None
    bd = 1e30
    for dr in (-1, 0, 1):
        row = r0 + dr
        c0 = round_js((x - (row & 1) * w / 2) / w)
        for dc in (-1, 0, 1):
            col = c0 + dc
            cx = col * w + (row & 1) * w / 2
            cy = row * h
            d = (cx - x) ** 2 + (cy - y) ** 2
            if d < bd:
                bd = d
                best = (f'{row}:{col}', cx, cy)
    return best


def round_js(x: float) -> int:
    return math.floor(x + 0.5)


class Oriyentyry(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.metro: list[tuple[str, float, float]] = []
        self.tc: list[tuple[str, float, float]] = []

    @staticmethod
    def nazva(t) -> str | None:
        return t.get('name:uk') or t.get('name')

    def node(self, n):
        t = n.tags
        if t.get('railway') == 'station' and t.get('station') == 'subway' and self.nazva(t):
            self.metro.append((self.nazva(t), n.location.lat, n.location.lon))
        elif t.get('shop') == 'mall' and self.nazva(t):
            self.tc.append((self.nazva(t), n.location.lat, n.location.lon))

    def way(self, w):
        t = w.tags
        if t.get('shop') == 'mall' and self.nazva(t):
            tochky = [(x.location.lat, x.location.lon) for x in w.nodes if x.location.valid()]
            if tochky:
                self.tc.append((self.nazva(t), sum(a for a, _ in tochky) / len(tochky), sum(b for _, b in tochky) / len(tochky)))


class Najblyzhche:
    """Найближчий об'єкт із переліку (назва, lat, lon) у метрах."""

    def __init__(self, obyekty):
        self.obyekty = list(obyekty)
        self.dereva = STRtree([Point(lo * MX, la * MY) for _, la, lo in self.obyekty]) if self.obyekty else None

    def poshuk(self, cx: float, cy: float, radius: float) -> str | None:
        if not self.dereva:
            return None
        i = int(self.dereva.nearest(Point(cx, cy)))
        n, la, lo = self.obyekty[i]
        return n if math.hypot(lo * MX - cx, la * MY - cy) <= radius else None


def vulytsia(nazva: str) -> str | None:
    """Назва вулиці без номера будинку (MV-25)."""
    v = re.split(r',\s*\d', nazva, maxsplit=1)[0].strip()
    return v or None


def zibraty(baza: Path, osm: Path, roky: list[int], stari: list[int], nepovnyi: int) -> dict:
    c = sqlite3.connect(f'file:{baza.as_posix()}?mode=ro', uri=True)
    rows = c.execute('''SELECT e.event_id, e.data_podii, e.chas, e.vyd, l.lat, l.lon FROM event e
                        JOIN location l ON l.location_id = e.location_id''').fetchall()
    gj = json.loads((KORIN / 'config/geocoding/kyiv_boundary.geojson').read_text(encoding='utf-8'))
    mezha = prep(shape(gj['geometry'] if gj.get('type') == 'Feature' else gj))
    bezrokiv = Counter()
    podii = []
    for eid, data, chas, vyd, la, lo in rows:
        rik = int(data[:4]) if data else None
        if rik not in roky:
            bezrokiv[rik] += 1
            continue
        if vyd not in HRUPA_VYDU or not mezha.contains(Point(lo, la)):
            bezrokiv['поза Києвом або інший вид'] += 1
            continue
        m = re.match(r'(\d{1,2})', chas or '')
        hod = int(m.group(1)) if m and int(m.group(1)) < 24 else None
        podii.append((eid, roky.index(rik), HRUPA_VYDU[vyd], hod, la, lo))
    print('Подій у вікні:', len(podii), 'Не взято:', dict(bezrokiv))

    problemy: dict[str, str] = {}
    for pid, mekh, natovp, vyd in c.execute('SELECT problem_id, mekhanizm, natovp, vyd FROM problem'):
        problemy[pid] = (mekh or vyd or '').strip()
    evp: dict[str, list[str]] = defaultdict(list)
    for pid, eid in c.execute('SELECT problem_id, event_id FROM problem_event'):
        evp[eid].append(pid)

    rayony = []
    for naz, kilce in json.loads((KORIN / 'data/borders.json').read_text(encoding='utf-8')).items():
        rayony.append((naz, prep(Polygon([(lo, la) for la, lo in kilce]))))
    h = Oriyentyry()
    h.apply_file(str(osm), locations=True)
    metro = Najblyzhche(h.metro)
    tc = Najblyzhche(h.tc)
    adresy = [(v, la, lo) for naz, la, lo in c.execute('SELECT nazva, lat, lon FROM address') if (v := vulytsia(naz))]
    vuli = Najblyzhche(adresy)

    def nazva_rayonu(cx: float, cy: float) -> str:
        p = Point(cx / MX, cy / MY)
        return next((n for n, g in rayony if g.contains(p)), '')

    def oriyentyr(riven: str, cx: float, cy: float) -> str:
        rm, rt, rv = ORIYENTYR_M[riven]
        if n := metro.poshuk(cx, cy, rm):
            return f'Біля метро {n}'
        if n := tc.poshuk(cx, cy, rt):
            return f'Біля ТЦ {n}'
        return vuli.poshuk(cx, cy, rv) or ''

    slovnyk_ray: dict[str, int] = {}
    slovnyk_or: dict[str, int] = {}
    slovnyk_pr: dict[str, int] = {}
    soty_out: dict[str, list] = {}
    for riven, r in RIVNI.items():
        B: dict[str, dict] = {}
        for eid, ri, gi, hod, la, lo in podii:
            k, cx, cy = hex_at(la, lo, r)
            b = B.setdefault(k, {'cx': cx, 'cy': cy, 'n': 0, 'g': [0] * 7, 'y': [0] * len(roky), 'h': Counter(), 'pr': Counter()})
            b['n'] += 1
            b['g'][gi] += 1
            b['y'][ri] += 1
            if hod is not None:
                b['h'][hod] += 1
            for pid in evp.get(eid, ()):
                b['pr'][pid] += 1
        out = []
        for k, b in B.items():
            pik, pik_n = (min(b['h'].items(), key=lambda kv: (-kv[1], kv[0])) if b['h'] else (-1, 0))
            pr_idx = []
            for pid, n in b['pr'].most_common():
                naz = problemy.get(pid)
                if n >= MIN_PODII_PROBLEMY and naz:
                    i = slovnyk_pr.setdefault(naz, len(slovnyk_pr))
                    if i not in pr_idx:
                        pr_idx.append(i)
            ray = slovnyk_ray.setdefault(nazva_rayonu(b['cx'], b['cy']), len(slovnyk_ray))
            orn = slovnyk_or.setdefault(oriyentyr(riven, b['cx'], b['cy']), len(slovnyk_or))
            out.append([k, round(b['cx'], 2), round(b['cy'], 2), b['n'], b['g'], b['y'], pik, pik_n, sum(b['h'].values()), ray, orn, pr_idx[:3]])
        out.sort(key=lambda x: x[0])
        soty_out[riven] = out
        print(riven, 'сот:', len(out), 'макс:', max(x[3] for x in out))

    s = soty_out['S']
    med = statistics.median(x[3] for x in s)
    kilca = list(json.loads((KORIN / 'data/borders.json').read_text(encoding='utf-8')).values())
    lat = [q[0] for k in kilca for q in k]
    lon = [q[1] for k in kilca for q in k]
    return {
        'meta': {'vypusk': '2026-11-08', 'podii': len(podii), 'roky': roky, 'stari': stari, 'nepovnyi': nepovnyi, 'period': f'{roky[0]}–{roky[-1]}',
                 'mediana130': med, 'centr': [50.45, 30.52], 'mezhi': [[min(lon), min(lat)], [max(lon), max(lat)]]},
        'hrupy': HRUPY,
        'rayony': sorted(slovnyk_ray, key=slovnyk_ray.get),
        'oriyentyry': sorted(slovnyk_or, key=slovnyk_or.get),
        'problemy': sorted(slovnyk_pr, key=slovnyk_pr.get),
        'soty': soty_out,
    }


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument('--baza', type=Path, required=True)
    a.add_argument('--osm', type=Path, required=True)
    a.add_argument('--roky', default='2024,2025,2026')
    a.add_argument('--stari', default='2016,2017,2018,2019,2020,2021,2022,2023')
    a.add_argument('--nepovnyi', type=int, default=2026, help='рік, за який дані ще неповні')
    p = a.parse_args()
    d = zibraty(p.baza, p.osm, [int(x) for x in p.roky.split(',')], [int(x) for x in p.stari.split(',')], p.nepovnyi)
    VYKHID.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print('Записано', VYKHID, VYKHID.stat().st_size, 'байт; медіана 130 м:', d['meta']['mediana130'])


if __name__ == '__main__':
    main()
