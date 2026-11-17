# -*- coding: utf-8 -*-
"""Друга гра «Вулиця дня» (ZAVDANNYA-101, прототип): дані гри з випуску events-<дата>.db і колоди.

  python site/hra/vulytsia_dnia.py --baza events-<дата>.db --koloda koloda-<дата>.json \
      [--pereimenuvannia ../dani-edrsr/config/pereimenuvannia-kyiv.csv] [--vykhid site/hra/vulytsia-dnia.json]

Що робить:
1. Бере вулиці так само, як сайт (`site/sait/dani.py`): ті самі назви, slug сторінки `/vulytsia/<slug>/`, район.
2. Для кожної вулиці — лише безкоштовні числа (MV-3, MV-32): подій за останні 3 роки, головна група, частина доби
   (для перевірки), «що вирізняє вулицю» (як на її сторінці), тип вулиці, середина вулиці (середня точка її подій). Без адрес і описів.
   Чутливих (статеві, щодо дітей) і домашнього насильства у грі не рахуємо зовсім (MV-12, MV-69).
3. Загадки — вулиці, що проходять перевірку «детектив, не лотерея» (`perevirka_zahadky`):
   - відповідь однозначно виводиться з того, що гра відкриває (район, тип, «що вирізняє», межі числа
     подій, які дає «більше / менше»): серед усіх вулиць гри з такими ознаками — рівно одна;
   - не надто легко: на старті (лише район) лишається щонайменше 25 вулиць;
   - кожна підказка відсікає кандидатів;
   - є подія з колоди гри (MV-12) на цій вулиці — це підказка після третьої спроби;
   - головна група — не «Насильство й грабежі» (у грі його не показуємо).
4. Пише один JSON: вулиці для спроб (без подій) і перелік загадок.

Колода — приватна (S-В.5 dani-edrsr), тож і цей файл у git не кладемо (`.gitignore`); у грі він публічний, як і колода (MV-12).
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import statistics
import sys
from collections import Counter
from pathlib import Path

KORIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
import dani as D  # noqa: E402

MIN_PODII_SPROBA = 5      # вулиця, яку можна назвати як спробу (має сторінку й профіль)
MIN_PODII_VIDPOVID = 20   # вулиця-відповідь (гра на папері: тихі вулиці спальних районів — перебір)
MIN_STARTU = 25           # кандидатів після першої підказки (лише район) — щонайменше
SPROB = 7
ZABORONENI = re.compile(r'небезпечн|безпечн|рейтинг', re.I)

HRUPY = dict(D.HRUPY)


def vyriznennia(dn, podii: list) -> str | None:
    """Що вирізняє вулицю — як на її сторінці (`dani.profil_vulytsi`): вид, частка якого на вулиці найбільше
    перевищує частку по місту (щонайменше 5 подій і в 1,2 раза). Немає — None («нічим особливим»)."""
    vydy = Counter(D.vyd_lyudskoyu(p.stattia, p.vyd) for p in podii)
    vsogo_m = sum(dn.misto_vydy.values()) or 1
    vsogo_v = sum(vydy.values()) or 1
    kraschi = []
    for vyd, n in vydy.items():
        if n < 5 or not dn.misto_vydy.get(vyd):
            continue
        lq = (n / vsogo_v) / (dn.misto_vydy[vyd] / vsogo_m)
        if lq >= 1.2:
            kraschi.append((-lq, -n, vyd))
    return min(kraschi)[2] if kraschi else None


def profil(dn, v) -> dict | None:
    podii = [dn.podii[i] for i in v.nedavni]
    podii = [p for p in podii if not p.chutlyva and not D.domashnie(p.stattia) and p.lat is not None]
    if len(podii) < MIN_PODII_SPROBA:
        return None
    hrupy = Counter(D.HRUPA_VYDU.get(p.vyd) for p in podii if D.HRUPA_VYDU.get(p.vyd))
    hrupa = max(hrupy, key=lambda h: (hrupy[h], h)) if hrupy else None
    rayon = v.rayony.most_common(1)[0][0] if v.rayony else None
    lat = statistics.median(p.lat for p in podii)
    lon = statistics.median(p.lon for p in podii)
    return {'slug': v.slug, 'nazva': v.nazva, 'typ': v.typ, 'rayon': rayon, 'n': len(podii),
            'hrupa': hrupa, 'vyrizn': vyriznennia(dn, podii), 'lat': round(lat, 5), 'lon': round(lon, 5)}


def vidstan_km(a: dict, b: dict) -> float:
    r = 6371.0
    f1, f2 = math.radians(a['lat']), math.radians(b['lat'])
    df, dl = f2 - f1, math.radians(b['lon'] - a['lon'])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def mezhi_chysla(n: int, vsi: list[int]) -> tuple[int, int]:
    """Що гравець може знати про число подій з відповідей «більше / менше / так само»: проміжок між сусідніми
    значеннями серед вулиць гри. Чесна межа — точне число (бо «так само» дає рівність). Для перевірки беремо
    грубшу межу — п'ятину розподілу, у якій лежить n: гравець не мусить влучити точно, щоб звузити."""
    s = sorted(vsi)
    k = len(s)
    mezhi = [s[min(k - 1, int(k * q))] for q in (0.2, 0.4, 0.6, 0.8)]
    niz = max([0] + [m for m in mezhi if m <= n])
    verkh = min([10 ** 9] + [m for m in mezhi if m > n])
    return niz, verkh


