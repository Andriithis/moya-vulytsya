"""Сценарії роликів рушія «Вау» (ZAVDANNYA-127) — з випуску бази, без ручних чисел.

    python video/vau/stsenarii.py <events.db> [--koloda koloda.json] [--lyshe 01,07]
    → video/vyhid/kesh/stsenarii/<id>.json (у git не йде) + video/vyhid/kesh/stsenarii/katalog.json

Кожен сценарій — одна функція `r_<номер>`; числа беруться з бази в момент збирання. Перед записом кожен проходить
`perevirka.pereviryty` (заборонені слова, сліди знеособлення, номер житлового будинку, місто, кінцівка-посилання).
Межі (AGENTS.md розд. 4, MV-25, MV-60, MV-69): жодних причин, рейтингів небезпеки, прогнозів і порад «будьте уважні»;
номер будинку — лише публічних місць (ТЦ); насильство, статеві справи й щодо дітей — не в роликах (dani.py їх не дає).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
sys.path.insert(0, str(TUT))
import dani as D  # noqa: E402
import perevirka  # noqa: E402

VYHID = KORIN / 'video' / 'vyhid' / 'kesh' / 'stsenarii'
MEZHA = json.loads((KORIN / 'site' / 'hra' / 'mezha-kyieva.geojson').read_text(encoding='utf-8'))
KYIV = (30.5234, 50.4501)        # Майдан — центр кадру міста
PROFIL = 'посилання в профілі'
TSIL = '#FFE45C'                 # колір «цілі» (група 6) — «Знайди точку»; не червоний (MV-58)
FORMY = ['подія', 'події', 'подій']


class Rolyk:
    """Збирач одного сценарію: доріжки камери, точок, тексту, звуку."""

    def __init__(self, id_, tryv, tema='temna', **meta):
        self.S = {'id': id_, 'tryvalist': tryv, 'tema': tema, 'kolory': D.kolory_hrup() + [TSIL, '#FFFFFF'], 'kamera': [], 'tochky': [],
                  'soty': [], 'lini': [], 'kiltsia': [], 'mitky': [], 'tekst': [], 'ui': [], 'spalakh': [], 'trus': [],
                  'mezha': MEZHA, 'zvuk': {'efekty': [], 'holos': []}}
        self.meta = dict(meta, id=id_, tryvalist=tryv)

    # -- камера
    def kam(self, t, c, z, p=0, b=0, e='io', luk=0):
        self.S['kamera'].append({'t': t, 'c': list(c), 'z': z, 'p': p, 'b': b, 'e': e, 'luk': luk})
        return self

    # -- шари
    def tochky(self, podii, chasy, rozmir=((0, 9),), yaskr=((0, 1),), org=None, te=None, **kw):
        d = D.tochky(podii, chasy)
        if org is not None:
            d['ox'] = [round(o[0] * 1e5) for o in org]
            d['oy'] = [round(o[1] * 1e5) for o in org]
        if te is not None:
            d['te'] = [round(x, 3) for x in te]
        self.S['tochky'].append(dict({'dani': d, 'rozmir': [list(x) for x in rozmir], 'yaskravist': [list(x) for x in yaskr]}, **kw))
        return self

    def soty(self, podii, riven=8, vysota=((0, 0),), prozorist=((0, 1),), min_chastka=0.0, min_n=1, **kw):
        self.S['soty'].append(dict({'dani': D.soty(podii, riven, min_chastka=min_chastka, min_n=min_n), 'vysota': [list(x) for x in vysota],
                                    'prozorist': [list(x) for x in prozorist]}, **kw))
        return self.S['soty'][-1]

    def liniia(self, coords, t0, t1, t2=None, kolir='#66E6BA', shyr=10):
        self.S['lini'].append({'coords': coords, 't0': t0, 't1': t1, 't2': t2, 'kolir': kolir, 'shyr': shyr})

    def kiltse(self, t, c, kolir='#66E6BA', radius=260, tryv=1.2):
        self.S['kiltsia'].append({'t': t, 'c': list(c), 'kolir': kolir, 'radius': radius, 'tryv': tryv})

    def mitka(self, t0, t1, c, tekst, **kw):
        self.S['mitky'].append(dict({'t0': t0, 't1': t1, 'c': list(c), 'tekst': tekst}, **kw))

    def tekst(self, t0, t1, styl, tekst='', **kw):
        self.S['tekst'].append(dict({'t0': t0, 't1': t1, 'styl': styl, 'tekst': tekst}, **kw))

    def ui(self, t0, t1, typ, **kw):
        self.S['ui'].append(dict({'t0': t0, 't1': t1, 'typ': typ}, **kw))

    def fin(self, t0, zag, tekst, knopka, t1=None, **kw):
        self.tekst(t0, t1 or self.S['tryvalist'] + 1, 'fin', tekst, zag=zag, knopka=knopka, y=kw.pop('y', 560), **kw)
        self.efekt(t0, 'dzvin', h=0.8, v=0.6)
        self.meta['kintsivka'] = knopka

    # -- ZAVDANNYA-129: кінцівка ≤ 1 с поверх руху, петля, удар на весь кадр, підпис публікації
    def baner(self, t0, zag, knopka=None, tryv=1.0, y=1180):
        """С1: заклик — банер ≤ 1 с поверх руху (камера не зупиняється); сам заклик дублюється в підписі публікації."""
        knopka = knopka or PROFIL
        self.tekst(t0, t0 + tryv, 'baner', '', zag=zag, knopka=knopka, y=y, vykhid=0.12)
        self.efekt(t0, 'dzvin', h=0.8, v=0.5)
        self.meta['kintsivka'] = knopka

    def petlia(self, tryv=0.45):
        """С1: останній кадр стикується з першим — камера повертається на старт, гачок знову стоїть повністю."""
        T = self.S['tryvalist']
        k0 = sorted(self.S['kamera'], key=lambda k: k['t'])[0]
        self.kam(T, k0['c'], k0['z'], k0['p'], k0['b'], e='io')
        hook = [it for it in self.S['tekst'] if it['t0'] <= 1e-6]
        if hook:
            self.S['tekst'].append(dict(hook[0], t0=round(T - tryv, 3), t1=T + 1, odrazu=True))
        self.efekt(T - tryv - 0.25, 'vzhukh', v=0.6)
        self.meta['petlia'] = True

    def slovo(self, t0, t1, tekst, klas='', **kw):
        """С6: план-удар — одне слово чи число на весь кадр."""
        self.tekst(t0, t1, 'slovo', tekst, klas=klas, anim='zhodnoi', krok=0, y=0, **kw)

    def pidpys(self, *riady):
        """Підпис публікації (С8): захисні фрази, джерело, заклик — сюди, а не в тіло ролика."""
        self.S.setdefault('pidpys_publikatsii', []).extend(riady)
        self.meta['pidpys'] = ' '.join(self.S['pidpys_publikatsii'])

    # -- звук
    def muzyka(self, styl, **kw):
        self.S['zvuk']['muzyka'] = dict({'styl': styl}, **kw)

    def efekt(self, t, typ, **kw):
        self.S['zvuk']['efekty'].append(dict({'t': round(t, 3), 'typ': typ}, **kw))

    def udar(self, t, sila=0.5, trus=16):
        self.efekt(t, 'udar')
        self.S['spalakh'].append({'t': t, 'sila': sila})
        if trus:
            self.S['trus'].append({'t': t, 'sila': trus})

    def holos(self, t, tekst, imia='mykyta', **kw):
        self.S['zvuk']['holos'].append(dict({'t': t, 'tekst': tekst, 'holos': imia}, **kw))

    def zvuk_tochok(self, chasy, maks=10, typ='pop', h0=0.9, h1=1.6, v=0.55, seed=1):
        """Звук до появи точок: не частіше maks на секунду; тон росте — «наростання», а не шум."""
        rng = random.Random(seed)
        ost = -1.0
        tt = sorted(chasy)
        for i, t in enumerate(tt):
            if t - ost >= 1.0 / maks:
                k = i / max(1, len(tt) - 1)
                self.efekt(t, typ, h=round(h0 + (h1 - h0) * k + rng.uniform(-0.05, 0.05), 3), v=v)
                ost = t

    def zberehty(self, teka=VYHID):
        teka.mkdir(parents=True, exist_ok=True)
        S = self.S
        S['kamera'].sort(key=lambda k: k['t'])
        if S['zvuk']['holos']:          # голос — завжди з позначкою в кадрі: чий голос, така й позначка (MV-150, MV-171)
            import holos_servis
            S['holos_poznaka'] = holos_servis.poznaka()
            self.meta['holos'] = True
        zauv = perevirka.pereviryty(S, self.meta)
        if zauv:
            raise SystemExit(f"{S['id']}: " + '; '.join(zauv))
        (teka / f"{S['id']}.json").write_text(json.dumps(S, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        return self.meta


# ------------------------------------------------------------------ розклади появи точок

def pryskorennia(n, t0, t1, p=0.45):
    """Спершу рідко (клік… клік…), далі злива: інтервали меншають."""
    return [t0 + (t1 - t0) * ((i + 1) / n) ** p for i in range(n)]


def khvylia(podii, c, t0, t1, rng=0.15, seed=1):
    """Хвиля від точки c: час ∝ відстань (з невеликим розкидом)."""
    r = random.Random(seed)
    d = [D.vidstan_m(c[1], c[0], p.lat, p.lon) for p in podii]
    m = max(d) or 1
    return [t0 + (t1 - t0) * (x / m) ** 0.8 + r.uniform(0, rng) for x in d]


def khronolohiia(podii, t0, t1, vid='2023-01-01', do='2026-11-01'):
    from datetime import date
    a, b = date.fromisoformat(vid), date.fromisoformat(do)
    out = []
    for p in podii:
        try:
            d = date.fromisoformat(p.data)
        except (TypeError, ValueError):
            d = a
        out.append(t0 + (t1 - t0) * min(1, max(0, (d - a).days / (b - a).days)))
    return out


def blyzko(podii, c, m):
    return [p for p in podii if D.vidstan_m(c[1], c[0], p.lat, p.lon) <= m]


def tsentr(podii):
    return (sum(p.lon for p in podii) / len(podii), sum(p.lat for p in podii) / len(podii))


def lanka_vulytsi(podii, krok=0.004):
    """Лінія вулиці з її точок: упорядкувати вздовж головної осі й згладити (без зовнішніх даних)."""
    import numpy as np
    xy = np.array([[p.lon, p.lat * 1.0] for p in podii])
    med = np.median(xy, 0)
    dal = np.hypot((xy[:, 0] - med[0]) * 71_000, (xy[:, 1] - med[1]) * 111_000)
    xy = xy[dal < max(1500, np.percentile(dal, 90))]       # без хибних точок далеко від вулиці
    c = xy.mean(0)
    u, s, vt = np.linalg.svd((xy - c) * [math.cos(math.radians(c[1])), 1], full_matrices=False)
    os_ = vt[0]
    pr = ((xy - c) * [math.cos(math.radians(c[1])), 1]) @ os_
    poriadok = np.argsort(pr)
    xy, pr = xy[poriadok], pr[poriadok]
    kroky = np.arange(pr.min(), pr.max() + krok, krok)
    lin = []
    for k in kroky:
        m = np.abs(pr - k) < krok * 1.5
        if m.any():
            lin.append([round(float(xy[m, 0].mean()), 6), round(float(xy[m, 1].mean()), 6)])
    return lin


# ------------------------------------------------------------------ сценарії

class Baza:
    def __init__(self, a):
        self.V = D.Vypusk(a.baza)
        self.P = self.V.podii
        self.koloda = {}
        if a.koloda and Path(a.koloda).is_file():
            self.koloda = {x['id']: x for x in json.loads(Path(a.koloda).read_text(encoding='utf-8'))['podii']}

    def podiia(self, eid):
        for p in self.P:
            if p.id == eid:
                return p
        raise SystemExit(f'немає події {eid} у випуску')

    def fabula(self, kw):
        return [p for p in self.P if p.fabula and re.search(kw, p.fabula, re.I)]


def r_01(B: Baza):
    """Вау: усе місто — 71 тисяча справжніх подій «вискакують», місто стає 3D."""
    P = list(B.P)
    n = len(P)
    R = Rolyk('01-misto-vsi-podii', 22, tema='temna', nazva='Усе місто: кожна точка — справа з суду', hrupa='Місто згори',
              hachok='«Кожна точка — справжня подія з рішення суду»', meta='впізнаваність → карта', liniia='Безкоштовна карта',
              kudy='/karta/')
    R.muzyka('puls', drop=2.2, huchnist=1.0)
    R.kam(0, KYIV, 9.15, 0, 0).kam(2.2, KYIV, 9.55, 0, 0, e='o')
    R.kam(11.5, (30.515, 50.452), 11.0, 52, -28, e='io').kam(16.5, (30.53, 50.448), 12.2, 62, -70, e='io')
    R.kam(22, (30.53, 50.448), 12.4, 64, -84, e='l')
    rng = random.Random(4)
    P.sort(key=lambda p: (p.data or '9'))
    chasy = khronolohiia(P, 2.2, 10.5)
    chasy = [t + rng.uniform(0, 0.25) for t in chasy]
    R.tochky(P, chasy, rozmir=((0, 9), (8, 6), (13, 6), (22, 8)), yaskr=((0, 1), (13, 0.85)), glow=0.3, tryv=0.4)
    R.soty(P, 8, vysota=((12.4, 0), (14.6, 1, 'oo')), prozorist=((0, 0), (12.2, 0), (13.0, 1)), maks_vysota=2600, zalyvka=0.08)
    R.efekt(0.0, 'rizer', v=0.8)
    R.udar(2.2, 0.55, 18)
    R.zvuk_tochok(chasy, maks=14, h0=0.8, h1=1.9, v=0.45)
    R.tekst(0.15, 2.15, 'hook', 'Кожна точка —\n*справжня подія*\nз рішення суду', y='verkh', anim='slam')
    R.tekst(2.6, 10.8, 'lich', kluchi=[[2.2, 0], [10.6, n, 'io']], pidpys=f'{fp(n)} на карті Києва', y=1060)
    roky = [('2023', 2.3), ('2024', 4.2), ('2025', 7.0), ('2026', 9.4)]
    for i, (rik, t) in enumerate(roky):
        R.tekst(t, t + 1.5, 'mala', rik, y=460, anim='pop')
        R.efekt(t, 'tik', h=1.2)
    R.udar(12.4, 0.3, 10)
    R.efekt(12.4, 'bas')
    R.tekst(12.9, 17.6, 'velykyi', 'Вище стовпчик —\n*більше даних.*\nЦе не оцінка місця.', y='verkh', anim='vgoru')
    R.fin(17.8, 'Знайди свою вулицю', 'Карта подій Києва з рішень судів', PROFIL)
    return R


def r_09(B: Baza):
    """Вау: соти розпадаються на події, каскадом від центру."""
    import h3
    P = list(B.P)
    c = KYIV
    R = Rolyk('09-soty-rozpadaiutsia', 25, tema='temna', nazva='Соти розпадаються на події', hrupa='Місто згори',
              hachok='3D-місто → одна сота «вибухає» на сотні подій', meta='впізнаваність, «заворожує»', liniia='Безкоштовна карта',
              kudy='/karta/?z=15')
    R.muzyka('epik', drop=4.0)
    sh = R.soty(P, 8, vysota=((0, 0.2), (3.5, 1.0, 'o')), prozorist=((0, 1),), maks_vysota=2400, zalyvka=0.06)
    by = D.soty_z_podiiamy(P, 8)
    tsentr_k = h3.latlng_to_cell(c[1], c[0], 8)
    kiltsia = [tsentr_k] + [k for k in h3.grid_ring(tsentr_k, 1)] + [k for k in h3.grid_ring(tsentr_k, 2)] + [k for k in h3.grid_ring(tsentr_k, 3)]
    kiltsia = [k for k in kiltsia if k in by]
    rozpad, vybrani, chasy, org = [], [], [], []
    rng = random.Random(9)
    t_pershyi = 6.0
    for i, k in enumerate(kiltsia):
        tr = t_pershyi if i == 0 else 9.0 + h3.grid_distance(tsentr_k, k) * 1.6 + rng.uniform(0, 0.9)
        rozpad.append({'id': k, 't': round(tr, 2)})
        lat, lon = h3.cell_to_latlng(k)
        idx = by[k]
        for j, ii in enumerate(idx):
            vybrani.append(P[ii])
            org.append((lon, lat))
            chasy.append(tr + 0.08 + (j / max(1, len(idx))) ** 0.7 * (1.4 if i == 0 else 0.9))
        R.efekt(tr, 'udar' if i == 0 else 'bas', v=0.9 if i == 0 else 0.35, h=1 + rng.uniform(-0.1, 0.1))
        if i == 0:
            R.S['spalakh'].append({'t': tr, 'sila': 0.5}); R.S['trus'].append({'t': tr, 'sila': 20})
    sh['rozpad'] = rozpad
    R.tochky(vybrani, chasy, org=org, rozmir=((0, 16), (12, 13), (25, 11)), yaskr=((0, 1),), glow=0.45, tryv=0.7)
    R.zvuk_tochok([t for t, o in zip(chasy, org) if o == org[0]], maks=16, typ='pop', h0=0.9, h1=1.8, v=0.5)
    R.zvuk_tochok([t for t, o in zip(chasy, org) if o != org[0]], maks=9, typ='klik', h0=0.9, h1=1.4, v=0.35, seed=3)
    # мітки виду над першими подіями з першої соти
    persha = [(p, t) for p, t, o in zip(vybrani, chasy, org) if o == org[0]]
    for p, t in persha[::max(1, len(persha) // 9)][:9]:
        R.mitka(t + 0.3, t + 1.7, (p.lon, p.lat), p.mitka, kolir=D.HRUPY[p.vyd][1])
    n0 = len(persha)
    R.kam(0, (30.50, 50.425), 11.4, 55, 20).kam(5.6, (c[0], c[1] - 0.006), 12.95, 60, -20, e='io')
    R.kam(10, (c[0], c[1] - 0.004), 13.2, 62, -55, e='io').kam(19, c, 12.5, 64, -150, e='io').kam(25, c, 12.2, 62, -175, e='l')
    R.efekt(3.0, 'rizer', v=0.7)
    R.tekst(0.2, 3.6, 'hook', 'Що всередині\n*однієї соти?*', y='verkh')
    R.tekst(6.4, 9.6, 'lich', kluchi=[[6.0, 0], [7.6, n0, 'o']], pidpys=f'{fp(n0)} в одній соті\nпоруч із Майданом', y='verkh')
    R.tekst(12.0, 17.6, 'velykyi', 'А тепер —\n*сусідні.*', y='verkh', anim='slam')
    R.fin(19.8, 'Розбери свою соту', 'Наблизь карту — соти розкриваються на події', PROFIL)
    return R


HODYNY_O = ['нульовій', 'першій', 'другій', 'третій', 'четвертій', "п'ятій", 'шостій', 'сьомій', 'восьмій', "дев'ятій",
            'десятій', 'одинадцятій', 'дванадцятій', 'тринадцятій', 'чотирнадцятій', "п'ятнадцятій", 'шістнадцятій',
            'сімнадцятій', 'вісімнадцятій', "дев'ятнадцятій", 'двадцятій', 'двадцять першій', 'двадцять другій', 'двадцять третій']


def fp(n):
    """Узгодити «подія» з числом: 1 подія, 3 події, 703 події, 71 428 подій."""
    return D.vidminok(n, ('подія', 'події', 'подій'))


def hrupa_kol(vyd):
    return D.HRUPY.get(vyd, ('', '#66E6BA'))[1]


def r_02(B: Baza):
    """Обірвана історія, 7 с: гачок → наближення → обрив."""
    pr = [p for p in B.V.problemy() if (p['masshtab'] or {}).get('name', '').startswith('Глобус')][0]
    pod = B.V.podii_problemy(pr['id'])
    c = (pr['lon'], pr['lat'])
    R = Rolyk('02-obryv-tts', 7, tema='temna', nazva='Обрив: «64 події біля одного ТЦ»', hrupa='Історії «під боком»',
              hachok=f'«{len(pod)} {fp(len(pod))} біля одного ТЦ у центрі. Майже всі — про одне»', meta='загадка → друга частина (ролик 03)',
              liniia='Мій район', kudy='ролик 03 → /mistse/globus/', obryv=True)
    R.muzyka('napruha', stop=6.05)
    R.kam(0, KYIV, 11.2, 20, 0).kam(3.4, (c[0], c[1] - 0.0012), 16.2, 58, -35, e='io').kam(6.05, (c[0], c[1] - 0.0008), 16.6, 62, -48, e='l')
    rng = random.Random(2)
    chasy = sorted(2.2 + 3.4 * ((i + 1) / len(pod)) ** 0.5 + rng.uniform(0, 0.08) for i in range(len(pod)))
    R.tochky(pod, chasy, rozmir=((0, 22),), glow=0.5, te=[6.05] * len(pod))
    R.zvuk_tochok(chasy, maks=14, h0=1.0, h1=2.0, v=0.55)
    R.efekt(0, 'vzhukh', v=0.8)
    R.tekst(0.1, 3.0, 'hook', f'*{len(pod)} події*\nбіля одного ТЦ\nу центрі Києва', y='verkh')
    R.tekst(3.1, 6.0, 'velykyi', 'Майже всі —\n*про одне й те саме.*', y='verkh', anim='slam')
    R.S['spalakh'].append({'t': 6.05, 'sila': 0})
    R.tekst(6.1, 7.2, 'velykyi', 'Що саме?\n*Частина 2 →*', y='tsentr', c=True, anim='pop', vkhid=0.05)
    R.S['zatemnennia'] = 1
    R.S['tekst'][-1]['styl'] = 'pytannia'
    R.ui(6.05, 7.5, 'zavisa', vkhid=0.01)   # чорна завіса — обрив
    R.efekt(6.05, 'hlych', v=0.8)
    return R


def r_03(B: Baza):
    """Частина 2: відповідь — ТЦ «Глобус», що саме в даних."""
    pr = [p for p in B.V.problemy() if (p['masshtab'] or {}).get('name', '').startswith('Глобус')][0]
    pod = B.V.podii_problemy(pr['id'])
    c = (pr['lon'], pr['lat'])
    vydy = Counter(p.mitka for p in pod).most_common(3)
    R = Rolyk('03-vidpovid-globus', 13, tema='temna', nazva='Частина 2: що саме біля ТЦ', hrupa='Історії «під боком»',
              hachok='«Частина 2. Відповідь»', meta='дочитування серії → сторінка місця', liniia='Мій район',
              kudy='/mistse/globus/', publichni=['Глобус'])
    R.muzyka('napruha', bpm=104)
    R.kam(0, (c[0], c[1] - 0.0008), 16.6, 62, -48).kam(13, (c[0] + 0.0004, c[1] - 0.0004), 16.9, 64, -120, e='l')
    chasy = sorted(0.9 + 3.2 * ((i + 1) / len(pod)) ** 0.6 for i in range(len(pod)))
    R.tochky(pod, chasy, rozmir=((0, 22),), glow=0.5)
    R.zvuk_tochok(chasy, maks=12, h0=1.0, h1=1.7, v=0.5)
    R.tekst(0.05, 2.6, 'hook', 'Частина 2.\n*ТЦ «Глобус»*\nна Майдані', y='verkh', anim='slam')
    R.mitka(1.0, 12.5, c, 'ТЦ «Глобус»', styl='velyka')
    R.tekst(2.8, 8.0, 'stovpchyky', riady=[{'tekst': v, 'n': n, 'kolir': '#F2C46D' if i == 0 else '#9C9DF0'} for i, (v, n) in enumerate(vydy)], y=1100)
    R.tekst(2.8, 8.0, 'velykyi', f'{len(pod)} {fp(len(pod))} у даних —\nмайже всі *про це:*', y='verkh', anim='vgoru')
    R.efekt(2.8, 'svish')
    R.tekst(8.2, 10.6, 'velykyi', 'Однотипне повторюється\nв одному місці —\n*карта це показує.*', y='verkh', anim='vgoru')
    R.holos(2.9, f'{len(pod)} {fp(len(pod))}. {vydy[0][1]} — {vydy[0][0]}, {vydy[1][1]} — {vydy[1][0]}.', 'mykyta')
    R.fin(10.7, 'Сторінка місця', 'Усі події біля ТЦ — з посиланнями на рішення', PROFIL)
    return R


def r_04(B: Baza):
    """Гра «Вгадай, де це було»: 23 сосни без бирок, грудень (до свят — актуально)."""
    p = B.podiia('124940125-1')
    ray = B.V.rayon(p) or 'Дарницький'
    c = (p.lon, p.lat)
    R = Rolyk('04-vgadai-yalynky', 20, tema='svitla', nazva='Вгадай, де це було: 23 сосни', hrupa='Ігри',
              hachok='«Вгадай район: 23 сосни без бирок»', meta='гра → «Де це було?» щодня', liniia='Гра', kudy='/hra/')
    R.muzyka('hra')
    R.kam(0, KYIV, 10.0, 0, 0).kam(10.0, KYIV, 10.2, 10, 5, e='l').kam(13.0, (c[0], c[1] - 0.002), 15.3, 55, -25, e='io', luk=0.9)
    R.kam(20, (c[0], c[1] - 0.0015), 15.6, 60, -60, e='l')
    R.tochky([p], [12.4], rozmir=((0, 64),), glow=0.6)
    R.tekst(0.1, 2.4, 'hook', 'Вгадай,\n*де це було*', y='verkh', anim='pop')
    R.efekt(0.1, 'svish')
    R.tekst(2.2, 9.4, 'kartka', 'Грудень, 14:00. Чоловік продавав з рук 23 новорічні сосни — без бирок обліку деревини. Дійшло до суду.',
            zag='Що сталося', dz=f'Рішення суду № {p.nomer_rishennia}', y=380, shvydkist=42)
    R.S['tekst'][-1]['t1'] = 7.0
    for i in range(0, 105, 3):
        R.efekt(2.5 + i / 42, 'druk', h=1 + (i % 5) * 0.03, v=0.35)
    variant = [('А', 'Оболонський'), ('Б', ray), ('В', 'Святошинський')]
    for i, (b, v) in enumerate(variant):
        R.tekst(5.4 + i * 0.25, 12.4, 'variant', v, bukva=b, y=1040 + i * 130, pravylno=(v == ray), vidpovid=10.0)
        R.efekt(5.4 + i * 0.25, 'pop', h=1.2 + i * 0.15, v=0.5)
    R.tekst(7.0, 10.0, 'vidlik', y=420)
    for t in (7.0, 8.0, 9.0):
        R.efekt(t, 'tik', h=1.3)
    R.efekt(10.0, 'dzvin', h=1.2)
    R.udar(12.4, 0.25, 8)
    R.kiltse(12.5, c, '#4447A6', 300)
    R.mitka(12.6, 19.5, c, f'{D.vulytsia(p.adresa)} · {ray} район', styl='velyka')
    R.tekst(12.8, 16.4, 'velykyi', f'*{ray}* район.\nВи вгадали?', y='verkh', anim='slam')
    R.fin(16.5, 'Нова загадка — щодня', 'Гра «Де це було?» на справжніх рішеннях', PROFIL)
    return R


def r_05(B: Baza):
    """Один випадок: шлагбаум і вантажівка (серія «Дійшло до суду», №1)."""
    p = B.podiia('123214075-1')
    c = (p.lon, p.lat)
    vsi = B.fabula('шлагбаум')
    R = Rolyk('05-odyn-vypadok-shlahbaum', 17, tema='temna', nazva='«Дійшло до суду» №1: шлагбаум', hrupa='Історії «під боком»',
              hachok='«Стріла шлагбаума опустилася на вантажівку»', meta='історія → сторінка вулиці (серія)', liniia='Мій район',
              kudy='/vulytsia/tyraspolska/')
    R.muzyka('lofi')
    R.kam(0, (c[0], c[1] - 0.0016), 16.4, 64, 30).kam(11.6, (c[0] - 0.0003, c[1] - 0.0013), 16.8, 66, -30, e='l')
    R.kam(14.0, (30.50, 50.43), 10.7, 35, -10, e='io', luk=0.5).kam(17, (30.50, 50.43), 10.9, 40, -20, e='l')
    R.tochky([p], [0.6], rozmir=((0, 64),), glow=0.6)
    R.kiltse(0.6, c, '#66E6BA', 300)
    inshi = [x for x in vsi if x.id != p.id]
    chasy_v = khvylia(inshi, c, 12.0, 14.2)
    R.tochky(inshi, chasy_v, rozmir=((0, 14),), glow=0.5)
    R.zvuk_tochok(chasy_v, maks=14, h0=1.0, h1=1.9, v=0.45)
    R.efekt(0.6, 'pop', h=1.2)
    R.tekst(0.0, 2.6, 'hook', 'Шлагбаум\n*проти вантажівки*', y='verkh', anim='slam')
    R.efekt(0.05, 'udar', v=0.6)
    tekst = ('Серпень, 13:46. Людина, що чергувала на в\'їзді до житлового комплексу, не зупинила стрілу шлагбаума. '
             'Стріла опустилася — і пошкодила вантажівку.')
    R.tekst(2.8, 11.6, 'kartka', tekst, zag='Дійшло до суду · №1', dz=f'{D.vulytsia(p.adresa)} · рішення суду № {p.nomer_rishennia}',
            y=330, shvydkist=24)
    R.holos(3.0, tekst, 'mykyta', shvydkist=1.05)
    R.mitka(1.0, 11.6, c, D.vulytsia(p.adresa))
    R.tekst(11.8, 14.4, 'lich', vid=0, do=len(vsi), tryv=1.2, pidpys='подій у даних,\nде згадано шлагбаум', y=430)
    R.efekt(11.6, 'vzhukh', v=0.7)
    R.fin(14.5, f'Що ще на {D.vulytsia(p.adresa).replace("вул. ", "вулиці ")}?', 'Сторінка вулиці — усі події з рішень', PROFIL)
    return R


def r_06(B: Baza):
    """Детектив одного дня: 12.12.2024 — п'ять справ про рибу з рук."""
    ids = [('125121807-1', '11:15', 150), ('124734012-1', '11:52', None), ('124358531-1', '14:25', 125),
           ('124432185-1', '14:45', 107), ('124768825-1', '15:40', 75)]
    pod = [B.podiia(i) for i, _, _ in ids]
    R = Rolyk('06-rybnyi-chetver', 24, tema='temna', nazva='Рибний четвер: один день — п\'ять справ', hrupa='Історії з даних',
              hachok='«12 грудня 2024. Один день. П\'ять адрес. 457 кг риби»', meta='детектив → підписка «Мій район»',
              liniia='Мій район', kudy='/rayon/desnianskyi/')
    R.muzyka('hra', bpm=118)
    R.tekst(0.0, 3.0, 'hook', '12 грудня 2024.\n*Один день.*\nП\'ять адрес.', y='verkh')
    R.kam(0, (30.62, 50.45), 10.9, 30, 0)
    t = 3.2
    kg = 0
    kluchi = [[3.0, 0]]
    chasy = []
    for i, (p, (eid, chas, vaga)) in enumerate(zip(pod, ids)):
        c = (p.lon, p.lat)
        R.kam(t, (c[0], c[1] - 0.004), 14.2, 50, -15 + 12 * i, e='io')
        chasy.append(t + 0.1)
        R.kiltse(t + 0.1, c, '#B8E07A', 240)
        R.efekt(t + 0.1, 'pop', h=1.0 + 0.12 * i)
        R.efekt(t - 0.9, 'svish', v=0.6)
        R.mitka(t + 0.2, t + 3.0, c, f'{chas} · {vaga} кг' if vaga else f'{chas} · вагу не записано', styl='velyka')
        if vaga:
            kg += vaga
            kluchi += [[t + 0.2, kluchi[-1][1]], [t + 1.0, kg, 'oo']]
            R.efekt(t + 0.9, 'kasa', h=0.8 + 0.1 * i, v=0.45)
        t += 3.2
    R.tochky(pod, chasy, rozmir=((0, 56),), glow=0.6)
    R.tekst(3.2, 19.5, 'lich', kluchi=kluchi, pidpys='кг риби з рук — там,\nде вагу записано', y=1120)
    R.kam(19.5, (30.63, 50.45), 11.3, 35, 10, e='io')
    R.tekst(19.4, 21.0, 'velykyi', 'Усі п\'ять — про продаж\nриби *без документів.*', y='verkh', anim='vgoru')
    R.fin(21.0, 'Що продають з рук біля тебе?', 'Сторінка району — нове щомісяця', PROFIL, y=600)
    return R


