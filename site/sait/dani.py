# -*- coding: utf-8 -*-
"""Дані для сайту «Моя вулиця» (ZAVDANNYA-10): з випуску events-<дата>.db — у числа для сторінок.

Що тут:
  * зведення назв вулиць до однієї (таблиця address — назви з OpenStreetMap, довідник перейменувань);
  * сторінка вулиці: роки, «години × дні», будинки числом, види, що вирізняють вулицю;
  * шестикутники H3 рівня 9 для головної карти.

Правила (AGENTS.md, MV-3, MV-4):
  * чутливі справи (прапорець chutlyva) і подібні до них за статтею — лише числом у шестикутнику:
    їх немає у видах, будинках, точках і історіях;
  * сайт нічого не вигадує: якщо подій мало, розділ не показується.
"""
from __future__ import annotations

import csv
import json
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

try:
    import h3
except ImportError:  # pragma: no cover — без h3 немає лише карти шестикутників
    h3 = None

RIVEN_H3 = 9
ROKY = list(range(2016, 2027))      # MV-2: Київ, 2016–2026

# Додатково до прапорця chutlyva: статті, що стосуються домашнього насильства й дітей, але
# не позначені у випуску (MV-4). На сайті вони — лише числом у шестикутнику.
CHUTLYVI_STATTI = re.compile(
    r'ст\.390-1 КК|заборонного припису|ст\.173-2|ст\.126-1|ст\.15[2-6] КК|ст\.180 КУпАП|ст\.180-1 КУпАП'
    r'|ст\.184 КУпАП|сексуальн|ст\.135 КК|ст\.166 КК|неповнолітн|дит')

# Слова, яких на сайті немає (docs/STYL.md): ні в наших текстах, ні в уривках історій.
ZABORONENI_SLOVA = re.compile(r'небезпечн|безпечн|рейтинг', re.I)

# Номер будинку в тексті: «вул. Хрещатик, 42», «буд. 5», «будинку 12».
NOMER_BUDYNKU = re.compile(r'(вул|просп|бульв|пров|пл)\.?\s+[^,;]{1,50},\s*\d|буд\w*\.?\s*№?\s*\d', re.I)

# ---------------------------------------------------------------- назви вулиць

TYPY = {
    'вул.': 'вулиця', 'вулиця': 'вулиця', 'просп.': 'проспект', 'проспект': 'проспект',
    'бульв.': 'бульвар', 'бульвар': 'бульвар', 'пл.': 'площа', 'площа': 'площа',
    'пров.': 'провулок', 'провулок': 'провулок', 'шосе': 'шосе', 'узвіз': 'узвіз',
    'наб.': 'набережна', 'набережна': 'набережна', 'майдан': 'майдан', 'проїзд': 'проїзд',
    'алея': 'алея', 'дорога': 'дорога', 'тупик': 'тупик', 'лінія': 'лінія', 'спуск': 'спуск',
    'сквер': 'сквер', 'парк': 'парк', 'міст': 'міст',
}
# Слова типу, що стоять після назви («Харківське шосе», «Кільцева дорога»).
TYPY_PISLYA = {'шосе', 'дорога', 'узвіз', 'проїзд', 'набережна', 'площа', 'провулок',
               'бульвар', 'лінія', 'тупик', 'спуск', 'вулиця', 'проспект', 'алея', 'міст', 'майдан'}

APOSTROFY = str.maketrans({'ʼ': "'", '’': "'", '`': "'", '‘': "'", '´': "'"})


def chystyi(tekst: str) -> str:
    tekst = unicodedata.normalize('NFC', tekst or '').translate(APOSTROFY)
    return re.sub(r'\s+', ' ', tekst).strip()


def rozibraty_vulytsiu(tekst: str) -> tuple[str, str] | None:
    """«вул. М. Бойчука» → ('вулиця', 'М. Бойчука'); «Йорданська вулиця» → ('вулиця', 'Йорданська')."""
    tekst = chystyi(tekst).strip(' ,')
    if not tekst:
        return None
    # «С.Бандери» → «С. Бандери»
    tekst = re.sub(r'(?<=\b[А-ЯІЇЄҐA-Zа-яіїєґ])\.(?=[А-ЯІЇЄҐа-яіїєґ])', '. ', tekst)
    tekst = re.sub(r'(?<=\bАк)\.(?=\S)', '. ', tekst)
    # «… поблизу житлового будинку», «… у дворі будинку», «… між будинками» — не частина назви.
    tekst = re.sub(r'(\s+[а-яіїєґ]+){1,3}\s+будин\w*.*$', '', tekst)
    # «О Теліги» → «О. Теліги» (ініціал без крапки)
    tekst = re.sub(r'(?<=\s)([А-ЯІЇЄҐ])\s(?=[А-ЯІЇЄҐ][а-яіїєґ\'])', r'\1. ', tekst)
    slova = tekst.split(' ')
    typ = None
    if slova[0].lower() in TYPY and len(slova) > 1:
        typ = TYPY[slova[0].lower()]
        slova = slova[1:]
    # «пл. Майдан Незалежності» — справжній тип стоїть першим словом назви.
    if len(slova) > 1 and slova[0].lower() in ('майдан', 'шосе', 'узвіз', 'набережна', 'дорога'):
        typ = TYPY[slova[0].lower()]
        slova = slova[1:]
    # «вул. Харківське шосе» — справжній тип стоїть у кінці.
    if len(slova) > 1 and slova[-1].lower() in TYPY_PISLYA:
        typ = TYPY[slova[-1].lower()]
        slova = slova[:-1]
    elif typ is None:
        for i, s in enumerate(slova):
            if s.lower() in TYPY and s.islower():
                typ = TYPY[s.lower()]
                slova = slova[:i] + slova[i + 1:]
                break
    if typ is None or not slova:
        return None
    nazva = ' '.join(slova)
    # Перша літера назви велика («Кільцева Дорога» і «Кільцева дорога» — одне).
    return typ, nazva


