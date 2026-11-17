# -*- coding: utf-8 -*-
"""Публічні названі місця з випуску (ZAVDANNYA-124; MV-54, MV-60, MV-98, MV-116, MV-135): станції метро, ТЦ, ринки,
вокзали, парки й сквери, пляжі, мости, острови.

Звідки: події, чиє місце в випуску — назване місце (`location.tochnist = 'mistse'`, підпис точки кроку 2:
«ст. м. Вокзальна», «ТРЦ «Ocean Plaza»», «пляж Венеція»…). Тип — за словом-типом на початку підпису (як `dani-edrsr/src/nazvani.py`).
Зупинки, житло, адреси з номером будинку — не публічні місця сторінки: їх тут немає (MV-25, MV-60).

Що рахуємо (лише числа, MV-3): події за останні 3 роки (як на сторінках вулиць), без статевих і щодо дітей (MV-102);
групи — словник MV-116; роки; порівняння «тут · у типовому місці того самого типу» — шкала MV-98 (до повного Києва без
«менше»). «Що поруч» не робимо.

  python site/sait/mistsia.py --baza events.db [--vykhid mistsia-media.csv]
      → список місць у форматі dani-edrsr/config/mistsia-media.csv: генератор візуалу «Для медіа»
        (dani-edrsr/src/vizual_mistsia.py --mistsia <файл>) робить картки саме для сторінок /mistse/<slug>/.
"""
from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))
import dani as D  # noqa: E402

# тип → (як зветься на сторінці, множина для покажчика, радіус кола візуалу «Для медіа», м)
TYPY = {
    'метро': ('станція метро', 'Станції метро', 300),
    'ТЦ': ('ТЦ', 'Торгові центри', 250),
    'ринок': ('ринок', 'Ринки', 300),
    'вокзал': ('вокзал', 'Вокзали', 300),
    'парк': ('парк', 'Парки й сквери', 400),
    'пляж': ('пляж', 'Пляжі', 300),
    'міст': ('міст', 'Мости', 300),
    'острів': ('острів', 'Острови', 500),
}
SLUG_TYPU = {'метро': 'metro', 'ТЦ': 'tts', 'ринок': 'rynok', 'вокзал': 'vokzal', 'парк': 'park', 'пляж': 'pliazh',
             'міст': 'mist', 'острів': 'ostriv'}
LAPKY = '«»"“”„\''
# Слово-тип на початку підпису точки → тип; решта підпису — власна назва (у лапках чи без).
# Слово-тип на початку чи в кінці підпису точки → (тип, як зветься на сторінці). {n} — власна назва (без лапок).
PATERNY = [
    ('метро', re.compile(r'^(?:ст\.?\s*м(?:етро)?\.?|станці\w*\s+(?:метро\w*|м\.)|метро(?:політен\w*)?)\s*(.+)$', re.I), 'станція метро «{n}»'),
    ('ТЦ', re.compile(r'^(?:ТРЦ|ТРК|ТЦ|торгов\w+(?:[\s-]+розважальн\w+)?\s+(?:центр|комплекс)\w*)\s*(.+)$'), 'ТЦ «{n}»'),
    ('ринок', re.compile(r'^ринок\s*(.+)$', re.I), 'ринок «{n}»'),
    ('ринок', re.compile(r'^(.+?)\s+ринок$', re.I), '{n} ринок'),
    ('вокзал', re.compile(r'^((?:Центральн|Південн|Дарницьк)\w*)(?:\s+залізничн\w*)?\s+вокзал\w*$', re.I), '{n} вокзал'),
    ('вокзал', re.compile(r'^(?:авто)?вокзал\w*\s*(.+)$', re.I), 'вокзал «{n}»'),
    ('пляж', re.compile(r'^пляж\w*\s*(.+)$', re.I), 'пляж «{n}»'),
    ('парк', re.compile(r'^сквер\w*\s*(?:ім\.+\s*|імені\s+)?(.+)$', re.I), 'сквер «{n}»'),
    ('парк', re.compile(r'^(?:парк\w*|ПКіВ|ПКВ)\s*(?:ім\.+\s*|імені\s+)?(.+)$', re.I), 'парк «{n}»'),
    ('парк', re.compile(r'^(.+?)\s+парк$', re.I), '{n} парк'),
    ('парк', re.compile(r'^(Гідропарк)$', re.I), '{n}'),
    ('міст', re.compile(r'^міст\w*\s*(?:ім\.+\s*|імені\s+)?(.+)$', re.I), 'міст {n}'),
    ('міст', re.compile(r'^(.+?)\s+міст$', re.I), '{n} міст'),
    ('острів', re.compile(r'^остр(?:ів|ова|ові)\s+(.+)$', re.I), 'острів {n}'),
    ('острів', re.compile(r'^(.+?)\s+острів$', re.I), '{n} острів'),
]
NOMER = re.compile(r',\s*\d')           # «вул. X, 5» — адреса будинку, не назване місце


