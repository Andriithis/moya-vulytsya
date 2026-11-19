"""Сценарії роликів ZAVDANNYA-138: нові типи й пачка на перший тиждень тесту — світла й темна тема, адреси, різні вигляди.

    python video/vau/stsenarii138.py <events.db> [--koloda koloda.json] [--lyshe 01,07]
    → video/vyhid/kesh/stsenarii/138-*.json (+ _druha-*.json для поділеного екрана)
    python video/vau/stsenarii138.py <events.db> --pachka          # лише перевірка чергування пачки (В2)

Що нового проти 129 (усе перевіряє `perevirka.py`, meta pravyla=138):
- стиль сот — лише явний вибір сценарію (`styl_sot`: sait · plytka · stovpchyky · …; ZAVDANNYA-139 додає свої);
- світла тема — повноправна (С7 скасовано, MV-158); точки й межа міста — над дорогами (MV-161);
- шар адрес (В3): місце → число подій, без адрес і номерів будинків (MV-25, MV-60);
- кожен ролик має осі В2 (тема, шар, рівень наближення); пачка (`PACHKA`) не ставить поруч два схожі.
Числа — з бази в момент збирання; жодних ручних чисел, крім слів-підписів.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
sys.path.insert(0, str(TUT))
import dani as D  # noqa: E402
import perevirka  # noqa: E402
from stsenarii import (FORMY, KYIV, PROFIL, TSIL, VYHID, Baza, Rolyk, blyzko, fp, hrupa_kol,  # noqa: E402,F401
                       khronolohiia, khvylia, lanka_vulytsi, tsentr)

SOTY = dict(min_chastka=0.35, min_n=3)       # «менше сот» (MV-151)
MISIATSI = ['січ', 'лют', 'бер', 'кві', 'тра', 'чер', 'лип', 'сер', 'вер', 'жов', 'лис', 'гру']
MISIATSI_R = ['січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада',
              'грудня']
HODYNY_SLOVOM = {0: 'опівночі', 7: 'о сьомій', 8: 'о восьмій', 9: 'о дев\'ятій', 12: 'о дванадцятій', 13: 'о тринадцятій',
                 14: 'о чотирнадцятій', 15: 'о п\'ятнадцятій', 16: 'о шістнадцятій', 17: 'о сімнадцятій', 18: 'о вісімнадцятій'}
PODII_FORMY = ('подія', 'події', 'подій')


def misdenyi(rayon: str) -> str:
    """«Дарницький» → «Дарницькому» (місцевий відмінок для «у … районі»)."""
    return re.sub(r'ий$', 'ому', rayon)


class R138(Rolyk):
    """Ролик 138: правила 129 + явний стиль сот, шар ролика (вісь В2), адреси, поділений екран."""

    def __init__(self, id_, tryv, tema='temna', shar='soty', **meta):
        super().__init__('138-' + id_, tryv, tema=tema, pravyla=138, shar=shar, **meta)
        self.S['nad_dorohamy'] = True          # MV-161: точки й межа міста — над дорогами
        if tema == 'svitla':                   # світле затемнення під текстом на 100 % стирає карту (аркуш 138-01)
            self.S['zatemnennia'] = 0.55
        self._druha = None

    def soty(self, podii, riven=8, styl_sot=None, **kw):
        if not styl_sot:
            raise ValueError('ZAVDANNYA-138: стиль сот — лише явний вибір (styl_sot)')
        return super().soty(podii, riven, styl_sot=styl_sot, **kw)

    def adresy(self, podii, chasy=None, styl_adres='kola', prozorist=((0, 1),), min_n=1, min_chyslo=2, **kw):
        """В3: місця з числом подій. У кадрі — лише число (MV-25)."""
        sh = dict({'dani': D.adresy(podii, chasy, min_n), 'styl_adres': styl_adres, 'prozorist': [list(x) for x in prozorist],
                   'min_chyslo': min_chyslo}, **kw)
        self.S.setdefault('adresy', []).append(sh)
        return sh

    def druha(self, R2: Rolyk, kordon):
        """Поділений екран: R2 — друга сцена (своя тема, свої шари); kordon [[t, частка висоти]] — де межа."""
        self._druha = R2
        self.S['druha'] = {'s': None, 'kordon': [list(x) for x in kordon]}

    def zberehty(self, teka=VYHID):
        if self._druha is not None:
            teka.mkdir(parents=True, exist_ok=True)
            S2 = self._druha.S
            S2.update(bez_nakladok=True, znak=False, dzherelo='', tekst=[], ui=[], mitky=[], zatemnennia=0, nad_dorohamy=True,
                      zvuk={'efekty': [], 'holos': []})
            if not S2['kamera']:
                S2['kamera'] = [dict(k) for k in self.S['kamera']]
            S2['kamera'].sort(key=lambda k: k['t'])
            f = teka / f"_druha-{self.S['id']}.json"
            f.write_text(json.dumps(S2, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            self.S['druha']['s'] = '/' + f.resolve().relative_to(KORIN).as_posix()
        meta = super().zberehty(teka)
        meta['osi'] = perevirka.osi(self.S, self.meta)
        return meta


# ================================================================== ТИПИ ТЕСТУ — нові варіанти (інший вигляд, тема, місце)

def s01(B):
    """Місто за N секунд — світла тема, 3D-стовпчики (кожна сота — стовпчик за числом), петля 9 с."""
    P = sorted(B.P, key=lambda p: p.data or '9')
    n = len(P)
    R = R138('01-misto-za-9-sekund-svitla', 9, tema='svitla', shar='soty', typ='Місто за N секунд', nazva='Київ за 9 секунд (світла, стовпчики)',
             hrupa='Місто згори', hachok='«Київ за 9 секунд. Кожна точка — подія з рішення суду» — точки вже світяться',
             meta='охоплення, повтори → карта', liniia='Безкоштовна карта', kudy='/karta/')
    R.muzyka('puls', drop=0.0, bpm=126)
    rng = random.Random(41)
    chasy = [t + rng.uniform(0, 0.2) for t in khronolohiia(P, -1.2, 4.9)]
    R.tochky(P, chasy, rozmir=((0, 10), (4.9, 7), (6.0, 4), (8.4, 4), (9, 10)), yaskr=((0, 1), (5.0, 1), (6.2, 0.35), (8.4, 0.35), (9, 1)),
             glow=0.2, tryv=0.35)
    R.soty(P, 8, styl_sot='stovpchyky', vysota=((5.0, 0), (7.0, 1, 'oo'), (8.3, 1), (8.95, 0)), prozorist=((0, 0), (5.0, 0), (5.5, 1), (8.4, 1), (8.95, 0)),
           maks_vysota=2600, **SOTY)
    R.kam(0, KYIV, 10.0, 20, 0).kam(5.0, KYIV, 10.3, 32, -12, e='io').kam(7.8, (30.52, 50.446), 11.1, 60, -58, e='io')
    R.efekt(0.0, 'udar', v=0.7)
    R.zvuk_tochok(chasy, maks=14, h0=0.8, h1=1.9, v=0.45)
    R.tekst(0, 2.2, 'hook', 'Київ за 9 секунд.\n*Кожна точка —*\nподія з рішення суду', y='verkh')
    R.tekst(2.3, 5.0, 'lich', kluchi=[[0, 0], [4.9, n, 'io']], pidpys='{f} на карті', formy=FORMY, y='verkh')
    for i, (rik, t) in enumerate([('2023', 0.0), ('2024', 1.3), ('2025', 2.6), ('2026', 3.9)]):
        R.tekst(t, t + 1.3 if i < 3 else 5.0, 'velykyi', f'*{rik}*', y=1300, c=True, anim='pop')
        R.efekt(t, 'tik', h=1.2)
    R.udar(5.0, 0.3, 12)
    R.tekst(5.1, 7.4, 'velykyi', 'Кожна сота —\n*стовпчик за числом*', y='verkh', anim='slam')
    R.udar(7.0, 0.2, 8)
    R.petlia(0.5)
    R.pidpys('Кожна точка — подія з рішення суду (ЄДРСР). Лише те, що дійшло до суду.',
             'Висота — кількість даних, не оцінка місця. Знайди свою вулицю — посилання в профілі.')
    R.meta['kintsivka'] = 'у підписі: посилання в профілі'
    return R


def s02(B):
    """Вгадай, де це було — квіти з рук під мостом напередодні 8 березня; відповідь — з адресами довкола (В3)."""
    p = B.podiia('117721532-1')
    ray = B.V.rayon(p) or 'Дніпровський'
    c = (p.lon, p.lat)
    R = R138('02-vgadai-kvity', 12, tema='temna', shar='adresy', typ='Вгадай, де це було', nazva='Вгадай, де це було: квіти під мостом',
             hrupa='Ігри', hachok='«Вгадай, де це було» + картка «квіти під мостом» з кадру 0', meta='коментарі, гра → «Де це було?» щодня',
             liniia='Гра', kudy='/karta/?ihry', odna_podiia=True)
    R.muzyka('hra', bpm=120)
    tlo = [x for x in B.P if x.id != p.id]
    R.tochky(tlo, [-1] * len(tlo), rozmir=((0, 5),), yaskr=((0, 0.4), (5.8, 0.4), (6.6, 0.0)), glow=0.15, kiltse=False)
    R.kam(0, KYIV, 10.2, 15, 0).kam(6.0, KYIV, 10.5, 25, 10, e='l').kam(8.0, (c[0], c[1] - 0.0035), 14.6, 50, -20, e='io', luk=0.9)
    R.kam(12, (c[0], c[1] - 0.003), 14.9, 56, -50, e='l')
    blyzki = [x for x in blyzko(B.P, c, 1300) if x.id != p.id]
    R.adresy(blyzki, khvylia(blyzki, c, 8.3, 9.6, seed=2), styl_adres='kola', prozorist=((0, 0), (8.2, 0), (8.4, 1)), min_n=2, min_chyslo=3)
    R.tochky([p], [7.6], rozmir=((0, 60),), glow=0.7)
    R.tekst(0, 6.0, 'hook', 'Вгадай,\n*де це було*', y='verkh')
    R.tekst(0, 3.0, 'kartka', 'Березень, за день до 8 Березня, 15:00. Квіти продавали з рук під мостом — без документів.',
            zag='Що сталося', dz=f'Рішення суду № {p.nomer_rishennia}', y=640)
    variant = [('А', 'Оболонський'), ('Б', 'Подільський'), ('В', ray)]
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
    R.tekst(8.2, 10.6, 'velykyi', f'*{ray}* район.\nА довкола — ще події', y='verkh', anim='slam')
    R.zvuk_tochok([f['properties']['t'] for f in R.S['adresy'][0]['dani']['features']], maks=10, typ='klik', h0=1.0, h1=1.5, v=0.35)
    R.mitka(9.4, 12, (c[0] + 0.0016, c[1] - 0.0012), D.vulytsia(p.adresa) + ' · під мостом')
    R.efekt(9.4, 'pop', h=1.4)
    R.baner(10.7, 'Нова загадка — щодня', 'Гра «Де це було?» · посилання в профілі')
    R.pidpys(f'Справжня справа з рішення суду № {p.nomer_rishennia}. Кола — місця поруч, число — скільки подій у даних.',
             'Гра «Де це було?» — нова загадка щодня, посилання в профілі.')
    return R


def s04(B):
    """Сота розпадається — «Плитка», найбільша сота лівого берега; петля 13 с."""
    import h3
    P = list(B.P)
    by = D.soty_z_podiiamy(P, 8)
    # найбільша сота подалі від центру (≥ 3 км від Майдану) — інше місце, ніж у t1
    k0 = max((k for k in by if D.vidstan_m(KYIV[1], KYIV[0], *h3.cell_to_latlng(k)) > 3000 and h3.cell_to_latlng(k)[1] > 30.56),
             key=lambda k: len(by[k]))
    lat0, lon0 = h3.cell_to_latlng(k0)
    c = (lon0, lat0)
    ray = B.V.rayony.rayon(lat0, lon0) or 'Дніпровський'
    R = R138('04-sota-rozpadaietsia-plytka', 13, tema='temna', shar='soty', typ='Сота розпадається',
             nazva='Сота розпадається (Плитка, лівий берег)', hrupa='Місто згори',
             hachok='«Що всередині однієї соти?» над «Плиткою» — і сота вибухає на події', meta='«вау», знайомить із картою',
             liniia='Безкоштовна карта', kudy='/karta/?z=15')
    R.muzyka('epik', drop=1.2)
    sh = R.soty(P, 8, styl_sot='plytka', vysota=((0, 0.9), (1.0, 1.0)), prozorist=((0, 1),), maks_vysota=1600, lyshe_rozpad=True,
                vershyny=False, **SOTY)
    kiltsia = [k0] + list(h3.grid_ring(k0, 1)) + list(h3.grid_ring(k0, 2))
    kiltsia = [k for k in kiltsia if k in by]
    rozpad, vybrani, chasy, org = [], [], [], []
    rng = random.Random(14)
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
    R.tochky(vybrani, chasy, org=org, rozmir=((0, 30), (8, 22), (13, 30)), glow=0.6, tryv=0.7)
    pershi = [(p, t) for p, t, o in zip(vybrani, chasy, org) if o == org[0]]
    R.zvuk_tochok([t for _, t in pershi], maks=16, typ='pop', h0=0.9, h1=1.8, v=0.5)
    R.zvuk_tochok([t for t, o in zip(chasy, org) if o != org[0]], maks=9, typ='klik', h0=0.9, h1=1.4, v=0.35, seed=3)
    vydy = Counter(p.mitka for p, _ in pershi).most_common(3)
    for j, (m, _) in enumerate(vydy):
        p = [p for p, _ in pershi if p.mitka == m][0]
        R.mitka(1.9 + j * 0.45, 4.2, (p.lon, p.lat), m, kolir=hrupa_kol(p.vyd), dx=(-260, 0, 260)[j], dy=(0, 120, 0)[j])
    n0 = len(pershi)
    R.kam(0, (c[0], c[1] - 0.0045), 13.4, 55, 25).kam(1.2, (c[0], c[1] - 0.004), 13.6, 58, 18, e='o')
    R.kam(4.4, (c[0], c[1] - 0.004), 13.8, 60, -5, e='io').kam(9.0, c, 12.6, 62, -85, e='io').kam(12.0, c, 12.9, 60, -115, e='io')
    R.tekst(0, 1.15, 'hook', 'Що всередині\n*однієї соти?*', y='verkh')
    R.tekst(1.5, 4.3, 'lich', kluchi=[[1.3, 0], [2.6, n0, 'o']], pidpys='{f} в одній соті\nу ' + misdenyi(ray) + ' районі', formy=FORMY, y='verkh')
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


def s05(B):
    """Міф чи факт №3 — «Найбільше ДТП — у ранкову годину пік»; світла тема, 24 стовпчики годин."""
    dtp = [p for p in B.P if p.vyd == 'ДТП' and p.hodyna is not None]
    hod = Counter(p.hodyna for p in dtp)
    pik = max(hod, key=hod.get)
    ranok = max((8, 9), key=hod.get)
    if pik in (8, 9):
        raise SystemExit('s05: у даних найбільше ДТП вранці — твердження не міф, ролик не збирається')
    R = R138('05-mif-dtp-hodyna-pik', 12, tema='svitla', shar='tochky', typ='Міф чи факт', nazva='Міф чи факт: найбільше ДТП — уранці',
             hrupa='Міф чи факт', hachok='«Найбільше ДТП — у ранкову годину пік» на весь кадр', meta='розрив очікувань, коментарі',
             liniia='Безкоштовна карта', kudy='/karta/', riven='misto')
    R.muzyka('napruha', bpm=110)
    R.kam(0, KYIV, 10.3, 30, 10).kam(12, KYIV, 10.9, 50, -50, e='l')
    R.tochky(dtp, [-1] * len(dtp), rozmir=((0, 5),), yaskr=((0, 0.75),), glow=0.12, kiltse=False)
    R.slovo(0, 2.0, 'Найбільше ДТП —\nу ранкову\n*годину пік*', pid='Міф чи факт?', klas='temne menshe')
    R.holos(0.2, 'Це правда?', 'tetiana')
    R.tekst(2.1, 3.8, 'shtamp', 'МІФ')
    R.udar(2.1, 0.3, 20)
    R.holos(2.2, f'Ні. У даних найбільше ДТП — {HODYNY_SLOVOM.get(pik, "увечері")} годині.', 'tetiana')
    riady = [{'tekst': f'{h:02d}' if h % 3 == 0 else '', 'n': hod.get(h, 0), 'akc': h == pik, 'pokaz': h == pik} for h in range(24)]
    R.tekst(3.9, 7.6, 'kolony', riady=riady, y=820, krok=0.05, vysota=520)
    R.tekst(3.9, 7.6, 'velykyi', 'ДТП у даних —\n*за годиною доби*', y='verkh', anim='vgoru')
    R.efekt(3.9, 'vzhukh')
    R.efekt(5.6, 'kasa', v=0.5)
    R.S['novynky'] = [5.6]
    R.tekst(7.5, 9.8, 'split', riady=[{'zag': f'о {pik}:00', 'n': hod[pik], 'tekst': 'ДТП у даних'},
                                        {'zag': f'о {ranok}:00', 'n': hod[ranok], 'tekst': 'ДТП у даних'}], y=560)
    R.udar(7.5, 0.2, 8)
    R.efekt(8.8, 'pop', h=1.3)
    R.S['novynky'].append(8.8)
    R.tekst(9.9, 12, 'velykyi', f'Найбільше —\n*о {pik}-й*', y='verkh', anim='slam')
    R.baner(11.0, 'Перевір свою вулицю', 'Карта подій · посилання в профілі')
    R.pidpys('Дані: ДТП з відомою годиною в рішеннях судів Києва в нашому випуску (ЄДРСР). Лише те, що дійшло до суду.',
             'Година — з рішення суду. Перевір свою вулицю — посилання в профілі.')
    return R


def s08(B):
    """Одна подія-петля — «Гірлянда. 100 LED. 472 грн.» (грудень), 7 с, магазин — публічне місце."""
    p = B.podiia('134231824-1')
    c = (p.lon, p.lat)
    vsi = sorted([x for x in B.fabula('гірлянд|ялинков|новорічн') if x.data], key=lambda x: x.data)
    R = R138('08-hirlianda-7s', 7, tema='temna', shar='tochky', typ='Одна подія-петля', nazva='Гірлянда. 100 LED. 472 грн',
             hrupa='Історії з даних', hachok='«Гірлянда. 100 LED. 472 грн.» — три удари', meta='гачок-вимір → сторінка вулиці',
             liniia='Мій район', kudy='/vulytsia/onore-de-balzaka/', odna_podiia=True)
    R.muzyka('puls', bpm=128, drop=0.0)
    R.kam(0, (c[0], c[1] - 0.0016), 14.8, 58, -20).kam(2.4, (c[0], c[1] - 0.0014), 15.2, 62, -40, e='o')
    R.kam(4.4, (c[0], c[1] - 0.0014), 15.2, 62, -50, e='l').kam(6.0, KYIV, 11.0, 40, -30, e='io', luk=0.4)
    R.tochky([p], [-0.5], rozmir=((0, 60), (4.4, 60), (5.6, 18)), glow=0.7)
    rng = random.Random(8)
    inshi = [x for x in vsi if x.id != p.id]
    chasy = sorted(4.5 + 1.6 * ((i + 1) / max(1, len(inshi))) ** 0.6 + rng.uniform(0, 0.05) for i in range(len(inshi)))
    R.tochky(inshi, chasy, rozmir=((0, 14),), glow=0.6)
    R.zvuk_tochok(chasy, maks=14, h0=1.0, h1=1.9, v=0.4)
    R.tekst(0, 2.3, 'hook', 'Гірлянда.\n100 LED.\n*472 грн.*', y='verkh')
    for t, s in ((0.02, 0.2), (0.75, 0.15), (1.5, 0.25)):
        R.udar(t, s, 16)
    R.tekst(2.4, 4.4, 'kartka', 'Грудень 2025, 15:50. У магазині взяли з полиці гірлянду на 100 LED і не заплатили.',
            zag='Дійшло до суду', dz=f'{D.vulytsia(p.adresa)} · рішення суду № {p.nomer_rishennia}', y='verkh')
    R.efekt(2.4, 'svish')
    R.mitka(3.4, 4.4, c, 'Епіцентр · 15:50', styl='velyka')
    R.efekt(3.4, 'pop', h=1.3)
    R.tekst(4.5, 6.6, 'lich', kluchi=[[4.5, 0], [6.1, len(vsi), 'io']], pidpys='{f} у даних,\nде згадано гірлянди й ялинки', formy=FORMY, y='verkh')
    R.efekt(4.4, 'vzhukh', v=0.7)
    R.petlia(0.45)
    R.pidpys(f'Справжня справа: рішення суду № {p.nomer_rishennia}. Що ще на твоїй вулиці — посилання в профілі.')
    R.meta['kintsivka'] = 'у підписі: посилання в профілі'
    R.meta['publichni'] = ['Епіцентр']
    return R


def s10(B):
    """Найдивніша справа тижня №3 — поні на Контрактовій (січень), 12 с."""
    p = B.podiia('134819479-1')
    c = (p.lon, p.lat)
    R = R138('10-dyvna-sprava-poni', 12, tema='temna', shar='tochky', typ='Найдивніша справа тижня',
             nazva='Найдивніша справа тижня №3: поні', hrupa='Найдивніша справа тижня', hachok='«Поні. Контрактова площа. Дійшло до суду.»',
             meta='серія щотижня → сторінка вулиці', liniia='Мій район', kudy='/vulytsia/kontraktova-ploshcha/', odna_podiia=True)
    R.muzyka('hra', bpm=116)
    tlo = [x for x in blyzko(B.P, c, 2500) if x.id != p.id]
    R.tochky(tlo, [-1] * len(tlo), rozmir=((0, 6),), yaskr=((0, 0.5),), glow=0.2, kiltse=False)
    R.kam(0, (c[0], c[1] - 0.012), 12.6, 40, -15).kam(4.6, (c[0], c[1] - 0.006), 13.6, 50, -30, e='io')
    R.kam(8.0, (c[0], c[1] - 0.0022), 15.0, 58, -60, e='io', luk=0.4).kam(12, (c[0], c[1] - 0.002), 15.2, 60, -90, e='l')
    R.tekst(0, 2.0, 'hook', 'Поні.\nКонтрактова площа.\n*Дійшло до суду.*', y='verkh')
    R.tekst(0, 2.0, 'mala', 'Найдивніша справа тижня · №3', y=1450, klas='zaklyk')
    R.udar(0.02, 0.2, 14)
    R.tekst(2.1, 6.4, 'kartka', 'Січень, 16:45. На Контрактовій катали на поні — протокол: порушені правила поводження з твариною.',
            zag='Найдивніша справа тижня · №3', dz=f'Контрактова площа · рішення суду № {p.nomer_rishennia}', y='verkh')
    R.efekt(2.1, 'svish')
    R.tochky([p], [3.6], rozmir=((0, 46),), glow=0.7)
    R.kiltse(3.65, c, '#B8E07A', 260)
    R.efekt(3.6, 'pop', h=1.2)
    R.slovo(6.5, 8.0, 'Поні', pid='протокол — і рішення суду', klas='fiolet')
    R.efekt(6.5, 'udar', v=0.7)
    R.mitka(8.1, 12, c, 'Контрактова площа', styl='velyka')
    R.tekst(8.3, 10.8, 'velykyi', 'А що дивного\n*на твоїй вулиці?*', y='verkh', anim='slam')
    R.efekt(8.3, 'pop', h=1.4)
    R.efekt(9.8, 'pop', h=1.5)
    R.S['novynky'] = [9.8]
    R.baner(10.9, 'Наступна — за тиждень', 'Сторінка вулиці · посилання в профілі')
    R.pidpys('Справжня справа з рішення суду, переказ без вигадок. Серія виходить щотижня.')
    return R


# ================================================================== НОВІ ТИПИ (реєстр, стан «зараз»)

def s03(B):
    """Календар року (не карта): 2025 — кожна клітинка день, колір — скільки подій у даних; найбільші дні."""
    dni = Counter()
    for p in B.P:
        try:
            d = date.fromisoformat(p.data or '')
        except ValueError:
            continue
        if d.year == 2025:
            dni[d] += 1
    vsi = [date.fromordinal(date(2025, 1, 1).toordinal() + i) for i in range(365)]
    znach = sorted(dni[d] for d in vsi)
    porohy = [znach[int(len(znach) * q)] for q in (0.25, 0.5, 0.75)]       # чверті: рівень 1–4 (0 — жодної події)

    def riven(n):
        return 0 if n == 0 else 1 + sum(1 for x in porohy if n > x)
    misiatsi, ind = [], {}
    for m in range(12):
        dd = [d for d in vsi if d.month == m + 1]
        for d in dd:
            ind[d] = len(ind)
        misiatsi.append({'nazva': MISIATSI[m], 'pochatok': dd[0].weekday(), 'dni': [riven(dni[d]) for d in dd]})
    top = dni.most_common(2)
    (d1, n1), (d2, n2) = top
    R = R138('03-kalendar-roku', 11, tema='svitla', shar='ne_karta', typ='Календар року', nazva='Календар року: 2025 за днями',
             hrupa='Не карта', hachok='«Кожна клітинка — один день 2025-го» над порожнім календарем, що заповнюється',
             meta='«вау» без карти, коментарі «а мій день?» → карта', liniia='Безкоштовна карта', kudy='/karta/')
    R.muzyka('lofi', bpm=100)
    R.kam(0, KYIV, 10.5, 0, 0).kam(11, KYIV, 10.6, 0, 0, e='l')
    R.ui(0, 12, 'zavisa')
    R.tekst(0, 2.6, 'velykyi', 'Кожна клітинка —\n*один день 2025-го*', y=380)
    R.tekst(0, 12, 'kalendar', misiatsi=misiatsi, kluchi=[[0.2, 0], [4.4, 364, 'io']], akc=[ind[d1]], akc_t=4.6, y=700)
    for i in range(12):
        R.efekt(0.2 + i * 0.35, 'klik', h=0.9 + i * 0.04, v=0.3)
    R.S['novynky'] = [1.6, 3.0, 4.4]
    R.tekst(2.7, 4.5, 'lich', kluchi=[[0.2, 0], [4.4, sum(dni.values()), 'io']], pidpys='{f} у даних за 2025 рік', formy=FORMY, y=380)
    R.tekst(0.6, 11, 'mala', 'Яскравіше — більше подій у даних', y=1500, klas='zaklyk')
    R.udar(4.6, 0.25, 0)
    R.tekst(4.6, 6.5, 'velykyi', f'Найбільше —\n*{d1.day} {MISIATSI_R[d1.month - 1]}*: {n1}', y=380, anim='slam')
    R.tekst(6.6, 8.5, 'velykyi', f'Друге місце —\n*{d2.day} {MISIATSI_R[d2.month - 1]}*: {n2}', y=380, anim='slam')
    R.S['tekst'][1]['akc'] = [[ind[d1], 4.6], [ind[d2], 6.6]]
    R.efekt(6.6, 'pop', h=1.4)
    R.tekst(8.6, 11, 'velykyi', 'А що було\n*на твоїй вулиці?*', y=380, anim='slam')
    R.baner(9.9, 'Карта подій Києва', 'Безкоштовно · посилання в профілі')
    R.pidpys(f'Кожна клітинка — день 2025 року; колір — скільки подій з рішень судів Києва в нашому випуску мають цю дату '
             f'({n1} — найбільше). Лише те, що дійшло до суду; причин не стверджуємо.')
    return R


def s07(B):
    """День і ніч — поділений екран: ліворуч світла карта й події вдень (8–18), праворуч темна й події вночі (22–5)."""
    den = [p for p in B.P if p.hodyna is not None and 8 <= p.hodyna <= 18]
    nich = [p for p in B.P if p.hodyna is not None and (p.hodyna >= 22 or p.hodyna <= 5)]
    vd = Counter(p.mitka for p in den).most_common(5)
    vn = Counter(p.mitka for p in nich).most_common(5)
    p130_d = sum(1 for p in den if p.mitka == "п'яний за кермом")
    p130_n = sum(1 for p in nich if p.mitka == "п'яний за кермом")
    R = R138('07-den-i-nich', 12, tema='svitla', shar='tochky', typ='День і ніч', nazva='День і ніч: що в даних удень і вночі',
             hrupa='Місто згори', hachok='поділений екран: «День» на світлій карті · «Ніч» на темній — точки біжать одночасно',
             meta='«вау» порівняння → карта', liniia='Безкоштовна карта', kudy='/karta/', tema_os='svitla+temna', riven='misto')
    R.muzyka('nich', bpm=96)
    R.S['zatemnennia'] = 0          # світле затемнення лягло б і на темну половину; текст має власну тінь
    rng = random.Random(7)
    zsuv = 0.27                     # Київ — у центрі своєї половини (270 px на z 9,45: 512-піксельні плитки)
    R.kam(0, (KYIV[0] + zsuv, KYIV[1]), 9.45, 0, 0).kam(12, (KYIV[0] + zsuv * 0.92, KYIV[1]), 9.57, 0, 0, e='l')
    tden = [0.2 + 4.0 * rng.random() ** 0.7 for _ in den]
    R.tochky(den, tden, rozmir=((0, 4),), yaskr=((0, 1),), glow=0.2, tryv=0.4, kiltse=False)
    R2 = R138('07-den-i-nich-druha', 12, tema='temna', shar='tochky')
    R2.kam(0, (KYIV[0] - zsuv, KYIV[1]), 9.45, 0, 0).kam(12, (KYIV[0] - zsuv * 0.92, KYIV[1]), 9.57, 0, 0, e='l')
    tnich = [0.2 + 4.0 * rng.random() ** 0.7 for _ in nich]
    R2.tochky(nich, tnich, rozmir=((0, 4),), yaskr=((0, 1),), glow=0.5, tryv=0.4, kiltse=False)
    R.druha(R2, [[0, 0.5]])
    R.S['druha']['os'] = 'x'
    R.zvuk_tochok(tden + tnich, maks=12, h0=0.8, h1=1.6, v=0.4)
    R.tekst(0, 4.4, 'hook', '*День*', y=360, klas='liva')
    R.tekst(0, 4.4, 'hook', '*Ніч*', y=360, klas='prava na-temnomu')
    R.tekst(0.2, 4.4, 'lich', kluchi=[[0.2, 0], [4.2, len(den), 'io']], pidpys='{f}\nз 8:00 до 18:59', formy=FORMY, y=1260, klas='liva')
    R.tekst(0.2, 4.4, 'lich', kluchi=[[0.2, 0], [4.2, len(nich), 'io']], pidpys='{f}\nз 22:00 до 5:59', formy=FORMY, y=1260, klas='prava na-temnomu')
    R.udar(4.5, 0.25, 10)
    R.tekst(4.5, 7.4, 'velykyi', f'Найчастіше —\n*{vd[0][0]}*', y=1260, anim='slam', klas='liva')
    nich_ne_dtp = [m for m, _ in vn if m != 'ДТП'][0]
    R.tekst(5.6, 7.4, 'velykyi', f'Ще й —\n*{nich_ne_dtp}*', y=1260, anim='slam', klas='prava na-temnomu')
    R.efekt(5.6, 'pop', h=1.3)
    R.tekst(7.5, 10.2, 'split', riady=[{'zag': 'Удень', 'n': p130_d, 'tekst': "п'яних за кермом у даних"},
                                         {'zag': 'Уночі', 'n': p130_n, 'tekst': "п'яних за кермом у даних"}], y=560)
    R.efekt(7.5, 'vzhukh')
    R.efekt(9.0, 'pop', h=1.3)
    R.S['novynky'] = [9.0]
    R.slovo(10.3, 12, 'А на твоїй вулиці?', pid='удень і вночі — на карті', klas='temne menshe')
    R.efekt(10.3, 'udar', v=0.6)
    R.baner(10.9, 'Карта подій Києва', 'Безкоштовно · посилання в профілі')
    R.pidpys('Ліворуч — події з відомою годиною від 8:00 до 18:59, праворуч — від 22:00 до 5:59; рішення судів Києва в нашому випуску.',
             'Година — з рішення суду. Причин не стверджуємо. Карта — посилання в профілі.')
    return R


def s09(B):
    """Адреса зблизька (публічне місце): ТЦ «Олімпійський» — події за 250 м, види стовпчиками, точка-повтор, адреси довкола."""
    pr = [p for p in B.V.problemy() if (p['masshtab'] or {}).get('name', '') == 'ТЦ Олімпійський'][0]
    pov = B.V.podii_problemy(pr['id'])
    c = (pr['lon'], pr['lat'])
    pod = blyzko(B.P, c, 250)
    n = len(pod)
    vydy = Counter(p.mitka for p in pod).most_common(3)
    vyd_pov = Counter(p.mitka for p in pov).most_common(1)[0]
    R = R138('09-adresa-zblyzka-olimpiiskyi', 12, tema='svitla', shar='adresy', typ='Адреса зблизька',
             nazva='Адреса зблизька: ТЦ «Олімпійський»', hrupa='Мій район', hachok='«ТЦ «Олімпійський». Зблизька.» — камера вже біля ТЦ, точки вискакують',
             meta='місце, яке знають усі → сторінка вулиці', liniia='Мій район', kudy='/vulytsia/velyka-vasylkivska/', publichni=['Олімпійськ'])
    R.muzyka('napruha', bpm=108)
    R.kam(0, (c[0], c[1] - 0.0022), 16.0, 60, 30).kam(5.5, (c[0], c[1] - 0.0018), 16.3, 62, 0, e='io')
    R.kam(8.6, (c[0], c[1] - 0.0045), 14.6, 55, -30, e='io').kam(12, (c[0], c[1] - 0.0047), 14.5, 55, -45, e='l')
    rng = random.Random(9)
    chasy = sorted(-0.4 + 2.6 * ((i + 1) / n) ** 0.6 + rng.uniform(0, 0.05) for i in range(n))
    R.tochky(pod, chasy, rozmir=((0, 18), (8.4, 18), (9.2, 9)), glow=0.25)
    R.zvuk_tochok([t for t in chasy if t > 0], maks=12, h0=1.0, h1=1.8, v=0.45)
    inshi = [x for x in blyzko(B.P, c, 800) if x not in pod]
    R.adresy(inshi, khvylia(inshi, c, 8.8, 10.2, seed=4), styl_adres='kiltsia', prozorist=((0, 0), (8.7, 0), (8.9, 1)), min_chyslo=3)
    R.mitka(0, 12, c, 'ТЦ «Олімпійський»', styl='velyka')
    R.tekst(0, 2.6, 'hook', 'ТЦ «Олімпійський».\n*Зблизька.*', y='verkh')
    R.udar(0.02, 0.2, 10)
    R.tekst(2.7, 5.6, 'lich', kluchi=[[2.7, 0], [3.9, n, 'o']], pidpys='{f} за 250 м від ТЦ', formy=FORMY, y='verkh')
    R.tekst(2.9, 5.6, 'stovpchyky', riady=[{'tekst': v, 'n': k, 'kolir': '#31B88D' if i == 0 else '#6066C1'} for i, (v, k) in enumerate(vydy)], y=1080)
    R.efekt(2.7, 'svish')
    R.efekt(4.2, 'pop', h=1.3)
    R.S['novynky'] = [4.2]
    R.slovo(5.7, 8.6, f'{vyd_pov[1]}', pid=f'разів — {vyd_pov[0]}\nв одній точці біля ТЦ', klas='fiolet')
    R.udar(5.7, 0.25, 12)
    R.kiltse(7.2, c, '#31B88D', 320)
    R.efekt(7.2, 'pop', h=1.2)
    R.tekst(8.7, 10.8, 'velykyi', 'А довкола —\n*ще місця з подіями*', y='verkh', anim='slam')
    R.efekt(8.8, 'vzhukh')
    R.baner(10.9, 'Сторінка вулиці', 'Велика Васильківська · посилання в профілі')
    R.pidpys('Дані: рішення судів (ЄДРСР) за 250 м від ТЦ; кільця — місця поруч, число — скільки подій у даних. Лише те, що дійшло до суду.',
             'Це кількість даних, не оцінка місця. Посилання в профілі.')
    return R


def s11(B):
    """Вгадай район за плиткою — лише соти одного району, без жодної назви на карті; відлік; відповідь — межа й назва."""
    rayon = 'Оболонський'
    poly = B.V.rayony.mezhi[rayon]
    pod = [p for p in B.P if B.V.rayon(p) == rayon]
    c = tsentr(pod)
    R = R138('11-vgadai-rayon-plytka', 11, tema='temna', shar='soty', typ='Вгадай район за плиткою', nazva='Вгадай район за плиткою',
             hrupa='Ігри', hachok='«Що це за район?» над плиткою сот без жодної назви', meta='коментарі (свій район впізнають) → район',
             liniia='Гра', kudy='/rayon/obolonskyi/')
    R.S['bez_pidpysiv'] = True
    R.S['bez_3d'] = True
    R.S['mezha'] = {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {}, 'geometry': {'type': 'MultiPolygon',
                    'coordinates': [[[[lon, lat] for lat, lon in pl]] for pl, _ in poly]}}]}
    R.muzyka('hra', bpm=118)
    R.soty(pod, 8, styl_sot='plytka', prozorist=((0, 1),), vysota=((0, 0),), min_chastka=0.0, min_n=1)
    R.kam(0, c, 11.6, 0, -35).kam(6.0, c, 11.8, 0, -25, e='l').kam(8.0, c, 11.4, 40, -10, e='io').kam(11, c, 11.5, 50, 5, e='l')
    R.tekst(0, 6.0, 'hook', 'Що це\n*за район?*', y='verkh')
    varianty = [('А', 'Дарницький'), ('Б', rayon), ('В', 'Святошинський')]
    for i, (b, v) in enumerate(varianty):
        R.tekst(1.2 + 0.2 * i, 7.6, 'variant', v, bukva=b, y=1180 + i * 120, pravylno=(v == rayon), vidpovid=6.0)
        R.efekt(1.2 + 0.2 * i, 'pop', h=1.2 + 0.15 * i, v=0.5)
    R.tekst(1.6, 6.0, 'mala', 'Підказка: вода праворуч', y=1560, klas='zaklyk')
    R.tekst(3.0, 6.0, 'vidlik', y=640)
    for t in (3.0, 4.0, 5.0):
        R.efekt(t, 'tik', h=1.3)
    R.efekt(6.0, 'dzvin', h=1.2)
    R.udar(6.0, 0.3, 12)
    R.tekst(6.1, 8.6, 'velykyi', f'*{rayon}*\nрайон', y='verkh', anim='slam')
    R.kiltse(7.3, c, '#66E6BA', 420, 1.4)
    R.efekt(7.3, 'pop', h=1.3)
    R.tekst(8.7, 10.9, 'lich', kluchi=[[8.7, 0], [9.9, len(pod), 'o']], pidpys='{f} у даних\nу ' + misdenyi(rayon) + ' районі', formy=FORMY, y='verkh')
    R.baner(10.0, 'Сторінка району', 'Оболонський · посилання в профілі')
    R.pidpys('Плитка — соти з подіями з рішень судів (ЄДРСР); колір — кількість даних, не оцінка місця.',
             'Пиши в коментарях, з якої букви вгадав. Сторінка району — посилання в профілі.')
    return R


def s12(B):
    """Сота пояснює (MV-148): персонаж «Сота» (знак без обличчя) стрибає картою — що таке сота, колір, наближення → адреси."""
    import h3
    P = list(B.P)
    by = D.soty_z_podiiamy(P, 8)
    c = (30.4686, 50.4505)        # Шулявка — житловий район, не центр
    k = h3.latlng_to_cell(c[1], c[0], 8)
    lat, lon = h3.cell_to_latlng(k)
    v_soti = [P[i] for i in by.get(k, [])]
    n = len(v_soti)
    R = R138('12-sota-poiasniuie', 13, tema='svitla', shar='soty', typ='Сота пояснює', nazva='Сота пояснює: що таке сота',
             hrupa='Як це працює', hachok='знак «Сота» стрибає на карту: «Я — Сота. Київ складено з мене»',
             meta='пояснює карту за 13 с → карта', liniia='Безкоштовна карта', kudy='/karta/', riven='rayon')
    R.muzyka('lofi', bpm=104)
    R.soty(P, 8, styl_sot='sait', prozorist=((0, 1), (8.6, 1), (9.4, 0.35)), vysota=((0, 0),), **SOTY)
    R.kam(0, KYIV, 10.6, 0, 0).kam(3.2, KYIV, 10.8, 0, 0, e='l').kam(5.2, (lon, lat - 0.004), 13.4, 35, -10, e='io', luk=0.4)
    R.kam(8.6, (lon, lat - 0.003), 13.6, 40, -20, e='l').kam(10.6, (lon, lat - 0.0025), 15.0, 50, -35, e='io').kam(13, (lon, lat - 0.0024), 15.2, 52, -45, e='l')
    blyzki = blyzko(P, (lon, lat), 900)
    R.adresy(blyzki, khvylia(blyzki, (lon, lat), 9.4, 10.6, seed=5), styl_adres='kola', prozorist=((0, 0), (9.3, 0), (9.5, 1)), min_chyslo=3)
    R.ui(0, 13, 'sota', kroky=[[0, KYIV[0] - 0.06, KYIV[1] - 0.03], [1.7, KYIV[0] + 0.09, KYIV[1] + 0.03], [3.4, lon - 0.012, lat + 0.006], [5.6, lon, lat], [7.3, lon - 0.0025, lat - 0.0015], [9.8, lon + 0.002, lat + 0.0012]],
         rozmir=150, vysota=260)
    for t in (0.0, 1.7, 3.4, 5.6, 7.3, 9.8):
        R.efekt(t, 'pop', h=1.0, v=0.6)
    R.tekst(0, 3.0, 'hook', 'Я — *Сота.*\nКиїв складено з мене', y='verkh')
    R.tekst(3.1, 5.3, 'velykyi', 'Колір —\n*скільки подій у даних*', y='verkh', anim='vgoru')
    R.tekst(5.3, 8.4, 'lich', kluchi=[[5.6, 0], [7.0, n, 'o']], pidpys='{f} в одній соті —\nз рішень судів', formy=FORMY, y='verkh')
    R.udar(5.6, 0.2, 10)
    R.tekst(8.5, 10.4, 'velykyi', 'Наближ —\n*і я розкриюсь на місця*', y='verkh', anim='slam')
    R.efekt(9.4, 'vzhukh')
    R.tekst(10.5, 12.0, 'velykyi', 'Число —\n*скільки подій у місці*', y='verkh', anim='vgoru')
    R.efekt(11.2, 'pop', h=1.3)
    R.S['novynky'] = [11.2]
    R.baner(12.0, 'Знайди свою соту', 'Карта Києва · посилання в профілі')
    R.pidpys('Сота — шестикутник ≈ 0,7 км² на карті. Колір — кількість подій з рішень судів (ЄДРСР), не оцінка місця.',
             'Наблизь карту — соти розкриваються на місця й події. Посилання в профілі.')
    return R


def s13(B):
    """Тур району: 5 зупинок — Подільський; на кожній — місце з найбільшим числом подій, вулиця без номера, вид."""
    rayon = 'Подільський'
    pod = [p for p in B.P if B.V.rayon(p) == rayon and p.tochnist == 'house' and p.vul and '/' not in p.vul]
    mists = defaultdict(list)
    for p in pod:
        mists[(round(p.lat, 4), round(p.lon, 4))].append(p)
    vybir, vul_bulo = [], set()
    for k, v in sorted(mists.items(), key=lambda x: -len(x[1])):
        vul = v[0].vul
        if vul in vul_bulo or any(D.vidstan_m(k[0], k[1], a[0], a[1]) < 900 for a, _ in vybir):
            continue
        vybir.append((k, v)); vul_bulo.add(vul)
        if len(vybir) == 5:
            break
    # маршрут — з півночі на південь, щоб камера не металась
    vybir.sort(key=lambda x: -x[0][0])
    T = 15
    R = R138('13-tur-raionu-podil', T, tema='temna', shar='adresy', typ='Тур району', nazva='Тур району: Поділ за 5 зупинок',
             hrupa='Мій район', hachok='«Поділ. 5 зупинок.» — камера вже над першою', meta='серія по районах → сторінка району',
             liniia='Мій район', kudy='/rayon/podilskyi/', riven='vulytsia')
    R.muzyka('puls', bpm=112, drop=0.0)
    R.adresy(pod, [-1] * len(pod), styl_adres='kiltsia', min_n=3, min_chyslo=6)
    t = 0.0
    krok = 2.5
    for i, ((lat, lon), v) in enumerate(vybir):
        t0 = 0.6 + i * krok
        R.kam(t0 - 0.6 if i else 0, (lon, lat - 0.0018), 15.0, 55, -20 + i * 18, e='io', luk=0.6 if i else 0)
        R.kam(t0 + krok - 1.0, (lon, lat - 0.0016), 15.2, 58, -10 + i * 18, e='l')
        top = ' · '.join(m for m, _ in Counter(p.mitka for p in v).most_common(2))
        R.mitka(t0, t0 + krok - 0.9, (lon, lat), v[0].vul, styl='velyka', n=f' · {len(v)}')
        R.tekst(t0, t0 + krok - 0.8, 'velykyi', f'*{i + 1}.* {top}', y=1300, anim='pop')
        R.kiltse(t0 + 0.05, (lon, lat), '#66E6BA', 240)
        R.efekt(t0, 'vzhukh' if i else 'udar', v=0.6)
    R.kam(T, (vybir[-1][0][1], vybir[-1][0][0] - 0.02), 13.2, 45, 80, e='io', luk=0.3)
    R.tekst(0, 2.2, 'hook', 'Поділ.\n*5 зупинок.*', y='verkh')
    R.tekst(2.3, 13.2, 'mala', 'Кільце — місце, число — скільки подій у даних', y=420, klas='zaklyk')
    R.tekst(13.2, T, 'pytannia', 'Який район наступний?', y=420)
    R.baner(13.9, 'Сторінка району', 'Поділ · посилання в профілі')
    R.pidpys('Тур району: п\'ять місць з найбільшим числом подій у даних (рішення судів, ЄДРСР). Вулиця — без номера будинку.',
             'Це кількість даних, не оцінка місця. Пиши в коментарях, який район наступний.')
    return R


def s14(B):
    """Вулиця тижня, частина 1 — «скільки»: Теремківська; лінія вулиці малюється, місця з числом, 57 подій."""
    vs = B.V.po_vulytsi()
    imia = 'вул. Теремківська'
    pod = [p for p in vs.get(imia, []) if (p.rik or 0) >= 2024]
    c = tsentr(pod)
    lin = lanka_vulytsi(pod)
    n = len(pod)
    vydy = Counter(p.mitka for p in pod).most_common(2)
    R = R138('14-vulytsia-tyzhnia-1-teremkivska', 13, tema='svitla', shar='adresy', typ='Вулиця тижня',
             nazva='Вулиця тижня: Теремківська, частина 1', hrupa='Вулиця тижня', hachok='«Вулиця тижня. Частина 1: скільки» — лінія вулиці вже малюється',
             meta='серія 3 частини → сторінка вулиці', liniia='Мій будинок', kudy='/vulytsia/teremkivska/', riven='vulytsia')
    R.muzyka('lofi', bpm=98)
    R.kam(0, (c[0], c[1] - 0.0035), 14.6, 45, 60).kam(6.0, (c[0], c[1] - 0.003), 15.0, 52, 35, e='io')
    R.kam(13, (c[0], c[1] - 0.0026), 15.2, 56, 10, e='l')
    R.liniia(lin, 0.0, 2.6, kolir='#4447A6', shyr=12)
    rng = random.Random(14)
    chasy = sorted(1.4 + 3.0 * ((i + 1) / n) ** 0.7 + rng.uniform(0, 0.05) for i in range(n))
    R.adresy(pod, chasy, styl_adres='kola', min_chyslo=2)
    R.zvuk_tochok(chasy, maks=10, typ='pop', h0=1.0, h1=1.6, v=0.4)
    R.tekst(0, 2.4, 'hook', 'Вулиця тижня:\n*Теремківська*', y='verkh')
    R.tekst(0, 2.4, 'mala', 'Частина 1 з 3 · скільки', y=640, klas='zaklyk')
    R.tekst(2.5, 5.2, 'lich', kluchi=[[1.4, 0], [4.5, n, 'io']], pidpys='{f} за 2024–2026', formy=FORMY, y='verkh')
    R.udar(4.7, 0.2, 8)
    R.tekst(5.3, 8.2, 'stovpchyky', riady=[{'tekst': v, 'n': k, 'kolir': '#31B88D' if i == 0 else '#6066C1'} for i, (v, k) in enumerate(vydy)], y=1080)
    R.tekst(5.3, 8.2, 'velykyi', f'Найчастіше —\n*{vydy[0][0]}*', y='verkh', anim='slam')
    R.efekt(5.3, 'svish')
    R.efekt(6.8, 'pop', h=1.3)
    R.S['novynky'] = [6.8]          # 6,8 с — стовпчики добігли до чисел
    mists = len(R.S['adresy'][0]['dani']['features'])
    R.tekst(8.3, 10.6, 'velykyi', f'*{mists}* різних місць\nна одній вулиці', y='verkh', anim='slam')
    R.efekt(8.3, 'pop', h=1.4)
    R.kiltse(9.5, c, '#4447A6', 360)
    R.tekst(10.7, 13, 'velykyi', 'Частина 2 —\n*коли саме*', y='verkh', anim='vgoru')
    R.efekt(10.7, 'vzhukh')
    R.baner(11.9, 'Сторінка вулиці', 'Теремківська · посилання в профілі')
    R.pidpys('Вулиця тижня — серія з 3 частин: скільки · коли · чим відрізняється від Києва. Дані — рішення судів (ЄДРСР), 2024–2026.',
             'Кола — місця на вулиці, число — скільки подій у даних; без номерів будинків. Посилання в профілі.')
    return R


SCENARII = {k[1:]: v for k, v in dict(globals()).items() if re.match(r's\d\d$', k)}

# Пачка на перший тиждень тесту (порядок публікації): В2 — два поспіль різні щонайменше за двома осями.
# 06 — запис справжнього сайту (zapys_saitu.py, z3 «POV: застава завтра»): тема темна, шар «запис», рівень — вулиця.
PACHKA = ['01', '02', '03', '04', '05', 'z3', '07', '08', '09', '10']
ZAPAS = ['11', '12', '13', '14']
OSI_ZAPYSU = {'z3': {'tema': 'temna', 'shar': 'zapys', 'riven': 'vulytsia'}}


def perevir_pachku(kesh=VYHID) -> list[str]:
    rolyky = []
    for k in PACHKA:
        if k in OSI_ZAPYSU:
            o = OSI_ZAPYSU[k]
            rolyky.append(({'id': k, 'tema': o['tema'], 'kamera': []}, {'id': k, 'shar': o['shar'], 'riven': o['riven']}))
            continue
        f = [x for x in kesh.glob(f'138-{k}-*.json') if 'druha' not in x.name]
        if not f:
            return [f'немає сценарію {k} — спершу зібрати']
        S = json.loads(f[0].read_text(encoding='utf-8'))
        kat = {m['id']: m for m in json.loads((kesh / 'katalog-138.json').read_text(encoding='utf-8'))}
        rolyky.append((S, kat[S['id']]))
    return perevirka.pereviryty_pachku(rolyky)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('baza', type=Path)
    a.add_argument('--koloda', type=Path)
    a.add_argument('--lyshe')
    a.add_argument('--pachka', action='store_true', help='лише перевірити чергування пачки (В2)')
    arg = a.parse_args()
    if arg.pachka:
        z = perevir_pachku()
        print('\n'.join(z) or 'пачка: В2 — гаразд')
        sys.exit(1 if z else 0)
    B = Baza(arg)
    vybir = arg.lyshe.split(',') if arg.lyshe else sorted(SCENARII)
    kat_f = VYHID / 'katalog-138.json'
    katalog = []
    if kat_f.is_file():
        katalog = [m for m in json.loads(kat_f.read_text(encoding='utf-8')) if m['id'].split('-')[1] not in vybir]
    for k in vybir:
        R = SCENARII[k](B)
        katalog.append(R.zberehty())
        print(R.S['id'], R.S['tryvalist'], 'с', R.meta['osi'])
    katalog.sort(key=lambda m: m['id'])
    kat_f.write_text(json.dumps(katalog, ensure_ascii=False, indent=1), encoding='utf-8')
    z = perevir_pachku()
    print('\n'.join(z) or 'пачка: В2 — гаразд')


if __name__ == '__main__':
    main()
