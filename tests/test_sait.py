"""Перевірки сайту, що збирається з випуску бази (ZAVDANNYA-10, п. 6).

Запуск: python -m unittest tests.test_sait -v
Сайт збирається з маленької штучної бази (без справжніх даних). Щоб прогнати ті самі
перевірки на справжньому випуску: MV_VYPUSK=/шлях/events-<дата>.db
(і за бажанням MV_PEREIMENUVANNYA=/шлях/dani-edrsr/config/pereimenuvannia-kyiv.csv).

Потрібна бібліотека h3 (pip install h3) — без неї перевірки пропускаються з поясненням.
"""
from __future__ import annotations

import hashlib
import html.parser
import json
import os
import re
import sqlite3
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))

try:
    import h3  # noqa: F401
    YE_H3 = True
except ImportError:
    YE_H3 = False

import dani as D  # noqa: E402
from html import escape as html_escape  # noqa: E402

ZABORONENO_V_HTML = re.compile(r'ОСОБА_|АДРЕСА_|\bкв\.\s*№?\s*\d|квартир[аиіу]?\s*№?\s*\d', re.I)
# «не «небезпечніше»» у легенді — обов'язковий підпис системи дизайну, не оцінка.
DOZVOLENI_FRAZY = ('не «небезпечніше»',)
ZABORONENI_SLOVA = re.compile(r'небезпечн|безпечн|рейтинг|страшн', re.I)   # «страшно» — Д-8, ZAVDANNYA-114
POROZHNI_TEHY = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'source', 'track', 'wbr'}

SKHEMA = '''
CREATE TABLE document (doc_id TEXT PRIMARY KEY, sud TEXT NOT NULL, data_rishennia TEXT, forma TEXT,
  kod_kategorii TEXT NOT NULL, nomer_spravy TEXT, url TEXT NOT NULL CHECK (url LIKE 'https://%'));
CREATE TABLE location (location_id INTEGER PRIMARY KEY, adresa TEXT NOT NULL, tochnist TEXT NOT NULL,
  lat REAL NOT NULL, lon REAL NOT NULL, sposib TEXT);
CREATE TABLE event (event_id TEXT PRIMARY KEY, doc_id TEXT NOT NULL, epizod INTEGER NOT NULL, data_podii TEXT,
  chas TEXT, vyd TEXT NOT NULL, stattia TEXT, fabula TEXT, chutlyva INTEGER NOT NULL, sota TEXT, location_id INTEGER);
CREATE TABLE address (address_id INTEGER PRIMARY KEY, nazva TEXT NOT NULL, lat REAL NOT NULL, lon REAL NOT NULL);
CREATE TABLE problem (problem_id TEXT PRIMARY KEY, riven TEXT, vyd TEXT, mekhanizm TEXT, status TEXT, lat REAL,
  lon REAL, podii INTEGER, natovp TEXT, masshtab TEXT);
CREATE TABLE problem_event (problem_id TEXT NOT NULL, event_id TEXT NOT NULL, PRIMARY KEY (problem_id, event_id));
CREATE TABLE withdrawal (doc_id TEXT PRIMARY KEY, data_zvernennia TEXT NOT NULL, prychyna TEXT NOT NULL);
CREATE TABLE release (versiia TEXT PRIMARY KEY, podii INTEGER NOT NULL, khesh_vkhodu TEXT NOT NULL);
'''

FABULA = ('ОСОБА_1 {d} року о 14 год. 20 хв., керуючи автомобілем біля будинку {b} по {v}, не дотримався '
          'безпечної дистанції та допустив зіткнення з автомобілем, що рухався попереду, чим порушив правила дорожнього руху. '
          'Потерпілий мешкає в кв. 15 цього ж будинку, ОСОБА_2 подав заяву.')
FABULA_CHYSTA = ('Водій {d} року о 14 год. 20 хв., керуючи автомобілем біля будинку {b} по {v}, не врахував '
                 'дорожньої обстановки та допустив зіткнення з автомобілем, що рухався попереду, чим порушив правила '
                 'дорожнього руху. ОСОБА_3 визнав вину, проживає у квартирі 42.')


def stvoryty_bazu(shlyakh: Path) -> None:
    """Маленька штучна база: Лобановського трьома назвами, Хрещатик, стара назва, чутливі справи."""
    con = sqlite3.connect(shlyakh)
    con.executescript(SKHEMA)
    con.executemany('INSERT INTO address VALUES (?,?,?,?)', [
        (1, 'проспект Валерія Лобановського, 4', 50.4290, 30.4850),
        (2, 'вулиця Хрещатик, 22', 50.4475, 30.5230),
        (3, 'Велика Васильківська вулиця, 100', 50.4220, 30.5190),
        (4, 'Васильківська вулиця, 2', 50.3960, 30.5100),
    ])
    varianty = [
        ('просп. В.Лобановського', 50.4290, 30.4850),
        ('просп. Лобановського', 50.4300, 30.4860),
        ('просп. Валерія Лобановського', 50.4310, 30.4870),
        ('вул. Хрещатик', 50.4475, 30.5230),
        ('вул. Червоноармійська', 50.4220, 30.5190),   # стара назва Великої Васильківської
        ('вул. Васильківська', 50.3960, 30.5100),
    ]
    n = 0
    for i, (vul, lat, lon) in enumerate(varianty):
        for j in range(8):
            n += 1
            bud = str(2 + (j % 3) * 2)
            con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)',
                        (str(n), 'суд', '2025-01-01', 'постанова', '41080', f'{n}/25', f'https://reyestr.court.gov.ua/Review/{n}'))
            con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)', (n, f'{vul}, {bud}', 'house', lat + j * 1e-4, lon, 'osm'))
            fab = (FABULA if j % 2 else FABULA_CHYSTA).format(d=f'0{1 + j % 9}.03.2025', b=bud, v=vul)
            con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                        (f'{n}-1', str(n), 1, f'2025-03-0{1 + j % 9}', f'{10 + j}:30', 'ДТП',
                         'ст.124 КУпАП · ДТП з пошкодженням майна' if j < 5 else "ст.130 КУпАП · керування у стані сп'яніння",
                         fab, 0, '11216:4344', n))
    # Чутлива подія: лише сота, без місця й опису (як у випуску).
    for k in range(2):
        n += 1
        con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)', (str(n), 'суд', '2025-01-01', 'постанова', '6062', '', f'https://x.ua/{n}'))
        con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (f'{n}-1', str(n), 1, '2025-02-02', None, 'НАС', 'ст.173-2 КУпАП · домашнє насильство', None, 1, '11206:4360', None))
    # Подія за ст. 390-1 КК (не позначена у випуску) — домашнє насильство: з MV-102 рахується нарівні з іншими.
    n += 1
    con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)', (str(n), 'суд', '2025-01-01', 'вирок', '1', '', f'https://x.ua/{n}'))
    con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)', (n, 'вул. Хрещатик, 99', 'house', 50.4480, 30.5232, 'osm'))
    con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (f'{n}-1', str(n), 1, '2025-04-04', None, 'НАС', 'ст.390-1 КК · невиконання обмежувальних приписів',
                 'ОСОБА_9 порушив припис', 0, '11210:4360', n))
    # MV-102: на Васильківській — домашнє насильство з точкою (рахується всюди) і статевий злочин та справа щодо
    # дитини з точкою (лише числом у великій соті, ні на вулиці, ні в районі, ні в будинку).
    for st, chut in (('ст.173-2 КУпАП · домашнє насильство', 1), ('ст.152 КК · зґвалтування', 1),
                     ('ст.166 КК · злісне невиконання обов’язків щодо дитини', 1)):
        n += 1
        con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)', (str(n), 'суд', '2025-01-01', 'вирок', '1', '', f'https://x.ua/{n}'))
        con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)', (n, 'вул. Васильківська, 2', 'house', 50.3960, 30.5100, 'osm'))
        con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (f'{n}-1', str(n), 1, '2025-05-05', None, 'НАС', st, 'ОСОБА_8 вдома', chut, '11200:4357', n))
    # Старші роки (MV-32): 7 подій 2023 року і 1 без дати на Хрещатику, 6 подій 2018 року на вулиці, де нових немає.
    # На сайті — лише прапорець «у підписці», жодного числа (ZAVDANNYA-46); «у підписці» — лише роки карти підписника
    # (від 2023, ZAVDANNYA-174): події 2018 року замка не дають.
    for vul, lat, lon, data in ([('вул. Хрещатик', 50.4476, 30.5231, f'2023-05-0{1 + j}') for j in range(7)]
                                + [('вул. Хрещатик', 50.4476, 30.5231, None)]
                                + [('вул. Інститутська', 50.4460, 30.5300, f'2018-06-0{1 + j}') for j in range(6)]):
        n += 1
        con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)',
                    (str(n), 'суд', data or '2020-01-01', 'постанова', '41080', f'{n}/19', f'https://reyestr.court.gov.ua/Review/{n}'))
        con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)', (n, f'{vul}, 7', 'house', lat, lon, 'osm'))
        con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (f'{n}-1', str(n), 1, data, '12:30', 'ДТП', 'ст.124 КУпАП · ДТП з пошкодженням майна',
                     FABULA_CHYSTA.format(d='01.05.2023', b='7', v=vul), 0, '11216:4344', n))
    con.execute("INSERT INTO release VALUES ('2026-11-08', ?, 'x')", (n,))
    con.commit()
    con.close()


BUDYNKY = {   # зведення будинків, як його дає dani-edrsr/src/budynky_sait.py (лише числа)
    'versiia': '2026-11-08', 'r_susidy_m': 300, 'dzherelo_1551': 'набір 1551, CC BY',
    'skarhy_misiatsi': [f'2025-{m:02d}' for m in (11, 12)] + [f'2026-{m:02d}' for m in range(1, 11)],
    'budynky': [
        {'k': 'хрещатик|22', 'vulytsia': 'вулиця Хрещатик', 'nomer': '22', 'lat': 50.4475, 'lon': 30.523, 'rayon': 'Печерський',
         'skarhy': {'світло': 2, 'вода': 5}, 'susidiv': 6, 'susidy': {'вода': 1, 'світло': 0},
         'podii': {'2023': {'kra': 1}, '2025': {'dtp': 3}}},
        {'k': 'хрещатик|24А', 'vulytsia': 'вулиця Хрещатик', 'nomer': '24-А', 'lat': 50.4477, 'lon': 30.5232, 'rayon': 'Печерський',
         'skarhy': {'ліфт': 1}},
        {'k': 'хрещатик|43', 'vulytsia': 'вулиця Хрещатик', 'nomer': '43 кв32', 'lat': 50.4479, 'lon': 30.5233,
         'rayon': 'Печерський', 'skarhy': {'вода': 1}},      # Б-2: квартира в номері зі старого зведення
        {'k': 'невідома|1', 'vulytsia': 'вулиця Невідома', 'nomer': '1', 'lat': 50.40, 'lon': 30.50, 'skarhy': {'вода': 4}},
    ]}