def rozibraty(adresa: str) -> tuple[str, str, str] | None:
    """Підпис точки → (тип, власна назва, як зветься на сторінці) або None (не публічне назване місце)."""
    a = D.chystyi(adresa or '').strip()
    if not a or NOMER.search(a) or re.match(r'^(вул|просп|пров|бульв|пл)\.?\s', a, re.I):
        return None
    for typ, rx, forma in PATERNY:
        m = rx.match(a)
        if m:
            vlasna = m.group(1).strip().strip(LAPKY).strip()
            if len(vlasna) < 2 or re.search(r'\d{2,}', vlasna) or re.search(r'ОСОБА|АДРЕСА|ІНФОРМАЦІЯ', vlasna):
                return None
            return typ, vlasna, forma.format(n=vlasna)
    return None


@dataclass
class Mistse:
    slug: str
    typ: str
    nazva: str                 # «станція метро «Лісова»»
    vlasna: str
    podii: list = field(default_factory=list)      # індекси подій dn.podii за відкриті роки (без статевих і щодо дітей)
    lat: float = 0.0
    lon: float = 0.0
    rayon: str | None = None
    vulytsia: str | None = None                    # slug найближчої вулиці зі сторінкою (≤ 400 м)


def zibraty(dn) -> dict:
    """slug → Mistse для всіх публічних названих місць випуску, де за відкриті роки є хоч одна подія."""
    roky = set(D.VIDKRYTI_ROKY)
    mistsia: dict[str, Mistse] = {}
    for i, p in enumerate(dn.podii):
        if p.tochnist != 'mistse' or p.lat is None or p.rik not in roky or p.chutlyva:
            continue
        r = rozibraty(p.adresa)
        if not r:
            continue
        typ, vlasna, nazva = r
        slug = SLUG_TYPU[typ] + '-' + D.translit(vlasna)
        if slug.endswith('-'):
            continue
        m = mistsia.get(slug)
        if not m:
            m = mistsia[slug] = Mistse(slug, typ, nazva, vlasna)
        m.podii.append(i)
    # Точка — середина точок місця; район — за межами районів; вулиця — найближча з подіями (≤ 400 м).
    sitka = {}
    for slug_v, v in dn.vulytsi.items():
        for i in v.nedavni:
            p = dn.podii[i]
            if p.lat is not None:
                sitka.setdefault((round(p.lat / 0.004), round(p.lon / 0.006)), []).append((p.lat, p.lon, slug_v))
    for m in mistsia.values():
        m.lat = round(statistics.median(dn.podii[i].lat for i in m.podii), 5)
        m.lon = round(statistics.median(dn.podii[i].lon for i in m.podii), 5)
        m.rayon = dn.rayony.rayon(m.lat, m.lon) if dn.rayony else None
        kl = (round(m.lat / 0.004), round(m.lon / 0.006))
        naiblyzhcha = None
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for la, lo, s in sitka.get((kl[0] + di, kl[1] + dj), ()):
                    d = vidstan_m(m.lat, m.lon, la, lo)
                    if d <= 400 and (naiblyzhcha is None or d < naiblyzhcha[0]):
                        naiblyzhcha = (d, s)
        m.vulytsia = naiblyzhcha[1] if naiblyzhcha else None
    return dict(sorted(mistsia.items()))