def kliuch(nazva: str) -> tuple[str, ...]:
    """Ключ для порівняння: без регістру, апострофів, лапок; «ґ» = «г»; латинське I = І."""
    t = nazva.lower().replace("'", '').replace('ґ', 'г').replace('i', 'і')
    t = re.sub(r'[«»"“”„]', '', t).replace('-', ' ')
    return tuple(s for s in t.split(' ') if s)


def sumisni(lok: tuple[str, ...], kan: tuple[str, ...]) -> tuple[bool, int, int]:
    """Чи може назва з тексту (lok) бути скороченням канонічної (kan).

    Повертає (так/ні, скільки слів kan пропущено, скільки слів скорочено).
    Останнє слово (прізвище чи головне слово) має збігатися точно.
    «м.» відповідає «миколи», «ак.» — «академіка»."""
    if not lok or not kan or lok[-1] != kan[-1]:
        return False, 0, 0
    i = 0
    propushcheno = skorocheno = 0
    for s in lok[:-1]:
        while i < len(kan) - 1:
            k = kan[i]
            i += 1
            if s == k:
                break
            if s.endswith('.') and len(s) > 1 and k.startswith(s[:-1]):
                skorocheno += 1
                break
            propushcheno += 1
        else:
            return False, 0, 0
    propushcheno += (len(kan) - 1) - i
    return True, propushcheno, skorocheno


def osnova_zbihaietsia(a: str, b: str) -> bool:
    """«відрадному» і «відрадний»: спільний початок ≥ 5 літер, різниця — лише закінчення (до 3 літер)."""
    if a.endswith('.') or b.endswith('.'):
        return False
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    return n >= 5 and len(a) - n <= 3 and len(b) - n <= 3