def stvoryty_pereimenuvannya(shlyakh: Path) -> None:
    # шапка — як у dani-edrsr/config/pereimenuvannia-kyiv.csv
    shlyakh.write_text('stara_nazva,nova_nazva,typ,rayon,nomer_rishennia,data_rishennia,posylannia,perelik_kmda,prymitka\n'
                       'Червоноармійська,Велика Васильківська,вулиця,,,,https://example.org,так,тест\n'
                       'Червонозоряний,Валерія Лобановського,проспект,,,,https://example.org,так,тест\n'
                       # Т-8 (ZAVDANNYA-110): стара назва, перейменована по-різному, — сторінка «оберіть» (як 24 на справжньому)
                       'Старокиївська,Хрещатик,вулиця,,,,https://example.org,так,тест\n'
                       'Старокиївська,Велика Васильківська,вулиця,,,,https://example.org,так,тест\n', encoding='utf-8')


class PerevirkaHtml(html.parser.HTMLParser):
    """Проста сувора перевірка: закриті теги, унікальні id, одна h1, мова, заголовок, опис."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stek, self.pomylky, self.ids, self.h1, self.meta = [], [], set(), 0, {}
        self.lang = None
        self.title = ''
        self._u_title = False

    def handle_starttag(self, teg, atr):
        a = dict(atr)
        if teg == 'html':
            self.lang = a.get('lang')
        if 'id' in a:
            if a['id'] in self.ids:
                self.pomylky.append(f'повторний id {a["id"]}')
            self.ids.add(a['id'])
        if teg == 'h1':
            self.h1 += 1
        if teg == 'meta' and a.get('name'):
            self.meta[a['name']] = a.get('content', '')
        if teg == 'img' and 'alt' not in a:
            self.pomylky.append('img без alt')
        if teg == 'title':
            self._u_title = True
        if teg not in POROZHNI_TEHY:
            self.stek.append(teg)

    def handle_startendtag(self, teg, atr):
        self.handle_starttag(teg, atr)
        if teg not in POROZHNI_TEHY:
            self.stek.pop()

    def handle_endtag(self, teg):
        if teg in POROZHNI_TEHY:
            return
        if teg == 'title':
            self._u_title = False
        if not self.stek or self.stek[-1] != teg:
            self.pomylky.append(f'</{teg}> не закриває <{self.stek[-1] if self.stek else "—"}>')
            if teg in self.stek:
                while self.stek and self.stek.pop() != teg:
                    pass
            return
        self.stek.pop()

    def handle_data(self, d):
        if self._u_title:
            self.title += d


def perevirka_storinky(tekst: str) -> list[str]:
    p = PerevirkaHtml()
    p.feed(tekst)
    p.close()
    pomylky = list(p.pomylky)
    if not tekst.lstrip().lower().startswith('<!doctype html>'):
        pomylky.append('немає <!doctype html>')
    if p.stek:
        pomylky.append(f'незакриті теги: {p.stek}')
    if p.lang != 'uk':
        pomylky.append('немає lang="uk"')
    if not p.title.strip():
        pomylky.append('немає <title>')
    if not p.meta.get('description'):
        pomylky.append('немає опису для пошуку')
    if p.h1 != 1:
        pomylky.append(f'h1: {p.h1} (має бути 1)')
    try:                                     # повна перевірка за стандартом HTML, якщо є html5lib
        import html5lib
        html5lib.HTMLParser(strict=True, namespaceHTMLElements=False).parse(tekst)
    except ImportError:
        pass
    except Exception as e:                   # noqa: BLE001 — html5lib кидає ParseError
        pomylky.append(f'html5lib: {e}')
    return pomylky


def sluzhbova(t: str) -> bool:
    """Переадресація зі старої назви або сторінка «перейменовано по-різному — оберіть» (Т-8): без «Оновлено» й картинки."""
    return 'http-equiv="refresh"' in t or 'їх перейменовано по-різному' in t


def vidbytok_teky(teka: Path) -> str:
    h = hashlib.sha256()
    for f in sorted(p for p in teka.rglob('*') if p.is_file()):
        h.update(str(f.relative_to(teka)).encode() + b'\0' + f.read_bytes())
    return h.hexdigest()


class ZvedenniaNazv(unittest.TestCase):
    def test_rozbir_nazv(self):
        self.assertEqual(D.rozibraty_vulytsiu('просп. С.Бандери'), ('проспект', 'С. Бандери'))
        self.assertEqual(D.rozibraty_vulytsiu('вул. Харківське шосе'), ('шосе', 'Харківське'))
        self.assertEqual(D.rozibraty_vulytsiu('пл. Майдан Незалежності'), ('майдан', 'Незалежності'))
        self.assertEqual(D.rozibraty_vulytsiu('Йорданська вулиця'), ('вулиця', 'Йорданська'))
        self.assertEqual(D.rozibraty_vulytsiu('вул. Олени Теліги поблизу житлового будинку'), ('вулиця', 'Олени Теліги'))

    def test_t4_smittia_v_nazvakh(self):
        """ZAVDANNYA-110, Т-4: шматки тексту рішення після назви — не частина назви; перехрестя — дві вулиці."""
        for t, tr in (('проспект Соборності біля електроопори', ('проспект', 'Соборності')),
                      ('проспект Повітряних Сил та Севастопольської площі', ('проспект', 'Повітряних Сил')),
                      ('вулиця Ю. Іллєнка навпроти будівлі номер', ('вулиця', 'Ю. Іллєнка')),
                      ('вулиця С. Петлюри. Грубо порушуючи вимоги п. п', ('вулиця', 'С. Петлюри')),
                      ('вулиця Пластова навпроти Пражська', ('вулиця', 'Пластова')),
                      ('вулиця Кільцева Дорога навпроти вул.', ('дорога', 'Кільцева')),
                      ('вулиця Проспек С. Бандери', ('проспект', 'С. Бандери')),
                      ('вулиця Акад. Заболотного', ('вулиця', 'Акад. Заболотного')),
                      ('вул. Червоної Калини', ('вулиця', 'Червоної Калини'))):
            self.assertEqual(D.rozibraty_vulytsiu(t), tr, t)
        self.assertEqual([x[1] for x in D.vulytsi_mistsia('вулиця Богатирської на проспект Степана Бандери', 'cross')],
                         ['Богатирської', 'Степана Бандери'])
        self.assertEqual([x[1] for x in D.vulytsi_mistsia('перехрестя вул. Хрещатик і вул. Прорізна', 'cross')],
                         ['Хрещатик', 'Прорізна'])
        self.assertEqual([x[1] for x in D.vulytsi_mistsia('вулиця В. Гетьмана - вул. Індустріальна', 'cross')],
                         ['В. Гетьмана', 'Індустріальна'])
        # ZAVDANNYA-150, п. 15: сміття з покажчика вулиць
        for t, tr in (('площа Києві Деміївська', ('площа', 'Деміївська')), ('Деміївська площа у м. Києві', ('площа', 'Деміївська')),
                      ('вулиця Ів.Пулюя', ('вулиця', 'Ів. Пулюя')), ('вул. Київська', ('вулиця', 'Київська')),
                      ('вулиця Києво-Святошинська', ('вулиця', 'Києво-Святошинська'))):
            self.assertEqual(D.rozibraty_vulytsiu(t), tr, t)
        kanon = {('бульвар', D.kliuch('Лесі Українки')): ('бульвар', 'Лесі Українки', 'бульвар Лесі Українки'),
                 ('площа', D.kliuch('Лесі Українки')): ('площа', 'Лесі Українки', 'площа Лесі Українки'),
                 ('вулиця', D.kliuch('Івана Пулюя')): ('вулиця', 'Івана Пулюя', 'вулиця Івана Пулюя')}
        z, _s, n = D.zvesty_nazvy(Counter({('вулиця', 'Лесі Українки'): 1, ('вулиця', 'Ів. Пулюя'): 1}), kanon, [])
        self.assertEqual(z[('вулиця', 'Лесі Українки')][2], 'бульвар Лесі Українки')
        self.assertEqual(z[('вулиця', 'Ів. Пулюя')][2], 'вулиця Івана Пулюя')
        self.assertEqual(n, [])
        kanon = {('вулиця', D.kliuch('Набережно-Хрещатицька')): ('вулиця', 'Набережно-Хрещатицька', 'Набережно-Хрещатицька вулиця')}
        z, _s, _n = D.zvesty_nazvy(Counter({('вулиця', 'Набержно-Хрещатицька'): 1}), kanon, [])
        self.assertEqual(z[('вулиця', 'Набержно-Хрещатицька')][1], 'Набережно-Хрещатицька')

    def test_skorochennia(self):
        self.assertTrue(D.sumisni(D.kliuch('В. Лобановського'), D.kliuch('Валерія Лобановського'))[0])
        self.assertTrue(D.sumisni(D.kliuch('Лобановського'), D.kliuch('Валерія Лобановського'))[0])
        self.assertFalse(D.sumisni(D.kliuch('М. Лобановського'), D.kliuch('Валерія Лобановського'))[0])

    def test_translit(self):
        self.assertEqual(D.translit('Хрещатик'), 'khreshchatyk')
        self.assertEqual(D.translit('Кадетський Гай'), 'kadetskyi-hai')
        self.assertEqual(D.translit("Юрія Іллєнка"), 'yuriia-illienka')

    def test_perevirka_perekazu(self):
        """ZAVDANNYA-110, Б-1: переказ для відкритої сторінки — без дат, годин, сум, марок авто, імен і уривків рішення."""
        import perekazy as PK
        fab = FABULA_CHYSTA.format(d='01.03.2025', b='4', v='вул. Хрещатик')
        self.assertEqual(PK.vady(PEREKAZ_DOBRYI, fab), [])
        for zle in ('Водій 01.03.2025 року врізався в авто попереду на Хрещатику, ніхто не постраждав.',
                    'Увечері о десятій годині водій врізався в авто попереду на вулиці, ніхто не постраждав.',
                    'Водій Toyota врізався в інше авто на вулиці; збитки оцінили в тисячу гривень.',
                    'ОСОБА_1 врізався в авто попереду на вулиці, ніхто не постраждав, потерпілих немає.',
                    'Водій Іваненко І.І. врізався в авто попереду на вулиці, ніхто не постраждав.',
                    'Постановою судді водія визнано винним у зіткненні з автомобілем на вулиці.',
                    'Водій не врахував дорожньої обстановки та допустив зіткнення з автомобілем, що рухався попереду.'):
            self.assertNotEqual(PK.vady(zle, fab), [], zle)


PEREKAZ_DOBRYI = 'Водій легковика не втримав дистанцію й врізався в авто попереду. Обійшлося без постраждалих.'


@unittest.skipUnless(YE_H3, 'немає бібліотеки h3 (pip install h3) — збирання сайту пропущено')
class Sait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zibraty_sait
        cls.zs = zibraty_sait
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        vypusk = os.environ.get('MV_VYPUSK')
        if vypusk:
            cls.baza = Path(vypusk)
            p = os.environ.get('MV_PEREIMENUVANNYA')
            cls.pereim = Path(p) if p else None
            cls.spravzhnii = True
            b = os.environ.get('MV_BUDYNKY')
            cls.budynky = Path(b) if b else None
        else:
            cls.baza = tmp / 'events.db'
            stvoryty_bazu(cls.baza)
            cls.pereim = tmp / 'pereim.csv'
            stvoryty_pereimenuvannya(cls.pereim)
            cls.spravzhnii = False
            cls.budynky = tmp / 'budynky.json'
            cls.budynky.write_text(json.dumps(BUDYNKY, ensure_ascii=False), encoding='utf-8')
        # Перекази ШІ для історій вулиць (ZAVDANNYA-110): на справжньому — MV_PEREKAZY (файл кроку
        # dani-edrsr/src/perekazy_istorii.py); на штучній — добрий переказ для Хрещатика, на решті — переказ
        # з датою й уривком рішення (сайт мусить його відкинути, і тоді історії немає).
        pk = os.environ.get('MV_PEREKAZY')
        if pk or cls.spravzhnii:
            cls.perekazy = Path(pk) if pk else None
        else:
            con = sqlite3.connect(cls.baza)
            ryady = con.execute("SELECT e.event_id, l.adresa FROM event e JOIN location l USING (location_id)").fetchall()
            con.close()
            cls.perekazy = tmp / 'perekazy.json'
            cls.perekazy.write_text(json.dumps({'perekazy': {
                eid: {'perekaz': PEREKAZ_DOBRYI if 'Хрещатик' in adr else
                      'Водій 01.03.2025 року о 14 год. 20 хв. не врахував дорожньої обстановки та допустив зіткнення з автомобілем.'}
                for eid, adr in ryady}}, ensure_ascii=False), encoding='utf-8')
        cls.kandydaty = tmp / 'kandydaty.json'
        cls.sait = tmp / 'sait'
        cls.zvit = zibraty_sait.zibraty_sait(cls.baza, cls.sait, cls.pereim, KORIN / 'data' / 'borders.json',
                                             budynky=cls.budynky, mezha_failiv=10 ** 6 if cls.spravzhnii else 20000,
                                             perekazy=cls.perekazy, kandydaty_istorii=cls.kandydaty)
        cls.storinky = sorted(cls.sait.rglob('*.html'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def nashi_storinky(self):
        """Сторінки сайту без заглушки (її перевіряє test_zahlushka)."""
        return [p for p in self.storinky if 'zahlushka' not in p.relative_to(self.sait).parts]

    def test_usi_storinky_proxodiat_perevirku_html(self):
        pomylky = {}
        for p in self.nashi_storinky():
            r = perevirka_storinky(p.read_text(encoding='utf-8'))
            if r:
                pomylky[str(p.relative_to(self.sait))] = r[:3]
        self.assertEqual(pomylky, {}, f'сторінки з помилками: {list(pomylky.items())[:5]}')

    def test_nemaye_imen_i_kvartyr(self):
        znaideno = []
        for p in sorted(self.sait.rglob('*')):
            if p.is_file() and p.suffix in ('.html', '.json', '.xml', '.txt') and 'zahlushka' not in p.relative_to(self.sait).parts:
                m = ZABORONENO_V_HTML.search(p.read_text(encoding='utf-8'))
                if m:
                    znaideno.append((str(p.relative_to(self.sait)), m.group(0)))
        self.assertEqual(znaideno, [])

    def test_b1_istoriia_lyshe_perekaz_shi(self):
        """ZAVDANNYA-110, Б-1: історія вулиці — лише перевірений переказ ШІ; переказу немає — блоку немає."""
        kand = json.loads(self.kandydaty.read_text(encoding='utf-8'))['vulytsi']
        self.assertTrue(kand)
        if self.spravzhnii:
            self.skipTest('на справжньому — лише перевірка публічних файлів нижче')
        khr = (self.sait / 'vulytsia' / 'khreshchatyk' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('Одна історія з вулиці', khr)
        self.assertIn(html_escape(PEREKAZ_DOBRYI), khr)
        self.assertIn('Переказ ШІ', khr)
        self.assertNotIn('Чернетка', khr)
        lob = next(self.sait.glob('vulytsia/*lobanovskoho*/index.html')).read_text(encoding='utf-8')
        self.assertNotIn('Одна історія з вулиці', lob)           # переказ з датою відкинуто — блоку немає

    def test_b1_u_publichnykh_failakh_nemaye_uryvkiv_rishen(self):
        """ZAVDANNYA-110, Б-1: у публічних файлах немає уривків рішень, дат з годиною, сум, марок авто, посилань на рішення."""
        import perekazy as PK
        kand = json.loads(self.kandydaty.read_text(encoding='utf-8'))['vulytsi']
        ids = sorted({i for v in kand.values() for i in v})
        con = sqlite3.connect(f'file:{self.baza}?mode=ro', uri=True)
        fabuly = []
        for i in range(0, len(ids), 500):
            ch = ids[i:i + 500]
            fabuly += [f for (f,) in con.execute(f'SELECT fabula FROM event WHERE event_id IN ({",".join("?" * len(ch))})', ch) if f]
        con.close()
        n = PK.SPILNYKH_SLIV
        uryvky = set()
        for f in fabuly:
            s = PK.slova(f)
            uryvky |= {tuple(s[j:j + n]) for j in range(len(s) - n + 1)}
        shablony = {
            'дата': re.compile(r'\b\d{1,2}\.\d{1,2}\.\d{4}\b'),
            'година': re.compile(r'\d{1,2}\s*год\.?\s*\d{1,2}\s*хв'),
            'сума з рішення': re.compile(r'\d[\d\s]*грн\.?\s*\d+\s*коп|\d+\s*(гривень|доларів|USD)', re.I),
            'марка авто': PK.MARKY,
            'посилання на рішення': re.compile(r'reyestr\.court\.gov\.ua/(Review|files)'),
        }
        znaideno = []
        for p in sorted(self.sait.rglob('*')):
            # Колода гри й дані ігор у карті — виняток MV-12 / MV-129 (перевіряє tests/test_ihry.py).
            if not p.is_file() or p.suffix not in ('.html', '.json') or {'zahlushka', 'ihry'} & set(p.relative_to(self.sait).parts):
                continue
            t = p.read_text(encoding='utf-8')
            if p.suffix == '.html':
                t = re.sub(r'<script[^>]*>.*?</script>|<[^>]+>', ' ', t, flags=re.S)
            for nazva, sh in shablony.items():
                m = sh.search(t)
                if m:
                    znaideno.append((str(p.relative_to(self.sait)), nazva, m.group(0)))
            s = PK.slova(t)
            for j in range(len(s) - n + 1):
                if tuple(s[j:j + n]) in uryvky:
                    znaideno.append((str(p.relative_to(self.sait)), 'уривок рішення', ' '.join(s[j:j + n])))
                    break
        self.assertEqual(znaideno[:10], [])

    def test_storinka_vulytsi_bez_biblioteky_karty_na_starti(self):
        """Т-12 (ZAVDANNYA-114): бібліотеку карти сторінка вулиці не вантажить одразу — karta.js довантажує її біля карти."""
        p = next((self.sait / 'vulytsia').glob('*/index.html'))
        t = p.read_text(encoding='utf-8')
        if 'id="karta-vulytsi"' not in t:
            self.skipTest('вулиця без карти')
        self.assertNotIn('maplibre-gl-csp.js', t)
        self.assertNotIn('maplibre-gl.css', t)
        self.assertIn('IntersectionObserver', (KORIN / 'site' / 'sait' / 'karta.js').read_text(encoding='utf-8'))

    def test_menyu_na_telefoni_maie_vsi_vitryny(self):
        """Д-5 (ZAVDANNYA-114): що сховано на телефоні (lyshe-komp), те є під «Ще»."""
        for p in [self.sait / 'index.html', self.sait / 'vulytsi' / 'index.html']:
            t = p.read_text(encoding='utf-8')
            nav = t[t.index('<nav class="menyu"'):t.index('</nav>', t.index('<nav class="menyu"'))]
            skhovani = re.findall(r'<a class="lyshe-komp" href="([^"]+)"', nav)
            self.assertTrue(skhovani, p)
            shche = nav[nav.index('<details class="menyu__shche">'):]
            for h in skhovani:
                self.assertIn(f'href="{h}"', shche, f'{p}: {h}')

    def test_nemaye_sliv_pro_nebezpeku(self):
        znaideno = []
        for p in self.nashi_storinky():
            t = p.read_text(encoding='utf-8')
            for f in DOZVOLENI_FRAZY:
                t = t.replace(f, '')
            m = ZABORONENI_SLOVA.search(t)
            if m:
                znaideno.append((str(p.relative_to(self.sait)), m.group(0)))
        self.assertEqual(znaideno, [])

    def test_zavd150_bez_sluzhbovykh_sliv(self):
        """ZAVDANNYA-150, п. 12 (AGENTS.md, розд. 4): на відкритих сторінках немає «медіана», номерів рішень, назв файлів
        документації й «Ціну бере сервер…»; ціни в описах — лише з таблиці (599 → 299)."""
        sluzhbovi = re.compile(r'медіан|\bMV-\d|docs/|[A-Z-]+\.md\b|Ціну бере сервер|повний звіт — 599', re.I)
        znaideno = []
        for p in self.nashi_storinky():
            t = re.sub(r'<script\b[^>]*>.*?</script>|<!--.*?-->', '', p.read_text(encoding='utf-8'), flags=re.S)
            m = sluzhbovi.search(t)
            if m:
                znaideno.append((str(p.relative_to(self.sait)), m.group(0)))
        self.assertEqual(znaideno, [])

    def test_zavd150_oplata_ne_pratsiuie_lyshe_skoro(self):
        """ZAVDANNYA-150, п. 2: «Оплата ще не працює» — лише в режимі «скоро»; з увімкненою оплатою рядка немає."""
        import storinky_mv100 as M
        import tsiny as T
        t = (self.sait / 'miy-budynok' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('Оплата ще не працює', t)          # збірка тестів — режим «скоро»
        stare = T.OPLATA['rezhym']
        try:
            T.OPLATA['rezhym'] = 'tak'
            self.assertEqual(M.prymitka_oplaty('Кнопка …'), '')
            self.assertNotIn('ще не працює', M.vitryna_miy_budynok('https://mv.test', []))
        finally:
            T.OPLATA['rezhym'] = stare

    def test_failiv_menshe_mezhi_cloudflare(self):
        if self.spravzhnii and self.budynky:
            self.skipTest('зі сторінками будинків справжній випуск більший за 20 000 файлів — платний план (ZVIT-85)')
        n = sum(1 for p in self.sait.rglob('*') if p.is_file())
        self.assertLess(n, 20000)

    def test_povtornyi_zapusk_daye_ti_sami_faily(self):
        druhyi = Path(self.tmp.name) / 'sait2'
        self.zs.zibraty_sait(self.baza, druhyi, self.pereim, KORIN / 'data' / 'borders.json',
                             budynky=self.budynky, mezha_failiv=10 ** 6, perekazy=self.perekazy)
        self.assertEqual(vidbytok_teky(self.sait), vidbytok_teky(druhyi))

    def test_sitemap_robots_i_rozmitka(self):
        self.assertTrue((self.sait / 'sitemap.xml').is_file())
        self.assertIn('Sitemap:', (self.sait / 'robots.txt').read_text(encoding='utf-8'))
        storinka = next(p for p in self.storinky if p.parts[-3] == 'vulytsia' and 'noindex' not in p.read_text(encoding='utf-8'))
        t = storinka.read_text(encoding='utf-8')
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', t, re.S).group(1))
        self.assertEqual(ld['@type'], 'Place')
        self.assertIn('<meta name="description"', t)

    def test_karta_bez_chutlyvykh_vydiv(self):
        for riven in (7, 8, 9):
            soty = json.loads((self.sait / 'karta' / f'soty-{riven}.json').read_text(encoding='utf-8'))
            tekst = json.dumps(soty, ensure_ascii=False)
            for slovo in ('домашнє насильство', 'обмежувальних приписів', 'статев', 'зґвалтування'):
                self.assertNotIn(slovo, tekst)
            self.assertTrue(soty['soty']['features'])

    def test_chutlyvi_lyshe_u_velykykh_sotakh(self):
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        suma = {}
        for riven in (7, 8, 9):
            soty = json.loads((self.sait / 'karta' / f'soty-{riven}.json').read_text(encoding='utf-8'))
            suma[riven] = sum(f['properties'].get('nas3', 0) for f in soty['soty']['features'])
        # MV-102: 2 домашніх без точки (числом по соті) + 390-1 і 173-2 з точкою + статевий і щодо дитини з точкою
        self.assertEqual(suma[7], 6)          # великі соти (≈ 5 км²) — усі, статеві й щодо дітей лише числом
        self.assertEqual(suma[8], 6)
        self.assertEqual(suma[9], 2)          # малі соти — лише домашнє насильство з точкою (390-1, 173-2)

    def test_mv102_domashnie_na_vidkrytykh_statevi_ni(self):
        """MV-102: домашнє насильство — на вулиці й у районі нарівні; статеві й щодо дітей — ні (обидва боки)."""
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        import storinky_mv100 as M
        dn = D.zibraty_dani(self.baza, self.pereim, KORIN / 'data' / 'borders.json')
        vas = next(v for v in dn.vulytsi.values() if v.korotka == 'Васильківська')
        statti = sorted(dn.podii[i].stattia.split(' ·')[0] for i in vas.nedavni if dn.podii[i].vyd == 'НАС')
        self.assertEqual(statti, ['ст.173-2 КУпАП'])
        khr = next(v for v in dn.vulytsi.values() if v.korotka == 'Хрещатик')
        self.assertIn('ст.390-1 КК', [dn.podii[i].stattia.split(' ·')[0] for i in khr.nedavni])
        rayony = M.podii_rayoniv(dn)
        self.assertEqual(sum(c['nas'] for c in rayony.values()), 2)      # 390-1 і 173-2; без 152 і 166 КК
        for st, vidkr in (('ст.173-2 КУпАП', True), ('ст.173-8 КУпАП', True), ('ст.126-1 КК', True), ('ст.390-1 КК', True),
                          ('ст.152 КК', False), ('ст.156 КК', False), ('ст.166 КК', False), ('ст.180 КУпАП', False),
                          ('ст.173-2 КУпАП · щодо дитини', False)):
            self.assertEqual(D.domashnie(st), vidkr, st)
        vas_html = (self.sait / 'vulytsia' / vas.slug / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('ґвалт', vas_html)
        self.assertNotIn('щодо дитини', vas_html)

    def test_publichni_faily_karty_bez_adres_i_opysiv(self):
        """Безкоштовно — лише числа по сотах (AGENTS.md, розд. 8): у файлах карти й пошуку немає номерів будинків,
        описів подій і посилань на рішення."""
        faily = sorted((self.sait / 'karta').glob('*.json')) + [self.sait / 'vulytsi' / 'pokazhchyk.json']
        self.assertEqual({f.name for f in faily}, {'soty-7.json', 'soty-8.json', 'soty-9.json', 'soty-8-m.json', 'soty-9-m.json',   # місяці — окремо (ZAVDANNYA-125)
                                                      'poshuk.json', 'pokazhchyk.json', 'rayony.json',
                                                      'mistsevosti.json'})   # rayony — межі районів (174); народні назви місцевостей (177)
        opys = re.compile(r'керуючи|зіткнення|порушив|визнав|reyestr\.court\.gov\.ua/Review|doc_url|fabula', re.I)
        for f in faily:
            tekst = f.read_text(encoding='utf-8')
            self.assertIsNone(D.NOMER_BUDYNKU.search(tekst), f.name)
            self.assertIsNone(opys.search(tekst), f.name)
            self.assertIsNone(re.search(r'[А-ЯІЇЄҐа-яіїєґ.]\s*,\s*\d+[а-я]?["\]]', tekst), f'{f.name}: схоже на адресу з номером')

    def test_poshuk_znakhodyt_vulytsiu_z_danykh(self):
        """Пошук на карті — з даних сайту: вулиця зі сторінкою, її старі назви, центр соти; райони — межами."""
        p = json.loads((self.sait / 'karta' / 'poshuk.json').read_text(encoding='utf-8'))
        storinky = {d.name for d in (self.sait / 'vulytsia').iterdir()}
        for v in p['vulytsi']:
            self.assertIn(v[2], storinky)
            self.assertTrue(30.2 < v[3] < 30.9 and 50.2 < v[4] < 50.6, v)
        nazvy = {v[0]: v for v in p['vulytsi']}
        khr = [v for n, v in nazvy.items() if 'Хрещатик' in n]
        self.assertTrue(khr, 'Хрещатика немає в пошуку')
        self.assertEqual(khr[0][2], 'khreshchatyk')
        self.assertEqual(len(nazvy), len(p['vulytsi']), 'назви в пошуку не повторюються')
        self.assertTrue(p['rayony'] and all(len(r) == 5 for r in p['rayony']))
        if not self.spravzhnii:
            vv = [v for v in p['vulytsi'] if v[2] == 'velyka-vasylkivska'][0]
            self.assertIn('Червоноармійська', vv[6])      # стара назва з довідника перейменувань

    def test_kolory_i_shryft_m7(self):
        css = (self.sait / 'sait' / 'sait.css').read_text(encoding='utf-8')
        self.assertIn('html[data-t="temna"]', css)
        for zm in ('--sc-1', '--sc-5', '--pk-1', '--pk-2', '--vyd', '--karta-park', '--karta-voda'):
            self.assertIn(zm + ':#', css)
        self.assertIn('font-family: Plex', css)
        self.assertTrue((self.sait / 'sait' / 'shryfty' / 'OFL-IBM-Plex-Sans.txt').is_file())
        holovna = (self.sait / 'index.html').read_text(encoding='utf-8')
        for id_ in ('poshuk-karty', 'f3d', 'ftema', 'finfo', 'filtr', 'kartka', 'dzherela'):
            self.assertIn(f'id="{id_}"', holovna)
        for f in self.nashi_storinky():                    # CSP style-src 'self' не пускає атрибутів style
            self.assertNotIn(' style="', f.read_text(encoding='utf-8'), str(f.relative_to(self.sait)))

    def test_nemaye_budynkiv_na_storintsi_vulytsi(self):
        bud = re.compile(r'біля буд\.|буд\.\s*№?\s*\d|будинку\s*№?\s*\d|(вул|просп|бульв)\.\s+[^,<]{1,50},\s*\d')
        znaideno = []
        for p in self.nashi_storinky():
            if p.parts[-3] == 'vulytsia':
                m = bud.search(p.read_text(encoding='utf-8'))
                if m:
                    znaideno.append((str(p.relative_to(self.sait)), m.group(0)))
        self.assertEqual(znaideno, [])
        t = (next(p for p in self.storinky if p.parts[-3] == 'vulytsia' and 'refresh' not in p.read_text(encoding='utf-8'))
             .read_text(encoding='utf-8'))
        self.assertIn('Що саме сталося біля кожного будинку — у довідці й підписці', t)

    def test_try_knopky_na_storintsi_vulytsi(self):
        t = next(p for p in self.storinky if p.parts[-3] == 'vulytsia' and 'refresh' not in p.read_text(encoding='utf-8')).read_text(encoding='utf-8')
        self.assertIn('Довідка про будинок — 199', t)   # MV-100
        self.assertIn('>Вулиця дня<', t)   # гра в карті (ZAVDANNYA-117)
        self.assertIn('в іншому місті — повідомимо', t)

    def test_shtuchna_baza_nazvy_zvedeni(self):
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        lob = self.sait / 'vulytsia' / 'prospekt-valeriia-lobanovskoho' / 'index.html'
        self.assertTrue(lob.is_file())
        self.assertIn('24 події', lob.read_text(encoding='utf-8'))
        # «Червоноармійська» — стара назва: події на сторінці Великої Васильківської, стара адреса веде туди.
        self.assertTrue((self.sait / 'vulytsia' / 'velyka-vasylkivska' / 'index.html').is_file())
        stara = (self.sait / 'vulytsia' / 'chervonoarmiiska' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('url=/vulytsia/velyka-vasylkivska/', stara)
        # «Васильківська» — окрема вулиця, не злита з Великою Васильківською.
        self.assertTrue((self.sait / 'vulytsia' / 'vasylkivska' / 'index.html').is_file())
        # Подія за ст. 390-1 — на сторінці Хрещатика числом (MV-102), але без опису.
        khr = (self.sait / 'vulytsia' / 'khreshchatyk' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('9 подій', khr)
        self.assertNotIn('порушив припис', khr)

    def test_lyshe_ostanni_try_roky(self):
        """MV-32 (ZAVDANNYA-46): у публічних файлах немає чисел за роки поза останніми трьома —
        лише прапорець «у підписці»; немає адрес і описів."""
        vidkryti = D.VIDKRYTI_ROKY
        self.assertEqual(len(vidkryti), 3)
        for riven in (7, 8, 9):
            d = json.loads((self.sait / 'karta' / f'soty-{riven}.json').read_text(encoding='utf-8'))
            for f in d['soty']['features']:
                vl = f['properties']
                self.assertFalse([k for k in vl if re.fullmatch(r'[a-z]+A', k)], f'числа «усі роки» у соті {vl["id"]}')
                self.assertEqual(len(vl['y']), 3, vl['id'])
                self.assertEqual(sum(vl['y']), vl['all3'], vl['id'])
                self.assertIn(vl.get('o', 1), (1,))
        for f in self.nashi_storinky():
            t = f.read_text(encoding='utf-8')
            for rik in D.STARI_ROKY:          # у таблиці років старші роки — без чисел
                self.assertIsNone(re.search(rf'<th scope="row">{rik}</th><td>\d', t), f'{f.relative_to(self.sait)}: {rik}')
            self.assertNotIn('data-period="A"', t)
        if self.spravzhnii:
            return
        # Хрещатик: 8 подій за 2025 + 390-1 (MV-102) + 7 за 2023 + 1 без дати — на сайті лише 9 і замок на 2023
        # (у підписці — лише роки карти підписника, ZAVDANNYA-174).
        khr = (self.sait / 'vulytsia' / 'khreshchatyk' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('Вулиця Хрещатик: за 2024–2026 у даних судів — 9 подій', khr)
        self.assertIn('rik--zamok', khr)
        self.assertIn('<th scope="row">2023</th><td>у підписці</td>', khr)
        self.assertNotIn('2016–2023', khr)
        for zayve in ('17 подій', '16 подій', '>17<', '>16<', '>7<'):
            self.assertNotIn(zayve, khr)
        # Покажчик і пошук — теж лише за останні 3 роки.
        pk = {r[0]: r[3] for r in json.loads((self.sait / 'vulytsi' / 'pokazhchyk.json').read_text(encoding='utf-8'))}
        self.assertEqual(pk['khreshchatyk'], 9)
        self.assertEqual(pk.get('instytutska', 0), 0)
        # Соти: прапорець «є старші» без чисел; сота лише зі старими подіями на карту не потрапляє.
        d9 = json.loads((self.sait / 'karta' / 'soty-9.json').read_text(encoding='utf-8'))['soty']['features']
        kh = h3.latlng_to_cell(50.4476, 30.5231, 9)
        ins = h3.latlng_to_cell(50.4460, 30.5300, 9)
        za_id = {f['properties']['id']: f['properties'] for f in d9}
        self.assertEqual(za_id[kh].get('o'), 1)
        self.assertNotIn(ins, za_id)
        vsogo8 = sum(f['properties']['all3'] for f in
                     json.loads((self.sait / 'karta' / 'soty-8.json').read_text(encoding='utf-8'))['soty']['features'])
        self.assertEqual(vsogo8, 54)        # 48 відкритих + 3 домашніх + 1 домашнє з точкою + статевий і щодо дитини; старих 14 — ні


    # ---------------------------------------------------------------- ZAVDANNYA-85: будинки, райони, вітрини

    def budynok(self, shl):
        return (self.sait / 'budynok' / shl / 'index.html').read_text(encoding='utf-8')

    def test_roky_lyshe_z_karty_pidpysnyka(self):
        """ZAVDANNYA-174 (ZVIT-166, №4): «у підписці» — лише роки, які є в карті підписника (dani-edrsr S-Д.8: від 2023);
        не обіцяти «усі роки» чи 2016–2022, яких там немає."""
        import tsiny as T
        self.assertEqual(D.PIDPYSKA_VID, T.PIDPYSKA_VID)
        self.assertTrue(all(r >= D.PIDPYSKA_VID for r in D.STARI_ROKY))
        self.assertFalse(D.u_pidpystsi(2018))
        self.assertFalse(D.u_pidpystsi(D.VIDKRYTI_ROKY[0]))
        daie = ' '.join(T.pidpyska_daie())
        self.assertIn(f'з {T.PIDPYSKA_VID} року', daie)
        self.assertNotIn('усі роки', daie)
        oferta = (KORIN / 'site' / 'zahlushka' / 'oferta.html').read_text(encoding='utf-8')
        self.assertIn(f'з {T.PIDPYSKA_VID} року', oferta)
        self.assertNotIn('усі роки даних', oferta)
        d = json.loads((self.sait / 'karta' / 'soty-9.json').read_text(encoding='utf-8'))
        self.assertEqual(d['roky'], D.STARI_ROKY + D.VIDKRYTI_ROKY)
        for f in self.nashi_storinky():
            tekst = f.read_text(encoding='utf-8')
            for m in re.finditer(r'(\d{4})(?:–\d{4})?(?:</th><td>|[^<\d]{0,30})у підписці', tekst):
                self.assertGreaterEqual(int(m.group(1)), D.PIDPYSKA_VID, f'{f.relative_to(self.sait)}: «{m.group(0)}» — такого року в підписці немає')

    def test_storinka_budynku_lyshe_chysla(self):
        """MV-99, MV-100: скарги 1551 відкрито, події з рішень — лише числом за роками й групами; без описів і посилань."""
        if self.spravzhnii:
            self.skipTest('лише для штучного зведення')
        t = self.budynok('khreshchatyk/22')
        self.assertIn('<h1>вулиця Хрещатик, 22</h1>', t)
        self.assertIn('href="/vulytsia/khreshchatyk/"', t)          # будинок → вулиця
        self.assertIn('href="/rayon/pecherskyi/"', t)               # будинок → район
        self.assertIn('надійшло 7 звернень. Найчастіше — вода (5) і світло (2)', t)
        self.assertLess(t.index('>Вода<'), t.index('>Світло<'))      # теми — від більшої
        self.assertIn('У сусідніх будинках у радіусі 300', t)   # ZAVDANNYA-177: людською мовою
        for k in ('Довідка про цей будинок — 199', '3 довідки для трьох адрес — 449', 'повний звіт перед купівлею — 299'):   # ZAVDANNYA-177
            self.assertIn(k, t)
        self.assertIn('Події за 2023 з адресою будинку теж є — у підписці', t)
        tabl = t.split('Події з рішень')[1].split('</table>')[0]
        self.assertIn('<th scope="row">ДТП</th><td>—</td><td>3</td><td>—</td>', tabl)
        self.assertNotIn('>2023<', tabl)                              # старші роки — без чисел (MV-32)
        self.assertIn('"@type": "BreadcrumbList"', t)
        self.assertIn('/oplata/?tovar=dovidka', t)

    def test_b2_kvartyra_ne_chastyna_nomera(self):
        """ZAVDANNYA-110, Б-2: «43 кв32» — будинок 43; квартири й офісу немає ні в адресі сторінки, ні в заголовку."""
        import storinky_mv100 as M
        for h, tr in (('43 кв32', '43'), ('82 оф4', '82'), ('28 оф248', '28'), ('15/5 оф73', '15/5'), ('10 кв2', '10'), ('24-А', '24-А')):
            self.assertEqual(M.bez_kvartyry(h), tr)
        if self.spravzhnii:
            if not self.budynky:
                self.skipTest('без MV_BUDYNKY')
        else:
            self.assertTrue((self.sait / 'budynok' / 'khreshchatyk' / '43' / 'index.html').is_file())
        pohani = [str(p.relative_to(self.sait)) for p in self.sait.glob('budynok/*/*/index.html')
                  if re.search(r'(kv|of)\d', p.parent.name) or re.search(r'<h1>[^<]*\b(кв|оф)\s*\d', p.read_text(encoding='utf-8'))]
        self.assertEqual(pohani, [])

    def test_budynky_bez_opysiv_i_posylan(self):
        opys = re.compile(r'керуючи|зіткнення|порушив|визнав|reyestr\.court\.gov\.ua|doc_url|fabula|ОСОБА_', re.I)
        storinky = sorted((self.sait / 'budynok').rglob('index.html'))
        self.assertTrue(storinky)
        for f in storinky:
            m = opys.search(f.read_text(encoding='utf-8'))
            self.assertIsNone(m, f'{f.relative_to(self.sait)}: {m and m.group(0)}')

    def test_vulytsia_posylaietsia_na_budynky_i_tonki_ne_v_poshuku(self):
        if self.spravzhnii:
            self.skipTest('лише для штучного зведення')
        khr = (self.sait / 'vulytsia' / 'khreshchatyk' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('href="/budynok/khreshchatyk/22/"', khr)
        self.assertIn('href="/budynok/khreshchatyk/24-a/"', khr)
        tonka = self.budynok('khreshchatyk/24-a')
        self.assertIn('noindex', tonka)                              # 1 звернення — не для пошуку Google
        mapa = (self.sait / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertIn('/budynok/khreshchatyk/22/', mapa)
        self.assertNotIn('/budynok/khreshchatyk/24-a/', mapa)
        self.assertTrue((self.sait / 'budynok' / 'nevidoma' / '1' / 'index.html').is_file())   # вулиця без сторінки

    def test_rayony_vitryny_i_dovidkovi(self):
        for shl in ('rayony', 'rayon/pecherskyi', 'miy-budynok', 'osbb', 'sudova-praktyka', 'biznes', 'oplata', 'vydalyty', 'pro-dani'):
            self.assertTrue((self.sait / shl / 'index.html').is_file(), shl)
        mb = (self.sait / 'miy-budynok' / 'index.html').read_text(encoding='utf-8')
        for k in ('199', '449', '299', '399', 'по 99', 'Підписка для рієлтора'):
            self.assertIn(k, mb)
        # ZAVDANNYA-109, п. 5: період подій у продажу — з випуску (те саме правило, що в звіті), не «10 років»
        import sqlite3
        if not self.spravzhnii:
            con = sqlite3.connect(self.baza)
            roky = D.roky_danykh(con)
            con.close()
            period = f'{roky[0]}–{roky[1]}' if roky[0] != roky[1] else str(roky[0])
            self.assertIn(f'події за {period} зі стислим описом з рішення', mb)
            self.assertIn(f'Київ, {period}', (self.sait / 'biznes' / 'index.html').read_text(encoding='utf-8'))
        for shl in ('miy-budynok', 'biznes'):
            self.assertNotIn('10 років', (self.sait / shl / 'index.html').read_text(encoding='utf-8'), shl)
        con = sqlite3.connect(':memory:')
        con.execute('create table document(data_rishennia text)')
        con.executemany('insert into document values (?)', [('2011-05-01',)] * 3 + [('2024-01-02',)] * 60 + [('2025-01-02',)] * 100)
        self.assertEqual(D.roky_danykh(con), (2024, 2025))
        self.assertIn('10 робочих днів', (self.sait / 'vydalyty' / 'index.html').read_text(encoding='utf-8'))
        oplata = (self.sait / 'oplata' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('noindex', oplata)
        self.assertIn('/zahlushka/?dzherelo=oplata#peredzamovlennya', oplata)
        self.assertNotIn('name="poshta"', oplata)                    # пошта не йде в адресу сторінки
        self.assertIn('скоро', (self.sait / 'sudova-praktyka' / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('оферт', (self.sait / 'biznes' / 'index.html').read_text(encoding='utf-8'))
        holovna = (self.sait / 'index.html').read_text(encoding='utf-8')
        for shl in ('/miy-budynok/', '/osbb/', '/sudova-praktyka/', '/biznes/', '/rayon/'):
            self.assertIn(f'href="{shl}', holovna)

    def test_tsiny_lyshe_z_mv100(self):
        """ZAVDANNYA-88, п. 2: на всьому сайті (і в заглушці з офертою) — лише суми з таблиці site/tsiny.py (MV-100, MV-102)
        і 0 за карту; 690 (MV-11) немає ніде; «Для бізнесу» — ціна за домовленістю з формою запиту."""
        import tsiny as T
        self.assertEqual({k: v for k, v in T.TSINY.items()},
                         {'dovidka': 199, 'try': 449, 'zvit': 299, 'pidpyska': 399, 'dodatkova': 99, 'rieltor': 799,
                          'osbb': 1490, 'biznes': None, 'spdovidka': 199, 'spyurist': 490})
        dozvoleni = T.dozvoleni_sumy()
        for f in self.storinky + sorted(self.sait.rglob('*.js')):
            t = f.read_text(encoding='utf-8')
            self.assertNotRegex(t, r'690[\s\u00a0]*грн', f'{f.relative_to(self.sait)}: 690 грн')
            for n in re.findall(r'(\d[\d\u00a0 ]*)(?:\u00a0|\s)?грн', t):
                self.assertIn(int(re.sub(r'\D', '', n)), dozvoleni, f'{f.relative_to(self.sait)}: {n} грн')
        biznes = (self.sait / 'biznes' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('ціна за домовленістю', biznes)
        # ZAVDANNYA-157: своя форма запиту (POST /api/forma/biznes), стара форма заглушки — запасна
        self.assertIn('id="biznes-forma"', biznes)
        self.assertIn('href="/zahlushka/?shcho=kompaniya&amp;dzherelo=biznes#peredzamovlennya">запасна форма', biznes)
        mb = (self.sait / 'miy-budynok' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('799\u00a0грн на місяць', mb)
        self.assertIn('1\u00a0490\u00a0грн на рік', (self.sait / 'osbb' / 'index.html').read_text(encoding='utf-8'))

    def test_dribnytsi_d1_d2_d6(self):
        """ZAVDANNYA-110: заголовки ≤ 70 знаків і описи ≤ 170 (Д-1); dateModified будинку, картинка району, розмітка
        WebSite й Organization на головній (Д-2); у покажчику району немає вулиць з «0» (Д-6)."""
        dovgi = []
        for p in self.nashi_storinky():
            t = p.read_text(encoding='utf-8')
            tl = html.unescape(re.search(r'<title>([^<]*)</title>', t).group(1))
            op = html.unescape(re.search(r'<meta name="description" content="([^"]*)">', t).group(1))
            if len(tl) > 70 and not tl.endswith(' — тепер'):
                if len(tl) - len(tl.split(',')[0]) > 70:      # довга сама назва вулиці — не наша вина
                    dovgi.append((str(p.relative_to(self.sait)), tl))
            if len(op) > 170:
                dovgi.append((str(p.relative_to(self.sait)), op))
        self.assertEqual(dovgi[:5], [])
        h = (self.sait / 'index.html').read_text(encoding='utf-8')
        self.assertIn('"@type": "WebSite"', h)
        self.assertIn('"@type": "Organization"', h)
        for r in self.sait.glob('rayon/*/index.html'):
            self.assertIn('og:image', r.read_text(encoding='utf-8'), r)
            self.assertTrue((r.parent / 'kartynka.png').is_file())
        if not self.spravzhnii:
            self.assertIn('"dateModified": "2026-11-08"', self.budynok('khreshchatyk/22'))
        for p in self.sait.glob('vulytsi/*/index.html'):
            self.assertNotRegex(p.read_text(encoding='utf-8'), r'<small>0</small>', p)

    def test_t8_storinka_vyboru_ye(self):
        """Т-8: штучна база тепер має сторінку «оберіть» — ту, на якій тести падали на справжньому випуску."""
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        t = (self.sait / 'vulytsia' / 'starokyivska' / 'index.html').read_text(encoding='utf-8')
        self.assertTrue(sluzhbova(t))
        self.assertIn('/vulytsia/khreshchatyk/', t)

    def test_onovleno_na_budynku_i_vulytsi(self):
        """ZAVDANNYA-88, п. 3: «Оновлено: місяць рік» на сторінках будинку й вулиці — з дати випуску."""
        versiia = self.zvit['versiia']
        m = re.match(r'(\d{4})-(\d{2})', versiia)
        ochikuvano = f'Оновлено: {self.zs.MISIATSI[int(m.group(2)) - 1]} {m.group(1)}'
        storinky = [p for p in self.storinky if p.relative_to(self.sait).parts[0] in ('budynok', 'vulytsia')
                    and not sluzhbova(p.read_text(encoding='utf-8'))]
        self.assertTrue(any(p.parts[-4] == 'budynok' or p.relative_to(self.sait).parts[0] == 'budynok' for p in storinky))
        for p in storinky:
            self.assertIn(ochikuvano, p.read_text(encoding='utf-8'), p.relative_to(self.sait))
        if not self.spravzhnii:
            self.assertEqual(ochikuvano, 'Оновлено: листопад 2026')

    def test_kartynky_dlia_soczmerezh(self):
        """ZAVDANNYA-88, п. 3: картинка для поширення (og:image) у будинку, вулиці й вітринах — 1200 × 630 PNG; підпис —
        лише назва й числа, без описів подій."""
        from PIL import Image
        mozhna = re.compile(r'^[^:]+: \d[\d\u00a0]* [^,\d]+( \d[\d–]*[^,]*)?(, \d[\d\u00a0]* [^,]+)*$')
        opys = re.compile(r'ОСОБА|керуючи|зіткнення|порушив|reyestr|ґвалт|дитин', re.I)
        z_kartynkoyu = 0
        for p in self.nashi_storinky():
            t = p.read_text(encoding='utf-8')
            chastyny = p.relative_to(self.sait).parts
            potribna = chastyny[0] in ('budynok', 'vulytsia', 'miy-budynok', 'osbb', 'sudova-praktyka', 'biznes') \
                and not sluzhbova(t)
            m = re.search(r'<meta property="og:image" content="([^"]+)">', t)
            if not potribna:
                continue
            self.assertIsNotNone(m, f'{p.relative_to(self.sait)}: немає og:image')
            url = m.group(1).split('://', 1)[1].split('/', 1)[1]
            f = self.sait / url
            self.assertTrue(f.is_file(), url)
            with Image.open(f) as im:
                self.assertEqual((im.format, im.size), ('PNG', (1200, 630)), url)
            alt = html.unescape(re.search(r'<meta property="og:image:alt" content="([^"]+)">', t).group(1))
            self.assertRegex(alt, mozhna)
            self.assertIsNone(opys.search(alt), alt)
            self.assertIsNone(ZABORONENI_SLOVA.search(alt), alt)
            self.assertIn('<meta name="twitter:card" content="summary_large_image">', t)
            z_kartynkoyu += 1
        self.assertGreater(z_kartynkoyu, 4)
        if not self.spravzhnii:
            t = self.budynok('khreshchatyk/22')
            self.assertIn('content="вулиця Хрещатик, 22: 7 звернень до 1551 за 12 місяців, 3 події з рішень судів за 2024–2026"', t)

    def test_khostynh_workers_pachky(self):
        """ZAVDANNYA-88, п. 1: варіант workers — будинки в пачках; кожен будинок дістається з пачки байт у байт таким,
        як у варіанті pages; файлів менше; скрипт worker/index.js віддає ту саму сторінку (перевірка в Node)."""
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        import khostynh as KH
        teka = Path(self.tmp.name) / 'sait-workers'
        stare, KH.BUDYNKIV_U_PACHTSI = KH.BUDYNKIV_U_PACHTSI, 1      # по пачці на будинок: перевіряє і хеш
        try:
            zv = self.zs.zibraty_sait(self.baza, teka, self.pereim, KORIN / 'data' / 'borders.json', budynky=self.budynky,
                                      khostynh='workers')
        finally:
            KH.BUDYNKIV_U_PACHTSI = stare
        self.assertFalse((teka / 'budynok').exists())
        self.assertEqual(zv['pachok_budynkiv'], len(BUDYNKY['budynky']))
        # файлів: як у pages, але замість двох файлів на будинок — дві пачки на кожні BUDYNKIV_U_PACHTSI будинків
        self.assertEqual(zv['failiv'], self.zvit['failiv'] - 2 * len(BUDYNKY['budynky']) + 2 * zv['pachok_budynkiv'])
        budynky = sorted(p.parent.relative_to(self.sait / 'budynok').as_posix()
                         for p in (self.sait / 'budynok').rglob('index.html'))
        self.assertTrue(budynky)
        for slug in budynky:
            self.assertRegex(slug, r'^[a-z0-9-]+/[a-z0-9-]+$')
            n = KH.fnv1a(slug) % zv['pachok_budynkiv']
            s = (teka / '_budynky' / KH.nazva_pachky(n, False)).read_bytes()
            k = (teka / '_budynky' / KH.nazva_pachky(n, True)).read_bytes()
            self.assertEqual(KH.rozpakuvaty(s, slug), (self.sait / 'budynok' / slug / 'index.html').read_bytes())
            self.assertEqual(KH.rozpakuvaty(k, slug), (self.sait / 'budynok' / slug / 'kartynka.png').read_bytes())
        konfig = (Path(zv['teka_workera']) / 'wrangler.jsonc').read_text(encoding='utf-8')
        konfig = json.loads(konfig.split('\n', 1)[1])
        self.assertEqual(konfig['vars']['PACHOK'], str(zv['pachok_budynkiv']))
        self.assertEqual(konfig['assets']['run_worker_first'], ['/budynok/*'] + KH.MARSHRUTY_PRODAZHU + KH.KOLODY_IHOR)
        # Колоди ігор зі збирача (крім налаштувань) — усі через скрипт, щоб прибрана подія зникала одразу (ZAVDANNYA-161)
        zibrani = set(re.findall(r"IHRY_DANI\['\w+'\] = '(/ihry/[a-z-]+\.json)'", (KORIN / 'site' / 'zibraty_sait.py').read_text(encoding='utf-8')))
        self.assertEqual(zibrani - {'/ihry/nalashtuvannia.json'}, set(KH.KOLODY_IHOR))
        js = (KORIN / 'site' / 'worker' / 'prodazh' / 'prybrannia.js').read_text(encoding='utf-8')
        self.assertEqual(re.findall(r"'(/ihry/[a-z-]+\.json)'", js.split('export const KOLODY = [', 1)[1].split('];', 1)[0]), KH.KOLODY_IHOR)
        self.assertNotIn('PRODAZH', konfig['vars'], 'без --prodazh-d1 продаж вимкнено')
        self.assertFalse((Path(zv['teka_workera']) / 'testy').exists())
        self.assertEqual(konfig['assets']['directory'], f'../{teka.name}')
        self.assertNotRegex(json.dumps(konfig), r'(?i)token|key|secret|ключ')
        # FNV-1a — як у JavaScript (контрольне значення для «a»).
        self.assertEqual(KH.fnv1a('a'), 0xE40C292C)
        import shutil
        import subprocess
        if not shutil.which('node'):
            self.skipTest('немає Node — скрипт Workers не запущено')
        skrypt = Path(self.tmp.name) / 'perevirka-workera.mjs'
        skrypt.write_text(f"""