def z_velykoi(t: str) -> str:
    return t[:1].upper() + t[1:]


def vidstan_m(la1: float, lo1: float, la2: float, lo2: float) -> float:
    return math.hypot((la2 - la1) * 111320, (lo2 - lo1) * 111320 * math.cos(math.radians(la1)))


def _poisson_sf(k: int, lam: float) -> float:
    """P(X ≥ k) для закону Пуассона — без scipy."""
    if k <= 0:
        return 1.0
    t, s = math.exp(-lam), 0.0
    for i in range(k):
        s += t
        t *= lam / (i + 1)
    return max(0.0, 1.0 - s)


def _poisson_cdf(k: int, lam: float) -> float:
    return 1.0 - _poisson_sf(k + 1, lam)


def mitka(tut: int, typove: float | None, menshe_mozhna: bool = False) -> str:
    """MV-98 — те саме правило, що `dani-edrsr/src/zvit/analityka.mitka_shkaly` (звіряє tests/test_mistsia.py):
    обидва ≤ 3 — «мало даних»; різниця невипадкова (p < 0,05) — «більше» («менше» — лише після повного Києва);
    помітна, але може бути випадковою — «мало даних»; інакше — «як зазвичай»."""
    if typove is None:
        return 'мало даних'
    if tut <= 3 and typove <= 3:
        return 'мало даних'
    lam = max(float(typove), .5)
    if tut > typove and _poisson_sf(tut, lam) < .05:
        return 'більше'
    if tut < typove and _poisson_cdf(tut, lam) < .05:
        return 'менше' if menshe_mozhna else 'як зазвичай'
    vyshche, nyzhche = max(tut, typove), max(min(tut, typove), .5)
    return 'мало даних' if vyshche / nyzhche >= 1.5 else 'як зазвичай'


def profil(dn, m: Mistse, vsi: dict) -> dict:
    """Числа сторінки місця: усього, групи (MV-116), роки, порівняння з типовим місцем того самого типу."""
    podii = [dn.podii[i] for i in m.podii]
    hrupy = Counter(D.HR.hrupa(p.vyd, p.stattia) or 'poza' for p in podii)
    roky = Counter(p.rik for p in podii)
    tsiogo_typu = [len(x.podii) for x in vsi.values() if x.typ == m.typ]
    typove = statistics.median(tsiogo_typu) if len(tsiogo_typu) >= 3 else None
    return {'vsogo': len(podii), 'hrupy': hrupy.most_common(), 'roky': {r: roky.get(r, 0) for r in D.VIDKRYTI_ROKY},
            'typove': typove, 'mists_typu': len(tsiogo_typu), 'mitka': mitka(len(podii), typove)}


def dlia_media(vsi: dict) -> list[dict]:
    """Рядки для генератора візуалу (формат dani-edrsr/config/mistsia-media.csv)."""
    ryadky = []
    for m in vsi.values():
        pidpys = 'Київ' + (f', {m.rayon} район' if m.rayon else '') + f' · {TYPY[m.typ][0]}'
        ryadky.append({'slug': m.slug, 'nazva': z_velykoi(m.nazva),
                       'typ': m.typ, 'lat': m.lat, 'lon': m.lon, 'radius': TYPY[m.typ][2], 'pidpys': pidpys,
                       'storinka': f'/mistse/{m.slug}/'})
    return ryadky


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('--baza', type=Path, required=True)
    a.add_argument('--mezhi', type=Path, default=TUT.parents[1] / 'data' / 'borders.json')
    a.add_argument('--vykhid', type=Path, default=Path('mistsia-media.csv'))
    x = a.parse_args(argv)
    dn = D.zibraty_dani(x.baza, None, x.mezhi)
    vsi = zibraty(dn)
    with x.vykhid.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['slug', 'nazva', 'typ', 'lat', 'lon', 'radius', 'pidpys', 'storinka'])
        w.writeheader()
        w.writerows(dlia_media(vsi))
    print(f'Публічних місць: {len(vsi)} ({", ".join(f"{t} — {n}" for t, n in Counter(m.typ for m in vsi.values()).most_common())}); файл {x.vykhid}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