def odna_odrukivka(a: str, b: str) -> bool:
    """Рядки відрізняються однією літерою (заміна, пропуск або зайва)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    if len(a) > len(b):
        a, b = b, a
    for i in range(len(b)):
        if b[:i] + b[i + 1:] == a:
            return True
    return False


TRANSLIT = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'h', 'ґ': 'g', 'д': 'd', 'е': 'e', 'є': 'ie', 'ж': 'zh',
    'з': 'z', 'и': 'y', 'і': 'i', 'ї': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
    'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
    'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ю': 'iu', 'я': 'ia', 'ь': '', "'": '', 'ы': 'y', 'э': 'e', 'ё': 'io',
}
NA_POCHATKU = {'є': 'ye', 'ї': 'yi', 'й': 'y', 'ю': 'yu', 'я': 'ya'}


def translit(tekst: str) -> str:
    """Транслітерація за постановою КМУ № 55 (2010): «Хрещатик» → «khreshchatyk»."""
    vykhid = []
    for slovo in re.split(r'[^0-9a-zа-яґєіїё\']+', tekst.lower()):
        if not slovo:
            continue
        slovo = slovo.replace('зг', 'zgh')
        chastyny = []
        for i, b in enumerate(slovo):
            if i == 0 and b in NA_POCHATKU:
                chastyny.append(NA_POCHATKU[b])
            else:
                chastyny.append(TRANSLIT.get(b, b))
        s = ''.join(chastyny).replace("'", '')
        if s:
            vykhid.append(s)
    return '-'.join(vykhid)


def povna_nazva(typ: str, nazva: str) -> str:
    """Як людина пише: «вулиця Хрещатик», «проспект Валерія Лобановського»; прикметник — «Йорданська вулиця»."""
    slova = nazva.split(' ')
    if len(slova) == 1 and re.search(r'(ська|цька|зька|ий|ій|ське|цьке|не|ня|ова|ева|єва|ина|іна)$', nazva):
        return f'{nazva} {typ}'
    return f'{typ} {nazva}'


@dataclass
class Vulytsia:
    slug: str
    nazva: str                     # як показуємо: «вулиця Хрещatик»
    typ: str
    korotka: str                   # без типу: «Хрещатик»
    dzherelo: str                  # osm | tekst
    varianty: Counter = field(default_factory=Counter)   # як ця вулиця записана в місцях подій
    rayony: Counter = field(default_factory=Counter)
    podii: list = field(default_factory=list)            # індекси подій


@dataclass
class Zvedennia:
    vulytsi: dict                  # slug → Vulytsia
    varianty: dict                 # (typ, nazva з тексту) → slug
    sumnivni: list                 # [(варіант, куди злито, чому)]
    neodnoznachni: list            # [(варіант, кандидати)]
    pereimenuvannia: list          # [(стара повна назва, slug нової або [slugs])]


def kanonichni_z_osm(con: sqlite3.Connection) -> dict:
    """Канонічні назви — з таблиці address (OpenStreetMap): (тип, ключ назви) → (тип, назва)."""
    kan = {}
    for (nazva,) in con.execute('SELECT nazva FROM address ORDER BY address_id'):
        vul = nazva.rsplit(',', 1)[0] if ',' in nazva else nazva
        r = rozibraty_vulytsiu(vul)
        if not r:
            continue
        typ, n = r
        kan.setdefault((typ, kliuch(n)), (typ, n, vul))
    return kan


def prochytaty_pereimenuvannia(shlyakh: Path | None) -> list[dict]:
    if not shlyakh or not Path(shlyakh).is_file():
        return []
    with open(shlyakh, encoding='utf-8') as f:
        return [r for r in csv.DictReader(f) if r.get('stara_nazva') and r.get('nova_nazva')]


def zvesty_nazvy(varianty: Counter, kanon: dict, pereim: list[dict]) -> tuple[dict, list, list]:
    """Кожному варіанту (тип, назва з тексту) — канонічний (тип, назва, джерело).

    Повертає (зіставлення, сумнівні, неоднозначні)."""
    za_ostannim = defaultdict(list)
    for (typ, k), v in kanon.items():
        za_ostannim[k[-1]].append((typ, k, v))
    stari = {}
    for r in pereim:
        stari.setdefault((r.get('typ') or 'вулиця', kliuch(chystyi(r['stara_nazva']))), []).append(r)

    zistavlennia, sumnivni, neodnoznachni = {}, [], []
    kanon_spysok = sorted((typ, k, v) for (typ, k), v in kanon.items())
    for (typ, nazva) in sorted(varianty):
        k = kliuch(nazva)
        if (typ, k) in kanon:
            zistavlennia[(typ, nazva)] = kanon[(typ, k)] + ('osm',)
            continue
        # Перейменування: стара назва → нова, якщо нова є в OSM.
        if (typ, k) in stari:
            novi = {(r.get('typ') or 'вулиця', kliuch(chystyi(r['nova_nazva']))) for r in stari[(typ, k)]}
            novi = [n for n in novi if n in kanon]
            if len(novi) == 1:
                zistavlennia[(typ, nazva)] = kanon[novi[0]] + ('pereimenuvannia',)
                continue
        kandydaty = []
        for (t2, k2, v) in za_ostannim.get(k[-1], []):
            ok, prop, skor = sumisni(k, k2)
            if ok:
                kandydaty.append((t2 != typ, prop, -skor, v))
        vidminok = False
        if not kandydaty:
            # «просп. Відрадному», «вул. Полярній» — назва у відмінку: зіставляємо за основою слів.
            for (t2, k2, v) in kanon_spysok:
                if t2 == typ and len(k2) == len(k) and all(a == b or osnova_zbihaietsia(a, b) for a, b in zip(k, k2)):
                    kandydaty.append((False, 0, 0, v))
            # «вул. Федорова Івана» — ті самі слова в іншому порядку.
            if not kandydaty:
                for (t2, k2, v) in kanon_spysok:
                    if len(k2) > 1 and sorted(k2) == sorted(k):
                        kandydaty.append((t2 != typ, 0, 0, v))
            # «Лобановсього» — одна літера пропущена чи зайва в останньому слові (одруківка).
            if not kandydaty and len(k[-1]) >= 7:
                for (t2, k2, v) in kanon_spysok:
                    if odna_odrukivka(k[-1], k2[-1]):
                        ok, prop, skor = sumisni(k[:-1] + (k2[-1],), k2)
                        if ok and not prop:
                            kandydaty.append((t2 != typ, 0, -skor, v))
            vidminok = bool(kandydaty)
        if not kandydaty:
            continue
        kandydaty.sort(key=lambda x: (x[0], x[1], x[2], x[3][2]))
        naikrashchi = [c for c in kandydaty if c[:3] == kandydaty[0][:3]]
        if len({c[3] for c in naikrashchi}) > 1:
            neodnoznachni.append(((typ, nazva), sorted({c[3] for c in naikrashchi})))
            continue
        inshyi_typ, prop, _, v = kandydaty[0]
        if inshyi_typ and prop and len({c[3] for c in kandydaty}) > 1:
            continue                       # інший тип, пропущені слова і є з чого вибирати — не зливаємо
        zistavlennia[(typ, nazva)] = v + ('osm',)
        if prop or inshyi_typ or vidminok:
            prychyna = ['назва у відмінку, з одруківкою або слова в іншому порядку'] if vidminok else []
            if prop:
                prychyna.append(f'пропущено слів: {prop}')
            if inshyi_typ:
                prychyna.append(f'у тексті «{typ}», в OpenStreetMap «{v[0]}»')
            sumnivni.append((f'{typ} {nazva}', v[2], '; '.join(prychyna)))
    return zistavlennia, sumnivni, neodnoznachni


# ---------------------------------------------------------------- райони

def tochka_v_mnohokutnyku(lat: float, lon: float, poly: list) -> bool:
    vseredyni = False
    j = len(poly) - 1
    for i in range(len(poly)):
        yi, xi = poly[i]
        yj, xj = poly[j]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi:
            vseredyni = not vseredyni
        j = i
    return vseredyni


class Rayony:
    """Межі районів Києва (data/borders.json: назва → [[lat, lon], …], OpenStreetMap)."""

    def __init__(self, shlyakh: Path | None):
        self.mezhi = {}
        if shlyakh and Path(shlyakh).is_file():
            for nazva, poly in json.loads(Path(shlyakh).read_text(encoding='utf-8')).items():
                if poly and isinstance(poly[0][0], (int, float)):
                    poly = [poly]
                ramka = [(min(p[0] for p in pl), max(p[0] for p in pl), min(p[1] for p in pl), max(p[1] for p in pl))
                         for pl in poly]
                self.mezhi[nazva] = list(zip(poly, ramka))
        self._kesh = {}

    def rayon(self, lat: float, lon: float) -> str | None:
        k = (round(lat, 4), round(lon, 4))
        if k in self._kesh:
            return self._kesh[k]
        r = None
        for nazva in sorted(self.mezhi):
            for poly, (a, b, c, d) in self.mezhi[nazva]:
                if a <= lat <= b and c <= lon <= d and tochka_v_mnohokutnyku(lat, lon, poly):
                    r = nazva
                    break
            if r:
                break
        self._kesh[k] = r
        return r


# ---------------------------------------------------------------- події

@dataclass
class Podiia:
    event_id: str
    rik: int | None
    data: str | None
    chas: str | None
    vyd: str
    stattia: str
    fabula: str | None
    lat: float | None
    lon: float | None
    adresa: str
    tochnist: str
    chutlyva: bool
    sota: str | None
    url: str | None


def vyd_lyudskoyu(stattia: str | None, vyd: str) -> str:
    """«ст.130 КУпАП · керування у стані сп'яніння» → «Керування у стані сп'яніння»."""
    t = (stattia or '').split('·', 1)[-1].strip() if stattia else ''
    if not t or t.startswith('ст.'):
        t = {'ДТП': 'ДТП', 'ДОР': 'Порушення на дорозі', 'ГП': 'Громадський порядок', 'НАР': 'Наркотики',
             'МАЙ': 'Майнові', 'АЛК': 'Торгівля алкоголем', 'НАС': 'Насильство'}.get(vyd, vyd)
    return t[:1].upper() + t[1:]


def prochytaty_podii(con: sqlite3.Connection) -> list[Podiia]:
    rows = con.execute('''
        SELECT e.event_id, e.data_podii, e.chas, e.vyd, e.stattia, e.fabula, e.chutlyva, e.sota,
               l.lat, l.lon, l.adresa, l.tochnist, d.url
        FROM event e LEFT JOIN location l ON l.location_id = e.location_id
        LEFT JOIN document d ON d.doc_id = e.doc_id
        WHERE e.doc_id NOT IN (SELECT doc_id FROM withdrawal)
        ORDER BY e.event_id''').fetchall()
    podii = []
    for (eid, data, chas, vyd, stattia, fabula, chut, sota, lat, lon, adresa, tochnist, url) in rows:
        rik = int(data[:4]) if data and data[:4].isdigit() else None
        chutlyva = bool(chut) or bool(CHUTLYVI_STATTI.search(stattia or ''))
        podii.append(Podiia(eid, rik, data, chas, vyd, stattia or '', fabula, lat, lon, adresa or '',
                            tochnist or '', chutlyva, sota, url))
    return podii


def tsentr_soty(sota: str) -> tuple[float, float] | None:
    """Сота випуску «i:j» (≈500 м, dani-edrsr/src/chutlyvi.py) → її центр."""
    try:
        i, j = sota.split(':')
        return int(i) * 0.0045, int(j) * 0.007
    except (ValueError, AttributeError):
        return None


def vulytsi_mistsia(adresa: str, tochnist: str) -> list[tuple[str, str, str | None]]:
    """Адреса місця → [(тип, назва, будинок)]. Перехрестя «А / Б» дає дві вулиці без будинку."""
    adresa = chystyi(adresa)
    if not adresa:
        return []
    chastyny = [c.strip() for c in adresa.split(' / ')] if ' / ' in adresa else [adresa]
    vykhid = []
    for ch in chastyny:
        budynok = None
        if ',' in ch:
            ch, budynok = [x.strip() for x in ch.rsplit(',', 1)]
        r = rozibraty_vulytsiu(ch)
        if r:
            vykhid.append((r[0], r[1], budynok if (tochnist == 'house' and len(chastyny) == 1) else None))
    return vykhid


# ---------------------------------------------------------------- збирання

@dataclass
class Dani:
    versiia: str
    podii: list
    vulytsi: dict
    zvedennia: Zvedennia
    misto_vydy: Counter
    soty: dict                                  # рівень H3 (7, 8, 9) → {клітинка: дані соти}
    vulytsi_podii: list = field(default_factory=list)
    rayony: object = None                       # межі районів (Rayony) — для назви району соти й пошуку


def ochyshchena_istoriia(fabula: str | None, mezha: int = 300) -> str | None:
    """Перші ~300 знаків фабули без імен і номерів квартир. None — якщо прибрати не вдалося."""
    if not fabula:
        return None
    t = chystyi(fabula)
    t = re.sub(r'ОСОБА_\d+', 'особа', t)
    t = re.sub(r'(в|у)?\s*(кв\.|квартир[аиіу]|квартирі)\s*(№\s*)?\d+[-\w]*', '', t, flags=re.I)
    t = re.sub(r'АДРЕСА_\d+', 'за адресою', t)
    t = re.sub(r'\b(АДРЕСА|ІНФОРМАЦІЯ|НОМЕР|ДАТА|ПІБ)_\d+', '…', t)
    # Номери будинків (MV-3: на безкоштовній сторінці немає адрес): «вул. Хрещатик, 42» → «вул. Хрещатик»,
    # «біля будинку 12» → «біля будинку», «буд. 5» → «будинку».
    t = re.sub(r'((?:вул|просп|пр-т|пр|бульв|пров|пл|наб|вулиц[яіі]|проспект[уі]?|бульвар[уі]?|провул[ок]\w*|площ[аіу]|шосе|узвіз)\.?\s+'
               r'[А-ЯІЇЄҐA-Z0-9][^,;.]{0,50}?)\s*,\s*(буд\.\s*|будинок\s*|№\s*)?\d+[\w/-]*', r'\1', t)
    t = re.sub(r'\b(будинок|будинку|будинком|будинка)\s*(№\s*)?\d+[а-яa-z]?([/-]\d*[а-яa-z]?)*', r'\1', t, flags=re.I)
    t = re.sub(r'\bбуд\.\s*(№\s*)?\d+[а-яa-z]?([/-]\d*[а-яa-z]?)*', 'будинку', t, flags=re.I)
    t = re.sub(r'№\s*\d+[\w/-]*', '', t)
    t = re.sub(r'\s+([,.;:])', r'\1', t)
    t = re.sub(r'\s{2,}', ' ', t).strip()
    if NOMER_BUDYNKU.search(t):
        return None
    # Імена, що могли лишитися: «Іванов І.І.», «гр. Петренко».
    if re.search(r'[А-ЯІЇЄҐ][а-яіїєґ\']+\s+[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.', t) or re.search(r'\bгр\.\s*[А-ЯІЇЄҐ]', t):
        return None
    if re.search(r'кв\.|квартир', t, re.I) or '_' in t:
        return None
    if ZABORONENI_SLOVA.search(t):
        return None
    t = t[:1].upper() + t[1:]
    if len(t) > mezha:
        t = t[:mezha].rsplit(' ', 1)[0].rstrip(',;:—-') + '…'
    return t


def zibraty_dani(baza: Path, pereimenuvannia: Path | None, mezhi_rayoniv: Path | None) -> Dani:
    con = sqlite3.connect(f'file:{baza}?mode=ro', uri=True)
    versiia = (con.execute('SELECT versiia FROM release ORDER BY versiia DESC LIMIT 1').fetchone() or ['?'])[0]
    podii = prochytaty_podii(con)
    kanon = kanonichni_z_osm(con)
    pereim = prochytaty_pereimenuvannia(pereimenuvannia)
    rayony = Rayony(mezhi_rayoniv)

    # 1. Які варіанти назв вулиць є в місцях подій.
    varianty = Counter()
    vulytsi_podii = []
    for i, p in enumerate(podii):
        vv = vulytsi_mistsia(p.adresa, p.tochnist) if p.lat is not None else []
        vulytsi_podii.append(vv)
        for (t, n, _) in vv:
            varianty[(t, n)] += 1

    # 2. Зведення: спершу до OpenStreetMap; що не знайшлося — між собою (повна назва бере скорочену).
    zist, sumnivni, neodnoz = zvesty_nazvy(varianty, kanon, pereim)
    # Неоднозначні («вулиця Т. Шевченка»: бульвар, площа чи провулок?) — до кандидата, у якого
    # в даних уп'ятеро більше подій, ніж у наступного; інакше лишаються окремою сторінкою.
    vaha = Counter()
    for v, kv in zist.items():
        vaha[kv[:3]] += varianty[v]
    nevyrisheni = []
    for v, kandydaty in neodnoz:
        ryad = sorted(kandydaty, key=lambda c: (-vaha[c], c[2]))
        if vaha[ryad[0]] >= 5 * max(vaha[ryad[1]], 1):
            zist[v] = ryad[0] + ('osm',)
            sumnivni.append((f'{v[0]} {v[1]}', ryad[0][2],
                             'кілька схожих вулиць; обрано ту, де в даних найбільше подій ('
                             + ', '.join(f'{c[2]} — {vaha[c]}' for c in ryad) + ')'))
        else:
            nevyrisheni.append((f'{v[0]} {v[1]}', [c[2] for c in ryad]))
    neodnoz = nevyrisheni
    zalyshok = Counter({v: n for v, n in varianty.items() if v not in zist})
    vlasni = {}
    for (t, n), _ in sorted(zalyshok.items(), key=lambda x: (-len(kliuch(x[0][1])), -x[1], x[0])):
        vlasni.setdefault((t, kliuch(n)), (t, n, povna_nazva(t, n)))
    z2, s2, n2 = zvesty_nazvy(zalyshok, vlasni, [])
    for k, v in z2.items():
        zist[k] = v[:3] + ('tekst',)
    sumnivni += s2
    neodnoz += [(f'{v[0]} {v[1]}', [c[2] for c in k]) for v, k in n2]
    for v in zalyshok:
        if v not in zist:
            t, n = v
            zist[v] = (t, n, povna_nazva(t, n), 'tekst')

    # 3. Вулиці зі slug.
    vulytsi: dict[str, Vulytsia] = {}
    za_kanonom: dict[tuple, str] = {}
    zainiati = set()
    for v in sorted(zist, key=lambda v: (-varianty[v], v)):
        t, n, povna, dzh = zist[v]
        kk = (t, kliuch(n))
        if kk not in za_kanonom:
            # Адреса сторінки — з назви, як її пишуть: «velyka-vasylkivska», «kiltseva-doroha»,
            # «prospekt-valeriia-lobanovskoho»; слово «вулиця» не пишемо.
            slova = povna.split(' ')
            if t == 'вулиця' and 'вулиця' in slova:
                slova.remove('вулиця')
            baza_slug = translit(' '.join(slova))
            slug = baza_slug or 'vulytsia'
            nomer = 2
            while slug in zainiati:
                slug = f'{baza_slug}-{nomer}'
                nomer += 1
            zainiati.add(slug)
            za_kanonom[kk] = slug
            vulytsi[slug] = Vulytsia(slug, povna, t, n, 'osm' if dzh in ('osm', 'pereimenuvannia') else 'tekst')
        vulytsi[za_kanonom[kk]].varianty[f'{v[0]} {v[1]}'] += varianty[v]
    varianty_slug = {v: za_kanonom[(zist[v][0], kliuch(zist[v][1]))] for v in zist}

    # 4. Події на вулицях, райони.
    for i, (p, vv) in enumerate(zip(podii, vulytsi_podii)):
        bachyly = set()
        if p.chutlyva:
            continue                      # чутливі — лише числом у шестикутнику, не на вулиці
        for (t, n, _) in vv:
            slug = varianty_slug[(t, n)]
            if slug in bachyly:
                continue
            bachyly.add(slug)
            vulytsi[slug].podii.append(i)
            r = rayony.rayon(p.lat, p.lon)
            if r:
                vulytsi[slug].rayony[r] += 1

    # 5. Перейменування: стара назва → нова сторінка (для переадресації).
    slug_za_povnoyu = {}
    for s, v in vulytsi.items():
        slug_za_povnoyu[(v.typ, kliuch(v.korotka))] = s
    pereim_vykhid = defaultdict(set)
    for r in pereim:
        typ = r.get('typ') or 'вулиця'
        nova = slug_za_povnoyu.get((typ, kliuch(chystyi(r['nova_nazva']))))
        if nova and vulytsi[nova].podii:
            pereim_vykhid[(typ, chystyi(r['stara_nazva']))].add(nova)
    pereim_spysok = sorted((f'{t} {n}', sorted(s)) for (t, n), s in pereim_vykhid.items())

    # 6. Місто: види (для коефіцієнта локалізації) і соти.
    misto_vydy = Counter(vyd_lyudskoyu(p.stattia, p.vyd) for p in podii if p.lat is not None and not p.chutlyva)
    problemy = con.execute('SELECT problem_id, vyd, mekhanizm, status, lat, lon, podii FROM problem '
                           'WHERE lat IS NOT NULL ORDER BY podii DESC, problem_id').fetchall()
    soty = {}
    if h3 is not None:
        for riven in (7, 8, 9):
            soty[riven] = soty_rivnia(podii, vulytsi_podii, varianty_slug, problemy, riven)

    zv = Zvedennia(vulytsi, varianty_slug, sumnivni, neodnoz, pereim_spysok)
    con.close()
    return Dani(versiia, podii, vulytsi, zv, misto_vydy, soty, vulytsi_podii, rayony)


# ---------------------------------------------------------------- соти головної карти

# Сім груп карти (друге уточнення центрального чату до ZAVDANNYA-10): ДТП окремо від інших дорожніх.
HRUPY = [('dtp', 'ДТП'), ('dor', 'Дороги'), ('hp', 'Громадський порядок'), ('mai', 'Майно'),
         ('nar', 'Наркотики'), ('alk', 'Алкоголь'), ('nas', 'Насильство')]
HRUPA_VYDU = {'ДТП': 'dtp', 'ДОР': 'dor', 'ГП': 'hp', 'МАЙ': 'mai', 'НАР': 'nar', 'АЛК': 'alk', 'НАС': 'nas'}
OSTANNI_ROKY = 3

# «Що страждає» по групах — пошуком слів у фабулі. Окремого поля цілі у випуску немає, тому
# це наближення; у картці показуємо лише те, що трапляється щонайменше в 5 подіях соти.
# Насильство — лише числом, тож для нього нічого не шукаємо.
TSILI = {
    'mai': ('беруть', [
        ('телефони', re.compile(r'мобільн\w*\s+телефон|смартфон|iphone|айфон|телефон\w*\s+(марки|«|"|samsung|xiaomi|apple)', re.I)),
        ('авто', re.compile(r'заволоді\w*\s+(транспортн|автомоб)|автомобіл\w*\s+(марки|«)', re.I)),
        ('алкоголь', re.compile(r'горілк|коньяк|віскі|алкогольн\w+\s+напо|бренді|\bром\b', re.I)),
        ('велосипеди й самокати', re.compile(r'велосипед|самокат', re.I)),
        ('гаманці й гроші', re.compile(r'гаман|грошов\w+\s+кошт|готівк', re.I)),
        ('продукти', re.compile(r'\bкав[аиу]\b|ковбас|\bсир\w*\s|шоколад|м.яс', re.I)),
        ('косметику', re.compile(r'косметик|парфум|шампун|дезодорант|бритв', re.I)),
        ('ноутбуки й планшети', re.compile(r'ноутбук|планшет|macbook', re.I)),
    ]),
    'dtp': ('зіткнення з', [
        ('припаркованими авто', re.compile(r'припаркован|нерухом\w+\s+(авто|транспорт)', re.I)),
        ('огорожами й стовпами', re.compile(r'огорож|відбійн|бордюр|стовп|паркан|дерев', re.I)),
        ('громадським транспортом', re.compile(r'автобус|тролейбус|трамва|маршрутн', re.I)),
        ('пішоходами', re.compile(r'пішоход', re.I)),
        ('мото й велосипедами', re.compile(r'мотоцикл|мопед|скутер|велосипед', re.I)),
    ]),
    'nar': ('речовина', [
        ('PVP', re.compile(r'PVP|піровалерон', re.I)),
        ('метадон', re.compile(r'метадон', re.I)),
        ('метамфетамін', re.compile(r'метамфетамін', re.I)),
        ('амфетамін', re.compile(r'(?<!мет)амфетамін', re.I)),
        ('канабіс', re.compile(r'канабіс|марихуан|коноп', re.I)),
        ('опіати', re.compile(r'опі[йу]|героїн', re.I)),
        ('кокаїн', re.compile(r'кокаїн', re.I)),
    ]),
    'alk': ('продають', [
        ('цигарки', re.compile(r'сигарет|тютюн', re.I)),
        ('овочі й фрукти', re.compile(r'овоч|фрукт|ягід|картопл', re.I)),
        ('рибу', re.compile(r'\bриб', re.I)),
        ('квіти', re.compile(r'квіт', re.I)),
        ('алкоголь', re.compile(r'алкогол|горілк|\bпив|\bвин[оа]', re.I)),
    ]),
    'hp': ('на кого', [
        ('перехожих', re.compile(r'перехож', re.I)),
        ('поліцейських', re.compile(r'поліцейськ|працівник\w*\s+поліції', re.I)),
        ('продавців і охорону', re.compile(r'продавц|касир|охоронц|охорон\w+\s+магазин', re.I)),
        ('сусідів', re.compile(r'сусід', re.I)),
    ]),
}

CHASTYNY_DOBY = [(0, 'вночі'), (6, 'вранці'), (12, 'вдень'), (18, 'ввечері')]


def hodyna_pik(hodyny: Counter) -> str | None:
    """3-годинне вікно з найбільшою кількістю подій: «ввечері 19–22». None — якщо подій з часом < 5."""
    if sum(hodyny.values()) < 5:
        return None
    naikrashche = max(range(24), key=lambda h: (sum(hodyny[(h + i) % 24] for i in range(3)), -h))
    chastyna = [n for h, n in CHASTYNY_DOBY if h <= (naikrashche + 1) % 24][-1]
    return f'{chastyna} {naikrashche}–{(naikrashche + 3) % 24 or 24}'


def soty_rivnia(podii: list, vulytsi_podii: list, varianty_slug: dict, problemy: list, riven: int) -> dict:
    """Соти одного рівня H3. Чутливі справи (MV-4) — лише у великих сотах (рівні 7 і 8) і лише числом
    у групі «Насильство»."""
    ostannii = ROKY[-1] - OSTANNI_ROKY + 1
    soty = {}
    for i, p in enumerate(podii):
        if p.chutlyva:
            if riven not in (7, 8):
                continue
            if p.lat is not None:
                lat, lon = p.lat, p.lon
            else:
                c = tsentr_soty(p.sota) if p.sota else None
                if not c:
                    continue
                lat, lon = c
        elif p.lat is None:
            continue
        else:
            lat, lon = p.lat, p.lon
        k = h3.latlng_to_cell(lat, lon, riven)
        s = soty.setdefault(k, {'chysla': Counter(), 'roky': Counter(), 'hodyny': Counter(),
                                'tsili': defaultdict(Counter), 'vulytsi': Counter(), 'z_adresoyu': 0, 'problemy': []})
        hrupa = 'nas' if p.chutlyva else HRUPA_VYDU.get(p.vyd)
        nedavno = bool(p.rik and p.rik >= ostannii)
        for h in ((hrupa, 'all') if hrupa else ('all',)):
            s['chysla'][f'{h}A'] += 1
            if nedavno:
                s['chysla'][f'{h}3'] += 1
        if p.rik:
            s['roky'][p.rik] += 1
        if p.chutlyva:
            continue                      # далі — лише відкриті події
        s['z_adresoyu'] += 1
        if p.chas and re.match(r'^\d{1,2}:', p.chas) and 0 <= int(p.chas.split(':')[0]) < 24:
            s['hodyny'][int(p.chas.split(':')[0])] += 1
        if hrupa in TSILI and p.fabula:
            for nazva, vz in TSILI[hrupa][1]:
                if vz.search(p.fabula):
                    s['tsili'][hrupa][nazva] += 1
        for (t, n, _) in vulytsi_podii[i]:
            s['vulytsi'][varianty_slug[(t, n)]] += 1
    for (pid, vyd, mekh, status, lat, lon, n) in problemy:
        if vyd == 'НАС':
            continue                      # насильство — лише числом
        k = h3.latlng_to_cell(lat, lon, riven)
        if k in soty:
            nazva = (mekh or '').strip()
            nazva = nazva[:1].lower() + nazva[1:]
            if nazva and nazva not in [x[0] for x in soty[k]['problemy']]:
                soty[k]['problemy'].append((nazva, status or ''))
    return soty


# ---------------------------------------------------------------- сторінка вулиці

DNI = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'нд']


def profil_vulytsi(dani: Dani, v: Vulytsia) -> dict:
    """Узагальнене для безкоштовної сторінки: без адрес подій і описів, крім однієї чернетки історії."""
    import datetime
    podii = [dani.podii[i] for i in v.podii]
    vidkryti = [p for p in podii if not p.chutlyva]
    roky = Counter(p.rik for p in podii if p.rik)
    poza_rokamy = sum(1 for p in podii if not p.rik or p.rik < ROKY[0])

    # Що вирізняє вулицю: коефіцієнт локалізації = частка виду на вулиці / частка по місту.
    vydy = Counter(vyd_lyudskoyu(p.stattia, p.vyd) for p in vidkryti)
    vsogo_m = sum(dani.misto_vydy.values()) or 1
    vsogo_v = sum(vydy.values()) or 1
    vyriznennia = []
    for vyd, n in vydy.items():
        if n < 5:
            continue
        lq = (n / vsogo_v) / (dani.misto_vydy[vyd] / vsogo_m)
        vyriznennia.append({'vyd': vyd, 'n': n, 'lq': lq, 'chastka': n / vsogo_v,
                            'chastka_misto': dani.misto_vydy[vyd] / vsogo_m})
    vyriznennia.sort(key=lambda x: (-x['lq'], -x['n'], x['vyd']))
    vyriznennia = [x for x in vyriznennia if x['lq'] >= 1.2][:3]

    # Ритм: дні тижня × години (по 3 години).
    rytm = [[0] * 8 for _ in range(7)]
    z_chasom = 0
    for p in vidkryti:
        if not (p.data and p.chas and re.match(r'^\d{4}-\d{2}-\d{2}$', p.data) and re.match(r'^\d{1,2}:', p.chas)):
            continue
        try:
            den = datetime.date.fromisoformat(p.data).weekday()
        except ValueError:
            continue
        hod = int(p.chas.split(':')[0])
        if 0 <= hod < 24:
            rytm[den][hod // 3] += 1
            z_chasom += 1

    # Карта вулиці — соти H3 рівня 9 з числом подій, без точок будинків (MV-3: без адрес).
    soty = Counter(h3.latlng_to_cell(p.lat, p.lon, 9) for p in vidkryti if p.lat is not None) if h3 else Counter()
    mists = len({(round(p.lat, 5), round(p.lon, 5)) for p in vidkryti if p.lat is not None})

    # Історія: найсвіжіша подія з придатною фабулою (не насильство, не чутлива).
    istoriia = None
    for p in sorted(vidkryti, key=lambda p: (p.data or '', p.event_id), reverse=True):
        if p.vyd in ('НАС',) or not p.fabula:
            continue
        t = ochyshchena_istoriia(p.fabula)
        if t and len(t) >= 80:
            istoriia = {'tekst': t, 'rik': p.rik, 'vyd': vyd_lyudskoyu(p.stattia, p.vyd), 'url': p.url}
            break

    return {
        'vsogo': len(podii), 'roky': {r: roky.get(r, 0) for r in ROKY}, 'poza_rokamy': poza_rokamy,
        'vyriznennia': vyriznennia, 'rytm': rytm, 'z_chasom': z_chasom,
        'soty': sorted(soty.items()), 'mists': mists, 'istoriia': istoriia,
        'pershyi_rik': min((r for r in roky if r >= ROKY[0]), default=None),
        'ostannii_rik': max(roky, default=None),
    }