def r_07(B: Baza):
    """Одна вулиця: Хрещатик — проліт уздовж, події «клікають» з підписами."""
    vs = B.V.po_vulytsi()
    imia = 'вул. Хрещатик'
    pod = vs[imia]
    serednie = round(sum(len(v) for v in vs.values()) / len(vs))
    lin = lanka_vulytsi(pod, 0.0015)
    R = Rolyk('07-vulytsia-khreshchatyk', 28, tema='temna', nazva='Одна вулиця: Хрещатик', hrupa='«Що болить вулиці»',
              hachok=f'«{len(pod)} {fp(len(pod))} на одній вулиці»', meta='сторінка вулиці → довідка', liniia='Мій будинок',
              kudy='/vulytsia/khreshchatyk/')
    R.muzyka('puls', drop=3.0)
    a, b = lin[0], lin[-1]
    R.kam(0, KYIV, 12.6, 30, -30).kam(3.0, (a[0], a[1]), 16.3, 58, -40, e='io')
    R.kam(15, (b[0], b[1]), 16.3, 60, -25, e='io').kam(19, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 0.003), 14.2, 58, 20, e='io')
    R.kam(28, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 - 0.003), 14.0, 55, 40, e='l')
    # події з'являються, коли камера пролітає повз (проєкція на лінію вулиці)
    import numpy as np
    vz = np.array([[x, y] for x, y in lin])
    def poz(p):
        d = ((vz[:, 0] - p.lon) ** 2 + (vz[:, 1] - p.lat) ** 2)
        return int(d.argmin()) / max(1, len(vz) - 1)
    rng = random.Random(7)
    chasy = [3.2 + 11.6 * poz(p) + rng.uniform(0, 0.6) for p in pod]
    R.tochky(pod, chasy, rozmir=((0, 17),), glow=0.45)
    R.liniia(lin, 2.8, 14.8, None, '#66E6BA', 8)
    R.zvuk_tochok(chasy, maks=9, h0=0.9, h1=1.5, v=0.45)
    R.udar(3.0, 0.3, 10)
    vybir = sorted(pod, key=lambda p: rng.random())[:14]
    for p in vybir:
        t = chasy[pod.index(p)]
        R.mitka(t + 0.2, t + 1.8, (p.lon, p.lat), p.mitka, kolir=hrupa_kol(p.vyd))
    R.tekst(0.1, 3.0, 'hook', f'*{D.chyslo(len(pod))} {fp(len(pod))}*\nна одній вулиці', y='verkh')
    R.tekst(3.2, 15.0, 'lich', kluchi=[[3.2, 0], [15.0, len(pod), 'l']], pidpys='Хрещатик у даних', y=1180)
    hr = Counter(p.vyd for p in pod).most_common(4)
    R.tekst(15.4, 22.6, 'stovpchyky', riady=[{'tekst': D.HRUPY[v][0], 'n': n, 'kolir': hrupa_kol(v)} for v, n in hr], y=1060)
    R.tekst(15.4, 22.6, 'velykyi', f'Тут — *{D.chyslo(len(pod))}*.\nУ середньому на вулиці\nКиєва — *{serednie}*.', y='verkh', anim='vgoru')
    R.holos(15.5, f'Тут — {len(pod)}. У середньому на вулиці Києва — {serednie}.', 'mykyta')
    R.efekt(15.4, 'svish')
    R.fin(23.0, 'Яка твоя вулиця?', 'Сторінка кожної вулиці — події з рішень судів', PROFIL)
    return R


