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
    # Старші роки (MV-32): 7 подій 2019 року і 1 без дати на Хрещатику, 6 подій 2018 року на вулиці, де нових немає.
    # На сайті — лише прапорець «у підписці», жодного числа (ZAVDANNYA-46).
    for vul, lat, lon, data in ([('вул. Хрещатик', 50.4476, 30.5231, f'2019-05-0{1 + j}') for j in range(7)]
                                + [('вул. Хрещатик', 50.4476, 30.5231, None)]
                                + [('вул. Інститутська', 50.4460, 30.5300, f'2018-06-0{1 + j}') for j in range(6)]):
        n += 1
        con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)',
                    (str(n), 'суд', data or '2020-01-01', 'постанова', '41080', f'{n}/19', f'https://reyestr.court.gov.ua/Review/{n}'))
        con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)', (n, f'{vul}, 7', 'house', lat, lon, 'osm'))
        con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                    (f'{n}-1', str(n), 1, data, '12:30', 'ДТП', 'ст.124 КУпАП · ДТП з пошкодженням майна',
                     FABULA_CHYSTA.format(d='01.05.2019', b='7', v=vul), 0, '11216:4344', n))
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
        self.assertEqual(suma[7], 3)          # великі соти (≈ 5 км²) — так само, лише числом
        self.assertEqual(suma[8], 3)          # 2 позначені чутливі + 1 за ст. 390-1
        self.assertEqual(suma[9], 0)

    def test_publichni_faily_karty_bez_adres_i_opysiv(self):
        """Безкоштовно — лише числа по сотах (AGENTS.md, розд. 8): у файлах карти й пошуку немає номерів будинків,
        описів подій і посилань на рішення."""
        faily = sorted((self.sait / 'karta').glob('*.json')) + [self.sait / 'vulytsi' / 'pokazhchyk.json']
        self.assertEqual({f.name for f in faily}, {'soty-7.json', 'soty-8.json', 'soty-9.json', 'poshuk.json', 'pokazhchyk.json'})
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
        # Хрещатик: 8 подій за 2025 + 7 за 2019 + 1 без дати — на сайті лише 8 і замок на 2016–2023.
        khr = (self.sait / 'vulytsia' / 'khreshchatyk' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('8 подій у даних судів за 2024–2026', khr)
        self.assertIn('rik--zamok', khr)
        self.assertIn('<th scope="row">2016–2023</th><td>у підписці</td>', khr)
        for zayve in ('16 подій', '15 подій', '>16<', '>15<', '>7<'):
            self.assertNotIn(zayve, khr)
        # Покажчик і пошук — теж лише за останні 3 роки.
        pk = {r[0]: r[3] for r in json.loads((self.sait / 'vulytsi' / 'pokazhchyk.json').read_text(encoding='utf-8'))}
        self.assertEqual(pk['khreshchatyk'], 8)
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
        self.assertEqual(vsogo8, 51)        # 48 відкритих + 3 чутливі, усі за 2025; старих 14 — не враховано


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
        zibraty_sait.zibraty_sait(tmp / 'events.db', tmp / 'sait', tmp / 'pereim.csv', KORIN / 'data' / 'borders.json')
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

    def storinka(self, shyryna=1280, vysota=800):
        k = self.b.new_context(viewport={'width': shyryna, 'height': vysota}, reduced_motion='reduce',
                               is_mobile=shyryna < 700, has_touch=shyryna < 700)
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        self.addCleanup(k.close)
        s = k.new_page()
        pomylky = []
        s.on('pageerror', lambda e: pomylky.append(str(e)))
        s.goto(self.url + '/#14.5/50.4477/30.5231/0/40')
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
            # MV-60: тихий шлях до платного — дві кнопки на сторінки заглушки
            dali = s.evaluate("() => [...document.querySelectorAll('#kartka .k-dali a')].map(a => [a.textContent, a.getAttribute('href')])")
            self.assertEqual(dali, [['Що саме тут було → підписка', '/zahlushka/?dzherelo=sota-pidpyska#tsiny'],
                                    ['Аналіз адреси', '/zahlushka/?dzherelo=sota-analiz#tsiny']])
            self.assertEqual(s.evaluate(ZNIMOK), do, f'{shyryna}: щось зсунулося при відкритті картки')
            s.click('.k-x')
            s.wait_for_timeout(300)
            self.assertTrue(s.evaluate('document.getElementById("kartka").hidden'))
            self.assertEqual(s.evaluate(ZNIMOK), do, f'{shyryna}: щось зсунулося при закритті картки')
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


if __name__ == '__main__':
    unittest.main()
