"""Перший екран головної й /karta/ — легка картинка карти, жива карта потім (ZAVDANNYA-164, MV-176).

Що стережемо:
* сторінка не тягне на старті бібліотеку карти (ні скрипта, ні стилів), ігри — теж ні; скрипти з defer;
* картинка — одна з чотирьох (телефон/комп'ютер × світла/темна), з сотами цього випуску, легка;
* сталі site/zastavka.py збігаються з karta.js — інакше картинка ляже не там, де стане жива карта;
* у браузері: пошук з підказками працює без бібліотеки карти; жива карта стає рівно на місце картинки (±2 px).
"""
from __future__ import annotations

import functools
import http.server
import io
import math
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
from test_sait import BRAUZER, YE_H3, stvoryty_bazu  # noqa: E402

import zastavka as Z  # noqa: E402

KARTA_JS = (KORIN / 'site' / 'sait' / 'karta.js').read_text(encoding='utf-8')


class StaliZKartoyu(unittest.TestCase):
    """Картинка повторює стартову камеру karta.js — сталі мусять бути ті самі."""

    def chysla(self, vyraz):
        return [float(x) for x in re.findall(r'-?\d+(?:\.\d+)?', vyraz)]

    def test_kyiv_kvant_vershyna_proz(self):
        kyiv = re.search(r'var KYIV = (\[\[.*?\]\]);', KARTA_JS).group(1)
        self.assertEqual(self.chysla(kyiv), [*Z.KYIV[0], *Z.KYIV[1]])
        self.assertEqual(self.chysla(re.search(r'KVANT = \[(.*?)\]', KARTA_JS).group(1)), list(Z.KVANT))
        self.assertEqual(float(re.search(r'VERSHYNA = ([\d.]+)', KARTA_JS).group(1)), Z.VERSHYNA)
        proz = re.search(r'var PROZ = \{ svitla: \[(.*?)\], temna: \[(.*?)\] \}', KARTA_JS)
        self.assertEqual(self.chysla(proz.group(1)), list(Z.PROZ['svitla']))
        self.assertEqual(self.chysla(proz.group(2)), list(Z.PROZ['temna']))

    def test_kamera_i_rivni(self):
        pad = re.search(r"var pad = telefon\(\) \? \{ t: (\d+), b: (\d+), l: (\d+), r: (\d+) \} : \{ t: (\d+), b: (\d+), l: (\d+), r: (\d+) \}", KARTA_JS)
        self.assertEqual(tuple(int(x) for x in pad.groups()[:4]), Z.VARIANTY['telefon']['polia'])
        self.assertEqual(tuple(int(x) for x in pad.groups()[4:]), Z.VARIANTY['komp']['polia'])
        zapas = re.search(r"zoom: z \+ \(telefon\(\) \? ([\d.]+) : ([\d.]+)\)", KARTA_JS)
        self.assertEqual((float(zapas.group(1)), float(zapas.group(2))), (Z.VARIANTY['telefon']['zapas'], Z.VARIANTY['komp']['zapas']))
        self.assertIn(f'window.innerWidth <= {Z.TELEFON_DO}', KARTA_JS)
        for v in Z.VARIANTY.values():
            k = re.search(r"\{ r: %d, id: '\w+', R: \d+, k: ([\d.]+)" % v['riven'], KARTA_JS)
            self.assertEqual(float(k.group(1)), v['k'])
        # стартовий зум комп'ютера — середні соти (рівень 8), телефона — великі (7): межа ZMINA[0] у karta.js
        zmina = float(re.search(r'var ZMINA = \[([\d.]+),', KARTA_JS).group(1))
        meta = Z.meta()
        self.assertLess(meta['telefon']['z'], zmina)
        self.assertGreater(meta['komp']['z'], zmina)

    def test_chastky_yak_u_karti(self):
        soty = [{'properties': {'id': str(i), 'all3': n}} for i, n in enumerate([0, 1, 1, 2, 5, 9])]
        q = Z.chastky(soty)
        self.assertNotIn('0', q, 'порожня сота — без кольору')
        self.assertEqual(q['1'], q['2'])                  # рівні числа — одна частка
        self.assertAlmostEqual(q['1'][0], 0.2)            # (0 + 2/2) / 5
        self.assertAlmostEqual(q['5'][0], 0.9)
        self.assertEqual(q['5'][1], 4)                    # вершина — найвищий клас


