"""Генератор сценаріїв роликів з бази (ZAVDANNYA-94; групи — MV-111, docs/KOMPAS.md, розд. 3а).

Випуск events-<дата>.db (+ скарги 1551, перекази ШІ, колода гри) → JSON-сценарій для video/rendery.py. Кожен сценарій
одразу проходить перевірку правил (video/perevirka.py); той, що не пройшов, не записується.

    python video/heneruvaty.py <events.db> --typ shcho_bolyt --vulytsia kadetskyi-hai \\
        --pereimenuvannya ../dani-edrsr/config/pereimenuvannia-kyiv.csv --1551 <тека dani-1551> --vykhid video/stsenarii/avto/

Типи (група → шаблон рушія):
    1 «Що болить вулиці»     shcho_bolyt   скарги 1551 за місяць + події числом, «тут · у середньому на вулиці району»
    2 Історії «під боком»     istoriia      одна вулиця — одна історія (лише переказ ШІ, що пройшов перевірку)
                              tur           тур району: 4–5 подій з колоди
    3 Ігри                    vhadai        «Вгадай, де це було»: 2 раунди з колоди
    4 Місто згори             taimlaps      соти наростають за періодами, наприкінці 3D-вершини (верхні 12 %)
                              perelit       переліт Україна → Київ → район → вулиця → «Що болить вашому будинку»
    5 Як це працює            yak_pratsiuie картки: звідки дані, що в довідці
    6 «Що буває за…»          shcho_buvaie  стаття: скільки справ у даних, коли (без порад «як уникнути», без імен суддів)
    7 Історії з даних         istoriia_danykh  картки: напр., о котрій годині найчастіше ДТП, що дійшли до суду

Правила (перевіряє програма, а не людина): вулиця без номера будинку (MV-25), номер — лише публічних місць (MV-60;
номер з точності «house» прибирається завжди); чутливі справи (MV-4) і насильство в роликах не беруться; текст історії —
лише переказ ШІ з файлу --perekazy, що пройшов perekaz_perevirka (MV-21: ШІ переписує, не вигадує); число — з
порівнянням; кожен ролик закінчується посиланням на сторінку цього місця (MV-106). Текст для голосу (holos) генератор
пише сам: роки й місяці — словами, щоб синтезатор не читав «дві тисячі двадцять п'ять році».
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parent
sys.path.insert(0, str(TUT))
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(KORIN / 'brend'))

import perevirka  # noqa: E402
from adresa_pokazu import adresa_dlia_pokazu, chutlyva  # noqa: E402

ADRESA_SAITU = 'https://moya-vulytsya.pages.dev'   # як у site/zibraty_sait.py (умовна, MV-23)
GRUPY = {
    'shcho_bolyt': (1, 'Що болить вулиці'), 'istoriia': (2, 'Історії «під боком»'), 'tur': (2, 'Історії «під боком»'),
    'vhadai': (3, 'Ігри'), 'taimlaps': (4, 'Місто згори'), 'perelit': (4, 'Місто згори'),
    'yak_pratsiuie': (5, 'Як це працює'), 'shcho_buvaie': (6, '«Що буває за…»'), 'istoriia_danykh': (7, 'Історії з даних'),
}
NE_V_ROLYKY = {'НАС'}          # насильство — не в безкоштовні ролики (MV-4, MV-69: як у грі)
MISIATSI = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень',
            'листопад', 'грудень']
MISIATSI_ZA = ['січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень',
               'листопад', 'грудень']
ROKY_SLOVAMY = {2016: 'шістнадцятий', 2017: 'сімнадцятий', 2018: 'вісімнадцятий', 2019: "дев'ятнадцятий", 2020: 'двадцятий',
                2021: 'двадцять перший', 2022: 'двадцять другий', 2023: 'двадцять третій', 2024: 'двадцять четвертий',
                2025: "двадцять п'ятий", 2026: 'двадцять шостий'}
ROKY_U = {2016: 'шістнадцятому', 2017: 'сімнадцятому', 2018: 'вісімнадцятому', 2019: "дев'ятнадцятому", 2020: 'двадцятому',
          2021: 'двадцять першому', 2022: 'двадцять другому', 2023: 'двадцять третьому', 2024: 'двадцять четвертому',
          2025: "двадцять п'ятому", 2026: 'двадцять шостому'}
SYMVOLIV_NA_SEKUNDU = 13.5      # Piper medium «Тетяна» (заміряно, ZAVDANNYA-94); рендер усе одно звіряє з реальним голосом


def vidminok(n: int, formy: tuple) -> str:
    o, d = n % 10, n % 100
    return formy[0] if o == 1 and d != 11 else formy[1] if 2 <= o <= 4 and not 12 <= d <= 14 else formy[2]


def chyslo(n: int) -> str:
    return f'{n:,}'.replace(',', ' ')


def skilky_holosu(tekst: str) -> float:
    """Скільки секунд голос читатиме текст. Є Piper — міряємо справжнім синтезом, ні — за швидкістю мовлення."""
    import zvuk
    if MIRIATY_HOLOS:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            try:
                f = zvuk.syntez(tekst, Path(d) / 'h.wav', 'piper')
                return zvuk.tryvalist(f)
            except Exception:
                pass
    return len(zvuk.tekst_dlia_holosu(tekst)) / SYMVOLIV_NA_SEKUNDU


MIRIATY_HOLOS = False


def tryv(holos: str, min_: float, vid: float = 0.0) -> float:
    """Тривалість відрізка: щоб голос вмістився після появи картки (+ запас), але не менше min_."""
    return round(max(min_, vid + 0.35 + skilky_holosu(holos) + 0.45) * 2) / 2


# ------------------------------------------------------------------ дані

class Baza:
    def __init__(self, a):
        import dani as D
        self.D = D
        self.dn = D.zibraty_dani(a.baza, a.pereimenuvannya, a.mezhi_rayoniv)
        self.versiia = self.dn.versiia
        self.perekazy = json.loads(Path(a.perekazy).read_text(encoding='utf-8')) if a.perekazy else {}
        if isinstance(self.perekazy, dict) and 'perekazy' in self.perekazy:
            self.perekazy = self.perekazy['perekazy']
        self.koloda = json.loads(Path(a.koloda).read_text(encoding='utf-8'))['podii'] if a.koloda else []
        self.teka_1551 = Path(a.d1551) if a.d1551 else None
        import sqlite3
        self.con = sqlite3.connect(f'file:{a.baza}?mode=ro', uri=True)

    # -- вулиці
    def vulytsia(self, slug: str):
        v = self.dn.vulytsi.get(slug)
        if not v:
            raise SystemExit(f'вулиці {slug!r} у випуску немає')
        return v

    def podii_vulytsi(self, v, vidkryti=True):
        return [p for p in (self.dn.podii[i] for i in v.nedavni) if not (vidkryti and (p.chutlyva or p.vyd in NE_V_ROLYKY))]

    def rayon_vulytsi(self, v) -> str | None:
        return v.rayony.most_common(1)[0][0] if v.rayony else None

    def tsentr(self, podii):
        t = [(p.lat, p.lon) for p in podii if p.lat is not None]
        if not t:
            return None
        # медіана, а не середнє: довга вулиця з точкою на іншому кінці не тягне центр у поле
        return statistics.median(x[0] for x in t), statistics.median(x[1] for x in t)

    def osm_nazva(self, v) -> list[str]:
        """Як вулиця підписана в OpenStreetMap (для м'ятної лінії): повна назва й варіанти."""
        n = {v.nazva, f'{v.korotka} {v.typ}', f'{v.typ} {v.korotka}'}
        return sorted(n)

    # -- скарги 1551
    def skarhy(self, misiats: str | None = None):
        """{slug вулиці: Counter(тема)} за місяць; місяць — останній повний із stan.json."""
        if not self.teka_1551:
            return None, {}
        stan = json.loads((self.teka_1551 / 'stan.json').read_text(encoding='utf-8')) if (self.teka_1551 / 'stan.json').exists() else {}
        fajly = sorted(self.teka_1551.glob('skargy-*.tsv.gz'))
        if not misiats:
            # останній місяць може бути неповним (збір щотижня) — беремо передостанній
            misiats = fajly[-2].stem.split('-', 1)[1].split('.')[0] if len(fajly) > 1 else fajly[-1].stem.split('-', 1)[1].split('.')[0]
        f = self.teka_1551 / f'skargy-{misiats}.tsv.gz'
        indeks = {}
        for slug, v in self.dn.vulytsi.items():
            indeks.setdefault((v.typ, self.D.kliuch(v.korotka)), slug)
        for (t, n), slug in self.dn.zvedennia.varianty.items():
            indeks.setdefault((t, self.D.kliuch(n)), slug)
        rez, vsogo, znaideno = defaultdict(Counter), 0, 0
        with gzip.open(f, 'rt', encoding='utf-8') as fh:
            for r in csv.DictReader(fh, delimiter='\t'):
                vsogo += 1
                tn = self.D.rozibraty_vulytsiu(r['vulytsia'] or '', z_tekstu=False)
                slug = indeks.get((tn[0], self.D.kliuch(tn[1]))) if tn else None
                if slug:
                    znaideno += 1
                    rez[slug][r['kind'] or 'інше'] += 1
        self.pokryttia_1551 = (znaideno, vsogo, stan)
        return misiats, rez


def posylannia_vulytsi(slug):
    return f'{ADRESA_SAITU}/vulytsia/{slug}/'


def posylannia_rayonu(rayon):
    import zibraty_sait as Z
    return f'{ADRESA_SAITU}/rayon/{Z.slug_rayonu(rayon)}/'


def koly(data: str | None) -> str:
    if not data or not re.match(r'^\d{4}-\d{2}', data):
        return ''
    return f'{MISIATSI[int(data[5:7]) - 1].capitalize()} {data[:4]}'


def kinets(tekst, pidtekst, pos, holos):
    return {'tekst': tekst, 'pidtekst': pidtekst, 'posylannia': pos, 'holos': holos,
            'tryvalist': tryv(holos, 3.5, 0.5)}


# ------------------------------------------------------------------ група 1: «Що болить вулиці»

def shcho_bolyt(B: Baza, slug: str):
    v = B.vulytsia(slug)
    rayon = B.rayon_vulytsi(v)
    misiats, skarhy = B.skarhy()
    tut = skarhy.get(slug, Counter())
    na_rayon = [sum(skarhy[s].values()) for s, x in B.dn.vulytsi.items() if B.rayon_vulytsi(x) == rayon and skarhy.get(s)]
    med_s = statistics.median(na_rayon) if na_rayon else 0
    podii = B.podii_vulytsi(v)
    roky = sorted({p.rik for p in podii if p.rik})
    z_podiiamy = [len(B.podii_vulytsi(x)) for x in B.dn.vulytsi.values() if B.rayon_vulytsi(x) == rayon and x.nedavni]
    med_p = statistics.median(z_podiiamy) if z_podiiamy else 0
    t = B.tsentr(podii)
    if not t or not tut:
        raise SystemExit(f'{slug}: немає точок подій або скарг 1551 за {misiats}')
    m = int(misiats[5:7]) - 1
    n_s = sum(tut.values())
    tema, n_t = tut.most_common(1)[0]
    vydy = Counter(B.D.vyd_lyudskoyu(p.stattia, p.vyd) for p in podii)
    vyd, n_v = vydy.most_common(1)[0]
    r0, r1 = (roky[0], roky[-1]) if roky else (None, None)
    period = f'{r0}–{r1}' if r0 != r1 else str(r0)
    korotka = v.nazva
    fakty = [
        {'mitka': f'{korotka} · {MISIATSI_ZA[m]} {misiats[:4]}', 'chyslo': chyslo(n_s),
         'tekst': f'{vidminok(n_s, ("звернення", "звернення", "звернень"))} мешканців до 1551',
         'pidpys': f'У середньому на вулиці району ({rayon}) — {chyslo(round(med_s))}. Скарга — звернення, не перевірений факт.',
         'holos': f'За {MISIATSI_ZA[m]} — {n_s} {vidminok(n_s, ("звернення", "звернення", "звернень"))} до 1551. '
                  f'У середньому на вулиці району — {round(med_s)}.'},
        {'mitka': 'Найчастіше скаржились', 'chyslo': chyslo(n_t), 'tekst': f'{tema.lower()}',
         'pidpys': 'Інші теми: ' + ', '.join(f'{k.lower()} — {n}' for k, n in tut.most_common(3)[1:]) if len(tut) > 1 else '',
         'holos': f'Найчастіше — {tema.lower()}: {n_t}.'},
        {'mitka': f'Події з рішень судів · {period}', 'chyslo': chyslo(len(podii)),
         'tekst': f'{vidminok(len(podii), ("подія", "події", "подій"))} з точкою на вулиці',
         'pidpys': f'У середньому на вулиці району — {chyslo(round(med_p))}. Найчастіше — {vyd.lower()} ({n_v}). Лише те, що дійшло до суду.',
         'holos': f'І {len(podii)} {vidminok(len(podii), ("подія", "події", "подій"))} з рішень судів за {len(roky)} '
                  f'{vidminok(len(roky), ("рік", "роки", "років"))}. Найчастіше — {vyd.lower()}.'},
    ]
    for f in fakty:
        f['tryvalist'] = tryv(f['holos'], 5.0, 0.0 if f is not fakty[0] else 1.1)
    S = {
        'nazva': f'Що болить вулиці: {korotka}', 'shablon': 'shcho_bolyt', 'hrupa': 1, 'z1551': True, 'muzyka': 'spokii',
        'opys': f'Скарги 1551 за {MISIATSI_ZA[m]} {misiats[:4]} і події з рішень судів числом. Випуск {B.versiia}.',
        'pidsvitka': B.osm_nazva(v),
        'vstup': {'mitka': 'Що болить вулиці', 'tekst': korotka, 'pidtekst': f'{rayon} район · скарги й події числом',
                  'holos': f'Що болить вулиці? {korotka}.'},
        'tsentr': {'nazva': korotka, 'lat': round(t[0], 6), 'lon': round(t[1], 6), 'zoom': 15.2},
        'tochky': fakty,
        'kinets': kinets('Що болить вашому будинку', 'Скарги мешканців і події з рішень судів — по кожному будинку. Сторінка вулиці:',
                         posylannia_vulytsi(slug), 'Що болить вашому будинку? Сторінка вулиці — за посиланням.'),
    }
    S['vstup']['tryvalist'] = tryv(S['vstup']['holos'], 3.0, 0)
    return S


# ------------------------------------------------------------------ група 2: «Одна вулиця — одна історія»

def rozbyty_na_karty(tekst: str, maks: int = 125) -> list[str]:
    rechennia = re.findall(r'[^.!?…]+[.!?…]+', tekst.strip()) or [tekst]
    karty, pot = [], ''
    for r in (x.strip() for x in rechennia):
        if pot and len(pot) + 1 + len(r) > maks:
            karty.append(pot)
            pot = r
        else:
            pot = (pot + ' ' + r).strip()
    if pot:
        karty.append(pot)
    if len(karty) == 1 and len(karty[0]) > 70:      # одне довге речення — дві картки по комі
        t = karty[0]
        i = t.find(',', len(t) // 3)
        if i > 0:
            karty = [t[:i + 1].strip(), t[i + 1:].strip().capitalize()]
    return karty[:3]


def istoriia(B: Baza, slug: str, event_id: str | None = None):
    import perekazy as PK
    v = B.vulytsia(slug)
    podii = [p for p in B.podii_vulytsi(v) if p.fabula and p.lat is not None]
    kand = [p for p in podii if (event_id is None or p.event_id == event_id) and p.event_id in B.perekazy]
    for p in kand:
        t = B.perekazy[p.event_id]
        if PK.vady(t, p.fabula) or perevirka.MV4_SLOVA.search(t) or chutlyva(p.vyd, t):
            continue
        karty = rozbyty_na_karty(t)
        if not 2 <= len(karty) <= 3:
            continue
        typ = 'nevidomo' if p.tochnist == 'house' else 'zaklad' if p.tochnist == 'mistse' else 'vulytsia'
        holos_ = [k for k in karty]
        holos_[0] = f'{koly(p.data).split()[0]} {ROKY_U[p.rik]} році. ' + holos_[0] if p.rik in ROKY_U and p.data else holos_[0]
        tryvalosti = [tryv(h, 4.5, 1.1 if i == 0 else 0) for i, h in enumerate(holos_)]
        tryvalosti[0] = max(tryvalosti[0], 1.8 + 3.0)        # переліт 1,8 с + читання
        rayon = B.rayon_vulytsi(v)
        S = {
            'nazva': f'Одна історія: {v.nazva}', 'shablon': 'istoriia', 'hrupa': 2, 'muzyka': 'vechir',
            'opys': f'Переказ ШІ однієї події з рішення суду (перевірено програмою, MV-21). Випуск {B.versiia}.',
            'pidsvitka': B.osm_nazva(v),
            'vstup': {'mitka': 'Одна вулиця — одна історія', 'tekst': v.nazva, 'pidtekst': f'{rayon} район',
                      'holos': f'Одна вулиця — одна історія. {v.nazva}.'},
            'tochky': [{
                'id': p.event_id, 'vyd': B.D.vyd_lyudskoyu(p.stattia, p.vyd), 'koly': koly(p.data),
                'adresa': adresa_dlia_pokazu(p.adresa, typ, chutlyva(p.vyd, t)), 'typ_mistsia': typ,
                'lat': round(p.lat, 6), 'lon': round(p.lon, 6), 'rishennya_url': p.url, 'rishennya_nomer': p.event_id.split('-')[0],
                'dzherelo_tekstu': 'perekaz_shi', 'karty': karty, 'holos': holos_, 'tryvalosti': tryvalosti,
                'tryvalist': sum(tryvalosti)}],
            'kinets': kinets('Що ще було на вашій вулиці?', 'Числа й історія вулиці — на її сторінці:', posylannia_vulytsi(slug),
                             'Що ще було на вашій вулиці? Сторінка вулиці — за посиланням.'),
        }
        S['vstup']['tryvalist'] = tryv(S['vstup']['holos'], 3.0, 0)
        return S
    raise SystemExit(f'{slug}: немає переказу ШІ, що пройшов перевірку (--perekazy)')


# ------------------------------------------------------------------ група 3: «Вгадай, де це було» (з колоди гри)

def vhadai(B: Baza, ids: list[str]):
    import perekazy as PK
    zk = {e['id']: e for e in B.koloda}
    tochky = []
    for i in ids:
        e = zk[i]
        t = B.perekazy.get(i)
        if not t or PK.vady(t):
            raise SystemExit(f'{i}: немає переказу ШІ, що пройшов перевірку')
        typ = 'nevidomo'
        hp = f'{t} Де це було?'
        tochky.append({'id': i, 'vyd': e['vyd'], 'koly': f'{e["rik"]}', 'adresa': adresa_dlia_pokazu(e['adresa'], typ), 'typ_mistsia': typ,
                       'lat': e['lat'], 'lon': e['lon'], 'tekst': t, 'rishennya_url': e['rishennya_url'],
                       'rishennya_nomer': str(e['rishennya_nomer']), 'dzherelo_tekstu': 'perekaz_shi',
                       'pytannya': tryv(hp, 4.5, 0), 'pauza': 3.0, 'holos_pytannya': hp,
                       'holos_vidpovid': f'{adresa_dlia_pokazu(e["adresa"], typ)}.', 'tryvalist': 4.0})
    ost = tochky[-1]
    import dani as D
    tn = D.rozibraty_vulytsiu(ost['adresa'])
    slug = next((s for (t_, n), s in B.dn.zvedennia.varianty.items() if tn and (t_, D.kliuch(n)) == (tn[0], D.kliuch(tn[1]))), None)
    S = {'nazva': 'Вгадай, де це було', 'shablon': 'vhadai', 'hrupa': 3, 'muzyka': 'hra',
         'opys': f'Два раунди гри з колоди {B.versiia}; тексти — переказ ШІ (перевірено програмою).',
         'vstup': {'mitka': 'Гра', 'tekst': 'Вгадай, де це було', 'pidtekst': 'Дві справжні події Києва',
                   'holos': 'Вгадай, де це було!'},
         'tochky': tochky,
         'kinets': kinets('Скільки вгадали?', 'Більше раундів — у грі на карті. Ця вулиця:',
                          posylannia_vulytsi(slug) if slug else f'{ADRESA_SAITU}/zahlushka/hra/', 'Скільки вгадали?')}
    S['vstup']['tryvalist'] = tryv(S['vstup']['holos'], 2.5, 0)
    return S


# ------------------------------------------------------------------ група 4: таймлапс і переліт

def taimlaps(B: Baza, pivrichchia: bool = True):
    import h3
    riven = 7
    rows = B.con.execute('SELECT e.data_podii, l.lat, l.lon FROM event e JOIN location l USING(location_id) '
                         'WHERE e.chutlyva = 0 AND e.data_podii IS NOT NULL').fetchall()
    po_rokakh = Counter(d[:4] for d, _, _ in rows)
    naibilshe = max(po_rokakh.values())
    # рік — якщо в ньому щонайменше десята частина подій найповнішого року (правило roky_danykh сайту і звіту)
    roky = sorted(int(r) for r, n in po_rokakh.items() if n * 10 >= naibilshe and r.isdigit())
    periody = []
    for r in roky:
        if pivrichchia:
            periody += [(r, 1), (r, 2)]
        else:
            periody.append((r, 0))
    ostannii = max(d for d, _, _ in rows)[:7]
    periody = [(r, h) for r, h in periody if f'{r}-{"01" if h < 2 else "07"}' <= ostannii]
    def nomer(d):
        r, m = int(d[:4]), int(d[5:7])
        k = (r, 0) if not pivrichchia else (r, 1 if m <= 6 else 2)
        return periody.index(k) if k in periody else None
    lich = defaultdict(lambda: [0] * len(periody))
    for d, la, lo in rows:
        i = nomer(d)
        if i is None:
            continue
        lich[h3.latlng_to_cell(la, lo, riven)][i] += 1
    for c in lich:                                    # наростання: сума від початку
        for i in range(1, len(periody)):
            lich[c][i] += lich[c][i - 1]
    lich = {c: n for c, n in lich.items() if n[-1] >= 3}
    kintsevi = sorted(n[-1] for n in lich.values())
    mezhi = [kintsevi[int(len(kintsevi) * q)] for q in (0.2, 0.4, 0.6, 0.88)]   # шкала частками MV-55 — за кінцевими
    def klas(n):
        return 0 if n == 0 else 1 + sum(n >= m for m in mezhi)
    ranh = {n: i for i, n in enumerate(kintsevi)}
    hmax = kintsevi[int(len(kintsevi) * 0.99)]
    fs = []
    for c, n in lich.items():
        q = (sum(1 for x in kintsevi if x < n[-1]) + sum(1 for x in kintsevi if x == n[-1]) / 2) / len(kintsevi)
        kon = [[round(lo, 5), round(la, 5)] for la, lo in h3.cell_to_boundary(c)]
        kon.append(kon[0])
        fs.append({'type': 'Feature', 'geometry': {'type': 'Polygon', 'coordinates': [kon]},
                   'properties': {'k': [klas(x) for x in n], 'v': 1 if q >= 0.88 else 0, 'q': round(q, 3),
                                  'h': round(2600 * math.sqrt(min(1, n[-1] / hmax)), 0)}})
    pidpys = lambda r, h: f'{r}' if not h else f'{r}, {"I" if h == 1 else "II"} півріччя'
    per = []
    for i, (r, h) in enumerate(periody):
        n = sum(1 for d, _, _ in rows if nomer(d) is not None and nomer(d) <= i)
        per.append({'mitka': pidpys(r, h), 'mitka_mala': 'Події в даних, наростаючим підсумком', 'tekst': f'{chyslo(n)} подій з точкою',
                    'holos': '', 'tryvalist': 2.0})
    per[0]['holos'] = f'Дві тисячі {ROKY_SLOVAMY.get(periody[0][0], "")} рік.'
    per[0]['tryvalist'] = tryv(per[0]['holos'], 2.0, 0.4)
    per[-1]['holos'] = 'І так — до сьогодні.'
    vsogo = len(rows)
    S = {
        'nazva': 'Таймлапс: події в даних Києва', 'shablon': 'taimlaps', 'hrupa': 4, 'muzyka': 'misto',
        'opys': (f'Соти H3 рівня {riven}: скільки подій з точкою (без чутливих) накопичилось у даних за півріччями. '
                 f'Роки — ті, де даних щонайменше десята частина найповнішого року: {roky[0]}–{roky[-1]} (пробний випуск {B.versiia}; '
                 f'10 років — після повного Києва). Росте кількість рішень у даних, а не «злочинність».'),
        'vstup': {'mitka': 'Місто згори', 'tekst': f'Київ у даних: {roky[0]}–{roky[-1]}',
                  'pidtekst': f'Пробні дані — {len(roky)} {vidminok(len(roky), ("рік", "роки", "років"))}. 10 років — після повного Києва',
                  'holos': f'Київ у даних судів. Поки що — {len(roky)} {vidminok(len(roky), ("рік", "роки", "років"))}; десять — згодом.'},
        'periody': per, 'soty': {'type': 'FeatureCollection', 'features': fs},
        'vershyny': {'mitka': 'Вершини', 'tekst': 'Стовпчиком — найгустіші 12\u00a0% сот',
                     'pidpys': f'Разом {chyslo(vsogo)} подій, що дійшли до суду. Колір — кількість, не небезпека.',
                     'holos': 'А тепер — вершини: дванадцять відсотків сот, де подій у даних найбільше. Колір — це кількість, а не небезпека.'},
        'kinets': kinets('А що під боком у вас?', 'Карта Києва з сотами й вершинами:', f'{ADRESA_SAITU}/karta/',
                         'А що під боком у вас? Карта — за посиланням.'),
    }
    S['vstup']['tryvalist'] = tryv(S['vstup']['holos'], 3.5, 0)
    S['vershyny']['tryvalist'] = tryv(S['vershyny']['holos'], 6.5, 1.2)
    return S


def perelit(B: Baza, slug: str):
    v = B.vulytsia(slug)
    rayon = B.rayon_vulytsi(v)
    podii = B.podii_vulytsi(v)
    t = B.tsentr(podii)
    rt = B.tsentr([B.dn.podii[i] for x in B.dn.vulytsi.values() if B.rayon_vulytsi(x) == rayon for i in x.nedavni[:50]])
    vsogo = sum(1 for p in B.dn.podii if p.lat is not None and not p.chutlyva and p.rik and p.rik >= 2024)
    stops = [
        {'lat': 50.452, 'lon': 30.523, 'zoom': 10.2, 'mitka': 'Київ', 'tekst': f'{chyslo(vsogo)} подій у даних', 'pidtekst': 'з точкою, за 2024–2026',
         'holos': f'Київ. Майже {round(vsogo, -3) // 1000} тисяч подій з рішень судів.', 'lit': 3.2},
        {'lat': round(rt[0], 5), 'lon': round(rt[1], 5), 'zoom': 12.6, 'pitch': 30, 'mitka': 'Район', 'tekst': f'{rayon} район',
         'holos': f'{rayon} район.', 'lit': 2.4},
        {'lat': round(t[0], 6), 'lon': round(t[1], 6), 'zoom': 15.6, 'pitch': 50, 'mitka': 'Вулиця', 'tekst': v.nazva,
         'pidtekst': f'{chyslo(len(podii))} подій з точкою за 2024–2026', 'holos': f'{v.nazva}. Що болить вашому будинку?', 'lit': 2.6},
    ]
    for s in stops:
        s['tryvalist'] = tryv(s['holos'], s['lit'] + 2.5, s['lit'] * 0.7)
    S = {'nazva': f'Переліт: {v.nazva}', 'shablon': 'perelit', 'hrupa': 4, 'muzyka': 'misto', 'pidsvitka': B.osm_nazva(v),
         'opys': f'Переліт від України до вулиці. Числа — з випуску {B.versiia}.',
         'vstup': {'mitka': 'Місто згори', 'tekst': 'Україна', 'pidtekst': 'Летимо до вашої вулиці', 'holos': 'Україна. Летимо до вашої вулиці.'},
         'tochky': stops,
         'kinets': kinets('Що болить вашому будинку', 'Скарги мешканців і події з рішень судів — по кожному будинку:', posylannia_vulytsi(slug),
                          'Що болить вашому будинку — дивіться на сторінці вулиці.')}
    S['vstup']['tryvalist'] = tryv(S['vstup']['holos'], 3.0, 0)
    return S


# ------------------------------------------------------------------ групи 5–7: картки

def kartky(B, nazva, hrupa, mitka_vstupu, tekst_vstupu, karty, kin, muzyka='spokii', kamera=None):
    for k in karty:
        k['tryvalist'] = tryv(k['holos'], 4.5, 1.1 if k is karty[0] else 0)
    S = {'nazva': nazva, 'shablon': 'kartky', 'hrupa': hrupa, 'muzyka': muzyka, 'opys': f'Числа — з випуску {B.versiia}.',
         'vstup': {'mitka': mitka_vstupu, 'tekst': tekst_vstupu, 'holos': tekst_vstupu + '.'}, 'tochky': karty, 'kinets': kin}
    if kamera:
        S['kamera'] = kamera
    S['vstup']['tryvalist'] = tryv(S['vstup']['holos'], 3.0, 0)
    return S


def yak_pratsiuie(B: Baza):
    n = sum(1 for p in B.dn.podii if p.rik and p.rik >= 2024 and not p.chutlyva)
    vul = sum(1 for v in B.dn.vulytsi.values() if v.nedavni)
    return kartky(B, 'Як це працює: звідки дані', 5, 'Як це працює', 'Звідки ці дані', [
        {'mitka': 'Джерело', 'tekst': 'Рішення судів з державного реєстру — лише те, що дійшло до суду',
         'holos': 'Джерело — рішення судів з державного реєстру. Лише те, що дійшло до суду.'},
        {'mitka': 'Що ми з ними робимо', 'chyslo': chyslo(n), 'tekst': 'подій з точкою на карті за 2024–2026',
         'holos': f'З рішень ми дістаємо подію і місце. Таких подій — {n}.'},
        {'mitka': 'Чого ми не робимо', 'tekst': 'Не оцінка місця й не прогноз. Колір — скільки подій у даних, не небезпека',
         'holos': 'Ми не оцінюємо місця й не прогнозуємо. Колір на карті — це кількість, а не небезпека.'},
        {'mitka': 'Ваша вулиця', 'chyslo': chyslo(vul), 'tekst': 'вулиць Києва зі своєю сторінкою',
         'holos': f'{vul} вулиць Києва вже мають свою сторінку.'},
    ], kinets('Як ми працюємо з даними', 'Джерела, межі й що ми не показуємо:', f'{ADRESA_SAITU}/pro-dani/',
              'Як ми працюємо з даними — за посиланням.'))


def shcho_buvaie(B: Baza, stattia: str = 'ст.130 КУпАП'):
    rows = [p for p in B.dn.podii if p.stattia and p.stattia.startswith(stattia) and p.rik and p.rik >= 2024]
    roky = Counter(p.rik for p in rows)
    hod = Counter(int(p.chas.split(':')[0]) for p in rows if p.chas and re.match(r'^\d{1,2}:', p.chas))
    nich = sum(n for h, n in hod.items() if h >= 22 or h < 6)
    dni = Counter()
    import datetime
    for p in rows:
        try:
            dni[datetime.date.fromisoformat(p.data).weekday()] += 1
        except (TypeError, ValueError):
            pass
    DNI = ['понеділок', 'вівторок', 'середа', 'четвер', "п'ятниця", 'субота', 'неділя']
    den, n_d = dni.most_common(1)[0]
    nazva = B.D.vyd_lyudskoyu(rows[0].stattia, rows[0].vyd)
    z_hod = sum(hod.values()) or 1
    return kartky(B, f'Що буває за {stattia}', 6, 'Що буває за…', f'{stattia}: {nazva.lower()}', [
        {'mitka': f'{stattia} · Київ · 2024–2026', 'chyslo': chyslo(len(rows)), 'tekst': 'справ у даних',
         'pidpys': ' · '.join(f'{r} — {chyslo(roky[r])}' for r in sorted(roky)) + ' (2026 — неповний)',
         'holos': f'За три роки в даних — {len(rows)} справ за цією статтею.'},
        {'mitka': 'Коли', 'chyslo': f'{round(100 * nich / z_hod)} %', 'tekst': 'випадків — між 22:00 і 6:00',
         'pidpys': f'Найчастіше — {DNI[den]} ({chyslo(n_d)}). Серед справ, де в рішенні є час.',
         'holos': f'{round(100 * nich / z_hod)} відсотків — уночі, між двадцять другою і шостою. Найчастіше — {DNI[den] if den != 2 else "у середу"}.'},
        {'mitka': 'Чим закінчуються', 'tekst': 'Частки рішень і строки — у розділі «Судова практика»',
         'pidpys': 'У пробних даних результатів справ ще немає — додамо після перевірки точності.',
         'holos': 'Чим закінчуються такі справи — покажемо в розділі «Судова практика», щойно перевіримо точність.'},
    ], kinets('Як суди Києва вирішують справи', 'за вашою статтею — розділ «Судова практика»:', f'{ADRESA_SAITU}/sudova-praktyka/',
              'Як суди Києва вирішують справи за вашою статтею — за посиланням.'), muzyka='vechir')


def istoriia_danykh(B: Baza, vyd: str = 'ДТП'):
    rows = [p for p in B.dn.podii if p.vyd == vyd and p.rik and p.rik >= 2024 and p.chas and re.match(r'^\d{1,2}:', p.chas)]
    hod = Counter(int(p.chas.split(':')[0]) % 24 for p in rows)
    pik, n_pik = hod.most_common(1)[0]
    nich = min(range(24), key=lambda h: hod.get(h, 0))
    vechir = sum(hod[h] for h in range(16, 20))
    return kartky(B, 'Історія з даних: коли ДТП', 7, 'Історії з даних', 'О котрій годині ДТП, що дійшли до суду', [
        {'mitka': 'ДТП · Київ · 2024–2026', 'chyslo': chyslo(len(rows)), 'tekst': 'ДТП з часом у рішенні суду',
         'holos': f'{len(rows)} ДеТеПе, де в рішенні суду вказано час.'},
        {'mitka': 'Пік', 'chyslo': f'{pik}:00–{pik + 1}:00', 'tekst': f'{chyslo(n_pik)} випадків — найбільше за годину доби',
         'pidpys': f'з 16:00 до 20:00 — {round(100 * vechir / len(rows))} % усіх', 'holos': f'Найбільше — з {pik} до {pik + 1} години. '
         f'А з шістнадцятої до двадцятої — {round(100 * vechir / len(rows))} відсотків усіх.'},
        {'mitka': 'Найтихіше', 'chyslo': f'{nich}:00–{nich + 1}:00', 'tekst': f'{chyslo(hod.get(nich, 0))} випадків за три роки',
         'pidpys': 'Це кількість у даних, а не ризик: уночі менше машин.', 'holos': f'Найменше — з {nich} до {nich + 1} години. Це кількість, а не ризик.'},
    ], kinets('Візуал для медіа', 'Пишете про місто — беріть цифри й карту з підписом «Джерело: Моя вулиця»:', f'{ADRESA_SAITU}/pro-dani/',
              'Пишете про місто? Беріть цифри й карту — посилання в описі.'), muzyka='misto')


# ------------------------------------------------------------------ запуск

def pidpys_merezhi(S, kanal='tiktok'):
    """Підпис під роликом: одне посилання — на сторінку цього місця, з міткою джерела (KOMPAS, розд. 5)."""
    pos = S['kinets']['posylannia']
    return f'{S["nazva"]}. {pos}?dzherelo={kanal}&rolyk={S["shablon"]}'


def main(argv=None):
    global MIRIATY_HOLOS
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('baza', type=Path)
    a.add_argument('--typ', required=True, choices=sorted(GRUPY))
    a.add_argument('--vulytsia', help='slug сторінки вулиці')
    a.add_argument('--podiia', help='event_id для istoriia')
    a.add_argument('--ids', help='id подій колоди через кому (vhadai)')
    a.add_argument('--stattia', default='ст.130 КУпАП')
    a.add_argument('--pereimenuvannya', type=Path)
    a.add_argument('--mezhi-rayoniv', type=Path, default=KORIN / 'data' / 'borders.json')
    a.add_argument('--1551', dest='d1551', help='тека гілки dani-1551 (skargy-*.tsv.gz)')
    a.add_argument('--perekazy', help='перекази ШІ {event_id: текст} (dani-edrsr/src/perekazy_istorii.py)')
    a.add_argument('--koloda', help='колода гри koloda-<дата>.json')
    a.add_argument('--miriaty-holos', action='store_true', help='тривалість відрізків — за справжнім синтезом Piper')
    a.add_argument('--vykhid', type=Path, default=TUT / 'stsenarii' / 'avto')
    a.add_argument('--imia', help='назва файлу без .json')
    arg = a.parse_args(argv)
    MIRIATY_HOLOS = arg.miriaty_holos
    B = Baza(arg)
    t = arg.typ
    if t == 'shcho_bolyt':
        S = shcho_bolyt(B, arg.vulytsia)
    elif t == 'istoriia':
        S = istoriia(B, arg.vulytsia, arg.podiia)
    elif t == 'vhadai':
        S = vhadai(B, arg.ids.split(','))
    elif t == 'taimlaps':
        S = taimlaps(B)
    elif t == 'perelit':
        S = perelit(B, arg.vulytsia)
    elif t == 'yak_pratsiuie':
        S = yak_pratsiuie(B)
    elif t == 'shcho_buvaie':
        S = shcho_buvaie(B, arg.stattia)
    elif t == 'istoriia_danykh':
        S = istoriia_danykh(B)
    else:
        raise SystemExit(f'тип {t}: генератор поки не вміє (tur — сценарій вручну з колоди)')
    S['versiia'] = B.versiia
    S['pidpys_merezhi'] = pidpys_merezhi(S)
    S['znimky'] = [1, 2, max(1, len(S.get('tochky', S.get('periody', []))) - 1 + (2 if t == 'taimlaps' else 1))]
    imia = arg.imia or f'{t}-{arg.vulytsia or B.versiia}'
    z = perevirka.pereviryty(S, imia)
    if z:
        raise SystemExit('Сценарій не пройшов перевірку:\n  ' + '\n  '.join(z))
    arg.vykhid.mkdir(parents=True, exist_ok=True)
    f = arg.vykhid / f'{imia}.json'
    f.write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{f}: {perevirka.tryvalist(S):.1f} с, група {GRUPY[t][0]} «{GRUPY[t][1]}», перевірку пройдено')
    if getattr(B, 'pokryttia_1551', None):
        zn, vs, _ = B.pokryttia_1551
        print(f'  1551: зіставлено з вулицями сайту {zn} з {vs} звернень ({100 * zn / max(1, vs):.0f} %)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