def r_08(B: Baza):
    """Місто за добу: години біжать, події спалахують."""
    pod = [p for p in B.P if p.hodyna is not None]
    hod = Counter(p.hodyna for p in pod)
    pik, min_ = max(hod, key=hod.get), min(hod, key=hod.get)
    R = Rolyk('08-misto-za-dobu', 17, tema='temna', nazva='Київ за добу', hrupa='Місто згори',
              hachok='«О котрій Київ найчастіше потрапляє в рішення суду?»', meta='впізнаваність → карта', liniia='Безкоштовна карта',
              kudy='/karta/')
    R.muzyka('napruha', bpm=120)
    rng = random.Random(8)
    T0, KR = 2.4, 0.45
    chasy = [T0 + p.hodyna * KR + rng.uniform(0, KR) for p in pod]
    te = [t + 0.55 for t in chasy]
    R.tochky(pod, chasy, te=te, rozmir=((0, 6),), glow=0.4, tryv=0.2, kiltse=False)
    R.kam(0, KYIV, 10.4, 35, -10).kam(13.5, KYIV, 10.9, 45, 25, e='l').kam(17, KYIV, 11.2, 48, 32, e='l')
    R.tekst(0.0, 2.4, 'hook', 'О котрій Київ\nнайчастіше потрапляє\n*у рішення суду?*', y='verkh')
    R.tekst(T0, T0 + 24 * KR + 0.2, 'godynnyk', hodyny=[[T0, 0, 'l'], [T0 + 24 * KR, 24, 'l']], pidpys='година подій', y=1150)
    for h in range(24):
        R.efekt(T0 + h * KR, 'tik', h=0.9 + hod[h] / max(hod.values()) * 0.8, v=0.55)
    R.udar(T0 + pik * KR, 0.2, 8)
    R.tekst(T0 + 24 * KR + 0.2, 15.0, 'velykyi', f'Найбільше — *о {pik}:00*\n({D.chyslo(hod[pik])}).\nНайменше — *о {min_}:00*\n({D.chyslo(hod[min_])}).', y='verkh', anim='vgoru')
    R.efekt(T0 + 24 * KR + 0.2, 'svish')
    R.fin(15.0, 'А коли — на твоїй вулиці?', 'Карта подій — з годинами й роками', PROFIL)
    return R


