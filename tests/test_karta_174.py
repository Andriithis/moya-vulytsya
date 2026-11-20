"""ZAVDANNYA-174: виправлення карти й сторінок сайту за критиками (docs/ZVIT-166.md, docs/ZVIT-171.md).

Запуск: python -m unittest tests/test_karta_174.py (потрібні Playwright, Chromium і h3; без них — пропуск).
Що перевіряє (у браузері, на штучному місті з tests/test_sait.py):
* картка соти — область з назвою; після пошуку клавіатурою фокус на її назві, Escape — фокус назад у поле (ZVIT-171 №3);
* полотно карти й кнопки бібліотеки — українською, не «Map» (ZVIT-171 №3, ZVIT-166 №6);
* «Роки оживають» зупиняє будь-яка клавіша; з «менше руху» — одразу кінцевий вигляд без лічильника (ZVIT-171 №5);
* «Де ви живете?» — з підписом і на телефоні; після вибору району ряд зникає, відкривається картка району з межею (ZVIT-166 №7);
* «Карта списком» — перше посилання після карти й у «Як читати карту» (ZVIT-171 №6);
* сторінка будинку: смуги 1551 сховані від читалки (таблиця є), у таблиці подій — підпис (ZVIT-171 №7);
* 320 px: шапка не ширша за екран (ZVIT-171 №8);
* /karta/ — легкий перший екран: бібліотеки карти в першу секунду немає (ZVIT-166 №10, як MV-176).
"""
from __future__ import annotations

import functools
import http.server
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
from test_sait import BRAUZER, BUDYNKY, stvoryty_bazu  # noqa: E402


