"""Сценарії роликів ZAVDANNYA-129: перемонтаж топ-5 (docs/ZVIT-128.md, розд. 5) і нові типи — за правилами MV-151.

    python video/vau/stsenarii129.py <events.db> [--koloda koloda.json] [--dani-1551 1551-DLIA-ZVITU.md] [--lyshe t1,n3]
    → video/vyhid/kesh/stsenarii/129-*.json

Відмінності від чернеток 127 (`stsenarii.py`, лишаються як були) — усе перевіряє `perevirka.py` (meta pravyla=129):
- С1: кінцівка — банер ≤ 1 с поверх руху або заклик у підписі публікації; ролики-петлі стикують останній кадр з першим;
- С2/С3: гачок стоїть повністю вже в кадрі 0, карта з кадру 0 не порожня;
- С4: щось нове щонайпізніше кожні 2 с; переказ — одним реченням, цілим;
- С5: джерело й «Голос згенеровано» — вгорі під логотипом; С6: ≥ 3 компонування; С7: лише темна тема;
- С8: захисні фрази — у підпис публікації (`R.pidpys`); С10: підпис лічильника узгоджується з числом у кожному кадрі;
- MV-151: житло — камера не ближче рівня вулиці (z ≤ 15,3); номер рішення — лише в ролику з однією подією;
  соти — менше й чіткіші (без «мурашника»).
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))
import dani as D  # noqa: E402
from stsenarii import (FORMY, KYIV, PROFIL, TSIL, VYHID, Baza, Rolyk, blyzko, fp, hrupa_kol,  # noqa: E402,F401
                       khronolohiia, khvylia, tsentr)

SOTY = dict(min_chastka=0.35, min_n=3)       # «менше сот» (MV-151)
MISIATSI = ['січ', 'лют', 'бер', 'кві', 'тра', 'чер', 'лип', 'сер', 'вер', 'жов', 'лис', 'гру']
MISIATSI_R = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада',
              'грудня']
DZHERELO_1551 = 'Звернення до 1551 (відкриті дані Києва) · 08.2025–10.2026'


def R129(id_, tryv, **meta):
    return Rolyk('129-' + id_, tryv, tema='temna', pravyla=129, **meta)


def datа_lyudska(d: str) -> str:
    x = date.fromisoformat(d)
    return f'{x.day} {MISIATSI_R[x.month - 1]} {x.year}'


# ================================================================== ТОП-5 (перемонтаж)

def t1(B):
    """Топ-1 «Сота розпадається» (чернетка 09 → К-02): 13 с, петля; вибух — з першої секунди, камера близько."""
    import h3
    P = list(B.P)
    c = KYIV
    R = R129('t1-sota-rozpadaietsia', 13, nazva='Сота розпадається', hrupa='Місто згори',
             hachok='«Що всередині однієї соти?» — і вона вибухає на сотні подій', meta='«вау», знайомить із картою',
             liniia='Безкоштовна карта', kudy='/karta/?z=15')
    R.muzyka('epik', drop=1.2)
    sh = R.soty(P, 8, vysota=((0, 0.9), (1.0, 1.0)), prozorist=((0, 1),), maks_vysota=1600, zalyvka=0.12, lyshe_rozpad=True, vershyny=False, **SOTY)
    by = D.soty_z_podiiamy(P, 8)
    k0 = h3.latlng_to_cell(c[1], c[0], 8)
    kiltsia = [k0] + list(h3.grid_ring(k0, 1)) + list(h3.grid_ring(k0, 2))
    kiltsia = [k for k in kiltsia if k in by]
    rozpad, vybrani, chasy, org = [], [], [], []
    rng = random.Random(9)
    for i, k in enumerate(kiltsia):
        tr = 1.2 if i == 0 else 4.6 + h3.grid_distance(k0, k) * 1.3 + rng.uniform(0, 0.7)
        rozpad.append({'id': k, 't': round(tr, 2)})
        lat, lon = h3.cell_to_latlng(k)
        for j, ii in enumerate(by[k]):
            vybrani.append(P[ii]); org.append((lon, lat))
            chasy.append(tr + 0.06 + (j / max(1, len(by[k]))) ** 0.7 * (1.2 if i == 0 else 0.8))
        R.efekt(tr, 'udar' if i == 0 else 'bas', v=0.9 if i == 0 else 0.35, h=1 + rng.uniform(-0.1, 0.1))
    R.S['spalakh'].append({'t': 1.2, 'sila': 0.5}); R.S['trus'].append({'t': 1.2, 'sila': 22})
    sh['rozpad'] = rozpad
    R.tochky(vybrani, chasy, org=org, rozmir=((0, 30), (8, 22), (13, 30)), glow=0.55, tryv=0.7)
    pershi = [(p, t) for p, t, o in zip(vybrani, chasy, org) if o == org[0]]
    R.zvuk_tochok([t for _, t in pershi], maks=16, typ='pop', h0=0.9, h1=1.8, v=0.5)
    R.zvuk_tochok([t for t, o in zip(chasy, org) if o != org[0]], maks=9, typ='klik', h0=0.9, h1=1.4, v=0.35, seed=3)
    # не більше трьох міток — рознесені по куту, щоб не перекривались
    vydy = Counter(p.mitka for p, _ in pershi).most_common(3)
    for j, (m, _) in enumerate(vydy):
        p = [p for p, _ in pershi if p.mitka == m][0]
        R.mitka(1.9 + j * 0.45, 4.2, (p.lon, p.lat), m, kolir=hrupa_kol(p.vyd), dx=(-260, 0, 260)[j], dy=(0, 120, 0)[j])
    n0 = len(pershi)
    R.kam(0, (c[0], c[1] - 0.0045), 13.4, 58, -10).kam(1.2, (c[0], c[1] - 0.004), 13.6, 60, -18, e='o')
    R.kam(4.4, (c[0], c[1] - 0.004), 13.8, 62, -40, e='io').kam(9.0, c, 12.6, 64, -120, e='io').kam(12.0, c, 12.9, 62, -150, e='io')
    R.tekst(0, 1.15, 'hook', 'Що всередині\n*однієї соти?*', y='verkh')
    R.tekst(1.5, 4.3, 'lich', kluchi=[[1.3, 0], [2.6, n0, 'o']], pidpys='{f} в одній соті\nпоруч із Майданом', formy=FORMY, y='verkh')
    R.tekst(4.5, 6.4, 'velykyi', 'А тепер —\n*сусідні.*', y='verkh', anim='slam')
    vsi = len(vybrani)
    R.tekst(6.6, 10.8, 'lich', kluchi=[[6.6, n0], [9.6, vsi, 'io']], pidpys=f'{{f}} у {len(kiltsia)} сотах довкола', formy=FORMY, y='verkh')
    R.udar(9.7, 0.25, 10)
    hr = Counter(p.vyd for p in vybrani).most_common(3)
    R.tekst(8.4, 10.8, 'stovpchyky', riady=[{'tekst': D.HRUPY[v][0], 'n': n, 'kolir': hrupa_kol(v)} for v, n in hr], y=1080)
    R.baner(11.0, 'Розбери свою соту')
    R.petlia(0.5)
    R.pidpys('Кожна точка — подія з рішення суду. Колір і висота — кількість даних, не оцінка місця.',
             'Наблизь карту — соти розкриваються на події. Посилання в профілі.')
    return R


def t5(B):
    """Топ-5 «Усе місто за 9 секунд» (чернетка 01 → К-01): петля, точки вискакують з кадру 0, рік — великий."""
    P = sorted(B.P, key=lambda p: p.data or '9')
    n = len(P)
    R = R129('t5-misto-za-9-sekund', 9, nazva='Усе місто за 9 секунд', hrupa='Місто згори',
             hachok='«Кожна точка — справжня подія з рішення суду»', meta='охоплення, повтори → карта', liniia='Безкоштовна карта',
             kudy='/karta/')
    R.muzyka('puls', drop=0.0, bpm=126)
    rng = random.Random(4)
    chasy = [t + rng.uniform(0, 0.2) for t in khronolohiia(P, -1.2, 5.4)]   # С3: частина точок уже світиться в кадрі 0
    R.tochky(P, chasy, rozmir=((0, 8), (5, 6), (7.5, 6), (9, 8)), yaskr=((0, 1), (7, 0.9)), glow=0.3, tryv=0.35)
    R.soty(P, 8, vysota=((5.6, 0), (7.4, 1, 'oo')), prozorist=((0, 0), (5.4, 0), (6.0, 1)), maks_vysota=2600, zalyvka=0.1, **SOTY)
    R.kam(0, KYIV, 10.0, 25, 0).kam(5.4, KYIV, 10.4, 32, -10, e='io')
    R.kam(7.9, (30.52, 50.448), 11.4, 58, -60, e='io')
    R.efekt(0.0, 'udar', v=0.7)
    R.zvuk_tochok(chasy, maks=14, h0=0.8, h1=1.9, v=0.45)
    R.tekst(0, 2.2, 'hook', 'Кожна точка —\n*справжня подія*\nз рішення суду', y='verkh')
    R.tekst(2.3, 5.6, 'lich', kluchi=[[0, 0], [5.4, n, 'io']], pidpys='{f} на карті Києва', formy=FORMY, y='verkh')
    for i, (rik, t) in enumerate([('2023', 0.0), ('2024', 1.4), ('2025', 2.9), ('2026', 4.3)]):
        R.tekst(t, t + 1.45 if i < 3 else 5.6, 'velykyi', f'*{rik}*', y=1300, c=True, anim='pop')
        R.efekt(t, 'tik', h=1.2)
    R.udar(5.6, 0.35, 12)
    R.udar(7.4, 0.2, 8)
    R.tekst(5.8, 8.0, 'velykyi', 'Де більше даних —\n*вищий стовпчик*', y='verkh', anim='slam')
    R.petlia(0.5)
    R.pidpys('Кожна точка — подія з рішення суду (ЄДРСР). Лише те, що дійшло до суду. Висота — кількість даних, не оцінка місця.',
             'Знайди свою вулицю — посилання в профілі.')
    R.meta['kintsivka'] = 'у підписі: посилання в профілі'
    return R


def t2(B):
    """Топ-2 «Вгадай, де це було» — 23 сосни (чернетка 04 → К-08): 12 с, темна; картка повна з кадру 0, відлік, відповідь."""
    p = B.podiia('124940125-1')
    ray = B.V.rayon(p) or 'Дарницький'
    c = (p.lon, p.lat)
    R = R129('t2-vgadai-sosny', 12, nazva='Вгадай, де це було: 23 сосни', hrupa='Ігри',
             hachok='«Вгадай, де це було» + картка «23 сосни без бирок» з кадру 0', meta='коментарі, гра → «Де це було?» щодня',
             liniia='Гра', kudy='/hra/', odna_podiia=True)
    R.muzyka('hra', bpm=120)
    tlo = [x for x in B.P if x.id != p.id]
    R.tochky(tlo, [-1] * len(tlo), rozmir=((0, 5),), yaskr=((0, 0.45), (5.8, 0.45), (6.6, 0.15)), glow=0.15, kiltse=False)
    R.kam(0, KYIV, 10.2, 20, 0).kam(6.0, KYIV, 10.5, 30, 8, e='l').kam(8.0, (c[0], c[1] - 0.0022), 15.0, 55, -25, e='io', luk=0.9)
    R.kam(12, (c[0], c[1] - 0.0018), 15.2, 60, -55, e='l')
    R.tochky([p], [7.6], rozmir=((0, 60),), glow=0.7)
    R.tekst(0, 6.0, 'hook', 'Вгадай,\n*де це було*', y='verkh')
    R.tekst(0, 3.0, 'kartka', 'Грудень, 14:00. Людина продавала з рук 23 новорічні сосни — без бирок обліку деревини.',
            zag='Що сталося', dz=f'Рішення суду № {p.nomer_rishennia}', y=640)
    variant = [('А', 'Оболонський'), ('Б', ray), ('В', 'Святошинський')]
    for i, (b, v) in enumerate(variant):
        R.tekst(1.5 + i * 0.2, 8.0, 'variant', v, bukva=b, y=1060 + i * 130, pravylno=(v == ray), vidpovid=6.0)
        R.efekt(1.5 + i * 0.2, 'pop', h=1.2 + i * 0.15, v=0.5)
    R.tekst(1.9, 6.0, 'mala', 'Пиши букву в коментарях', y=1450, klas='zaklyk')
    R.tekst(3.0, 6.0, 'vidlik', y=600)
    for t in (3.0, 4.0, 5.0):
        R.efekt(t, 'tik', h=1.3)
    R.efekt(6.0, 'dzvin', h=1.2)
    R.udar(7.6, 0.3, 10)
    R.kiltse(7.7, c, '#66E6BA', 300)
    R.mitka(7.8, 12, c, f'{ray} район', styl='velyka')
    R.tekst(8.2, 10.6, 'velykyi', f'*{ray}* район.\nВи вгадали?', y='verkh', anim='slam')
    R.mitka(9.4, 12, (c[0] + 0.0012, c[1] - 0.0009), D.vulytsia(p.adresa))
    R.efekt(9.4, 'pop', h=1.4)
    R.baner(10.7, 'Нова загадка — щодня', 'Гра «Де це було?» · посилання в профілі')
    R.pidpys(f'Справжня справа з рішення суду № {p.nomer_rishennia}. Гра «Де це було?» — нова загадка щодня, посилання в профілі.')
    return R


def t3(B):
    """Топ-3 «Самокат. 00:46. 1,68 проміле» (чернетка 18 → К-16): 7 с, петля; три удари — гачок повністю з кадру 0."""
    p = B.podiia('130939371-1')
    c = (p.lon, p.lat)
    vsi = sorted([x for x in B.fabula('самокат') if x.data], key=lambda x: x.data)
    R = R129('t3-samokat-7s', 7, nazva='Самокат. 00:46. 1,68 проміле', hrupa='Історії з даних',
             hachok='«Самокат. 00:46. 1,68 проміле.» — три удари', meta='гачок-вимір → сторінка вулиці',
             liniia='Мій район', kudy='/vulytsia/petra-sahaidachnoho/', odna_podiia=True)
    R.muzyka('puls', bpm=128, drop=0.0)
    R.kam(0, (c[0], c[1] - 0.0016), 14.8, 60, 20).kam(2.4, (c[0], c[1] - 0.0014), 15.2, 62, -5, e='o')
    R.kam(4.4, (c[0], c[1] - 0.0014), 15.2, 62, -15, e='l').kam(6.0, KYIV, 11.0, 40, -10, e='io', luk=0.4)
    R.tochky([p], [-0.5], rozmir=((0, 60), (4.4, 60), (5.6, 18)), glow=0.7)
    rng = random.Random(18)
    inshi = [x for x in vsi if x.id != p.id]
    chasy = sorted(4.5 + 1.6 * ((i + 1) / len(inshi)) ** 0.6 + rng.uniform(0, 0.05) for i in range(len(inshi)))
    R.tochky(inshi, chasy, rozmir=((0, 10),), glow=0.5)
    R.zvuk_tochok(chasy, maks=14, h0=1.0, h1=1.9, v=0.4)
    R.tekst(0, 2.3, 'hook', 'Самокат.\n00:46.\n*1,68 проміле.*', y='verkh')
    for t, s in ((0.02, 0.2), (0.75, 0.15), (1.5, 0.25)):        # три удари поверх повного гачка
        R.udar(t, s, 16)
    R.tekst(2.4, 4.4, 'kartka', 'Серпень 2025, Поділ. Водій електросамоката напідпитку: прилад показав 1,68 проміле.',
            zag='Дійшло до суду', dz=f'{D.vulytsia(p.adresa)} · рішення суду № {p.nomer_rishennia}', y='verkh')
    R.efekt(2.4, 'svish')
    R.mitka(3.4, 4.4, c, 'Поділ · 00:46', styl='velyka')
    R.efekt(3.4, 'pop', h=1.3)
    R.tekst(4.5, 6.6, 'lich', kluchi=[[4.5, 0], [6.1, len(vsi), 'io']], pidpys='{f} у даних,\nде згадано самокат', formy=FORMY, y='verkh')
    R.efekt(4.4, 'vzhukh', v=0.7)
    R.petlia(0.45)
    R.pidpys(f'Справжня справа: рішення суду № {p.nomer_rishennia}. Що ще на твоїй вулиці — посилання в профілі.')
    R.meta['kintsivka'] = 'у підписі: посилання в профілі'
    return R


def dani_1551(f: Path) -> dict:
    """Місячні числа й групи 1551 з dani-edrsr/docs/1551-DLIA-ZVITU.md (заміри ZAVDANNYA-66) — без ручних чисел."""
    t = f.read_text(encoding='utf-8')
    num = lambda x: int(x.replace(' ', '').replace(' ', ''))
    mis = [(m.group(1), num(m.group(2))) for m in re.finditer(r'^\| (\d{4}-\d{2}) \| ([\d  ]+) \|', t, re.M)]
    hr = {m.group(1).strip(): num(m.group(2)) for m in re.finditer(r'^\| ([а-яєіїґ\' ,()]+?) \| ([\d  ]+) \| [\d  ]+ \|', t, re.M)}
    return {'misiatsi': mis, 'hrupy': hr}


def t4(B):
    """Топ-4 «Січень: 211 тисяч» (К-28, 1551): 15 с; число на весь кадр з кадру 0, місяці стовпчиками, тема №1 — тепло."""
    d = dani_1551(B.dani_1551)
    mis = d['misiatsi']
    sich = [n for m, n in mis if m.endswith('-01')][0]
    serp = [n for m, n in mis if m == '2025-08'][0]
    liut = [n for m, n in mis if m.endswith('-02')][0]
    hr = d['hrupy']
    tema = [(k, hr[k]) for k in ('тепло', 'вода', 'світло', 'ліфт')]
    raz = round(sich / serp)
    R = R129('t4-sichen-211-tysiach', 15, nazva='Січень: 211 тисяч', hrupa='«Що болить будинку»',
             hachok=f'«{D.chyslo(sich)}» на весь кадр — стільки разів кияни написали в 1551 за один січень',
             meta='охоплення → «Мій будинок»', liniia='Мій будинок', kudy='/miy-budynok/')
    R.S['dzherelo'] = DZHERELO_1551
    R.muzyka('napruha', bpm=100)
    R.kam(0, KYIV, 10.6, 45, -20).kam(15, (30.55, 50.45), 11.2, 55, -80, e='l')
    R.slovo(0, 1.8, D.chyslo(sich), pid='разів кияни написали в 1551\nза один січень')
    R.holos(0.15, 'Стільки разів кияни написали в п\'ятнадцять п\'ятдесят один за один січень.', 'tetiana')
    R.efekt(0.0, 'udar', v=0.8)
    riady = [{'tekst': MISIATSI[int(m[5:]) - 1], 'n': n, 'akc': m.endswith('-01'), 'pokaz': m.endswith('-01')} for m, n in mis]
    R.tekst(1.8, 7.4, 'kolony', riady=riady, y=760, krok=0.1)
    R.efekt(1.8, 'vzhukh')
    R.tekst(2.0, 3.9, 'velykyi', f'Серпень — *{D.chyslo(serp)}*', y='verkh', anim='vgoru')
    R.tekst(4.0, 5.7, 'velykyi', f'Січень — *у {raz} рази* більше', y='verkh', anim='slam')
    R.udar(4.0, 0.3, 12)
    R.holos(4.1, f'У січні — у {raz} рази більше, ніж у серпні.', 'tetiana')
    R.tekst(5.8, 7.4, 'velykyi', f'Лютий — майже стільки ж:\n*{D.chyslo(liut)}*', y='verkh', anim='vgoru')
    R.tekst(7.5, 10.9, 'stovpchyky', riady=[{'tekst': k, 'n': n, 'kolir': '#66E6BA' if i == 0 else '#9C9DF0'} for i, (k, n) in enumerate(tema)], y=900)
    R.tekst(7.5, 10.9, 'velykyi', 'Тема №1 за 15 місяців —\n*тепло*', y='verkh', anim='slam')
    R.efekt(7.5, 'svish')
    R.holos(7.7, f'Тема номер один — тепло: {tema[0][1] // 1000} тисяча звернень.', 'tetiana')
    R.udar(9.3, 0.2, 8)
    R.tekst(11.0, 13.7, 'velykyi', 'Що писали про\n*ваш будинок?*', y='verkh', anim='slam')
    R.udar(11.0, 0.25, 10)
    R.holos(11.1, 'А що писали про ваш будинок?', 'tetiana')
    R.efekt(12.6, 'pop', h=1.3)
    R.S['novynky'] = [12.6]
    R.baner(13.8, 'Мій будинок', 'Скарги 1551 по кожному будинку · посилання в профілі')
    R.pidpys('Дані: звернення до 1551 (відкриті дані Києва), серпень 2025 — жовтень 2026; повторні перенаправлення рахуємо раз.',
             'Скарга — звернення, а не перевірений факт. Що писали про ваш будинок — посилання в профілі.')
    return R


SCENARII = {k: v for k, v in dict(globals()).items() if re.match(r'[tn]\d+$', k)}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('baza', type=Path)
    a.add_argument('--koloda', type=Path)
    a.add_argument('--dani-1551', type=Path, help='dani-edrsr/docs/1551-DLIA-ZVITU.md — місячні числа й групи 1551')
    a.add_argument('--lyshe')
    arg = a.parse_args()
    B = Baza(arg)
    B.dani_1551 = arg.dani_1551
    vybir = arg.lyshe.split(',') if arg.lyshe else sorted(SCENARII)
    kat_f = VYHID / 'katalog-129.json'
    katalog = []
    if kat_f.is_file():
        katalog = [m for m in json.loads(kat_f.read_text(encoding='utf-8')) if m['id'].split('-')[1] not in vybir]
    for k in vybir:
        R = SCENARII[k](B)
        katalog.append(R.zberehty())
        print(R.S['id'], R.S['tryvalist'], 'с')
    katalog.sort(key=lambda m: m['id'])
    kat_f.write_text(json.dumps(katalog, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
