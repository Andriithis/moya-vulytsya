"""Перевірки гри «Вгадай, де це було» (ZAVDANNYA-07).

Запуск: python -m unittest tests.test_hra -v
Розрахунки гри (hra-yadro.js) перевіряються в Node; перевірки в браузері — лише якщо
є Playwright і Chrome (інакше — «пропущено» з причиною). Підкладку карти в перевірках
не завантажуємо: запити до неї перехоплюються, тож результат не залежить від мережі.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
HRA = KORIN / 'site' / 'hra'
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka'))
sys.path.insert(0, str(HRA))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import koloda  # noqa: E402
import zibraty  # noqa: E402
import zahlushka_pidmina  # noqa: E402
from test_zahlushka import CHROME  # noqa: E402

# Дозволений перелік доменів у файлах гри (крім файлів бібліотеки MapLibre у biblioteka/,
# де адреси стоять лише в коментарях ліцензії):
DOZVOLENI_DOMENY = {
    'tiles.openfreemap.org': 'підкладка карти: тайли й шрифти підписів (запити)',
    'supabase.co': 'сховище лічильників MV-8 (запити через nadsylannya.js)',
    'openstreetmap.org': 'посилання в підписі «© учасники OpenStreetMap» (не запит)',
    'w3.org': 'простір імен SVG у коді (не запит)',
}
# Куди сторінка гри може робити запити (перевірка в браузері).
DOZVOLENI_ZAPYTY = ('tiles.openfreemap.org',)
ZABORONENI = ('statevi_zlochyny', 'shchodo_ditei', 'domashnie_nasylstvo')


def demo():
    return json.loads((HRA / 'koloda-demo.json').read_text(encoding='utf-8'))


def podiya(id_, kategoriia='dtp', **inshe):
    p = {'id': id_, 'vyd': 'ДТП', 'kategoriia': kategoriia, 'rik': 2024,
         'opys_korotkyi': 'Умовний опис події для перевірки гри.', 'opys_povnyi': 'Умовний повний опис події для перевірки.',
         'adresa': 'умовна адреса', 'lat': 50.45, 'lon': 30.52, 'rishennya_nomer': '', 'rishennya_url': ''}
    p.update(inshe)
    return p


def spravzhnia_koloda(n=12, dodaty=()):
    """Умовна «справжня» колода для перевірки збирання (номери вигадані, лише для тесту)."""
    podii = [podiya(f'{100000 + i}-1', rishennya_nomer=str(100000 + i),
                    rishennya_url=f'https://reyestr.court.gov.ua/Review/{100000 + i}') for i in range(n)]
    return {'demo': False, 'versiya': 1, 'misto': 'Київ', 'podii': podii + list(dodaty)}


def node(skrypt: str) -> dict:
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(skrypt)
    try:
        return json.loads(subprocess.check_output(['node', f.name, str(HRA / 'hra-yadro.js')], timeout=30))
    finally:
        Path(f.name).unlink()


@unittest.skipUnless(shutil.which('node'), 'немає Node.js — перевірку розрахунків гри пропущено')
class YadroTests(unittest.TestCase):
    """hra-yadro.js — те, що реально працює в грі."""

    def test_formula_ochok(self):
        r = node(r'''
const Y = require(process.argv[2]);
const d = [0, 10, 50, 50.5, 100, 200, 500, 1000, 2000, 4999, 5000, 12000, -5, NaN];
const mon = [];
for (let m = 50; m <= 5000; m += 7) mon.push(Y.ochky(m));
process.stdout.write(JSON.stringify({ o: d.map(Y.ochky), mon,
  vidstan: Math.round(Y.vidstan(50.4501, 30.5241, 50.4651, 30.5157)),
  tekst: [30, 340, 999, 1000, 1240, 9960, 12400].map(Y.vidstanTekstom),
  slovo: [0, 1, 2, 4, 5, 11, 12, 21, 22, 25, 111, 1000].map(Y.slovoOchky),
  chyslo: [0, 999, 1000, 12400, 10000].map(Y.chyslo) }));
''')
        self.assertEqual(r['o'][:3], [1000, 1000, 1000])
        self.assertEqual(r['o'][3], 998, 'Одразу за 50 м — уже трохи менше')
        self.assertEqual(r['o'][4:10], [849, 699, 500, 349, 199, 0])
        self.assertEqual(r['o'][10:], [0, 0, 0, 0])
        self.assertTrue(all(a >= b for a, b in zip(r['mon'], r['mon'][1:])), 'Очки мають плавно спадати з відстанню')
        self.assertTrue(1700 < r['vidstan'] < 1850, r['vidstan'])  # Майдан — Контрактова ≈ 1,8 км
        nbsp = ' '
        self.assertEqual(r['tekst'], [f'30{nbsp}м', f'340{nbsp}м', f'1,0{nbsp}км',
                                      f'1,0{nbsp}км', f'1,2{nbsp}км', f'10{nbsp}км', f'12{nbsp}км'])
        self.assertEqual(r['slovo'], ['очок', 'очко', 'очки', 'очки', 'очок', 'очок', 'очок', 'очко', 'очки', 'очок', 'очок', 'очок'])
        self.assertEqual(r['chyslo'], ['0', '999', f'1{nbsp}000', f'12{nbsp}400', f'10{nbsp}000'])

    def test_formula_v_dokumentatsii(self):
        doc = (KORIN / 'docs' / 'IHRY.md').read_text(encoding='utf-8')
        self.assertIn('1000 × ln(5000 / d) / ln(5000 / 50)', doc)
        js = (HRA / 'hra-yadro.js').read_text(encoding='utf-8')
        self.assertIn('1000 × ln(5000 / d) / ln(5000 / 50)', js)

    def test_mv12_vidkydaie_zaboroneni_katehorii(self):
        fail = {'demo': False, 'podii': [podiya('1-1'), podiya('2-1', 'statevi_zlochyny'), podiya('3-1', 'SHCHODO_DITEI'),
                                         podiya('4-1', ' domashnie_nasylstvo '), podiya('5-1', 'vbyvstvo'), podiya('6-1', 'tilesni')]}
        r = node('const Y = require(process.argv[2]); process.stdout.write(JSON.stringify(Y.pidhotuvatyKolodu('
                 + json.dumps(fail, ensure_ascii=False) + ').podii.map(p => p.id)));')
        self.assertEqual(r, ['1-1', '5-1', '6-1'], 'Вбивства й тілесні — можна; MV-4 — ніколи')

    def test_vidkydaie_neprydatni(self):
        fail = {'podii': [podiya('1-1'), podiya('1-1'), podiya('2-1', lat=48.5), podiya('3-1', adresa=''), {'id': 'x'}, None]}
        r = node('const Y = require(process.argv[2]); const k = Y.pidhotuvatyKolodu('
                 + json.dumps(fail, ensure_ascii=False) + '); process.stdout.write(JSON.stringify([k.demo, k.podii.map(p => p.id)]));')
        self.assertEqual(r, [False, ['1-1']])

    def test_podiya_dnya_odnakova_dlia_dnia(self):
        r = node(r'''
const Y = require(process.argv[2]);
const fs = require('fs'), path = require('path');
const fail = JSON.parse(fs.readFileSync(path.join(path.dirname(process.argv[2]), 'koloda-demo.json'), 'utf8'));
const k = Y.pidhotuvatyKolodu(fail);
// Та сама дата — та сама подія, навіть якщо порядок у файлі інший.
const perevernuta = Y.pidhotuvatyKolodu({ demo: true, podii: fail.podii.slice().reverse() });
const a = Y.podiyaDnya(k.podii, '2026-11-07').id, b = Y.podiyaDnya(perevernuta.podii, '2026-11-07').id;
const dni = [];
const pochatok = Date.UTC(2026, 0, 1);
for (let i = 0; i < 400; i++) { const d = new Date(pochatok + i * 86400000).toISOString().slice(0, 10); dni.push(Y.podiyaDnya(k.podii, d).id); }
// Київська дата: 23:30 UTC 6 листопада — це вже 7 листопада в Києві.
const kyiv = Y.dataKyiv(new Date(Date.UTC(2026, 10, 6, 23, 30)));
process.stdout.write(JSON.stringify({ a, b, dni, n: k.podii.length, kyiv }));
''')
        self.assertEqual(r['a'], r['b'])
        self.assertEqual(r['kyiv'], '2026-11-07')
        self.assertGreater(len(set(r['dni'])), 1, 'Подія дня має змінюватися з датою')
        n = r['n']
        # Від початку будь-якого «кола» кожна подія трапляється рівно раз.
        poch = next(i for i in range(n) if (20454 + i) % n == 0)   # 20454 — номер дня 01.01.2026
        kolo = r['dni'][poch:poch + n]
        self.assertEqual(len(set(kolo)), n)


class KolodaTests(unittest.TestCase):
    def test_demo_koloda(self):
        d = demo()
        self.assertIs(d['demo'], True)
        self.assertEqual(len(d['podii']), 20)
        ids = [p['id'] for p in d['podii']]
        self.assertEqual(len(set(ids)), 20)
        for p in d['podii']:
            with self.subTest(p['id']):
                self.assertRegex(p['id'], r'^demo-\d{2}$')
                self.assertIs(p['demo'], True)
                self.assertEqual(p['rishennya_nomer'], '')
                self.assertEqual(p['rishennya_url'], '')
                self.assertNotIn(p['kategoriia'], ZABORONENI)
                self.assertTrue(koloda.prydatna(p))
                self.assertIn('Демо-подія', p['opys_povnyi'])
                # Публічне місце: площа або станція метро, не житловий будинок.
                self.assertRegex(p['adresa'], r'площа|Площа|метро|Майдан')
                self.assertNotRegex(p['adresa'], r'\d')
                # Опис завдання не називає місця з відповіді.
                for slovo in re.findall(r'«([^»]+)»', p['adresa']) + [p['adresa'].split(',')[0]]:
                    self.assertNotIn(slovo.lower(), p['opys_korotkyi'].lower())

    def test_skhema_opysuie_vsi_polya(self):
        skhema = json.loads((HRA / 'koloda.schema.json').read_text(encoding='utf-8'))
        polya = set(skhema['$defs']['podiya']['properties'])
        for p in demo()['podii']:
            self.assertLessEqual(set(p), polya)
        self.assertLessEqual({'id', 'vyd', 'rik', 'opys_korotkyi', 'opys_povnyi', 'adresa', 'lat', 'lon',
                              'rishennya_nomer', 'rishennya_url', 'kategoriia'}, set(skhema['$defs']['podiya']['required']))
        self.assertEqual(set(skhema['$defs']['podiya']['properties']['kategoriia']['not']['enum']), set(ZABORONENI))

    def test_mv12_u_zbyranni(self):
        fail = spravzhnia_koloda(dodaty=[podiya('900001-1', k) for k in ZABORONENI])
        gotova = koloda.pidhotuvaty(fail)
        self.assertEqual(len(gotova['podii']), 12)
        self.assertFalse(any(koloda.zaboronena(p) for p in gotova['podii']))


class ZbyrannyaHryTests(unittest.TestCase):
    URL = 'https://abcdefghijklmnopqrst.supabase.co'
    ZAPOVNENNYA = {'НАЗВА ВЛАСНИКА ПРОЄКТУ': 'Умовна назва', 'ВЛАСНИК': 'Умовний власник',
                   'КОНТАКТ': 'умовний контакт', 'СЕРВІС І КРАЇНА ЗБЕРІГАННЯ': 'Умовний сервіс, ЄС',
                   'ДАТА': '01.01.2027', 'САЙТ': 'умовний-сайт', 'КОД': 'умовний код', 'АДРЕСА': 'умовна адреса'}

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def zapysaty(self, dani):
        f = self.tmp / 'koloda-test.json'
        f.write_text(json.dumps(dani, ensure_ascii=False), encoding='utf-8')
        return f

    def test_perehliad_z_demo(self):
        zibraty.zibraty(self.tmp / 'z', '', '', {}, False)
        k = json.loads((self.tmp / 'z' / 'hra' / 'koloda.json').read_text(encoding='utf-8'))
        self.assertTrue(k['demo'])
        self.assertTrue((self.tmp / 'z' / 'hra' / 'biblioteka' / 'maplibre-gl-csp.js').is_file())
        self.assertFalse(list((self.tmp / 'z' / 'hra').rglob('*.py')), 'Код .py не йде на сайт')
        m = json.loads((self.tmp / 'z' / 'manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertEqual(m['shortcuts'][0]['short_name'], 'Грати')
        self.assertTrue(m['shortcuts'][0]['url'].startswith('hra/'))

    def test_demo_ne_prokhodyt_publikatsiyu(self):
        with self.assertRaises(zibraty.PomylkaZbyrannya) as e:
            zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', self.ZAPOVNENNYA, True, koloda.DEMO)
        self.assertIn('демо', str(e.exception).lower())
        # Підмішана демо-подія в «справжній» колоді — теж ні.
        fail = spravzhnia_koloda()
        fail['podii'][0]['demo'] = True
        with self.assertRaises(zibraty.PomylkaZbyrannya):
            zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', self.ZAPOVNENNYA, True, self.zapysaty(fail))

    def test_publikatsiya_bez_koloda_bez_hry(self):
        zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', self.ZAPOVNENNYA, True)
        self.assertFalse((self.tmp / 'z' / 'hra').exists(), 'Без справжньої колоди гра не публікується')
        m = json.loads((self.tmp / 'z' / 'manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertNotIn('shortcuts', m)

    def test_publikatsiya_zi_spravzhnoiu_kolodoiu(self):
        fail = spravzhnia_koloda(dodaty=[podiya('900001-1', 'domashnie_nasylstvo',
                                                rishennya_nomer='900001', rishennya_url='https://reyestr.court.gov.ua/Review/900001')])
        zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', self.ZAPOVNENNYA, True, self.zapysaty(fail))
        hra = self.tmp / 'z' / 'hra'
        k = json.loads((hra / 'koloda.json').read_text(encoding='utf-8'))
        self.assertFalse(k['demo'])
        self.assertNotIn('900001-1', [p['id'] for p in k['podii']], 'MV-12: заборонена категорія не потрапляє на сайт')
        self.assertFalse((hra / 'koloda-demo.json').exists())
        html = (hra / 'index.html').read_text(encoding='utf-8')
        self.assertIn('data-sait="умовний-сайт"', html)
        self.assertIn(f'connect-src \'self\' https://tiles.openfreemap.org {self.URL}', html)

    def test_publikatsiya_bez_posylan_na_rishennya(self):
        fail = spravzhnia_koloda()
        fail['podii'][3]['rishennya_url'] = ''
        with self.assertRaises(zibraty.PomylkaZbyrannya):
            zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', self.ZAPOVNENNYA, True, self.zapysaty(fail))

    def test_publikatsiya_bez_saitu(self):
        z = dict(self.ZAPOVNENNYA)
        del z['САЙТ']
        with self.assertRaises(zibraty.PomylkaZbyrannya) as e:
            zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', z, True, self.zapysaty(spravzhnia_koloda()))
        self.assertIn('hra/index.html: [САЙТ]', str(e.exception))


class StorinkaHryTests(unittest.TestCase):
    def faily(self):
        return sorted(p for p in HRA.rglob('*') if p.is_file() and p.suffix in ('.html', '.css', '.js')
                      and 'biblioteka' not in p.parts)

    def test_lyshe_dozvoleni_domeny(self):
        adresa = re.compile(r'(?:https?:)?//([A-Za-z0-9*.-]+\.[A-Za-z]{2,})', re.I)
        pohani = []
        for p in self.faily():
            for m in adresa.finditer(p.read_text(encoding='utf-8')):
                domen = m.group(1).lower().lstrip('*.')
                if not any(domen == d or domen.endswith('.' + d) for d in DOZVOLENI_DOMENY):
                    pohani.append(f'{p.name}: {m.group(0)}')
        self.assertEqual(pohani, [], 'Сторонні домени поза дозволеним переліком')

    def test_csp(self):
        html = (HRA / 'index.html').read_text(encoding='utf-8')
        csp = re.search(r'Content-Security-Policy" content="([^"]+)"', html).group(1)
        self.assertIn("script-src 'self';", csp)
        self.assertIn("connect-src 'self' https://tiles.openfreemap.org https://*.supabase.co;", csp)
        self.assertNotIn('unsafe-inline', csp)
        self.assertNotIn('unsafe-eval', csp)

    def test_bez_trekeriv_i_kuki(self):
        zaboroneno = re.compile(r'document\.cookie|sessionStorage|indexedDB|googletagmanager|google-analytics|'
                                r'gtag\(|fbq\(|hotjar|fonts\.googleapis|fonts\.gstatic', re.I)
        for p in self.faily():
            self.assertIsNone(zaboroneno.search(p.read_text(encoding='utf-8')), p.name)
        js = (HRA / 'hra.js').read_text(encoding='utf-8')
        # Пам'ять пристрою — лише через try/catch.
        vyklyky = list(re.finditer(r'window\.localStorage\.', js))
        self.assertEqual(len(vyklyky), 2)
        for m in vyklyky:
            pered = js[max(0, m.start() - 60):m.start()]
            self.assertIn('try', pered)

    def test_podii_rakhunku(self):
        js = (KORIN / 'site' / 'zahlushka' / 'nadsylannya.js').read_text(encoding='utf-8')
        hra = (HRA / 'hra.js').read_text(encoding='utf-8')
        for nazva in ('hra_start', 'hra_vidpovid', 'hra_kinets', 'hra_podilytysia', 'den_zihrano'):
            self.assertIn(f"'{nazva}'", js)
            self.assertIn(f"nadislaty('{nazva}')", hra)
        sql = (KORIN / 'docs' / 'hra-podii.sql').read_text(encoding='utf-8')
        self.assertIn('den_zihrano', sql)

    def test_biblioteka_i_litsenziyi(self):
        for f in ('maplibre-gl-csp.js', 'maplibre-gl-csp-worker.js', 'maplibre-gl.css', 'LICENSE-maplibre.txt'):
            self.assertTrue((HRA / 'biblioteka' / f).is_file(), f)
        self.assertIn('v5.16.0', (HRA / 'biblioteka' / 'maplibre-gl-csp.js').read_text(encoding='utf-8')[:300])
        mezha = json.loads((HRA / 'mezha-kyieva.geojson').read_text(encoding='utf-8'))
        self.assertEqual(mezha['properties']['license'], 'ODbL-1.0')
        self.assertIn('OpenStreetMap', (HRA / 'hra-karta.js').read_text(encoding='utf-8'))

    def test_holovnu_ne_chipaly(self):
        html = (KORIN / 'site' / 'zahlushka' / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('hra/', html, 'Посилання на гру з головної не додаємо (ZAVDANNYA-07)')


@unittest.skipUnless(CHROME, 'немає Playwright або Chrome — перевірку гри в браузері пропущено')
class BrauzerHryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.tmp = Path(tempfile.mkdtemp())
        cls.server, cls.skh, cls.url = zahlushka_pidmina.zapustyty(str(cls.tmp))
        zibraty.zibraty(cls.tmp / 'zahlushka', cls.url, zahlushka_pidmina.PUBLICHNYI, {}, False)
        cls.pw = sync_playwright().start()
        cls.brauzer = cls.pw.chromium.launch(executable_path=CHROME, args=[
            '--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'])

    @classmethod
    def tearDownClass(cls):
        cls.brauzer.close()
        cls.pw.stop()
        cls.server.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.skh.ryadky = {'zayavka': [], 'podiya': [], 'zvernennya': []}

    def vidkryty(self, shyryna=390, bez_pamiati=False, kontekst=None):
        k = kontekst or self.brauzer.new_context(viewport={'width': shyryna, 'height': 844 if shyryna < 600 else 860})
        self.zapyty = []
        self.pomylky = []
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        if bez_pamiati:
            k.add_init_script('Object.defineProperty(window, "localStorage", { get() { throw new Error("немає пам\'яті"); } });')
        s = k.new_page()
        s.on('request', lambda z: self.zapyty.append(z.url))
        s.on('pageerror', lambda e: self.pomylky.append(str(e)))
        s.on('console', lambda m: m.type == 'error' and 'ERR_FAILED' not in m.text and self.pomylky.append(m.text))
        s.goto(f'{self.url}/zahlushka/hra/?dzherelo=test-hra')
        s.wait_for_selector('#pochaty-raund')
        return k, s

    def chekaty_kartu(self, s):
        s.wait_for_function('() => !!(window.MvHraKarta && MvHraKarta.ostannia && MvHraKarta.ostannia.karta.loaded())', timeout=20000)

    def torknutysia(self, s, dx=0, dy=0):
        r = s.locator('#karta').bounding_box()
        s.mouse.click(r['x'] + r['width'] / 2 + dx, r['y'] + r['height'] / 2 + dy)

    def bez_prokruchuvannia_vbik(self, s, shyryna):
        self.assertLessEqual(s.evaluate('document.documentElement.scrollWidth'), shyryna)

    def zovnishni(self):
        return [u for u in self.zapyty if not u.startswith(self.url) and not u.startswith(('data:', 'blob:'))
                and not any(f'//{d}/' in u for d in DOZVOLENI_ZAPYTY)]

    def test_raund_na_telefoni(self):
        k, s = self.vidkryty(390)
        self.assertTrue(s.is_visible('#mitka-demo'), 'Немає помітки «Демо-колода»')
        self.bez_prokruchuvannia_vbik(s, 390)
        s.click('#pochaty-raund')
        self.chekaty_kartu(s)
        self.assertTrue(s.is_disabled('#vidpovisty'))
        self.assertIn('1 / 10', s.inner_text('#nadpys').replace(' ', ' '))
        # Завдання на телефоні — без прокручування і вниз: карта займає залишок екрана.
        self.assertLessEqual(s.evaluate('document.documentElement.scrollHeight'), 844)
        self.bez_prokruchuvannia_vbik(s, 390)
        for i in range(10):
            self.torknutysia(s, 10, 10)
            self.torknutysia(s, -15 + i, 20)      # пересунути позначку можна
            self.assertFalse(s.is_disabled('#vidpovisty'))
            s.click('#vidpovisty')
            s.wait_for_selector('#vidpovid:not([hidden])')
            self.assertTrue(s.inner_text('#adresa'))
            self.assertRegex(s.inner_text('#vidstan').replace(' ', ' '), r'^(за [\d ,]+ (м|км)|Влучно)$')
            self.bez_prokruchuvannia_vbik(s, 390)
            s.click('#dali')
        s.wait_for_selector('#ekran-kinets:not([hidden])')
        self.bez_prokruchuvannia_vbik(s, 390)
        self.assertEqual(s.locator('#spysok-raundu li').count(), 10)
        suma = int(s.inner_text('#suma').replace(' ', '').replace(' ', ''))
        self.assertGreaterEqual(suma, 0)
        self.assertEqual(s.evaluate('JSON.parse(localStorage.getItem("mv-hra-naikrashchyi")).ochky'), suma)
        # «Поділитися» на комп'ютері / без системного меню — завантаження картинки 1080 × 1350.
        with s.expect_download() as zav:
            s.click('#podilytysia')
        self.assertTrue(zav.value.suggested_filename.endswith('.png'))
        rozmir = s.evaluate('(() => { const c = MvHraKartka.namaluvaty(MvHra.daniKartky()); return [c.width, c.height]; })()')
        self.assertEqual(rozmir, [1080, 1350])
        time.sleep(0.5)
        podii = [p['nazva'] for p in self.skh.ryadky['podiya'] if p['kanal'] == 'test-hra']
        self.assertEqual(podii.count('hra_start'), 1)
        self.assertEqual(podii.count('hra_vidpovid'), 10)
        self.assertEqual(podii.count('hra_kinets'), 1)
        self.assertEqual(podii.count('hra_podilytysia'), 1)
        self.assertEqual(self.zovnishni(), [], 'Запити на недозволені адреси')
        self.assertEqual(self.pomylky, [])
        k.close()

    def test_podiya_dnya_raz_na_dobu(self):
        k, s = self.vidkryty(1280)
        s.click('#pochaty-den')
        self.chekaty_kartu(s)
        pershyi_opys = s.inner_text('#opys-korotkyi')
        self.torknutysia(s, 30, 30)
        s.click('#vidpovisty')
        s.wait_for_selector('#den-zihrano:not([hidden])')
        ochky = s.inner_text('#ochky')
        adresa = s.inner_text('#adresa')
        # Повторний вхід того ж дня — та сама подія, вже зіграна, без нового завдання.
        s.goto(f'{self.url}/zahlushka/hra/?dzherelo=test-hra')
        s.wait_for_selector('#pochaty-den')
        self.assertIn('Сьогодні зіграно', s.inner_text('#den-opys'))
        s.click('#pochaty-den')
        s.wait_for_selector('#vidpovid:not([hidden])')
        self.assertEqual(s.inner_text('#adresa'), adresa)
        self.assertEqual(s.inner_text('#ochky'), ochky)
        self.assertIn('вже зіграли', s.inner_text('#den-zihrano'))
        self.assertTrue(s.is_hidden('#vidpovisty'))
        # Інший пристрій (порожня пам'ять) того ж дня отримує ту саму подію.
        k2, s2 = self.vidkryty(390)
        s2.click('#pochaty-den')
        s2.wait_for_selector('#zavdannya:not([hidden])')
        self.assertEqual(s2.inner_text('#opys-korotkyi'), pershyi_opys)
        time.sleep(0.5)
        podii = [p['nazva'] for p in self.skh.ryadky['podiya']]
        self.assertEqual(podii.count('den_zihrano'), 1)
        self.assertEqual(self.pomylky, [])
        k.close()
        k2.close()

    def test_bez_pamiati_hra_ide(self):
        k, s = self.vidkryty(390, bez_pamiati=True)
        s.click('#pochaty-raund')
        self.chekaty_kartu(s)
        self.torknutysia(s)
        s.click('#vidpovisty')
        s.wait_for_selector('#vidpovid:not([hidden])')
        self.assertEqual(self.pomylky, [])
        k.close()

    def test_komp_bez_prokruchuvannia_vbik(self):
        k, s = self.vidkryty(1280)
        s.click('#pochaty-raund')
        self.chekaty_kartu(s)
        self.bez_prokruchuvannia_vbik(s, 1280)
        self.assertLessEqual(s.evaluate('document.documentElement.scrollHeight'), 860)
        k.close()


if __name__ == '__main__':
    unittest.main()