def perevirka_zahadky(vidp: dict, vulytsi: list[dict], chysla: list[int]) -> tuple[bool, dict]:
    """Перевірка «детектив, не лотерея» (IHRY-2, розд. 2.4, для цієї гри). Повертає (годиться, кроки звуження)."""
    niz, verkh = mezhi_chysla(vidp['n'], chysla)
    kroky = [
        ('rayon', lambda v: v['rayon'] == vidp['rayon']),
        ('vyrizn', lambda v: v['vyrizn'] == vidp['vyrizn']),
        ('n', lambda v: niz <= v['n'] < verkh),
        ('typ', lambda v: v['typ'] == vidp['typ']),
    ]
    kandydaty = list(vulytsi)
    zvuzhennia = {'vsi': len(kandydaty)}
    for nazva, umova in kroky:
        dali = [v for v in kandydaty if umova(v)]
        if len(dali) >= len(kandydaty) and len(kandydaty) > 1:
            return False, {'chomu': f'ознака {nazva} нічого не відсікає'}
        kandydaty = dali
        zvuzhennia[nazva] = len(kandydaty)
    if zvuzhennia['rayon'] < MIN_STARTU:
        return False, {'chomu': 'замало вулиць у районі — надто легко'}
    if len(kandydaty) != 1 or kandydaty[0]['slug'] != vidp['slug']:
        return False, {'chomu': f'після всіх ознак лишається {len(kandydaty)} вулиць'}
    return True, zvuzhennia


def podii_kolody(koloda: dict, dn) -> dict:
    """slug вулиці → події колоди на ній (лише короткий опис, вид, рік, посилання — без адреси)."""
    za_slug = {}
    for p in koloda.get('podii', []):
        if p.get('kategoriia') in ('statevi_zlochyny', 'shchodo_ditei', 'domashnie_nasylstvo'):
            continue
        for (t, n, _) in D.vulytsi_mistsia(p.get('adresa', ''), 'house'):
            slug = dn.zvedennia.varianty.get((t, n))
            if slug:
                za_slug.setdefault(slug, []).append(p)
    return za_slug


def chystyi_opys(t: str) -> str:
    t = re.sub(r'\s+', ' ', t or '').strip()
    return t


