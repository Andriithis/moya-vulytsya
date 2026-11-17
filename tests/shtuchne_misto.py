"""Штучний випуск на весь Київ — лише для прототипу «вау» і смуги «роки · місяці» (ZAVDANNYA-105).

    python tests/shtuchne_misto.py <events.db> [--podii 40000]

Справжній випуск — приватний Release `dani-edrsr`, хмарна сесія його не завантажує. Тому тут — ШТУЧНІ події:
точки в межах районів Києва (`data/borders.json`), скупчення в ≈ 70 випадкових місцях, місяці 2024-01 … 2026-10 із
сезонністю й «хвостом» 2026 року (рішення ще не всі опубліковані). Числа нічого не означають — лише рух і вигляд.
Однаковий результат при кожному запуску (зерно 105). Нічого не публікує.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sqlite3
import sys
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_sait import SKHEMA  # noqa: E402

VYDY = [('ДТП', 'ст.124 КУпАП · ДТП з пошкодженням майна', 0.34), ('ДОР', "ст.130 КУпАП · керування у стані сп'яніння", 0.18),
        ('ГП', 'ст.173 КУпАП · дрібне хуліганство', 0.14), ('МАЙ', 'ст.51 КУпАП · дрібне викрадення', 0.14),
        ('НАР', 'ст.309 КК · наркотики без мети збуту', 0.10), ('АЛК', 'ст.178 КУпАП · розпивання в громадському місці', 0.06),
        ('НАС', 'ст.125 КК · легкі тілесні ушкодження', 0.04)]


def v_mnohokutnyku(lat: float, lon: float, poly: list) -> bool:
    vse, j = False, len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i]; yj, xj = poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            vse = not vse
        j = i
    return vse


# Публічні названі місця (ZAVDANNYA-124): підпис точки — як у випуску (`location.tochnist = 'mistse'`), точка — на об'єкті.
# Окремий генератор (зерно 124), щоб решта штучного міста лишилась такою самою. «Теремки» — 2 події (тонка сторінка).
MISTSIA = [('ст. м. Лісова', 50.46476, 30.64597, 60), ('ст. м. Теремки', 50.36691, 30.45382, 2),
           ('ст. м. Вокзальна', 50.44165, 30.48817, 35), ('ТРЦ «Ocean Plaza»', 50.41220, 30.52260, 48),
           ('ТЦ «Блокбастер»', 50.49660, 30.49880, 22), ('Центральний вокзал', 50.44001, 30.48848, 70),
           ("Лук'янівський ринок", 50.46250, 30.48250, 30), ('парк «Наталка»', 50.50400, 30.52350, 18),
           ('Голосіївський парк', 50.39350, 30.51250, 12), ('пляж «Венеція»', 50.45200, 30.57600, 9),
           ('міст Патона', 50.43300, 30.56500, 15), ('зупинка «Майдан»', 50.45010, 30.52340, 5)]


def dodaty_mistsia(con, pochatok: int) -> int:
    rnd = random.Random(124)
    n = pochatok
    for adresa, lat, lon, skilky in MISTSIA:
        for _ in range(skilky):
            n += 1
            vyd, st, _ = rnd.choices(VYDY, [v[2] for v in VYDY])[0]
            data = f'{rnd.choice((2024, 2025, 2026))}-{rnd.randint(1, 9):02d}-{rnd.randint(1, 28):02d}'
            con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)',
                        (str(n), 'штучний суд', data, 'постанова', '0', f'{n}/0', f'https://reyestr.court.gov.ua/Review/{n}'))
            con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)',
                        (n, adresa, 'mistse', round(lat + rnd.gauss(0, 2e-4), 6), round(lon + rnd.gauss(0, 3e-4), 6), 'nazvani'))
            con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (f'{n}-1', str(n), 1, data, f'{rnd.randint(7, 22):02d}:{rnd.randint(0, 59):02d}', vyd, st,
                         'Штучна подія для прототипу.', 0, None, n))
    return n


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('baza', type=Path)
    ap.add_argument('--podii', type=int, default=40000)
    a = ap.parse_args(argv)
    rnd = random.Random(105)
    rayony = json.loads((KORIN / 'data' / 'borders.json').read_text(encoding='utf-8'))
    polihony = list(rayony.values())
    lat0, lat1 = min(p[0] for r in polihony for p in r), max(p[0] for r in polihony for p in r)
    lon0, lon1 = min(p[1] for r in polihony for p in r), max(p[1] for r in polihony for p in r)

    def u_kyievi(lat, lon):
        return any(v_mnohokutnyku(lat, lon, r) for r in polihony)

    def vypadkova_tochka():
        while True:
            lat, lon = rnd.uniform(lat0, lat1), rnd.uniform(lon0, lon1)
            if u_kyievi(lat, lon):
                return lat, lon
    # Скупчення: щільніше ближче до центру (Майдан), як у справжніх даних великого міста.
    tsentr = (50.4501, 30.5234)
    skupchennia = []
    while len(skupchennia) < 70:
        lat, lon = vypadkova_tochka()
        d = math.hypot((lat - tsentr[0]) * 111, (lon - tsentr[1]) * 71)
        if rnd.random() < math.exp(-d / 9):
            skupchennia.append((lat, lon, rnd.uniform(0.004, 0.02), rnd.paretovariate(1.3)))
    vahy = [s[3] for s in skupchennia]
    misiatsi = [(r, m) for r in (2024, 2025, 2026) for m in range(1, 13) if not (r == 2026 and m > 10)]
    vahy_mis = []
    for r, m in misiatsi:
        sezon = 1 + 0.18 * math.cos((m - 7) / 12 * 2 * math.pi)       # улітку більше
        khvist = 1.0 if r < 2026 else max(0.25, 1 - 0.08 * m)           # 2026 ще не весь опублікований
        vahy_mis.append(sezon * khvist * (1 + 0.1 * (r - 2024)))

    a.baza.unlink(missing_ok=True)
    con = sqlite3.connect(a.baza)
    con.executescript(SKHEMA)
    for n in range(1, a.podii + 1):
        if rnd.random() < 0.7:
            lat, lon, sigma, _ = rnd.choices(skupchennia, vahy)[0]
            lat, lon = rnd.gauss(lat, sigma), rnd.gauss(lon, sigma * 1.5)
            if not u_kyievi(lat, lon):
                lat, lon = vypadkova_tochka()
        else:
            lat, lon = vypadkova_tochka()
        r, m = rnd.choices(misiatsi, vahy_mis)[0]
        vyd, st, _ = rnd.choices(VYDY, [v[2] for v in VYDY])[0]
        data = f'{r}-{m:02d}-{rnd.randint(1, 28):02d}'
        con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)',
                    (str(n), 'штучний суд', data, 'постанова', '0', f'{n}/0', f'https://reyestr.court.gov.ua/Review/{n}'))
        con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)',
                    (n, f'вул. Штучна {1 + n % 400}, {1 + n % 97}', 'house', round(lat, 6), round(lon, 6), 'osm'))
        con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (f'{n}-1', str(n), 1, data, None, vyd, st, 'Штучна подія для прототипу.', 0, None, n))
    n = dodaty_mistsia(con, a.podii)
    con.execute('INSERT INTO release VALUES (?,?,?)', ('shtuchnyi-105', n, 'shtuchnyi'))
    con.commit()
    con.close()
    print(f'{a.baza}: {a.podii} штучних подій, {len(misiatsi)} місяців')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