@unittest.skipUnless(YE_H3, 'немає h3 — сайт не зібрати')
class ZibranyiSait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zibraty_sait
        cls.zs = zibraty_sait
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        stvoryty_bazu(tmp / 'events.db')
        cls.sait = tmp / 'sait'
        zibraty_sait.zibraty_sait(tmp / 'events.db', cls.sait, None, KORIN / 'data' / 'borders.json')
        cls.css = (cls.sait / 'sait' / 'sait.css').read_text(encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_bez_biblioteky_karty_na_starti(self):
        for shl in ('index.html', 'karta/index.html'):
            html = (self.sait / shl).read_text(encoding='utf-8')
            self.assertNotIn('maplibre', html, f'{shl}: бібліотека карти — лише коли потрібна')
            self.assertIn('<div class="zastavka" aria-hidden="true"></div>', html)
            skrypty = re.findall(r'<script src="([^"]+)"([^>]*)>', html)
            self.assertIn('/sait/karta.js', [s for s, _ in skrypty])
            for s, atr in skrypty:
                if s != '/sait/tema.js':                  # тема — у <head>, щоб не було спалаху
                    self.assertIn('defer', atr, f'{shl}: {s} без defer тримає перший екран')
            ihry = re.search(r'data-ihry="([^"]+)"', html).group(1).split()
            self.assertEqual(tuple(ihry), self.zs.SKRYPTY_IHOR, 'ігри — не на старті, а з data-ihry')
            self.assertFalse(set(ihry) & {s for s, _ in skrypty})
            self.assertEqual(len(re.findall(r'<link rel="preload" as="image" href="/karta/zastavka-', html)), 4)

    def test_chotyry_kartynky_lehki_y_u_styliakh(self):
        from PIL import Image
        fayly = sorted((self.sait / 'karta').glob('zastavka-*.webp'))
        self.assertEqual(len(fayly), 4)
        meta = Z.meta()
        for f in fayly:
            m = re.fullmatch(r'zastavka-(telefon|komp)-(svitla|temna)-[0-9a-f]{10}\.webp', f.name)
            self.assertTrue(m, f.name)
            self.assertLess(f.stat().st_size, 160_000, f'{f.name}: картинка першого екрана має бути легкою')
            self.assertIn(f'/karta/{f.name}', self.css)
            im = Image.open(io.BytesIO(f.read_bytes()))
            mv = meta[m.group(1)]
            self.assertEqual(im.size, (round(mv['sirina'] * mv['dpr']), round(mv['vysota'] * mv['dpr'])))
        self.assertIn('container-type:size', self.css)
        self.assertIn('@media (max-width:700px)', self.css)

    def test_soty_namalovano(self):
        """Соти з даних справді лягли на підкладку: картинка з сотами ≠ сама підкладка (у межах Києва)."""
        from PIL import Image, ImageChops
        f = next((self.sait / 'karta').glob('zastavka-telefon-svitla-*.webp'))
        z_sotamy = Image.open(f).convert('RGB')
        tlo = Image.open(Z.PIDKLADKA / 'telefon-svitla-tlo.webp').convert('RGB')
        rizn = ImageChops.difference(z_sotamy, tlo).convert('L').point(lambda v: 255 if v > 24 else 0)
        self.assertGreater(sum(rizn.histogram()[255:]), 2000)

    def test_povtornyi_zapusk_ti_sami_kartynky(self):
        druhyi = Path(self.tmp.name) / 'sait2'
        self.zs.zibraty_sait(Path(self.tmp.name) / 'events.db', druhyi, None, KORIN / 'data' / 'borders.json')
        self.assertEqual(sorted(p.name for p in (self.sait / 'karta').glob('zastavka-*')),
                         sorted(p.name for p in (druhyi / 'karta').glob('zastavka-*')))


def kut_kartynky(variant: str) -> tuple[float, float]:
    """Довгота/широта лівого верхнього кута картинки варіанта."""
    m = Z.meta()[variant]
    cx, cy = Z.merc(*m['tsentr'], m['z'])
    x, y, s = cx - m['sirina'] / 2, cy - m['vysota'] / 2, 512 * 2 ** m['z']
    return x / s * 360 - 180, (2 * math.atan(math.exp((1 - 2 * y / s) * math.pi)) - math.pi / 2) * 180 / math.pi


@unittest.skipUnless(BRAUZER, 'немає Playwright або Chrome/Edge, або h3 — перевірку в браузері пропущено')
class UBrauzeri(unittest.TestCase):
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
        cls.b = cls.pw.chromium.launch(executable_path=BRAUZER, args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])

    @classmethod
    def tearDownClass(cls):
        cls.b.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.tmp.cleanup()

    def vidkryty(self, shliakh, shyryna, vysota):
        k = self.b.new_context(viewport={'width': shyryna, 'height': vysota}, device_scale_factor=1)
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        s = k.new_page()
        s.zapyty, s.pomylky = [], []
        s.on('request', lambda r: s.zapyty.append(r.url))
        s.on('pageerror', lambda e: s.pomylky.append(str(e)))
        s.goto(self.url + shliakh)
        self.addCleanup(k.close)
        return s

    def test_poshuk_bez_biblioteky(self):
        s = self.vidkryty('/?vau=0', 390, 844)
        s.fill('#poshuk-karty', 'Хрещ')
        s.wait_for_selector('#pidkazky li[data-j]', timeout=10000)
        self.assertFalse(s.evaluate('() => !!window.maplibregl'), 'підказки — без бібліотеки карти')
        self.assertFalse(any('maplibre' in z for z in s.zapyty))
        s.click('#pidkazky li[data-j="0"]')          # вулиця → жива карта вантажиться й летить до неї
        s.wait_for_function("() => MvKarta.zaraz && MvKarta.zaraz() && MvKarta.zaraz().id === 'S'", timeout=40000)
        self.assertEqual(s.evaluate('() => MvKarta.stan.zapusk'), 'poshuk')
        self.assertEqual(s.pomylky, [])

    def test_karta_stae_na_mistse_kartynky(self):
        for variant, (w, h) in (('telefon', (390, 844)), ('komp', (1280, 860)), ('komp', (1920, 1080))):
            with self.subTest(variant=variant, ekran=(w, h)):
                s = self.vidkryty('/?vau=0', w, h)
                ramka = s.evaluate("""() => { const z = document.querySelector('.zastavka').getBoundingClientRect(),
                    k = document.getElementById('karta-mista').getBoundingClientRect();
                    return [z.left - k.left, z.top - k.top, z.width]; }""")
                self.assertFalse(s.evaluate('() => !!window.maplibregl'))
                s.evaluate("() => MvKarta.zapustyty('test')")
                s.wait_for_function('() => MvKarta.gotovo', timeout=60000)
                s.wait_for_function("() => !document.querySelector('.zastavka')", timeout=30000)
                s.evaluate('() => MvKarta.karta.jumpTo({ pitch: 0 })')
                lon, lat = kut_kartynky(variant)
                kut = s.evaluate(f'() => {{ const p = MvKarta.karta.project([{lon}, {lat}]); return [p.x, p.y]; }}')
                self.assertAlmostEqual(kut[0], ramka[0], delta=2, msg=f'ліво {kut} vs {ramka}')
                self.assertAlmostEqual(kut[1], ramka[1], delta=2, msg=f'верх {kut} vs {ramka}')
                m = Z.meta()[variant]
                masshtab = 2 ** (s.evaluate('() => MvKarta.karta.getZoom()') - m['z'])
                self.assertAlmostEqual(ramka[2], m['sirina'] * masshtab, delta=2)
                self.assertEqual(s.pomylky, [])

    def test_spokii_vantazhyt_kartu_sama(self):
        s = self.vidkryty('/?vau=0', 390, 844)
        s.wait_for_timeout(1000)
        self.assertFalse(s.evaluate('() => !!window.maplibregl'), 'за секунду — ще картинка')
        s.wait_for_function('() => MvKarta.gotovo', timeout=60000)
        self.assertEqual(s.evaluate('() => MvKarta.stan.zapusk'), 'spokii')
        self.assertTrue(s.evaluate('() => !!window.MvIhry'), 'ігри довантажено')

    def test_dotyk_vantazhyt_kartu(self):
        s = self.vidkryty('/?vau=0', 390, 844)
        s.mouse.click(200, 520)
        s.wait_for_function('() => MvKarta.gotovo', timeout=60000)
        self.assertEqual(s.evaluate('() => MvKarta.stan.zapusk'), 'dotyk')
        s.wait_for_function("() => !document.querySelector('.zastavka')", timeout=30000)
        s.wait_for_function('() => MvKarta.karta.getPitch() > 30', timeout=10000)   # нахил у 3D, як на старті
        self.assertEqual(s.pomylky, [])

    def test_hra_v_posylanni_odrazu_zhyva(self):
        s = self.vidkryty('/karta/?ihry', 1280, 860)
        s.wait_for_function('() => MvKarta.gotovo', timeout=60000)
        self.assertEqual(s.evaluate('() => MvKarta.stan.zapusk'), 'odrazu')
        self.assertFalse(s.evaluate("() => !!document.querySelector('.zastavka')"))
        s.wait_for_function("() => !document.getElementById('ihry').hidden", timeout=15000)


if __name__ == '__main__':
    unittest.main()