@unittest.skipUnless(BRAUZER, 'немає Playwright, Chromium або h3 — перевірку пропущено')
class Karta174(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zibraty_sait
        from playwright.sync_api import sync_playwright
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        stvoryty_bazu(tmp / 'events.db')
        (tmp / 'budynky.json').write_text(json.dumps(BUDYNKY, ensure_ascii=False), encoding='utf-8')
        cls.sait = tmp / 'sait'
        zibraty_sait.zibraty_sait(tmp / 'events.db', cls.sait, None, KORIN / 'data' / 'borders.json', budynky=tmp / 'budynky.json')
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(cls.sait)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        cls.pw = sync_playwright().start()
        cls.b = cls.pw.chromium.launch(executable_path=BRAUZER, args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])

    @classmethod
    def tearDownClass(cls):
        cls.b.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.tmp.cleanup()

    def vidkryty(self, shliakh, shyryna=1280, vysota=860, tykho=False, chekaty=True):
        k = self.b.new_context(viewport={'width': shyryna, 'height': vysota}, device_scale_factor=1,
                               reduced_motion='reduce' if tykho else 'no-preference')
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        self.addCleanup(k.close)
        s = k.new_page()
        s.zapyty, s.pomylky = [], []
        s.on('request', lambda r: s.zapyty.append(r.url))
        s.on('pageerror', lambda e: s.pomylky.append(str(e)))
        s.goto(self.url + shliakh)
        if chekaty:
            s.wait_for_function('() => window.MvKarta && MvKarta.gotovo', timeout=60000)
        return s

    # ---------------------------------------------------------------- картка соти: фокус і оголошення (ZVIT-171 №3)
    def test_kartka_fokus_i_nazad(self):
        s = self.vidkryty('/karta/?vau=0&zhyva')
        kartka = s.evaluate("() => { const k = document.getElementById('kartka'); return [k.getAttribute('role'), k.getAttribute('aria-labelledby')]; }")
        self.assertEqual(kartka, ['region', 'kartka-nazva'])
        s.click('#poshuk-karty')
        s.keyboard.type('хрещ')
        s.wait_for_selector('#pidkazky li[data-j]')
        s.keyboard.press('ArrowDown')
        s.keyboard.press('Enter')
        s.wait_for_function('() => !document.getElementById("kartka").hidden', timeout=20000)
        s.wait_for_timeout(200)
        self.assertEqual(s.evaluate('() => document.activeElement.id'), 'kartka-nazva', 'фокус — на назві соти')
        self.assertIn('Хрещатик', s.evaluate('() => document.activeElement.textContent'))
        s.keyboard.press('Escape')
        s.wait_for_timeout(200)
        self.assertTrue(s.evaluate('() => document.getElementById("kartka").hidden'))
        self.assertEqual(s.evaluate('() => document.activeElement.id'), 'poshuk-karty', 'фокус — назад у поле пошуку')
        self.assertEqual(s.pomylky, [])

    def test_karta_ukrainskoiu(self):
        s = self.vidkryty('/karta/?vau=0&zhyva')
        self.assertEqual(s.evaluate("() => MvKarta.karta.getCanvas().getAttribute('aria-label')"), 'Карта Києва')
        for zayve in ('"Map"', 'Zoom in', 'Zoom out'):
            self.assertNotIn(zayve, s.content())
        self.assertEqual(s.pomylky, [])

    # ---------------------------------------------------------------- «оживання» (ZVIT-171 №5, WCAG 2.2.2)
    def test_ozhyvannia_zupyniaie_klavisha(self):
        s = self.vidkryty('/karta/?zhyva')
        s.wait_for_selector('.vau-lich', timeout=20000)
        s.keyboard.press('Shift')
        s.wait_for_function("() => !document.querySelector('.vau-lich') || document.querySelector('.vau-lich--hasne')", timeout=3000)
        self.assertEqual(s.pomylky, [])

    def test_menshe_rukhu_bez_ozhyvannia(self):
        s = self.vidkryty('/karta/?zhyva', tykho=True)
        s.wait_for_selector('.vau-rayony', timeout=20000)       # запрошення є
        self.assertFalse(s.evaluate("() => !!document.querySelector('.vau-lich')"), '«менше руху» — без лічильника місяців')
        self.assertEqual(s.pomylky, [])

    # ---------------------------------------------------------------- «Де ви живете?» (ZVIT-166 №7)
    def test_de_vy_zhyvete_rayon(self):
        s = self.vidkryty('/karta/?zhyva', tykho=True)
        s.wait_for_selector('.vau-rayony [data-rayon]', timeout=20000)
        rayon = s.evaluate("() => document.querySelector('.vau-rayony [data-rayon]').getAttribute('data-rayon')")
        s.click('.vau-rayony [data-rayon] >> nth=0')
        s.wait_for_function('() => !document.getElementById("kartka").hidden', timeout=20000)
        self.assertFalse(s.evaluate("() => !!document.querySelector('.vau-rayony')"), 'ряд районів після вибору зникає')
        self.assertEqual(s.inner_text('#kartka h2'), f'{rayon} район')
        s.wait_for_function("() => document.querySelector('#kartka a[href^=\"/rayon/\"]')", timeout=10000)
        s.wait_for_function("() => MvKarta.karta.getSource('k-rayon') && MvKarta.karta.querySourceFeatures('k-rayon').length > 0", timeout=10000)
        self.assertTrue(s.evaluate("() => !!document.querySelector('#kartka .k-dali a[href*=\"/oplata/\"]')"), 'з картки району — шлях до покупки')
        s.click('#kartka .k-x')
        s.wait_for_timeout(300)
        self.assertEqual(s.evaluate("() => MvKarta.karta.querySourceFeatures('k-rayon').length"), 0, 'межа зникає з карткою')
        self.assertFalse(s.evaluate("() => !!document.querySelector('.vau-rayony')"), 'ряд не повертається')
        self.assertEqual(s.pomylky, [])

    def test_de_vy_zhyvete_khovaietsia_pislia_poshuku(self):
        s = self.vidkryty('/karta/?zhyva', tykho=True)
        s.wait_for_selector('.vau-rayony', timeout=20000)
        s.click('#poshuk-karty')
        self.assertFalse(s.evaluate("() => !!document.querySelector('.vau-rayony')"))

    def test_de_vy_zhyvete_na_telefoni_z_pidpysom(self):
        s = self.vidkryty('/karta/?zhyva', 390, 844, tykho=True)
        s.wait_for_selector('.vau-rayony', timeout=20000)
        self.assertTrue(s.is_visible('.vau-rayony .vr-pyt'), 'на телефоні — слова «Де ви живете?»')
        r = s.evaluate("() => { const e = document.querySelector('.vau-rayony').getBoundingClientRect(); return [e.left, e.right]; }")
        self.assertGreaterEqual(r[0], 0)
        self.assertLessEqual(r[1], 390)

    # ---------------------------------------------------------------- карта списком (ZVIT-171 №6)
    def test_karta_spyskom(self):
        html = (self.sait / 'karta' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('<a class="karta-spyskom" href="/rayony/">Карта списком: райони → вулиці → будинки</a>', html)
        info = html.split('id="info"')[1].split('</section>')[0]
        self.assertIn('href="/rayony/"', info)
        s = self.vidkryty('/karta/?vau=0&zhyva')
        s.evaluate('() => MvKarta.karta.getCanvas().focus()')
        s.keyboard.press('Tab')
        self.assertEqual(s.evaluate('() => document.activeElement.className'), 'karta-spyskom', 'одразу після карти — «Карта списком»')
        self.assertTrue(s.evaluate("() => { const r = document.activeElement.getBoundingClientRect(); return r.bottom <= innerHeight && r.top >= 0; }"),
                        'у фокусі посилання видно')
        mezhi = json.loads((self.sait / 'karta' / 'rayony.json').read_text(encoding='utf-8'))
        self.assertTrue(mezhi['features'])
        z_adresoyu = [f['properties']['slug'] for f in mezhi['features'] if f['properties']['slug']]
        self.assertTrue(z_adresoyu)
        self.assertTrue(all((self.sait / 'rayon' / sl / 'index.html').is_file() for sl in z_adresoyu), z_adresoyu)

    # ---------------------------------------------------------------- сторінка будинку (ZVIT-171 №7)
    def test_budynok_dlia_chytalky(self):
        t = (self.sait / 'budynok' / 'khreshchatyk' / '22' / 'index.html').read_text(encoding='utf-8')
        self.assertNotIn('<div class="por__ryad">', t)
        self.assertIn('<div class="por__ryad" aria-hidden="true">', t)
        self.assertIn('<caption class="prykhovano">Скільки подій з адресою будинку — за групами й роками</caption>', t)

    # ---------------------------------------------------------------- 320 px (ZVIT-171 №8)
    def test_shyryna_320(self):
        for shl in ('/vulytsia/khreshchatyk/', '/budynok/khreshchatyk/22/', '/miy-budynok/', '/rayon/pecherskyi/'):
            k = self.b.new_context(viewport={'width': 320, 'height': 640})
            self.addCleanup(k.close)
            s = k.new_page()
            s.goto(self.url + shl)
            shyr = s.evaluate("() => [document.documentElement.scrollWidth, document.querySelector('.shapka__vnutri').scrollWidth]")
            self.assertLessEqual(shyr[0], 320, f'{shl}: сторінка ширша за 320 px')
            self.assertLessEqual(shyr[1], 320, f'{shl}: шапка ширша за 320 px')

    # ---------------------------------------------------------------- /karta/ — легкий перший екран (ZVIT-166 №10)
    def test_karta_lehkyi_pershyi_ekran(self):
        s = self.vidkryty('/karta/?vau=0', 390, 844, chekaty=False)
        s.wait_for_timeout(1000)
        self.assertFalse(s.evaluate('() => !!window.maplibregl'), '/karta/: за секунду — ще картинка')
        self.assertFalse([z for z in s.zapyty if 'maplibre' in z or 'soty-8' in z])
        self.assertTrue(s.is_visible('.zastavka'))


if __name__ == '__main__':
    unittest.main()
