"""Соти для схематичної карти роликів (ZAVDANNYA-11).

Рахує події з випуску `events-<дата>.db` по шестикутниках ~1 км і пише
`video/dani/soty-kyiv.geojson`: лише форма соти, кількість і клас 1–5 (шкала data-1…5).
Адрес, описів і точок у файлі немає — це рівень «безкоштовно» з MV-3.

Беремо лише події з точкою (`location_id`). Чутливі справи MV-4 точки не мають,
тож сюди не потрапляють (на сайті вони рахуються числом по соті окремо).

Запуск: python video/soty.py шлях/до/events-2026-11-08.db
Готовий файл уже лежить у git, тож для рендеру роликів база не потрібна.
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import Counter
from pathlib import Path

TUT = Path(__file__).resolve().parent
VYKHID = TUT / 'dani' / 'soty-kyiv.geojson'

# Місцева площина навколо центру Києва: метри на градус.
LAT0, LON0 = 50.45, 30.52
M_LAT = 110_540.0
M_LON = 111_320.0 * math.cos(math.radians(LAT0))
R = 620.0  # радіус соти (від центру до кута), м; ширина соти ≈ 1,07 км
MIN_PODIY = 3  # соти з меншою кількістю не малюємо — щоб не вказувати на окремий будинок


def v_metry(lat, lon):
    return (lon - LON0) * M_LON, (lat - LAT0) * M_LAT


def v_hradusy(x, y):
    return LAT0 + y / M_LAT, LON0 + x / M_LON


def sota(x, y):
    """Осьові координати шестикутника (гострий верх) для точки в метрах."""
    q = (math.sqrt(3) / 3 * x - y / 3) / R
    r = (2 / 3 * y) / R
    # округлення в кубічних координатах
    s = -q - r
    rq, rr, rs = round(q), round(r), round(s)
    dq, dr, ds = abs(rq - q), abs(rr - r), abs(rs - s)
    if dq > dr and dq > ds:
        rq = -rr - rs
    elif dr > ds:
        rr = -rq - rs
    return rq, rr


def kuty(q, r):
    cx = R * math.sqrt(3) * (q + r / 2)
    cy = R * 1.5 * r
    tochky = []
    for i in range(7):
        a = math.radians(60 * (i % 6) - 30)
        lat, lon = v_hradusy(cx + R * math.cos(a), cy + R * math.sin(a))
        tochky.append([round(lon, 5), round(lat, 5)])
    return tochky


def main(db):
    c = sqlite3.connect(db)
    ryadky = c.execute('select l.lat, l.lon from event e join location l using(location_id) '
                       'where e.chutlyva = 0').fetchall()
    lich = Counter(sota(*v_metry(lat, lon)) for lat, lon in ryadky)
    lich = {k: v for k, v in lich.items() if v >= MIN_PODIY}
    znach = sorted(lich.values())
    # межі класів — квінтилі серед сот, де є події
    mezhi = [znach[int(len(znach) * p)] for p in (0.2, 0.4, 0.6, 0.8)]

    def klas(n):
        return 1 + sum(n > m for m in mezhi)

    vyp = c.execute('select versiia from release').fetchone()
    fc = {
        'type': 'FeatureCollection',
        'properties': {
            'dzherelo': 'Моя вулиця, випуск %s; події з точкою, без чутливих (MV-4)' % (vyp[0] if vyp else '?'),
            'radius_m': R, 'min_podiy': MIN_PODIY, 'mezhi_klasiv': mezhi,
            'podiy_razom': sum(lich.values()),
        },
        'features': [
            {'type': 'Feature', 'properties': {'n': n, 'k': klas(n)},
             'geometry': {'type': 'Polygon', 'coordinates': [kuty(q, r)]}}
            for (q, r), n in sorted(lich.items())
        ],
    }
    VYKHID.parent.mkdir(parents=True, exist_ok=True)
    VYKHID.write_text(json.dumps(fc, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'{len(fc["features"])} сот, {fc["properties"]["podiy_razom"]} подій, межі класів {mezhi} → {VYKHID}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