def r_10(B: Baza):
    """«Заворожує»: нічний проліт, події запалюються, як зорі. Без голосу."""
    P = sorted(B.P, key=lambda p: p.data or '9')
    rng = random.Random(10)
    chasy = [t + rng.uniform(0, 0.4) for t in khronolohiia(P, 3.0, 28.0)]
    R = Rolyk('10-nich-zori', 35, tema='temna', nazva='Нічний Київ: події як зорі', hrupa='Місто згори',
              hachok='«Увімкни звук. Просто подивись»', meta='«заворожує», впізнаваність', liniia='Безкоштовна карта', kudy='/karta/')
    R.muzyka('nich')
    R.S['znak_prozorist'] = [[0, 0.5]]
    R.tochky(P, chasy, rozmir=((0, 7), (20, 6), (35, 7)), yaskr=((0, 0.55),), glow=0.6, aditiv=True, kiltse=False, tryv=1.2)
    R.kam(0, (30.50, 50.47), 13.2, 60, -20).kam(12, (30.53, 50.455), 12.6, 64, -60, e='io')
    R.kam(24, (30.58, 50.44), 12.0, 66, -110, e='io').kam(35, (30.55, 50.45), 11.2, 58, -150, e='io')
    for t in [c for c in chasy[::2400]]:
        R.efekt(t, 'dzvin', h=random.Random(int(t * 100)).choice([1, 1.122, 1.335, 1.498]), v=0.18)
    R.tekst(0.3, 3.4, 'velykyi', 'Увімкни звук.\n*Просто подивись.*', y='verkh', anim='vgoru', krok=0.12)
    R.tekst(28.4, 31.4, 'velykyi', f'*{D.chyslo(len(P))}* {fp(len(P))}.\nОдне місто.', y='verkh', anim='vgoru', krok=0.12)
    R.fin(31.6, 'Моя вулиця', 'Що відбувається під боком', PROFIL)
    return R


