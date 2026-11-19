# -*- coding: utf-8 -*-
"""Довга гра «Літопис міста» (ZAVDANNYA-140, ZAVDANNYA-141): дані гри з випуску events-<дата>.db і колоди.

  python site/ihry/litopys/litopys.py --baza events-<дата>.db --koloda koloda-<дата>.json \
      [--pereimenuvannia ../dani-edrsr/config/pereimenuvannia-kyiv.csv] [--vykhid site/ihry/litopys/litopys.json]

Що робить:
1. Вулиці — так само, як сайт і «Вулиця дня» (`site/sait/dani.py`, `site/hra/vulytsia_dnia.py`): назва, район, лише
   безкоштовні числа за останні 3 роки (MV-3, MV-32), головна група, середина вулиці. Чутливих і домашнього насильства
   у числах гри немає (MV-12, MV-69).
2. Події, що відкриваються разом з вулицею, — лише з колоди гри (MV-12: адреса до будинку — як у колоді). Події з
   потерпілими (крадіжки, грабежі, тілесні ушкодження, вбивства тощо) — є (MV-165); поза грою лише статеві, щодо дітей
   і домашнє насильство (MV-12, MV-69). Подача поважна (MV-165): для видів з потерпілими (`Z_POTERPILYMY`) у файл іде
   лише вид, рік, адреса й посилання на рішення — без опису, щоб у грі не було деталей про потерпілого; такі картки
   не дають бонусу до читання («без балів за шкоду») і не йдуть у «Справу дня».
3. Картки видів подій — рідкість за справжньою частотою у випуску (усі нечутливі події з точкою), а не за випадком.
   Що дасть вулиця, видно наперед: гравець бачить види на картці вулиці ще до відкриття (без лотереї, MV-155 П8).
4. Межі районів — `data/borders.json` (OpenStreetMap).

Колода приватна (S-В.5 dani-edrsr), тож і цей файл у git не кладемо (`.gitignore`), як `vulytsia-dnia.json`.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path

KORIN = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(KORIN / 'site' / 'hra'))
import dani as D  # noqa: E402
import vulytsia_dnia as VD  # noqa: E402

# Види з потерпілими (MV-165): у грі є, але поважно — без опису події, без бонусу, без «Справи дня».
# Крадіжки — подія з потерпілим-власником, але без шкоди людині; їх опис лишається, як у колоді ігор (MV-12).
Z_POTERPILYMY = {'tilesni', 'hrabizh_rozbii', 'vbyvstvo', 'strilba', 'pohroza', 'dtp_poterpili',
                 'zhorstokist_do_tvaryn', 'nedopomoha', 'samoupravstvo'}
MV4 = {'statevi_zlochyny', 'shchodo_ditei', 'domashnie_nasylstvo'}
ZABORONENI = re.compile(r'небезпечн|безпечн|рейтинг', re.I)

# Рідкість — частка виду серед усіх нечутливих подій з точкою (поріг у відсотках).
RIDKIST = [(5.0, 'zvychaina', 'звичайна'), (1.0, 'nechasta', 'нечаста'), (0.1, 'ridkisna', 'рідкісна'),
           (0.0, 'duzhe', 'дуже рідкісна')]
PODII_NA_VULYTSIU = 3


def ridkist(chastka: float) -> str:
    for porih, kod, _ in RIDKIST:
        if chastka >= porih:
            return kod
    return RIDKIST[-1][1]


def chastoty_vydiv(baza: Path) -> dict:
    """Код виду колоди → (назва, кількість) серед усіх нечутливих подій з точкою (dani-edrsr/src/koloda.vyd_podii).
    Без конвеєра — частоти лише з колоди (позначка `dzherelo`)."""
    try:
        sys.path.insert(0, str(KORIN.parent / 'dani-edrsr' / 'src'))
        import koloda as K  # noqa: E402
    except Exception:  # pragma: no cover — немає сусіднього репозиторію
        return {}
    n = Counter()
    con = sqlite3.connect(baza)
    for kod, ch, lid in con.execute('SELECT d.kod_kategorii, e.chutlyva, e.location_id FROM event e '
                                    'JOIN document d USING(doc_id)'):
        if ch or lid is None:
            continue
        v = K.vyd_podii(kod)
        if v:
            n[v] += 1
    return {k: (vyd, m) for (k, vyd), m in n.items()}


def zibraty(baza: Path, koloda_shlyakh: Path, pereim: Path | None, mezhi: Path) -> dict:
    dn = D.zibraty_dani(baza, pereim, mezhi)
    koloda = json.loads(koloda_shlyakh.read_text(encoding='utf-8'))
    return zibraty_z_dani(dn, koloda, chastoty_vydiv(baza), json.loads(mezhi.read_text(encoding='utf-8')))


def zibraty_z_dani(dn, koloda: dict, chastoty: dict, mezhi_rayoniv: dict) -> dict:
    kol = VD.podii_kolody(koloda, dn)
    if not chastoty:   # запасний шлях — частоти з колоди
        c = Counter((p['kategoriia'], p['vyd']) for p in koloda.get('podii', []))
        chastoty = {k: (v, m) for (k, v), m in c.items()}
    vsogo = sum(m for _, m in chastoty.values()) or 1
    vydy = {}
    for k, (nazva, m) in chastoty.items():
        if k in MV4:
            continue
        ch = 100.0 * m / vsogo
        vydy[k] = {'nazva': nazva, 'n': m, 'chastka': round(ch, 3), 'ridkist': ridkist(ch)}
        if k in Z_POTERPILYMY:
            vydy[k]['povazhna'] = True

    vulytsi, podii = [], {}
    for v in dn.vulytsi.values():
        p = VD.profil(dn, v)
        if not p or not p['rayon']:
            continue
        svoi = []
        for e in sorted(kol.get(v.slug, []), key=lambda e: e['id']):
            if e['kategoriia'] in MV4 or e['kategoriia'] not in vydy:
                continue
            if ZABORONENI.search(e.get('opys_korotkyi', '')) or e['id'] in podii:
                continue
            svoi.append(e)
        # Різні види першими — вулиця дає більше карток, але все одно видно наперед, які саме.
        bachyly, rang = Counter(), {}
        for e in svoi:
            rang[e['id']] = bachyly[e['kategoriia']]
            bachyly[e['kategoriia']] += 1
        svoi.sort(key=lambda e: (rang[e['id']], e['id']))
        svoi = svoi[:PODII_NA_VULYTSIU]
        for e in svoi:
            opys = '' if e['kategoriia'] in Z_POTERPILYMY else VD.chystyi_opys(e['opys_korotkyi'])
            podii[e['id']] = [e['kategoriia'], e['rik'], opys, e['adresa'],
                              e['lat'], e['lon'], e['rishennya_url'], e['rishennya_nomer']]
        vulytsi.append([v.slug, p['nazva'], p['rayon'], p['n'], p['hrupa'], p['lat'], p['lon'], [e['id'] for e in svoi]])
    vulytsi.sort(key=lambda v: (v[2], -v[3], v[0]))

    rayony = {}
    for v in vulytsi:
        r = rayony.setdefault(v[2], {'vulyts': 0, 'podii': 0, 'z_podiiamy_kolody': 0})
        r['vulyts'] += 1
        r['podii'] += v[3]
        r['z_podiiamy_kolody'] += 1 if v[7] else 0
    mezhi = {}
    for nazva, poly in mezhi_rayoniv.items():
        if nazva not in rayony:
            continue
        if poly and isinstance(poly[0][0], (int, float)):
            poly = [poly]
        mezhi[nazva] = [[[round(lon, 4), round(lat, 4)] for lat, lon in pl[::3]] for pl in poly]
    return {
        'versiia': 2, 'vypusk': dn.versiia, 'koloda': koloda.get('zibrano'), 'demo': bool(koloda.get('demo')),
        'zibrano': datetime.date.today().isoformat(),
        'roky': f'{D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]}',
        'hrupy': dict(D.HRUPY),
        'ridkist': {kod: nazva for _, kod, nazva in RIDKIST},
        'vydy': vydy, 'rayony': rayony, 'mezhi': mezhi,
        'vulytsi': vulytsi, 'podii': podii,
    }


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--baza', type=Path, required=True)
    a.add_argument('--koloda', type=Path, required=True)
    a.add_argument('--pereimenuvannia', type=Path)
    a.add_argument('--mezhi', type=Path, default=KORIN / 'data' / 'borders.json')
    a.add_argument('--vykhid', type=Path, default=Path(__file__).with_name('litopys.json'))
    x = a.parse_args(argv)
    d = zibraty(x.baza, x.koloda, x.pereimenuvannia, x.mezhi)
    x.vykhid.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Вулиць: {len(d["vulytsi"])}; з подіями колоди: {sum(1 for v in d["vulytsi"] if v[7])}; '
          f'подій: {len(d["podii"])}; видів-карток: {len(d["vydy"])}; районів: {len(d["rayony"])}')


if __name__ == '__main__':
    main()
