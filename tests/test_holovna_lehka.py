"""Головна з картою легша (ZAVDANNYA-125, борг Т-12): дрібні соти — лише при наближенні; місяці — лише для потрібного рівня.

Запуск: python -m unittest tests/test_holovna_lehka.py (потрібні Playwright, Chromium і h3; без них — пропуск).
Не зламати: «Роки оживають», смуга «рік · місяць», пошук, «Де ви живете?», ігри в карті, 3D.
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
from test_sait import BRAUZER, stvoryty_bazu  # noqa: E402

try:
    from test_zahlushka import CHROME  # noqa: E402
except Exception:   # noqa: BLE001
    CHROME = None


@unittest.skipUnless(BRAUZER and CHROME, 'немає Playwright, Chromium або h3 — перевірку пропущено')
class HolovnaLehka(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zibraty_sait
        from playwright.sync_api import sync_playwright
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        stvoryty_bazu(tmp / 'events.db')
        cls.sait = tmp / 'sait'
        zibraty_sait.zibraty_sait(tmp / 'events.db', cls.sait, None, KORIN / 'data' / 'borders.json')
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(cls.sait)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        cls.pw = sync_playwright().start()
        cls.b = cls.pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])

    @classmethod
    def tearDownClass(cls):
        cls.b.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.tmp.cleanup()

    def vidkryty(self, shliakh, shyryna=1280, vysota=860):
        k = self.b.new_context(viewport={'width': shyryna, 'height': vysota}, device_scale_factor=1)
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        s = k.new_page()
        s.zapyty, s.pomylky = [], []
        s.on('request', lambda r: s.zapyty.append(r.url.split('?')[0].rsplit('/', 1)[-1]))
        s.on('pageerror', lambda e: s.pomylky.append(str(e)))
        s.goto(self.url + shliakh)
        s.wait_for_function('() => window.MvKarta && MvKarta.gotovo', timeout=60000)
        self.addCleanup(k.close)
        return s

    def test_faily_misiatsiv_okremo(self):
        for r in (8, 9):
            d = json.loads((self.sait / 'karta' / f'soty-{r}.json').read_text(encoding='utf-8'))
            self.assertFalse(any('m' in f['properties'] for f in d['soty']['features']), f'soty-{r}: місяці мають бути окремо')
            m = json.loads((self.sait / 'karta' / f'soty-{r}-m.json').read_text(encoding='utf-8'))['m']
            self.assertTrue(m and set(m) <= {f['properties']['id'] for f in d['soty']['features']})
        d7 = json.loads((self.sait / 'karta' / 'soty-7.json').read_text(encoding='utf-8'))
        self.assertTrue(any('m' in f['properties'] for f in d7['soty']['features']), 'рівень 7 — з місяцями')

    def test_drib_ni_soty_lyshe_pry_nablyzhenni(self):
        s = self.vidkryty('/?vau=0')
        s.wait_for_timeout(800)
        self.assertNotIn('soty-9.json', s.zapyty)
        self.assertNotIn('soty-8-m.json', s.zapyty)
        self.assertFalse(s.evaluate('() => MvKarta.maie().soty.S'))
        s.evaluate('() => MvKarta.karta.jumpTo({ center: [30.5232, 50.4480], zoom: 13.3 })')
        s.wait_for_function('() => MvKarta.maie().soty.S', timeout=30000)
        s.wait_for_timeout(1500)
        self.assertGreater(s.evaluate("() => MvKarta.karta.querySourceFeatures('k-hex-S').length"), 0)
        self.assertIn('soty-9.json', s.zapyty)
        self.assertNotIn('soty-9-m.json', s.zapyty, 'місяці дрібних сот — лише коли потрібні')
        self.assertEqual(s.pomylky, [])

    def test_hlybyna_z_adresy(self):
        s = self.vidkryty('/karta/?vau=0#13.5/50.4480/30.5232/0/0')
        self.assertTrue(s.evaluate('() => MvKarta.maie().soty.S'), 'зблизька за посиланням — дрібні соти одразу')
        self.assertEqual(s.pomylky, [])

    def test_roky_ozhyvaiut_i_smuha(self):
        s = self.vidkryty('/')            # «Роки оживають» за замовчуванням
        s.wait_for_selector('.vau-lich', state='attached', timeout=20000)   # ZAVDANNYA-177: на головній лічильник прихований
        s.wait_for_function("() => !document.querySelector('.vau-lich') || document.querySelector('.vau-lich--hasne')", timeout=60000)
        vydno = s.evaluate('() => MvKarta.colG()')
        if vydno == 'L':
            self.assertIn('soty-8-m.json', s.zapyty)
        self.assertNotIn('soty-9.json', s.zapyty)
        self.assertNotIn('soty-9-m.json', s.zapyty)
        # смуга «Рік» після наближення — місяці дрібних сот довантажуються, числа є
        s.evaluate('() => MvKarta.karta.jumpTo({ center: [30.5232, 50.4480], zoom: 13.3 })')
        s.wait_for_function('() => MvKarta.maie().soty.S', timeout=30000)
        s.evaluate("() => MvKarta.chas('rik')")
        s.wait_for_function('() => MvKarta.maie().misiatsi.S', timeout=30000)
        s.wait_for_timeout(800)
        self.assertGreater(s.evaluate("() => MvKarta.karta.querySourceFeatures('k-hex-S').length"), 0)
        self.assertEqual(s.pomylky, [])

    def test_poshuk_bez_povnoho_zavantazhennia(self):
        s = self.vidkryty('/?vau=0')
        nazvy = s.evaluate("() => MvKarta.poshuk('Хрещатик')")
        self.assertTrue(nazvy)
        self.assertNotIn('soty-9.json', s.zapyty, 'пошук не тягне дрібні соти заздалегідь')
        s.evaluate('() => MvKarta.vybraty(0)')
        s.wait_for_function("() => MvKarta.zaraz() && MvKarta.zaraz().id === 'S'", timeout=30000)
        self.assertEqual(s.pomylky, [])

    def test_3d_i_ihry(self):
        s = self.vidkryty('/?vau=0')
        s.click('#f3d')
        s.wait_for_timeout(900)
        s.click('#fihry')
        s.wait_for_selector('#ihry:not([hidden])')
        self.assertEqual(s.pomylky, [])

    def test_de_vy_zhyvete_na_telefoni(self):
        s = self.vidkryty('/', 390, 844)
        s.wait_for_selector('.vau-rayony', timeout=60000)
        s.click('.vau-rayony [data-rayon] >> nth=0')
        s.wait_for_timeout(1500)
        self.assertEqual(s.pomylky, [])


if __name__ == '__main__':
    unittest.main()