def r_11(B: Baza):
    """Як користуватися: пошук вулиці → проліт → картка з числами (продукт: сторінка вулиці)."""
    vs = B.V.po_vulytsi()
    imia = 'просп. Оболонський'
    pod = vs[imia]
    serednie = round(sum(len(v) for v in vs.values()) / len(vs))
    c = tsentr(pod)
    dtp = sum(1 for p in pod if p.vyd == 'ДТП')
    R = Rolyk('11-yak-znaity-vulytsiu', 18, tema='svitla', nazva='Як знайти свою вулицю', hrupa='Як це працює',
              hachok='«Введи вулицю — побач, що тут дійшло до суду»', meta='спосіб користування: пошук → сторінка вулиці',
              liniia='Мій будинок', kudy='/vulytsia/obolonskyi-prospekt/')
    R.muzyka('lofi', bpm=88)
    R.kam(0, KYIV, 10.6, 0, 0).kam(3.0, KYIV, 10.7, 0, 0).kam(6.4, (c[0], c[1] - 0.006), 14.2, 50, -20, e='io', luk=0.6)
    R.kam(18, (c[0], c[1] - 0.005), 14.5, 55, -35, e='l')
    R.ui(0.2, 5.6, 'poshuk', tekst='Оболонський проспект', druk=1.6, pidkazka='Адреса або вулиця')
    for i in range(0, 20, 2):
        R.efekt(0.55 + i * 0.08, 'druk', v=0.5)
    R.efekt(2.4, 'klik', h=0.8)
    rng = random.Random(11)
    chasy = sorted(6.0 + 2.6 * ((i + 1) / len(pod)) ** 0.5 + rng.uniform(0, 0.1) for i in range(len(pod)))
    R.tochky(pod, chasy, rozmir=((0, 15),), glow=0.3)
    R.zvuk_tochok(chasy, maks=10, h0=1.0, h1=1.6, v=0.4)
    R.ui(9.0, 18.5, 'panel', zag='Оболонський проспект', pid='Події з рішень судів · 2023–2026',
         chysla=[[len(pod), 'подій тут'], [serednie, 'у середньому на вулиці'], [dtp, 'з них ДТП']], knopka='Відкрити сторінку вулиці')
    R.efekt(9.0, 'svish')
    R.holos(0.4, 'Введи свою вулицю.', 'tetiana')
    R.holos(9.4, f'Тут — {len(pod)} {fp(len(pod))}. У середньому на вулиці Києва — {serednie}.', 'tetiana')
    R.meta['kintsivka'] = 'Відкрити сторінку вулиці'
    R.tekst(14.6, 18.5, 'velykyi', 'Твоя вулиця —\n*за 10 секунд.*', y=420, anim='pop')
    return R


def r_12(B: Baza):
    """Підписка: сповіщення «нова подія на вашій вулиці»."""
    vs = B.V.po_vulytsi()
    imia = 'вул. Антоновича'
    pod = sorted([p for p in vs[imia] if p.data], key=lambda p: p.data)
    ost = pod[-1]
    c = (ost.lon, ost.lat)
    R = Rolyk('12-stezhu-za-vulytseiu', 14, tema='temna', nazva='Стеж за своєю вулицею (підписка)', hrupa='Як це працює',
              hachok='«Нова подія на вашій вулиці»', meta='підписка 399 грн/міс', liniia='Мій район', kudy='/pidpyska/')
    R.muzyka('lofi', bpm=84)
    R.kam(0, (c[0], c[1] - 0.006), 13.6, 45, 0).kam(3.0, (c[0], c[1] - 0.006), 13.6, 45, 0)
    R.kam(6.0, (c[0], c[1] - 0.0012), 16.2, 62, -30, e='io').kam(14, (c[0], c[1] - 0.001), 16.4, 64, -60, e='l')
    R.tochky(pod[:-1], [0.2] * (len(pod) - 1), rozmir=((0, 7),), yaskr=((0, 0.45),), glow=0.2, kiltse=False)
    R.tochky([ost], [5.6], rozmir=((0, 64),), glow=0.6)
    R.ui(1.0, 5.4, 'spov', zag='Лист «Нове біля дому»', tekst=f'{imia} · {ost.mitka}', koly='раз на місяць')   # ZAVDANNYA-150: лист, не миттєве сповіщення
    R.efekt(1.0, 'spov')
    R.kiltse(5.6, c, '#66E6BA', 320)
    R.efekt(5.6, 'pop', h=1.2)
    R.mitka(5.8, 13, c, f'{ost.mitka} · {ost.data[8:10]}.{ost.data[5:7]}.{ost.data[:4]}', kolir=hrupa_kol(ost.vyd))
    R.tekst(6.2, 10.0, 'velykyi', 'Стеж за своєю вулицею.\n*Нове — щомісяця.*', y='verkh', anim='vgoru')
    R.holos(6.3, 'Стеж за своєю вулицею. Нове — щомісяця.', 'tetiana')
    R.fin(10.2, 'Підписка «Моя вулиця»', '399 грн на місяць · одна довідка про будинок — включена', PROFIL)
    return R


def r_13(B: Baza):
    """Продукт: довідка про будинок за 199 грн (Мій будинок)."""
    R = Rolyk('13-dovidka-199', 19, tema='svitla', nazva='Що болить будинку: довідка 199 грн', hrupa='«Що болить вулиці»',
              hachok='«Орендуєш квартиру? Спершу подивись, що болить будинку»', meta='довідка 199 грн', liniia='Мій будинок',
              kudy='/mii-budynok/')
    R.muzyka('lofi', bpm=92)
    P = [p for p in B.P if D.vidstan_m(50.4501, 30.5234, p.lat, p.lon) < 9000]
    R.tochky(P, [0] * len(P), rozmir=((0, 6),), yaskr=((0, 0.5),), glow=0.15, kiltse=False)
    R.kam(0, (30.50, 50.44), 12.8, 50, -20).kam(19, (30.52, 50.445), 13.4, 58, -60, e='l')
    R.tekst(0.0, 3.4, 'hook', 'Орендуєш\nквартиру?', y='verkh')
    R.tekst(1.5, 3.4, 'velykyi', 'Спершу подивись,\n*що болить будинку.*', y=640, anim='vgoru')
    R.efekt(0.0, 'udar', v=0.5)
    R.ui(3.6, 14.6, 'dokument', zag='Довідка про будинок', pid='Події з рішень судів і скарги мешканців · поруч і в порівнянні',
         tsina='199 грн', krok=0.9, sektsii=[
             {'zag': 'Події поруч за 3 роки', 'bary': [[180, '#6066C1'], [120, '#66E6BA'], [60, '#F2C46D']]},
             {'zag': 'Скарги мешканців (1551)', 'bary': [[220, '#9C9DF0'], [90, '#6CC9F2']]},
             {'zag': 'Тут · у сусідніх будинках', 'bary': [[150, '#4447A6'], [170, '#B5B7C4']]},
             {'zag': 'Посилання на кожне рішення'}])
    for i in range(4):
        R.efekt(4.2 + i * 0.9, 'pop', h=1.0 + i * 0.12, v=0.5)
    R.efekt(3.6, 'vzhukh')
    R.holos(3.9, 'Події з рішень судів і скарги мешканців — по кожному будинку. І порівняння із сусідами.', 'tetiana')
    R.fin(14.8, 'Що болить вашому будинку', 'Знайди свій будинок — довідка за 199 грн', PROFIL)
    return R


def r_14(B: Baza):
    """Рієлтор: відповідь клієнту за хвилину."""
    vs = B.V.po_vulytsi()
    imia = 'вул. Зодчих'
    pod = vs[imia]
    c = tsentr(pod)
    hr = Counter(p.vyd for p in pod).most_common(2)
    R = Rolyk('14-rieltor', 12, tema='temna', nazva='Рієлтору: «А що тут за будинок?»', hrupa='Як це працює',
              hachok='«Клієнт питає: а що тут за будинок?»', meta='підписка рієлтора 799 грн/міс', liniia='Рієлтор',
              kudy='/rieltor/')
    R.muzyka('puls', bpm=126, drop=2.6)
    R.kam(0, (c[0], c[1] - 0.006), 13.8, 50, 10).kam(12, (c[0], c[1] - 0.005), 14.3, 58, -30, e='l')
    rng = random.Random(14)
    chasy = sorted(2.8 + 2.0 * ((i + 1) / len(pod)) ** 0.5 + rng.uniform(0, 0.05) for i in range(len(pod)))
    R.tochky(pod, chasy, rozmir=((0, 15),), glow=0.4)
    R.zvuk_tochok(chasy, maks=12, h0=1.0, h1=1.8, v=0.4)
    R.tekst(0.0, 2.6, 'hook', 'Клієнт питає:\n*«А що тут\nза будинок?»*', y='verkh')
    R.udar(2.6, 0.3, 10)
    R.ui(5.0, 9.4, 'panel', zag=imia, pid='Відповідь за хвилину · події з рішень судів',
         chysla=[[len(pod), f'{fp(len(pod))} на вулиці'], [hr[0][1], D.HRUPY[hr[0][0]][0]], [hr[1][1], D.HRUPY[hr[1][0]][0]]])
    R.efekt(5.0, 'svish')
    R.tekst(2.8, 4.9, 'velykyi', 'Відповідь —\n*за хвилину.*', y='verkh', anim='slam')
    R.fin(9.5, 'Для рієлторів', '799 грн/міс · 5 довідок про будинки', PROFIL)
    return R


def r_15(B: Baza):
    """ОСББ: щомісячний звіт будинку (макет)."""
    R = Rolyk('15-osbb', 14, tema='svitla', nazva='ОСББ: що болить будинку щомісяця', hrupa='Як це працює',
              hachok='«Що болить вашому будинку — щомісяця»', meta='ОСББ 1 490 грн/рік', liniia='ОСББ', kudy='/osbb/')
    R.muzyka('hra', bpm=110)
    P = [p for p in B.P if D.vidstan_m(50.40, 30.62, p.lat, p.lon) < 6000]
    R.tochky(P, [0] * len(P), rozmir=((0, 6),), yaskr=((0, 0.5),), glow=0.15, kiltse=False)
    R.kam(0, (30.62, 50.40), 13.0, 50, 0).kam(14, (30.62, 50.40), 13.5, 55, -40, e='l')
    R.tekst(0.0, 2.8, 'hook', 'Голова ОСББ?', y='verkh', anim='pop')
    R.tekst(1.0, 2.8, 'velykyi', 'Що болить вашому будинку —\n*щомісяця.*', y=520, anim='vgoru')
    R.ui(3.0, 10.4, 'dokument', zag='Будинок · жовтень', pid='Скарги мешканців і події поруч — у порівнянні із сусідами',
         tsina='1 490 грн/рік', krok=0.7, sektsii=[
             {'zag': 'Скарги цього місяця', 'bary': [[120, '#4447A6'], [200, '#B5B7C4']]},
             {'zag': 'Події поруч', 'bary': [[90, '#66E6BA'], [140, '#B5B7C4']]},
             {'zag': 'Що змінилося з минулого місяця'}])
    for i in range(3):
        R.efekt(3.6 + i * 0.7, 'pop', h=1.1 + i * 0.1, v=0.5)
    R.holos(3.3, 'Скарги мешканців і події поруч. Щомісяця, у порівнянні із сусідами.', 'mykyta')
    R.fin(10.6, 'Для ОСББ', 'Звіт будинку щомісяця · 1 490 грн на рік', PROFIL)
    return R


