"""ZAVDANNYA-153: сторінки-входи під рекламу й мітки джерела.

Запуск: python -m unittest tests.test_vkhody -v
Сайт збирається з тієї самої штучної бази, що tests/test_sait.py. Перевірки в браузері (мітка доходить з входу до кнопки
оплати на сторінці будинку) — лише коли є Playwright і Chrome.
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_sait import (BUDYNKY, ZABORONENI_SLOVA, perevirka_storinky, stvoryty_bazu,  # noqa: E402
                       stvoryty_pereimenuvannya)
from test_zahlushka import CHROME  # noqa: E402

try:
    import h3  # noqa: F401
    YE_H3 = True
except ImportError:
    YE_H3 = False

# Що кожен вхід продає (головна картка) і що ще можна на ньому купити — ZAVDANNYA-153.
TOVARY = {
    'orenda': ('dovidka', {'dovidka', 'try'}), 'kupivlia': ('zvit', {'zvit', 'dovidka'}),
    'rieltor': ('rieltor', {'rieltor', 'dovidka'}), 'dlia-osbb': ('osbb', {'osbb'}),
    'yurystu': ('spyurist', {'spyurist', 'spdovidka'}), 'tut': ('dovidka', {'dovidka', 'pidpyska'}),
}
# AGENTS.md, розд. 4 (той самий перелік, що dani-edrsr/src/zvit/storinka.py, ZABOR) — у видимому тексті входів.
ZABOR = [r'прогноз', r'найгірш', r'найімовірніше', r'станеться знову', r'триває й далі', r'дивіться уважніше', r'будьте уважн',
         r'бути уважніш', r'уникайте', r'не ходіть', r'краще не ', r'обходьте', r'через те, що', r'спричин', r'призвод',
         r'макет', r'конвеєр', r'медіан', r'\bMV-\d', r'ОСОБА_']


def vydymyi(html_: str) -> str:
    t = html_[html_.index('<main'):html_.index('</main>')]      # шапка й підвал — спільні для всього сайту
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t))


def zibraty(tmp: Path, z_budynkamy: bool = True) -> Path:
    import zibraty_sait
    stvoryty_bazu(tmp / 'events.db')
    stvoryty_pereimenuvannya(tmp / 'pereim.csv')
    bud = None
    if z_budynkamy:
        bud = tmp / 'budynky.json'
        bud.write_text(json.dumps(BUDYNKY, ensure_ascii=False), encoding='utf-8')
    zibraty_sait.zibraty_sait(tmp / 'events.db', tmp / 'sait', tmp / 'pereim.csv', KORIN / 'data' / 'borders.json',
                              budynky=bud)
    return tmp / 'sait'


@unittest.skipUnless(YE_H3, 'немає бібліотеки h3 (pip install h3)')
class Vkhody(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import storinky_vkhody as VK
        import tsiny as T
        cls.VK, cls.T = VK, T
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sait = zibraty(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def html(self, slug):
        return (self.sait / slug / 'index.html').read_text(encoding='utf-8')

    def test_usi_vkhody_ye_i_pravylni(self):
        self.assertEqual(set(self.VK.VKHODY), set(TOVARY))
        mapa = (self.sait / 'sitemap.xml').read_text(encoding='utf-8') if (self.sait / 'sitemap.xml').exists() else ''
        for slug, kod in self.VK.VKHODY.items():
            with self.subTest(slug):
                h = self.html(slug)
                self.assertEqual(perevirka_storinky(h), [])
                self.assertIn('noindex', h, 'входи — під рекламу, не для Google')
                self.assertNotIn(f'/{slug}/<', mapa)
                self.assertIn(f'data-vkhid="{kod}"', h)
                self.assertIn('/sait/vkhid.css', h)
                self.assertIn('/sait/vkhid.js', h)

    def test_pershyi_ekran_potreba_i_poshuk(self):
        """Спершу потреба (h1) і одразу пошук; продукт (картки з цінами) — нижче (В6, MV-158)."""
        for slug in self.VK.VKHODY:
            with self.subTest(slug):
                h = self.html(slug)
                ekran = h[h.index('class="vkhid__ekran'):]
                ekran = ekran[:ekran.index('</section>')]
                self.assertIn('<h1>', ekran)
                pole = 'id="vkhid-stattia"' if slug == 'yurystu' else 'id="poshuk-vulytsi"'
                self.assertIn(pole, ekran)
                self.assertLess(h.index(pole), h.index('class="tovary"'))
                if slug != 'yurystu':
                    self.assertIn('/sait/poshuk.js', h)

    def test_tovary_tsiny_i_mitky(self):
        T = self.T
        for slug, (holovnyi, usi) in TOVARY.items():
            with self.subTest(slug):
                h = self.html(slug)
                kod = self.VK.VKHODY[slug]
                tovary = set(re.findall(r'/oplata/\?tovar=([a-z]+)', h))
                self.assertEqual(tovary, usi)
                self.assertRegex(h, rf'tovar tovar--holovnyi"><h3>{re.escape(T.TOVARY[holovnyi])}')
                self.assertIn(T.tsina(holovnyi), h)
                for kl in usi:
                    self.assertIn(f'/oplata/?tovar={kl}&amp;dzherelo={kod}', h)
                # лише суми з site/tsiny.py
                for n in re.findall(r'(\d[\d  ]*)(?: |\s)?грн', h):
                    self.assertIn(int(re.sub(r'\D', '', n)), T.dozvoleni_sumy(), f'{slug}: {n} грн')

    def test_chesno(self):
        for slug in self.VK.VKHODY:
            with self.subTest(slug):
                t = vydymyi(self.html(slug))
                self.assertIsNone(ZABORONENI_SLOVA.search(t), slug)
                for z in ZABOR:
                    self.assertIsNone(re.search(z, t, re.I), f'{slug}: {z}')
                self.assertTrue('не перевірений факт' in t or 'не юридична допомога' in t, slug)

    def test_urivok_z_chysel_budynku(self):
        """Уривок — справжні числа одного будинку з відкритої сторінки, без нових фактів."""
        h = self.html('orenda')
        self.assertIn('Уривок довідки — справжні числа цього будинку', h)
        self.assertNotIn('вигадані', h)
        m = re.search(r'<a href="(/budynok/[^"?]+/)\?dzherelo=or">Сторінка цього будинку</a>', h)
        self.assertTrue(m)
        b = (self.sait / m.group(1).strip('/') / 'index.html').read_text(encoding='utf-8')
        # Хрещатик, 22 — єдиний зі скаргами, порівнянням і подіями: 7 звернень, «вода» 5 проти 1 у сусідів, 3 події
        self.assertIn('вулиця Хрещатик, 22', h)
        self.assertIn('7 звернень', h)
        self.assertIn('найчастіше «вода» — тут 5, у сусідніх будинках у радіусі 300 м зазвичай 1', h)
        self.assertIn('3 події', h)
        self.assertIn('7 звернень', b)

    def test_varianty_orendy(self):
        for v in self.VK.VARIANTY_ORENDY:
            with self.subTest(v):
                h = self.VK.orenda('https://x.ua', None, v)
                self.assertEqual(perevirka_storinky(h), [])
                self.assertIn('id="poshuk-vulytsi"', h)
                self.assertIn('Зразок: адреса й числа вигадані', h)
        self.assertIn(self.VK.VARIANT_ORENDY, self.VK.VARIANTY_ORENDY)
        with self.assertRaises(ValueError):
            self.VK.orenda('https://x.ua', None, 'Я')

    def test_dovzhyna_kanalu(self):
        """Канал заявки — до 40 знаків (site/worker/prodazh/formy.js): найдовший — «oplata-dodatkova-» + код + мітка."""
        js = (KORIN / 'site' / 'sait' / 'vkhid.js').read_text(encoding='utf-8')
        maks = int(re.search(r'MAKS_MITKY = (\d+)', js).group(1))
        self.assertEqual(maks, self.VK.MAKS_MITKY)
        naidovshyi = max(len(f'oplata-{k}-') for k in self.T.TSINY) + max(map(len, self.VK.VKHODY.values())) + 1 + maks
        self.assertLessEqual(naidovshyi, 40)


@unittest.skipUnless(YE_H3, 'немає бібліотеки h3 (pip install h3)')
class BezBudynkiv(unittest.TestCase):
    def test_zrazok_pidpysanyi(self):
        with tempfile.TemporaryDirectory() as t:
            sait = zibraty(Path(t), z_budynkamy=False)
            for slug in ('orenda', 'kupivlia', 'rieltor', 'dlia-osbb', 'tut'):
                h = (sait / slug / 'index.html').read_text(encoding='utf-8')
                self.assertIn('Зразок: адреса й числа вигадані', h, slug)
                self.assertNotIn('справжні числа', h, slug)


@unittest.skipUnless(YE_H3 and CHROME, 'немає h3, Playwright або Chrome — перевірку в браузері пропущено')
class MitkyUBrauzeri(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import functools
        import http.server
        import threading
        from playwright.sync_api import sync_playwright
        cls.tmp = tempfile.TemporaryDirectory()
        sait = zibraty(Path(cls.tmp.name))
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(sait)))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f'http://127.0.0.1:{cls.server.server_address[1]}'
        cls.pw = sync_playwright().start()
        cls.b = cls.pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.b.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.tmp.cleanup()

    def knopka(self, s, tovar):
        return s.get_attribute(f'a[href*="tovar={tovar}"]', 'href')

    def test_mitka_vid_vkhodu_do_budynku(self):
        k = self.b.new_context()
        self.addCleanup(k.close)
        s = k.new_page()
        s.goto(self.url + '/orenda/?dzherelo=TT0412!!')
        self.assertIn('dzherelo=or-tt0412', self.knopka(s, 'dovidka'))
        # пошук → сторінка будинку: кнопка оплати там уже з міткою входу
        s.fill('#poshuk-vulytsi', 'Хрещатик 22')
        s.wait_for_selector('#poshuk-spysok a')
        s.click('#poshuk-spysok a')
        s.wait_for_load_state('load')
        self.assertIn('/budynok/', s.url)
        self.assertIn('dzherelo=or-tt0412', self.knopka(s, 'dovidka'))
        # оплата-заглушка передає мітку у форму передзамовлення
        s.click('a[href*="tovar=dovidka"]')
        s.wait_for_load_state('load')
        self.assertIn('dzherelo=oplata-dovidka-or-tt0412', s.get_attribute('#oplata-poshta', 'href'))

    def test_bez_mitky_i_dovha_mitka(self):
        k = self.b.new_context()
        self.addCleanup(k.close)
        s = k.new_page()
        s.goto(self.url + '/dlia-osbb/')
        self.assertIn('dzherelo=os', self.knopka(s, 'osbb'))
        s.goto(self.url + '/rieltor/?dzherelo=' + 'a' * 60)
        self.assertIn('dzherelo=rl-' + 'a' * 16, self.knopka(s, 'rieltor'))
        self.assertNotIn('a' * 17, self.knopka(s, 'rieltor'))

    def test_vnutrishni_posylannia_ne_zatyraiut(self):
        k = self.b.new_context()
        self.addCleanup(k.close)
        s = k.new_page()
        s.goto(self.url + '/tut/?dzherelo=ig7')
        s.goto(self.url + '/miy-budynok/?dzherelo=holovna')
        self.assertIn('dzherelo=tut-ig7', self.knopka(s, 'dovidka'))

    def test_rolyk_odrazu_na_budynok(self):
        k = self.b.new_context()
        self.addCleanup(k.close)
        s = k.new_page()
        s.goto(self.url + '/budynok/khreshchatyk/22/?dzherelo=tt99')
        self.assertIn('dzherelo=tt99', self.knopka(s, 'dovidka'))

    def test_bez_vkhodu_mitka_ne_zminiuietsia(self):
        k = self.b.new_context()
        self.addCleanup(k.close)
        s = k.new_page()
        s.goto(self.url + '/miy-budynok/')
        self.assertIn('dzherelo=miy-budynok', self.knopka(s, 'dovidka'))


if __name__ == '__main__':
    unittest.main()