def zibraty(baza: Path, koloda_shlyakh: Path, pereim: Path | None, mezhi: Path) -> dict:
    dn = D.zibraty_dani(baza, pereim, mezhi)
    vulytsi = [p for v in dn.vulytsi.values() if (p := profil(dn, v)) and p['rayon']]
    vulytsi.sort(key=lambda v: v['slug'])
    chysla = [v['n'] for v in vulytsi]
    # Старі назви (довідник перейменувань): гравець шукає й так — «Шамо (кол. Давидова)».
    stari = {}
    for stara, slugy in dn.zvedennia.pereimenuvannia:
        if len(slugy) == 1:
            stari.setdefault(slugy[0], []).append(stara)
    koloda = json.loads(koloda_shlyakh.read_text(encoding='utf-8'))
    kol = podii_kolody(koloda, dn)
    zahadky, vidkynuto = [], Counter()
    for v in vulytsi:
        if v['n'] < MIN_PODII_VIDPOVID or v['hrupa'] in (None, 'nas') or not v['vyrizn']:
            vidkynuto['мало даних або «Насильство й грабежі» головне'] += 1
            continue
        podii = [p for p in kol.get(v['slug'], []) if not ZABORONENI.search(p.get('opys_korotkyi', ''))]
        # Короткий опис не має називати саму вулицю (колода вже вирізає, тут — ще раз).
        korin = re.sub(r'\W', '', v['nazva'].split(' ')[-1].lower())[:5]
        podii = [p for p in podii if korin and korin not in p['opys_korotkyi'].lower()]
        if not podii:
            vidkynuto['немає події з колоди'] += 1
            continue
        hodytsia, zv = perevirka_zahadky(v, vulytsi, chysla)
        if not hodytsia:
            vidkynuto[zv['chomu'].split(' ')[0] + ' …'] += 1
            continue
        # Найкращий опис: починається з великої літери чи цифри, найдовший (колода ріже фабулу правилами).
        p = sorted(podii, key=lambda p: (not re.match(r'^[А-ЯІЇЄҐ0-9]', p['opys_korotkyi']),
                                         re.match(r'^[А-ЯІЇЄҐ][а-яіїєґ]\b', p['opys_korotkyi']) is not None,
                                         -len(p['opys_korotkyi']), p['id']))[0]
        zahadky.append({'slug': v['slug'], 'zvuzhennia': zv,
                        'podiia': {'vyd': p['vyd'], 'rik': p['rik'], 'opys': chystyi_opys(p['opys_korotkyi']),
                                   'url': p['rishennya_url'], 'nomer': p['rishennya_nomer']}})
    return {
        'versiia': 1, 'vypusk': dn.versiia, 'koloda': koloda.get('zibrano'), 'demo': bool(koloda.get('demo')),
        'zibrano': datetime.date.today().isoformat(), 'sprob': SPROB,
        'roky': f'{D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]}',
        'hrupy': HRUPY,
        'vulytsi': [[v['slug'], v['nazva'], v['typ'], v['rayon'], v['n'], v['vyrizn'], v['lat'], v['lon'],
                     ' · '.join(sorted(stari.get(v['slug'], [])))]
                    for v in vulytsi],
        'zahadky': zahadky,
        'vidkynuto': dict(vidkynuto),
    }


def main(argv=None):
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--baza', type=Path, required=True)
    a.add_argument('--koloda', type=Path, required=True)
    a.add_argument('--pereimenuvannia', type=Path)
    a.add_argument('--mezhi', type=Path, default=KORIN / 'data' / 'borders.json')
    a.add_argument('--vykhid', type=Path, default=KORIN / 'site' / 'hra' / 'vulytsia-dnia.json')
    x = a.parse_args(argv)
    d = zibraty(x.baza, x.koloda, x.pereimenuvannia, x.mezhi)
    x.vykhid.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f'Вулиць для спроб: {len(d["vulytsi"])}; загадок: {len(d["zahadky"])}; відкинуто: {d["vidkynuto"]}')
    print(f'Файл: {x.vykhid} ({x.vykhid.stat().st_size // 1024} КБ)')


if __name__ == '__main__':
    main()
