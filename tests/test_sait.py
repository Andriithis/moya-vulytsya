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

ZABORONENO_V_HTML = re.compile(r'ОСОБА_|АДРЕСА_|\bкв\.\s*№?\s*\d|квартир[аиіу]?\s*№?\s*\d', re.I)
# «не «небезпечніше»» у легенді — обов'язковий підпис системи дизайну, не оцінка.
DOZVOLENI_FRAZY = ('не «небезпечніше»',)
ZABORONENI_SLOVA = re.compile(r'небезпечн|безпечн|рейтинг', re.I)
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
    # Подія за ст. 390-1 КК (не позначена у випуску) — на сайті лише числом у шестикутнику.
    n += 1
    con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)', (str(n), 'суд', '2025-01-01', 'вирок', '1', '', f'https://x.ua/{n}'))
    con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)', (n, 'вул. Хрещатик, 99', 'house', 50.4480, 30.5232, 'osm'))
    con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (f'{n}-1', str(n), 1, '2025-04-04', None, 'НАС', 'ст.390-1 КК · невиконання обмежувальних приписів',
                 'ОСОБА_9 порушив припис', 0, '11210:4360', n))
    con.execute("INSERT INTO release VALUES ('2026-11-08', ?, 'x')", (n,))
    con.commit()
    con.close()


def stvoryty_pereimenuvannya(shlyakh: Path) -> None:
    # шапка — як у dani-edrsr/config/pereimenuvannia-kyiv.csv
    shlyakh.write_text('stara_nazva,nova_nazva,typ,rayon,nomer_rishennia,data_rishennia,posylannia,perelik_kmda,prymitka\n'
                       'Червоноармійська,Велика Васильківська,вулиця,,,,https://example.org,так,тест\n'
                       'Червонозоряний,Валерія Лобановського,проспект,,,,https://example.org,так,тест\n', encoding='utf-8')


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

    def test_skorochennia(self):
        self.assertTrue(D.sumisni(D.kliuch('В. Лобановського'), D.kliuch('Валерія Лобановського'))[0])
        self.assertTrue(D.sumisni(D.kliuch('Лобановського'), D.kliuch('Валерія Лобановського'))[0])
        self.assertFalse(D.sumisni(D.kliuch('М. Лобановського'), D.kliuch('Валерія Лобановського'))[0])

    def test_translit(self):
        self.assertEqual(D.translit('Хрещатик'), 'khreshchatyk')
        self.assertEqual(D.translit('Кадетський Гай'), 'kadetskyi-hai')
        self.assertEqual(D.translit("Юрія Іллєнка"), 'yuriia-illienka')

    def test_istoriia_bez_imen_i_kvartyr(self):
        t = D.ochyshchena_istoriia('ОСОБА_1 вчинив ДТП біля буд. 5 і мешкає в кв. 12, ОСОБА_2 свідок. ' * 3)
        self.assertNotIn('ОСОБА_', t)
        self.assertIsNone(re.search(r'кв\.\s*\d', t))
        self.assertIsNone(D.ochyshchena_istoriia('Водій Іваненко І.І. порушив правила дорожнього руху на перехресті вулиць.'))
        self.assertLessEqual(len(t), 301)


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
        else:
            cls.baza = tmp / 'events.db'
            stvoryty_bazu(cls.baza)
            cls.pereim = tmp / 'pereim.csv'
            stvoryty_pereimenuvannya(cls.pereim)
            cls.spravzhnii = False
        cls.sait = tmp / 'sait'
        cls.zvit = zibraty_sait.zibraty_sait(cls.baza, cls.sait, cls.pereim, KORIN / 'data' / 'borders.json')
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

    def test_failiv_menshe_mezhi_cloudflare(self):
        n = sum(1 for p in self.sait.rglob('*') if p.is_file())
        self.assertLess(n, 20000)

    def test_povtornyi_zapusk_daye_ti_sami_faily(self):
        druhyi = Path(self.tmp.name) / 'sait2'
        self.zs.zibraty_sait(self.baza, druhyi, self.pereim, KORIN / 'data' / 'borders.json')
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
        for riven in (8, 9):
            soty = json.loads((self.sait / 'karta' / f'soty-{riven}.json').read_text(encoding='utf-8'))
            tekst = json.dumps(soty, ensure_ascii=False)
            for slovo in ('домашнє насильство', 'обмежувальних приписів', 'статев', 'зґвалтування'):
                self.assertNotIn(slovo, tekst)
            self.assertTrue(soty['soty']['features'])

    def test_chutlyvi_lyshe_na_rivni_8(self):
        if self.spravzhnii:
            self.skipTest('лише для штучної бази')
        suma = {}
        for riven in (8, 9):
            soty = json.loads((self.sait / 'karta' / f'soty-{riven}.json').read_text(encoding='utf-8'))
            suma[riven] = sum(f['properties'].get('nasA', 0) for f in soty['soty']['features'])
        self.assertEqual(suma[8], 3)          # 2 позначені чутливі + 1 за ст. 390-1
        self.assertEqual(suma[9], 0)

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
        self.assertIn('Події по будинках цієї вулиці — у підписці', t)

    def test_try_knopky_na_storintsi_vulytsi(self):
        t = next(p for p in self.storinky if p.parts[-3] == 'vulytsia' and 'refresh' not in p.read_text(encoding='utf-8')).read_text(encoding='utf-8')
        self.assertIn('Звіт по адресі — 690', t)
        self.assertIn('>Грати<', t)
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
        # Подія за ст. 390-1 не потрапляє на сторінку Хрещатика.
        khr = (self.sait / 'vulytsia' / 'khreshchatyk' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('8 подій', khr)
        self.assertNotIn('порушив припис', khr)


if __name__ == '__main__':
    unittest.main()