import fs from 'node:fs';
const w = (await import({json.dumps((Path(zv['teka_workera']) / 'index.js').as_uri())})).default;
const koren = {json.dumps(str(teka))};
const env = {{ PACHOK: {json.dumps(str(zv['pachok_budynkiv']))}, ASSETS: {{ async fetch(req) {{
  const p = new URL(req.url).pathname;
  const f = koren + (p.endsWith('/') ? p + 'index.html' : p);
  if (!fs.existsSync(f)) return new Response('nema', {{ status: 404 }});
  return new Response(fs.readFileSync(f));
}} }} }};
const out = {{}};
for (const shl of process.argv.slice(2)) {{
  const r = await w.fetch(new Request('https://x.ua' + shl), env);
  const b = Buffer.from(await r.arrayBuffer());
  out[shl] = [r.status, r.headers.get('content-type'), r.headers.get('location'), b.toString('base64')];
}}
console.log(JSON.stringify(out));
""", encoding='utf-8')
        self.assertGreater(len({KH.fnv1a(s) % zv['pachok_budynkiv'] for s in budynky}), 1, 'будинки — у різних пачках')
        slug = budynky[0]
        shliakhy = ([f'/budynok/{s}/' for s in budynky] + [f'/budynok/{s}/kartynka.png' for s in budynky]
                    + [f'/budynok/{slug}', '/budynok/nema/1/', '/vulytsi/'])
        r = json.loads(subprocess.run(['node', str(skrypt), *shliakhy], capture_output=True, text=True, check=True).stdout)
        import base64
        for s in budynky:
            st, typ, _, tilo = r[f'/budynok/{s}/']
            self.assertEqual((st, typ), (200, 'text/html; charset=utf-8'))
            self.assertEqual(base64.b64decode(tilo), (self.sait / 'budynok' / s / 'index.html').read_bytes())
            st, typ, _, tilo = r[f'/budynok/{s}/kartynka.png']
            self.assertEqual((st, typ), (200, 'image/png'))
            self.assertEqual(base64.b64decode(tilo), (self.sait / 'budynok' / s / 'kartynka.png').read_bytes())
        self.assertEqual(r[f'/budynok/{slug}'][0], 301)
        self.assertTrue(r[f'/budynok/{slug}'][2].endswith(f'/budynok/{slug}/'))
        self.assertEqual(r['/budynok/nema/1/'][0], 404)
        self.assertEqual(r['/vulytsi/'][0], 200)      # решта сайту — звичайні файли

    def test_mezha_failiv_pages(self):
        """Межа 20 000 файлів лишається для варіанта pages (ZAVDANNYA-88: не прибирати, доки не вибрано)."""
        import khostynh as KH
        self.assertEqual(KH.MEZHA_FAILIV['pages'], 20000)
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        with self.assertRaises(SystemExit):
            self.zs.zibraty_sait(self.baza, Path(self.tmp.name) / 'sait-mezha', self.pereim, KORIN / 'data' / 'borders.json',
                                 budynky=self.budynky, mezha_failiv=50)

    def test_google_154(self):
        """ZAVDANNYA-154: зібраний сайт «очима Google» — без помилок (site/perevirka_google.py): канонічні адреси, один
        заголовок і опис потрібної довжини, карта сайту ↔ noindex, без сиріт, битих посилань і дублікатів, розмітка
        schema.org; у заголовках і описах — ні оцінки безпечності, ні «відгуків»."""
        import perevirka_google as G
        import zaholovky as ZH
        z = G.perevirka(self.sait, self.zs.ADRESA_SAITU)
        self.assertEqual(z['pomylky'], {})
        self.assertGreater(z['jsonld'].get('BreadcrumbList', 0), 0)
        for p in self.nashi_storinky():
            t = p.read_text(encoding='utf-8')
            for m in (G.TITLE.search(t), G.OPYS.search(t)):
                if m:
                    self.assertIsNone(ZH.ZABORONENO.search(m.group(1)), (p, m.group(1)))
        if self.spravzhnii:
            return
        b = self.budynok('khreshchatyk/22')
        self.assertIn('<title>вул. Хрещатик, 22, Київ — скарги мешканців і події з рішень судів</title>', b)
        import storinky_mv100 as M          # сусіди інших вулиць у радіусі 400 м, найближчі першими
        bb = [{'slug': s, 'vulytsia': v, 'lat': lat, 'lon': 30.5} for s, v, lat in
              (('a/1', 'A', 50.4500), ('a/2', 'A', 50.4501), ('b/1', 'B', 50.4520), ('c/1', 'C', 50.4510), ('d/1', 'D', 50.4600))]
        self.assertEqual([x['slug'] for x in M.budynky_poruch(bb)['a/1']], ['c/1', 'b/1'])
        self.assertIn('/budynok/nevidoma/1/', (self.sait / 'rayony' / 'index.html').read_text(encoding='utf-8'))
        red = (self.sait / '_redirects').read_text(encoding='utf-8')
        self.assertIn('/vulytsia/chervonoarmiiska/ /vulytsia/velyka-vasylkivska/ 301', red)
        self.assertIn('/oferta.html /zahlushka/oferta.html 301', red)      # ZAVDANNYA-172: коротка адреса оферти не 404
        oferta = (self.sait / 'zahlushka' / 'oferta.html').read_text(encoding='utf-8')
        self.assertIn('href="/dostupnist/">Доступність', oferta)          # правові сторінки — у вигляді сайту
        self.assertNotIn('Передзамовлення', oferta)

    def test_zaholovky_vmishchuiutsia(self):
        """ZAVDANNYA-154: довгі адреси — коротший хвіст, а не обрізаний Google заголовок."""
        import zaholovky as ZH
        for v in ('a', 'b', 'c'):
            for vul, nom in (('вулиця Хрещатик', '22'), ('проспект Академіка Глушкова', '40/2'),
                             ('вулиця Генерала Генерального Дуже-Довгоназвенка', '148-В корп. 2')):
                self.assertLessEqual(len(ZH.title_budynku(vul, nom, v)), 70, (v, vul))
        self.assertEqual(ZH.korotka_nazva('Йорданська вулиця'), 'вул. Йорданська')
        self.assertEqual(ZH.korotka_nazva('Харківське шосе'), 'Харківське шосе')
        self.assertLessEqual(len(ZH.opys_budynku('проспект Академіка Глушкова', '40/2', 'Голосіївський район',
                                                 '1 125 звернень', 'опалення й гаряча вода', '112 подій', '2024–2026')), 160)

    def test_sitemap_dilytsia_na_chastyny(self):
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        stara = self.zs.MEZHA_SITEMAP
        self.zs.MEZHA_SITEMAP = 5
        try:
            teka = Path(self.tmp.name) / 'sait-sitemap'
            self.zs.zibraty_sait(self.baza, teka, self.pereim, KORIN / 'data' / 'borders.json', budynky=self.budynky)
        finally:
            self.zs.MEZHA_SITEMAP = stara
        indeks = (teka / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertIn('<sitemapindex', indeks)
        # ZAVDANNYA-154: частини за видом сторінок, кожна до MEZHA_SITEMAP адрес
        chastyny = sorted(p.name for p in teka.glob('sitemap-*.xml'))
        self.assertIn('sitemap-vulytsi-2.xml', chastyny)
        self.assertIn('sitemap-budynky.xml', chastyny)
        self.assertIn('sitemap-inshe-2.xml', chastyny)
        for n in chastyny:
            self.assertIn(f'/{n}</loc>', indeks)
            self.assertLessEqual((teka / n).read_text(encoding='utf-8').count('<loc>'), 5)


def brauzer_dlya_karty() -> str | None:
    """Chrome чи Edge для перевірки карти (потрібен WebGL; програмний — swiftshader)."""
    import shutil
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return None
    for p in (os.environ.get('MV_CHROME'), shutil.which('google-chrome'), shutil.which('chromium'),
              r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe', r'C:\Program Files\Microsoft\Edge\Application\msedge.exe'):
        if p and Path(p).is_file():
            return p
    return None


BRAUZER = brauzer_dlya_karty() if YE_H3 else None


@unittest.skipUnless(BRAUZER, 'немає Playwright або Chrome/Edge, або h3 — перевірку в браузері пропущено')
class SaitUBrauzeri(unittest.TestCase):
    """ZAVDANNYA-110: пошук будинку (Т-2), оплата пам'ятає вибір (Т-3), телефон — ширина (Т-5), назва логотипа (Т-6),
    кнопки карти (Т-11)."""

    @classmethod
    def setUpClass(cls):
        import functools
        import http.server
        import threading
        import zibraty_sait
        from playwright.sync_api import sync_playwright
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        stvoryty_bazu(tmp / 'events.db')
        stvoryty_pereimenuvannya(tmp / 'pereim.csv')
        (tmp / 'budynky.json').write_text(json.dumps(BUDYNKY, ensure_ascii=False), encoding='utf-8')
        zibraty_sait.zibraty_sait(tmp / 'events.db', tmp / 'sait', tmp / 'pereim.csv', KORIN / 'data' / 'borders.json',
                                  budynky=tmp / 'budynky.json')
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(tmp / 'sait')))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        cls.pw = sync_playwright().start()
        cls.b = cls.pw.chromium.launch(executable_path=BRAUZER, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.b.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.tmp.cleanup()

    def storinka(self, shlyakh, telefon=False):
        k = self.b.new_context(viewport={'width': 390, 'height': 844} if telefon else {'width': 1280, 'height': 800},
                               is_mobile=telefon, has_touch=telefon, reduced_motion='reduce')
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        self.addCleanup(k.close)
        s = k.new_page()
        pomylky = []
        s.on('pageerror', lambda e: pomylky.append(str(e)))
        s.goto(self.url + shlyakh)
        return s, pomylky

    def poshuk(self, s, zapyt):
        s.fill('#poshuk-vulytsi', zapyt)
        s.wait_for_function('() => !document.getElementById("poshuk-spysok").hidden')
        s.wait_for_timeout(200)
        return s.eval_on_selector_all('#poshuk-spysok li', 'ls => ls.map(l => [l.textContent, (l.querySelector("a") || {}).href || ""])')

    def test_t2_poshuk_budynku_i_staroi_nazvy(self):
        for shlyakh in ('/miy-budynok/', '/vulytsi/'):
            s, pomylky = self.storinka(shlyakh)
            r = self.poshuk(s, 'Хрещатик 24а')
            self.assertTrue(r[0][1].endswith('/budynok/khreshchatyk/24-a/'), r)
            r = self.poshuk(s, 'хрещатик, буд. 22')
            self.assertTrue(r[0][1].endswith('/budynok/khreshchatyk/22/'), r)
            r = self.poshuk(s, 'Хрещатик 999')
            self.assertIn('Будинку 999 в даних немає', r[0][0])
            self.assertTrue(r[1][1].endswith('/vulytsia/khreshchatyk/'), r)
            r = self.poshuk(s, 'Червоноармійська')
            self.assertIn('Велика Васильківська', r[0][0])
            self.assertEqual(pomylky, [])

    def test_t3_oplata_pamiataie_vybir(self):
        s, pomylky = self.storinka('/budynok/khreshchatyk/22/')
        s.click('a.knopka--holovna[href^="/oplata/"]')
        s.wait_for_selector('#vybir:not([hidden])')
        self.assertIn('Довідка про будинок', s.inner_text('#vybir'))
        self.assertIn('вулиця Хрещатик, 22', s.inner_text('#vybir'))
        href = s.get_attribute('#oplata-poshta', 'href')
        self.assertIn('dzherelo=oplata-dovidka-budynok', href)
        self.assertIn('shcho=analiz', href)
        s.click('#oplata-poshta')
        s.wait_for_selector('#adresa2')
        s.wait_for_function("() => document.querySelector('#adresa2').value !== ''", timeout=5000)   # поле заповнює скрипт після завантаження
        self.assertEqual(s.input_value('#adresa2'), 'вулиця Хрещатик, 22')
        self.assertEqual(s.input_value('#shcho'), 'analiz')
        self.assertEqual(pomylky, [])

    def test_t5_t6_t11_telefon(self):
        for shlyakh in ('/budynok/khreshchatyk/22/', '/vulytsia/khreshchatyk/', '/miy-budynok/', '/oplata/?tovar=dovidka'):
            s, _ = self.storinka(shlyakh, telefon=True)
            s.wait_for_timeout(300)
            self.assertLessEqual(s.evaluate('document.documentElement.scrollWidth'), 390, shlyakh)
            self.assertEqual(s.get_attribute('a.lohotyp', 'aria-label'), 'Моя вулиця — на головну')
        s, _ = self.storinka('/?vau=0', telefon=True)
        s.wait_for_timeout(500)
        prava = s.evaluate('Math.max(...[...document.querySelectorAll(".verkh-ryad > *")].map(e => e.getBoundingClientRect().right))')
        self.assertLessEqual(prava, 390)
ZNIMOK = '''() => { const r = s => { const b = document.querySelector(s).getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; };
    const k = MvKarta.karta, c = k.getCenter();
    return { verkh: r('.verkh-ryad'), filtr: r('#filtr'), dzherela: r('#dzherela'), karta: r('#karta-mista'),
             kamera: [c.lng.toFixed(6), c.lat.toFixed(6), k.getZoom().toFixed(4), k.getPitch().toFixed(2)] }; }'''


@unittest.skipUnless(BRAUZER, 'немає Playwright або Chrome/Edge, або h3 — перевірку карти в браузері пропущено')
class KartaUBrauzeri(unittest.TestCase):
    """Карта у вигляді М7 (ZAVDANNYA-45): нічого не рухається, коли картка відкривається й закривається; пошук
    знаходить вулицю з даних і відкриває її соту. Підкладку не вантажимо — перевірка не залежить від мережі."""

    @classmethod
    def setUpClass(cls):
        import functools
        import http.server
        import threading
        import zibraty_sait
        from playwright.sync_api import sync_playwright
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        stvoryty_bazu(tmp / 'events.db')
        stvoryty_pereimenuvannya(tmp / 'pereim.csv')
        (tmp / 'budynky.json').write_text(json.dumps(BUDYNKY, ensure_ascii=False), encoding='utf-8')
        zibraty_sait.zibraty_sait(tmp / 'events.db', tmp / 'sait', tmp / 'pereim.csv', KORIN / 'data' / 'borders.json',
                                  budynky=tmp / 'budynky.json')
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(tmp / 'sait')))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        cls.pw = sync_playwright().start()
        cls.b = cls.pw.chromium.launch(executable_path=BRAUZER, args=[
            '--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])

    @classmethod
    def tearDownClass(cls):
        cls.b.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.tmp.cleanup()

    def storinka(self, shyryna=1280, vysota=800, vau='0'):
        k = self.b.new_context(viewport={'width': shyryna, 'height': vysota}, reduced_motion='reduce',
                               is_mobile=shyryna < 700, has_touch=shyryna < 700)
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        self.addCleanup(k.close)
        s = k.new_page()
        pomylky = []
        s.on('pageerror', lambda e: pomylky.append(str(e)))
        s.goto(self.url + ('/?vau=' + vau if vau is not None else '/') + '#14.5/50.4477/30.5231/0/40')
        s.wait_for_function('() => window.MvKarta && MvKarta.gotovo', timeout=60000)
        s.wait_for_timeout(500)
        return s, pomylky

    def test_nichoho_ne_zsuvayetsya_pry_kartsi(self):
        for shyryna, vysota in ((1280, 800), (390, 844)):
            s, pomylky = self.storinka(shyryna, vysota)
            do = s.evaluate(ZNIMOK)
            k = s.evaluate("() => { const id = MvKarta.colG(); const v = MvKarta.vershyny(id); return [id, v[0]]; }")
            self.assertTrue(k[1], 'немає жодної вершини')
            s.evaluate('([id, k]) => MvKarta.vidkryty(id, k)', k)
            s.wait_for_timeout(400)
            self.assertFalse(s.evaluate('document.getElementById("kartka").hidden'))
            # ZAVDANNYA-174 (ZVIT-166, №2): кнопки — на покупку цього місця, не на заглушку
            dali = s.evaluate("() => [...document.querySelectorAll('#kartka .k-dali a')].map(a => [a.textContent, a.getAttribute('href')])")
            self.assertTrue(dali[0][0].startswith('Що саме тут було — адреси й описи · підписка 399'), dali)
            self.assertIn('Скоро — залиште пошту', dali[0][0])                # збірка тесту — без оплати («скоро»)
            self.assertEqual(dali[0][1], '/oplata/?tovar=pidpyska&dzherelo=sota')
            self.assertEqual(dali[1], ['Довідка про свій будинок — 199\xa0грн', '/miy-budynok/?dzherelo=sota'])
            self.assertFalse([h for _, h in dali if 'zahlushka' in h], dali)
            # ZAVDANNYA-135: третя — «Як суди вирішують такі справи» (покажчик «Судової практики»), якщо найчастіша група має статтю
            for napys, href in dali[2:]:
                self.assertEqual(napys, 'Як суди вирішують такі справи')
                self.assertRegex(href, r'^/sudova-praktyka/\?q=(124|130|185|309|173)&dzherelo=sota#poshuk$')
            self.assertEqual(s.evaluate(ZNIMOK), do, f'{shyryna}: щось зсунулося при відкритті картки')
            # Підписник (карта підписника відкривалась у цьому браузері) — одразу це місце в його карті
            s.evaluate("([id, k]) => { localStorage.setItem('mv-pidpysnyk', String(Date.now())); MvKarta.vidkryty(id, k); }", k)
            pk = s.evaluate("() => [...document.querySelectorAll('#kartka .k-dali a')].map(a => [a.textContent, a.getAttribute('href')])")
            self.assertEqual(pk[0][0], 'Відкрити це місце в моїй карті')
            self.assertRegex(pk[0][1], r'^/pidpysnyk/#z=1[2-5](\.\d)?/50\.\d{5}/30\.\d{5}$')
            self.assertNotIn('/oplata/', ' '.join(h for _, h in pk))
            s.evaluate("([id, k]) => { localStorage.removeItem('mv-pidpysnyk'); MvKarta.vidkryty(id, k); }", k)
            s.wait_for_timeout(300)
            s.click('.k-x')
            s.wait_for_timeout(300)
            self.assertTrue(s.evaluate('document.getElementById("kartka").hidden'))
            self.assertEqual(s.evaluate(ZNIMOK), do, f'{shyryna}: щось зсунулося при закритті картки')
            self.assertEqual(pomylky, [])

    def test_vau_za_zamovchuvanniam(self):
        """MV-120: без параметра — «вау», сторінка без помилок. Тут «менше руху» в системі — тому одразу кінцевий вигляд і
        «Де ви живете?», без лічильника місяців (ZAVDANNYA-174, ZVIT-171 №5); «Роки оживають» без «менше руху» —
        tests/test_holovna_lehka.py і tests/test_karta_174.py."""
        s, pomylky = self.storinka(vau=None)
        s.wait_for_selector('.vau-rayony', timeout=15000)
        self.assertFalse(s.evaluate("() => !!document.querySelector('.vau-lich')"))
        self.assertEqual(pomylky, [])

    def test_poshuk_vulytsi_z_danykh(self):
        s, pomylky = self.storinka()
        znaideno = s.evaluate("() => MvKarta.poshuk('хрещ')")
        self.assertTrue(any('Хрещатик' in n for n in znaideno), znaideno)
        s.fill('#poshuk-karty', '')
        s.click('#poshuk-karty')
        s.keyboard.type('хрещ')
        s.wait_for_selector('#pidkazky li[data-j]')
        s.keyboard.press('Enter')
        s.wait_for_function('() => !document.getElementById("kartka").hidden', timeout=15000)
        self.assertIn('Хрещатик', s.inner_text('#kartka h2'))
        self.assertIn('под', s.inner_text('#kartka'))
        self.assertEqual(pomylky, [])
        # Без подій у даних — так і кажемо.
        s.click('.k-x')
        s.evaluate("() => MvKarta.karta.jumpTo({center: [30.30, 50.30], zoom: 14})")
        s.wait_for_timeout(300)
        s.mouse.click(640, 500)
        s.wait_for_timeout(300)
        self.assertEqual(s.inner_text('#pidkazka'), 'Тут немає подій у даних')

    def test_poshuk_budynku_na_holovnii(self):
        """ZAVDANNYA-150, п. 1: «вулиця + номер» на головній → сторінка будинку, як у «Мій будинок»."""
        s, pomylky = self.storinka()
        znaideno = s.evaluate("() => MvKarta.poshuk('Хрещатик, буд. 22')")
        self.assertTrue(znaideno[0].endswith('/budynok/khreshchatyk/22/'), znaideno)
        s.fill('#poshuk-karty', '')
        s.click('#poshuk-karty')
        s.keyboard.type('хрещатик 24а')
        s.wait_for_selector('#pidkazky li[data-j]')
        self.assertIn('будинок', s.inner_text('#pidkazky li[data-j="0"]'))
        s.keyboard.press('Enter')
        s.wait_for_url('**/budynok/khreshchatyk/24-a/', timeout=10000)
        self.assertEqual(pomylky, [])


if __name__ == '__main__':
    unittest.main()