def r_16(B: Baza):
    """Судова практика: ст. 130 — скільки й коли (без порад «як уникнути»)."""
    pod = [p for p in B.P if re.search(r'ст\.130\b', p.stattia)]
    DNI = ['Нд', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб']
    from datetime import date
    dni = Counter(date.fromisoformat(p.data).isoweekday() % 7 for p in pod if p.data)
    poriadok = [1, 2, 3, 4, 5, 6, 0]
    pik = max(dni, key=dni.get)
    R = Rolyk('16-st130-sudova-praktyka', 22, tema='temna', nazva='Ст. 130: скільки й коли (Судова практика)',
              hrupa='«Що буває за…»', hachok=f'«{D.chyslo(len(pod))} {fp(len(pod))} про п\'яне керування»',
              meta='Судова практика → довідка 199 / юристу 490', liniia='Судова практика', kudy='/sudova-praktyka/kupap/130/')
    R.muzyka('napruha', bpm=96)
    rng = random.Random(16)
    chasy = [2.6 + 6.0 * ((i + 1) / len(pod)) ** 0.55 + rng.uniform(0, 0.1) for i in range(len(pod))]
    R.tochky(pod, chasy, rozmir=((0, 6),), yaskr=((0, 0.85),), glow=0.3, tryv=0.4)
    R.zvuk_tochok(chasy, maks=12, h0=0.8, h1=1.6, v=0.4)
    R.kam(0, KYIV, 10.0, 0, 0).kam(9.0, KYIV, 10.6, 45, -25, e='io').kam(22, KYIV, 10.9, 52, -50, e='l')
    R.tekst(0.0, 2.6, 'hook', 'Стаття 130.\n*П\'яний за кермом.*', y='verkh')
    R.udar(2.6, 0.3, 10)
    R.tekst(2.8, 9.0, 'lich', kluchi=[[2.6, 0], [8.6, len(pod), 'io']], pidpys=f'{fp(len(pod))} у даних по Києву', y=1120)
    R.tekst(9.2, 16.0, 'stovpchyky', riady=[{'tekst': DNI[d], 'n': dni[d], 'kolir': '#9C9DF0' if d != pik else '#66E6BA'} for d in poriadok], y=820)
    R.tekst(9.2, 16.0, 'velykyi', f'Найчастіше —\n*{["у неділю","у понеділок","у вівторок","у середу","у четвер","у п\'ятницю","у суботу"][pik]}.*', y='verkh', anim='vgoru')
    R.efekt(9.2, 'svish')
    R.holos(9.4, f'Найчастіше такі події стаються {["у неділю","у понеділок","у вівторок","у середу","у четвер","у п\'ятницю","у суботу"][pik]}.', 'mykyta')
    R.tekst(16.2, 18.4, 'velykyi', 'А як суди Києва\n*вирішують такі справи?*', y='verkh', anim='vgoru')
    R.fin(18.5, 'Судова практика', 'Як суди Києва вирішують справи за вашою статтею', PROFIL)
    return R


def r_17(B: Baza):
    """Telegram району: Оболонський — ролик веде в канал."""
    ray = 'Оболонський'
    pod = [p for p in B.P if abs(p.lat - 50.51) < 0.08 and abs(p.lon - 30.49) < 0.1 and B.V.rayon(p) == ray]
    hr = Counter(p.vyd for p in pod).most_common(1)[0]
    z_datoiu = sorted([p for p in pod if p.data], key=lambda p: p.data)
    ost = z_datoiu[-1]
    mezha = json.loads((KORIN / 'data' / 'borders.json').read_text(encoding='utf-8'))[ray]
    if mezha and isinstance(mezha[0][0], (int, float)):
        mezha = [mezha]
    kontur = max(mezha, key=len)
    c = tsentr(pod)
    R = Rolyk('17-telegram-obolon', 16, tema='temna', nazva='Канал району: Оболонь', hrupa='Історії «під боком»',
              hachok='«Оболонь — у твоєму Telegram»', meta='Telegram району → підписка', liniia='Мій район',
              kudy='/telegram/obolonskyi/')
    R.muzyka('hra', bpm=112)
    R.kam(0, KYIV, 10.4, 0, 0).kam(3.0, (c[0], c[1] - 0.02), 11.8, 45, -10, e='io').kam(16, (c[0], c[1] - 0.02), 12.1, 50, -35, e='l')
    R.liniia([[x[1], x[0]] for x in kontur[::3]] + [[kontur[0][1], kontur[0][0]]], 0.8, 3.4, None, '#B37BFF', 6)
    rng = random.Random(17)
    chasy = sorted(2.0 + 3.0 * ((i + 1) / len(pod)) ** 0.5 + rng.uniform(0, 0.1) for i in range(len(pod)))
    R.tochky(pod, chasy, rozmir=((0, 7),), glow=0.3)
    R.zvuk_tochok(chasy, maks=10, h0=1.0, h1=1.6, v=0.4)
    R.tekst(0.0, 3.0, 'hook', 'Живеш\n*на Оболоні?*', y='verkh', anim='pop')
    R.ui(5.4, 12.6, 'kanal', zag='Моя вулиця · Оболонь', pid='канал району', krok=1.4, dopysy=[
        [f'Оболонський район у даних: {D.chyslo(len(pod))} {fp(len(pod))} з рішень судів', 'пн'],
        [f'Найчастіше — {D.HRUPY[hr[0]][0]}: {D.chyslo(hr[1])}', 'ср'],
        [f'Нове в даних: {D.vulytsia(ost.adresa)} — {ost.mitka}', 'пт']])
    for i in range(3):
        R.efekt(5.9 + i * 1.4, 'spov', h=1 + i * 0.06, v=0.5)
    R.fin(12.8, 'Канал твого району', 'Одна історія з даних щодня', PROFIL)
    return R


def r_18(B: Baza):
    """Актуальне: самокати — серія «Дійшло до суду», №2."""
    p = B.podiia('130939371-1')
    c = (p.lon, p.lat)
    vsi = sorted([x for x in B.fabula('самокат') if x.data], key=lambda x: x.data)
    rng = random.Random(18)
    R = Rolyk('18-samokat-1-68', 18, tema='temna', nazva='«Дійшло до суду» №2: самокат, 1,68 проміле', hrupa='Історії з даних',
              hachok='«Самокат. 00:46. 1,68 проміле»', meta='серія → сторінка вулиці', liniia='Мій район',
              kudy='/vulytsia/petra-sahaidachnoho/')
    R.muzyka('puls', bpm=124, drop=2.4)
    R.kam(0, (c[0], c[1] - 0.0015), 16.2, 62, 20).kam(9.0, (c[0], c[1] - 0.0012), 16.6, 64, -25, e='l')
    R.kam(12.0, KYIV, 11.0, 40, -10, e='io', luk=0.4).kam(18, KYIV, 11.2, 45, -25, e='l')
    R.tochky([p], [0.5], rozmir=((0, 64), (10, 20)), glow=0.6)
    chasy = khronolohiia(vsi, 11.0, 14.6, '2023-01-01', '2026-11-01')
    R.tochky(vsi, chasy, rozmir=((0, 10),), glow=0.5)
    R.zvuk_tochok(chasy, maks=12, h0=1.0, h1=1.8, v=0.4)
    R.tekst(0.0, 2.4, 'hook', 'Самокат.\n00:46.\n*1,68 проміле.*', y='verkh')
    R.udar(2.4, 0.3, 12)
    tekst = 'Серпень, 00:46, Поділ. Водій електросамоката їхав напідпитку: прилад показав 1,68 проміле.'
    R.tekst(2.6, 10.6, 'kartka', tekst, zag='Дійшло до суду · №2', dz=f'{D.vulytsia(p.adresa)} · рішення суду № {p.nomer_rishennia}', y=330, shvydkist=26)
    R.holos(2.8, tekst.replace('00:46', 'нуль нуль сорок шість').replace('1,68', 'одна ціла шістдесят вісім сотих'), 'tetiana')
    R.tekst(11.2, 15.2, 'lich', kluchi=[[11.0, 0], [14.6, len(vsi), 'io']], pidpys='подій у даних,\nде згадано самокат', y=380)
    R.fin(15.3, 'Сезон самокатів', 'Що на твоїй вулиці — сторінка вулиці', PROFIL)
    return R


def r_19(B: Baza):
    """POV-мем, 9 с."""
    vs = B.V.po_vulytsi()
    pod = vs['просп. Оболонський']
    c = tsentr(pod)
    R = Rolyk('19-pov-karta-vulytsi', 9, tema='temna', nazva='POV: вперше відкрив карту своєї вулиці', hrupa='Місто згори',
              hachok='«POV: ти вперше відкрив карту своєї вулиці»', meta='гумор, впізнаваність → карта', liniia='Безкоштовна карта',
              kudy='/karta/')
    R.muzyka('puls', bpm=128, drop=3.0)
    R.kam(0, KYIV, 10.8, 0, 0).kam(3.0, (c[0], c[1] - 0.006), 14.3, 60, -30, e='i').kam(9, (c[0], c[1] - 0.005), 14.6, 62, -60, e='l')
    rng = random.Random(19)
    chasy = sorted(3.0 + 2.2 * ((i + 1) / len(pod)) ** 0.4 + rng.uniform(0, 0.05) for i in range(len(pod)))
    R.tochky(pod, chasy, rozmir=((0, 17),), glow=0.5)
    R.zvuk_tochok(chasy, maks=16, h0=1.0, h1=2.2, v=0.45)
    R.tekst(0.0, 3.0, 'velykyi', 'POV: ти вперше\nвідкрив карту\n*своєї вулиці*', y='verkh', anim='vgoru')
    R.efekt(0.0, 'rizer', d=3.0)
    R.udar(3.0, 0.5, 20)
    R.tekst(5.6, 7.6, 'hook', '…і завис\n*на годину.*', y='verkh', anim='slam')
    R.fin(7.6, 'Твоя вулиця', '', PROFIL)
    return R


def r_20(B: Baza):
    """Як це працює: звідки точки (рішення → подія → адреса → точка)."""
    p = B.podiia('116084498-1')
    c = (p.lon, p.lat)
    R = Rolyk('20-zvidky-tochky', 24, tema='svitla', nazva='Звідки ці точки', hrupa='Як це працює',
              hachok='«Звідки ці точки?»', meta='довіра → усі лінії', liniia='усі', kudy='/pro-dani/')
    R.muzyka('lofi', bpm=86)
    R.kam(0, (c[0], c[1] - 0.004), 14.2, 40, 0).kam(9.0, (c[0], c[1] - 0.004), 14.2, 40, 0).kam(13, (c[0], c[1] - 0.0012), 16.0, 60, -30, e='io')
    R.kam(24, (c[0], c[1] - 0.001), 16.2, 62, -60, e='l')
    R.tekst(0.0, 2.4, 'hook', 'Звідки\n*ці точки?*', y='verkh', anim='pop')
    R.ui(2.4, 9.6, 'dokument', zag='Рішення суду', pid='Відкритий реєстр судових рішень (ЄДРСР)', tsina='', krok=1.2,
         sektsii=[{'zag': '1. Що сталося'}, {'zag': '2. Де: адреса з рішення'}, {'zag': '3. Суд підтвердив'}, {'zag': '4. Посилання на оригінал'}])
    for i in range(4):
        R.efekt(3.0 + i * 1.2, 'pop', h=1 + 0.1 * i, v=0.5)
    R.holos(2.6, 'Кожна точка — подія з рішення суду. Беремо, що сталося, і адресу. Лише те, що суд підтвердив.', 'mykyta')
    R.tochky([p], [10.4], rozmir=((0, 64),), glow=0.5)
    R.kiltse(10.4, c, '#4447A6', 300)
    R.efekt(10.4, 'pop', h=1.3)
    R.mitka(10.6, 23, c, D.vulytsia(p.adresa) + ' · ДТП', kolir=hrupa_kol('ДТП'))
    R.tekst(11.0, 15.4, 'velykyi', 'Лише те,\n*що дійшло до суду.*', y='verkh', anim='vgoru')
    R.tekst(15.6, 19.8, 'velykyi', 'Колір — кількість даних.\n*Не оцінка місця.*', y='verkh', anim='vgoru')
    R.holos(15.8, 'Колір на карті — це кількість даних, а не оцінка місця.', 'mykyta')
    R.fin(20.0, 'Під кожною подією —', 'посилання на рішення суду', PROFIL)
    return R


def r_21(B: Baza):
    """Переліт: Україна → Київ → вулиця → «Що болить вашому будинку»."""
    vs = B.V.po_vulytsi()
    pod = vs['бульв. Лесі Українки']
    c = tsentr(pod)
    R = Rolyk('21-perelit-ukraina-budynok', 12, tema='temna', nazva='Переліт: від країни до будинку', hrupa='Місто згори',
              hachok='«Від країни — до твого будинку»', meta='Мій будинок → сторінка будинку', liniia='Мій будинок',
              kudy='/mii-budynok/', za_mezhamy=True)
    R.muzyka('epik', drop=5.2)
    R.kam(0, (31.2, 48.9), 5.2, 0, 0).kam(2.6, (30.6, 50.3), 7.6, 10, 0, e='io').kam(5.2, KYIV, 11.0, 35, -15, e='io')
    R.kam(8.4, (c[0], c[1] - 0.002), 15.6, 64, -40, e='io').kam(12, (c[0], c[1] - 0.0018), 15.9, 66, -60, e='l')
    R.efekt(0.0, 'rizer', d=5.2)
    rng = random.Random(21)
    P = blyzko(B.P, c, 6000)
    chasy = khvylia(P, c, 5.2, 8.2)
    R.tochky(P, chasy, rozmir=((0, 6), (8, 10)), glow=0.35, kiltse=False)
    R.udar(5.2, 0.45, 16)
    R.zvuk_tochok(chasy, maks=10, h0=1.0, h1=1.7, v=0.35)
    R.tekst(0.0, 2.6, 'velykyi', 'Від країни —', y='verkh', anim='slam')
    R.tekst(2.6, 5.1, 'velykyi', '…до міста —', y='verkh', anim='slam')
    R.tekst(5.3, 8.6, 'hook', '…до твого\n*будинку.*', y='verkh', anim='slam')
    R.fin(8.7, 'Що болить вашому будинку', 'Скарги мешканців і події з рішень судів', PROFIL)
    return R


def r_22(B: Baza):
    """Довгий, 60 с: Київ за хвилину — місто, доба, вулиця, випадок, 3D."""
    P = sorted(B.P, key=lambda p: p.data or '9')
    n = len(P)
    rng = random.Random(22)
    vs = B.V.po_vulytsi()
    vul = vs['вул. Велика Васильківська']
    lin = lanka_vulytsi(vul, 0.0015)
    p1 = B.podiia('128903549-1')
    hod = Counter(p.hodyna for p in P if p.hodyna is not None)
    pik = max(hod, key=hod.get)
    R = Rolyk('22-kyiv-za-khvylynu', 60, tema='temna', nazva='Київ за хвилину (довгий)', hrupa='Місто згори',
              hachok='«Київ за хвилину — у рішеннях судів»', meta='довгий формат, YouTube/TikTok → карта', liniia='Безкоштовна карта',
              kudy='/karta/')
    R.muzyka('puls', bpm=116, drop=3.0)
    # 1. місто (0–12)
    chasy = [t + rng.uniform(0, 0.3) for t in khronolohiia(P, 3.0, 10.0)]
    R.tochky(P, chasy, rozmir=((0, 8), (10, 6), (40, 6), (60, 8)), yaskr=((0, 1), (12, 0.75), (14, 0.35), (44, 0.35), (47, 0.8)), glow=0.3, tryv=0.4)
    R.zvuk_tochok(chasy, maks=12, h0=0.8, h1=1.8, v=0.4)
    R.kam(0, KYIV, 9.2, 0, 0).kam(11.5, KYIV, 10.3, 35, -20, e='io')
    R.tekst(0.1, 3.0, 'hook', 'Київ\n*за хвилину*\nу рішеннях судів', y='verkh')
    R.udar(3.0, 0.4, 14)
    R.tekst(3.2, 11.5, 'lich', kluchi=[[3.0, 0], [10.4, n, 'io']], pidpys=f'{fp(n)} на карті', y=1150)
    R.holos(3.4, f'{n} {fp(n)}. Кожна — з рішення суду.', 'mykyta')
    # 2. доба (12–22)
    R.tekst(12.0, 21.6, 'godynnyk', hodyny=[[12.0, 0, 'l'], [21.0, 24, 'l']], pidpys='година подій', y=1150)
    for h in range(24):
        R.efekt(12.0 + h * 9 / 24, 'tik', h=0.9 + hod[h] / max(hod.values()) * 0.8, v=0.5)
    R.tekst(17.0, 21.6, 'velykyi', f'Найбільше —\n*о {pik}:00.*', y='verkh', anim='vgoru')
    R.holos(17.2, f'Найбільше подій — о {HODYNY_O[pik]}.', 'mykyta')
    R.kam(21.5, KYIV, 10.8, 45, -40, e='io')
    # 3. вулиця (22–36)
    a, b = lin[0], lin[-1]
    R.kam(24.0, (a[0], a[1]), 14.6, 62, -10, e='io').kam(33.0, (b[0], b[1]), 14.6, 62, 10, e='io')
    R.liniia(lin, 23.8, 33.0, 35.5, '#66E6BA', 8)
    import numpy as np
    vz = np.array(lin)
    chasy_v = [24.0 + 9.0 * int(((vz[:, 0] - p.lon) ** 2 + (vz[:, 1] - p.lat) ** 2).argmin()) / max(1, len(vz) - 1) for p in vul]
    R.tochky(vul, chasy_v, rozmir=((0, 11),), glow=0.45, te=[36.0] * len(vul))
    R.zvuk_tochok(chasy_v, maks=8, h0=1.0, h1=1.5, v=0.4, typ='klik')
    for p in sorted(vul, key=lambda x: rng.random())[:10]:
        t = chasy_v[vul.index(p)]
        R.mitka(t + 0.2, t + 1.8, (p.lon, p.lat), p.mitka, kolir=hrupa_kol(p.vyd))
    R.tekst(22.2, 26.6, 'velykyi', f'Одна вулиця —\n*{D.chyslo(len(vul))} {fp(len(vul))}.*', y='verkh', anim='slam')
    R.holos(22.4, f'Велика Васильківська — {len(vul)} {fp(len(vul))}.', 'mykyta')
    # 4. один випадок (36–46)
    c1 = (p1.lon, p1.lat)
    R.kam(36.5, (c1[0], c1[1] - 0.0014), 16.3, 62, -20, e='io', luk=0.6).kam(46, (c1[0], c1[1] - 0.0012), 16.6, 64, -60, e='l')
    R.tochky([p1], [37.0], rozmir=((0, 64),), glow=0.6)
    tekst = 'Січень, 15:05. У магазині взяли батончики, жуйку й шоколад — разом на 214 гривень 67 копійок. Дійшло до суду.'
    R.tekst(37.2, 45.6, 'kartka', tekst, zag='Один випадок', dz=f'{D.vulytsia(p1.adresa)} · рішення суду № {p1.nomer_rishennia}', y=330, shvydkist=30)
    R.holos(37.4, tekst, 'tetiana')
    # 5. 3D (46–60)
    R.kam(48.5, KYIV, 11.4, 58, -60, e='io').kam(55, (30.53, 50.445), 11.9, 64, -110, e='io').kam(60, (30.53, 50.445), 12.0, 64, -125, e='l')
    R.soty(P, 8, vysota=((47.0, 0), (49.5, 1, 'oo')), prozorist=((0, 0), (46.6, 0), (47.4, 1)), maks_vysota=2600, zalyvka=0.08)
    R.udar(47.0, 0.3, 10)
    R.tekst(49.0, 54.4, 'velykyi', 'Вище стовпчик —\n*більше даних.*\nЦе не оцінка місця.', y='verkh', anim='vgoru')
    R.holos(49.2, 'Вище стовпчик — більше даних. Це не оцінка місця.', 'mykyta')
    R.fin(54.6, 'Знайди свою вулицю', 'Моя вулиця — що відбувається під боком', PROFIL)
    return R


def r_23(B: Baza):
    """Актуальне до свят: новорічні ночі в даних — відлік і «салют» подій."""
    pod = [p for p in B.P if p.data and p.data[5:] in ('12-31', '01-01')]
    nich = [p for p in pod if p.hodyna is not None and (p.hodyna >= 22 or p.hodyna <= 3)]
    top = Counter(p.mitka for p in nich).most_common(2)
    R = Rolyk('23-novorichna-nich', 15, tema='temna', nazva='Новорічна ніч у даних', hrupa='Місто згори',
              hachok='«Що Київ робить у новорічну ніч — за рішеннями судів»', meta='актуальне (сезон) → карта', liniia='Безкоштовна карта',
              kudy='/karta/')
    R.muzyka('epik', drop=5.0)
    R.kam(0, KYIV, 10.6, 40, 0).kam(5.0, KYIV, 10.9, 48, -10, e='io').kam(15, KYIV, 11.4, 55, -50, e='l')
    rng = random.Random(23)
    chasy = sorted(5.0 + 2.6 * rng.random() ** 1.6 for _ in nich)
    R.tochky(nich, chasy, rozmir=((0, 11),), glow=0.6)
    for t in chasy[::max(1, len(chasy) // 18)]:
        R.efekt(t, 'pop', h=rng.uniform(0.9, 2.0), v=0.4)
    R.tekst(0.0, 2.4, 'hook', 'Новорічна ніч\n*у рішеннях судів*', y='verkh')
    R.tekst(1.2, 5.0, 'godynnyk', hodyny=[[1.2, 23 + 56 / 60, 'l'], [5.0, 24.0, 'l']], pidpys='31 грудня', y=1100)
    for t in (2.0, 3.0, 4.0):
        R.efekt(t, 'tik', h=1.3)
    R.udar(5.0, 0.6, 18)
    R.efekt(5.0, 'dzvin', h=1.0)
    R.tekst(5.2, 10.8, 'lich', vid=0, do=len(nich), tryv=2.6, pidpys=f'{fp(len(nich))} у даних —\nз 22:00 до 3:00 новорічних ночей', y=1080)
    R.tekst(7.9, 10.8, 'velykyi', f'Найчастіше —\n*{top[0][0]}*.', y='verkh', anim='vgoru')
    R.fin(11.0, 'А на твоїй вулиці?', 'Карта подій — з датами й годинами', PROFIL)
    return R


def r_24(B: Baza):
    """Персонаж «Сота» (MV-148) веде картою: місто → соти → адреса → подія (спосіб користування)."""
    import h3
    vs = B.V.po_vulytsi()
    vul = vs['просп. Оболонський']
    adr = Counter(p.adresa for p in vul if p.tochnist == 'house').most_common(1)[0][0]
    tut = [p for p in vul if p.adresa == adr]
    p1 = sorted(tut, key=lambda p: p.data or '')[-1]
    ca = (tut[0].lon, tut[0].lat)
    k = h3.latlng_to_cell(ca[1], ca[0], 8)
    v_soti = [B.P[i] for i in D.soty_z_podiiamy(B.P, 8)[k]]
    lat_k, lon_k = h3.cell_to_latlng(k)
    R = Rolyk('24-sota-vede', 22, tema='temna', nazva='«Сота» показує, як читати карту', hrupa='Як це працює',
              hachok='«Карта Києва — за 20 секунд: місто, сота, адреса, подія»', meta='спосіб користування картою → сторінка будинку',
              liniia='Мій будинок', kudy='/budynok/ (Оболонський проспект)')
    R.muzyka('hra', bpm=116)
    R.soty(B.P, 8, vysota=((0, 0),), prozorist=((0, 1), (6.5, 1), (7.5, 0.25)), zalyvka=0.5)
    rng = random.Random(24)
    ch = [7.0 + 1.2 * ((i + 1) / len(v_soti)) ** 0.5 for i in range(len(v_soti))]
    R.tochky(v_soti, ch, org=[(lon_k, lat_k)] * len(v_soti), rozmir=((0, 12),), glow=0.4, tryv=0.6)
    R.zvuk_tochok(ch, maks=14, h0=1.0, h1=1.8, v=0.4)
    R.kam(0, KYIV, 10.5, 0, 0).kam(3.0, KYIV, 10.6, 0, 0)
    R.kam(6.0, (lon_k, lat_k - 0.004), 13.4, 45, -10, e='io').kam(10.5, (lon_k, lat_k - 0.003), 13.8, 50, -20, e='l')
    R.kam(13.0, (ca[0], ca[1] - 0.0012), 16.4, 58, -30, e='io').kam(22, (ca[0], ca[1] - 0.001), 16.6, 60, -50, e='l')
    kroky = [[0.4, 30.5234, 50.4501], [5.6, lon_k, lat_k], [12.6, ca[0], ca[1]], [17.0, p1.lon + 0.0001, p1.lat + 0.0001]]
    R.ui(0.4, 22.5, 'sota', kroky=kroky, rozmir=140)
    for t in (0.4, 5.6, 12.6, 17.0):
        R.efekt(t, 'pop', h=1.3, v=0.7)
        R.efekt(t - 0.5, 'svish', v=0.5)
    R.tekst(0.6, 5.0, 'velykyi', '*Місто.*\nТемніша сота — більше даних.', y='verkh', anim='vgoru')
    R.tekst(6.0, 11.8, 'velykyi', f'*Сота.*\nНаближ — і вона розкриється:\n{D.chyslo(len(v_soti))} {fp(len(v_soti))}.', y='verkh', anim='vgoru')
    R.udar(7.0, 0.3, 10)
    R.tekst(12.6, 16.6, 'velykyi', f'*Адреса.*\nУсе, що тут було: {len(tut)} {fp(len(tut))}.', y='verkh', anim='vgoru')
    R.tekst(17.2, 20.6, 'velykyi', '*Подія.*\nІ посилання на рішення суду.', y='verkh', anim='vgoru')
    R.mitka(17.3, 21.0, (p1.lon, p1.lat), f'{p1.mitka} · рішення № {p1.nomer_rishennia}', kolir=hrupa_kol(p1.vyd))
    R.holos(0.7, 'Місто. Темніша сота — більше даних.', 'tetiana')
    R.holos(6.2, 'Наближ — і сота розкриється на події.', 'tetiana')
    R.holos(12.8, 'Адреса — усе, що тут було.', 'tetiana')
    R.holos(17.4, 'Подія — і посилання на рішення суду.', 'tetiana')
    R.fin(20.8, 'Спробуй на своїй вулиці', '', PROFIL)
    return R


def r_25(B: Baza):
    """«Два будинки поруч» (MV-149): без номерів, без «кращий/гірший» — лише теми й числа; веде на довідку."""
    a_adr, b_adr = 'вул. Хрещатик, 27', 'вул. Хрещатик, 25'
    A = [p for p in B.P if p.adresa == a_adr and p.tochnist == 'house']
    Bb = [p for p in B.P if p.adresa == b_adr and p.tochnist == 'house']
    ca, cb = (A[0].lon, A[0].lat), (Bb[0].lon, Bb[0].lat)
    d = round(D.vidstan_m(ca[1], ca[0], cb[1], cb[0]))
    c = ((ca[0] + cb[0]) / 2, (ca[1] + cb[1]) / 2)
    ta, tb = Counter(p.mitka for p in A).most_common(3), Counter(p.mitka for p in Bb).most_common(3)
    R = Rolyk('25-dva-budynky-porudh', 20, tema='temna', nazva='Два будинки поруч', hrupa='«Що болить вулиці»',
              hachok=f'«Два будинки. {d} метрів між ними. Зовсім різне»', meta='довідка 199 (порівняння із сусідами)',
              liniia='Мій будинок', kudy='/mii-budynok/')
    R.muzyka('lofi', bpm=96)
    R.kam(0, (c[0], c[1] - 0.004), 15.0, 50, 0).kam(3.0, (c[0], c[1] - 0.0013), 17.0, 60, -20, e='io')
    R.kam(20, (c[0], c[1] - 0.0011), 17.2, 62, -45, e='l')
    rng = random.Random(25)
    cha = [3.2 + 2.0 * ((i + 1) / len(A)) ** 0.6 for i in range(len(A))]
    chb = [5.6 + 2.0 * ((i + 1) / len(Bb)) ** 0.6 for i in range(len(Bb))]
    R.tochky(A, cha, rozmir=((0, 30),), glow=0.5)
    R.tochky(Bb, chb, rozmir=((0, 30),), glow=0.5)
    R.zvuk_tochok(cha, maks=10, h0=0.9, h1=1.3, v=0.45)
    R.zvuk_tochok(chb, maks=10, h0=1.3, h1=1.8, v=0.45, seed=2)
    R.mitka(3.2, 19.5, ca, f'Будинок 1 · {len(A)} {fp(len(A))}', styl='velyka', dy=0 if ca[1] > cb[1] else 110)
    R.mitka(5.6, 19.5, cb, f'Будинок 2 · {len(Bb)} {fp(len(Bb))}', styl='velyka', dy=110 if ca[1] > cb[1] else 0)
    R.tekst(0.0, 3.0, 'hook', f'Два будинки.\n*{d} метрів* між ними.', y='verkh')
    R.tekst(8.0, 15.4, 'stovpchyky', riady=[{'tekst': f'1 · {v}', 'n': n, 'kolir': '#66E6BA'} for v, n in ta] +
            [{'tekst': f'2 · {v}', 'n': n, 'kolir': '#9C9DF0'} for v, n in tb], y=1080)
    R.tekst(8.0, 15.4, 'velykyi', 'Поруч —\nа *теми різні.*', y='verkh', anim='slam')
    R.efekt(8.0, 'svish')
    R.tekst(15.6, 17.4, 'velykyi', 'Різні.\n*Не кращі й не гірші.*', y='verkh', anim='vgoru')
    R.holos(8.2, f'Поруч, а теми різні. Біля першого найчастіше — {ta[0][0]}. Біля другого — {tb[0][0]}.', 'mykyta')
    R.fin(17.5, 'Порівняй свій будинок із сусідами', 'Довідка про будинок — 199 грн', PROFIL)
    return R


SCENARII = {k[2:]: v for k, v in dict(globals()).items() if re.match(r'r_\d\d$', k)}


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('baza', type=Path)
    a.add_argument('--koloda', type=Path)
    a.add_argument('--lyshe')
    arg = a.parse_args()
    B = Baza(arg)
    vybir = arg.lyshe.split(',') if arg.lyshe else sorted(SCENARII)
    katalog = []
    kat_f = VYHID / 'katalog.json'
    if kat_f.is_file():
        katalog = [m for m in json.loads(kat_f.read_text(encoding='utf-8')) if m['id'][:2] not in vybir]
    for k in vybir:
        R = SCENARII[k](B)
        katalog.append(R.zberehty())
        print(R.S['id'], R.S['tryvalist'], 'с')
    katalog.sort(key=lambda m: m['id'])
    kat_f.write_text(json.dumps(katalog, ensure_ascii=False, indent=1), encoding='utf-8')


if __name__ == '__main__':
    main()
