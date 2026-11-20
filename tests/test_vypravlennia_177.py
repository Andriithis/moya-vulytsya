"""ZAVDANNYA-177: виправлення сторінок і пошуку за критиком ZVIT-165 (топ-10).

Запуск: python -m unittest tests.test_vypravlennia_177 -v
Сайт збирається з тієї самої штучної бази, що tests/test_sait.py (без справжніх даних).
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(KORIN / 'tests'))

import dani as D  # noqa: E402

try:
    import h3  # noqa: F401
    YE_H3 = True
except ImportError:
    YE_H3 = False


def dodaty_odrukivku(baza: Path) -> None:
    """«просп. Вололодимира Лобановського» — одруківка, як «Вололодимира Івасюка» у справжньому випуску."""
    con = sqlite3.connect(baza)
    n = con.execute('SELECT max(CAST(doc_id AS INTEGER)) FROM document').fetchone()[0] + 1
    con.execute('INSERT INTO document VALUES (?,?,?,?,?,?,?)', (str(n), 'суд', '2025-01-01', 'постанова', '41080', f'{n}/25',
                                                               f'https://reyestr.court.gov.ua/Review/{n}'))
    con.execute('INSERT INTO location VALUES (?,?,?,?,?,?)', (n, 'просп. Вололодимира Лобановського, 4', 'house', 50.4291, 30.4851, 'osm'))
    con.execute('INSERT INTO event VALUES (?,?,?,?,?,?,?,?,?,?,?)',
                (f'{n}-1', str(n), 1, '2025-03-03', '10:30', 'ДТП', 'ст.124 КУпАП · ДТП з пошкодженням майна',
                 'Водій допустив зіткнення.', 0, '11216:4344', n))
    con.commit()
    con.close()


# словник народних назв — як dani-edrsr/config/mistsevosti-kyiv.csv (у штучному місті є лише три райони)
MISTSEVOSTI = ('nazva,inshi_nazvy,rayony,prymitka\n'
               "Шулявка,,Шевченківський;Солом'янський,тест\n"
               'Троєщина,Троя,Деснянський,району в штучному місті немає — не показуємо\n')

VYPRAVLENNIA = ('typ,pomylka,typ_pravylnyi,pravylno,prymitka\n'
                'проспект,Вололодимира Лобановського,проспект,Валерія Лобановського,тест\n')


@unittest.skipUnless(YE_H3, 'потрібна бібліотека h3')
class Vypravlennia(unittest.TestCase):
    """П. 10: одруківка з таблиці dani-edrsr (S-М.21) — не окрема вулиця."""

    def test_odrukivka_ne_okrema_vulytsia(self):
        import test_sait as TS
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            TS.stvoryty_bazu(t / 'events.db')
            dodaty_odrukivku(t / 'events.db')
            TS.stvoryty_pereimenuvannya(t / 'pereimenuvannia-test.csv')
            bez = D.zibraty_dani(t / 'events.db', t / 'pereimenuvannia-test.csv', None)
            self.assertTrue(any('Вололодимира' in v.nazva for v in bez.vulytsi.values()), 'без таблиці одруківка — окрема')
            (t / 'vypravlennia-nazv-test.csv').write_text(VYPRAVLENNIA, encoding='utf-8')
            z = D.zibraty_dani(t / 'events.db', t / 'pereimenuvannia-test.csv', None)
            self.assertFalse([v.nazva for v in z.vulytsi.values() if 'Вололодимира' in v.nazva])
            lob = [v for v in z.vulytsi.values() if v.nazva == 'проспект Валерія Лобановського'][0]
            lob0 = [v for v in bez.vulytsi.values() if v.nazva == 'проспект Валерія Лобановського'][0]
            self.assertEqual(len(lob.podii), len(lob0.podii) + 1)

    def test_tablytsia_dani_edrsr_chytaietsia(self):
        f = KORIN.parent / 'dani-edrsr' / 'config' / 'vypravlennia-nazv-kyiv.csv'
        if not f.is_file():
            self.skipTest('dani-edrsr не лежить поруч')
        t = D.prochytaty_vypravlennia(f)
        self.assertEqual(t[('проспект', D.kliuch('І. Івасюка'))], ('проспект', 'Володимира Івасюка'))


class Rayony(unittest.TestCase):
    """П. 4 і 8: відмінок району; вулиця на межі районів — усі її райони."""

    def test_mistsevyi_vidminok_10_rayoniv(self):
        import zibraty_sait as Z
        mezhi = json.loads((KORIN / 'data' / 'borders.json').read_text(encoding='utf-8'))
        self.assertEqual(len(mezhi), 10)
        for r in mezhi:
            t = Z.u_rayoni(r)
            self.assertRegex(t, r'^[УВ] \S+(ському|цькому) районі$', r)
        self.assertEqual(Z.u_rayoni('Оболонський'), 'В Оболонському районі')
        self.assertEqual(Z.u_rayoni('Дарницький'), 'У Дарницькому районі')
        self.assertEqual(Z.u_rayoni("Солом'янський", False), "у Солом'янському районі")

    def test_vulytsia_na_mezhi(self):
        import zibraty_sait as Z
        from collections import Counter
        v = D.Vulytsia('khreshchatyk', 'вулиця Хрещатик', 'вулиця', 'Хрещатик', 'osm')
        v.rayony = Counter({'Печерський': 40, 'Шевченківський': 30, 'Голосіївський': 3})
        self.assertEqual(Z.rayony_vulytsi(v), ['Печерський', 'Шевченківський'])
        self.assertEqual(Z.rayony_tekst(Z.rayony_vulytsi(v)), 'Печерський і Шевченківський райони')
        self.assertEqual(Z.rayony_tekst(['Печерський']), 'Печерський район')
        self.assertEqual(Z.rayony_tekst([], False), '')


@unittest.skipUnless(YE_H3, 'потрібна бібліотека h3')
class Sait(unittest.TestCase):
    """Зібраний штучний сайт: перший екран головної, район, «немає будинку», будинок, вхід."""

    @classmethod
    def setUpClass(cls):
        import test_sait as TS
        import zibraty_sait as Z
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        TS.stvoryty_bazu(t / 'events.db')
        TS.stvoryty_pereimenuvannya(t / 'pereimenuvannia-kyiv.csv')
        (t / 'mistsevosti-kyiv.csv').write_text(MISTSEVOSTI, encoding='utf-8')
        (t / 'budynky.json').write_text(json.dumps(TS.BUDYNKY, ensure_ascii=False), encoding='utf-8')
        cls.sait = t / 'sait'
        Z.zibraty_sait(t / 'events.db', cls.sait, t / 'pereimenuvannia-kyiv.csv', KORIN / 'data' / 'borders.json',
                       budynky=t / 'budynky.json')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def html(self, shlyakh):
        return (self.sait / shlyakh).read_text(encoding='utf-8')

    def test_pershyi_ekran_holovnoi(self):
        h = self.html('index.html')
        h1 = re.findall(r'<h1[^>]*>(.*?)</h1>', h, re.S)
        self.assertEqual(len(h1), 1)
        self.assertIn('кожній вулиці й кожному будинку Києва', h1[0])
        blok = re.search(r'<div class="vstup-holovnoi.*?</div>', h, re.S).group(0)
        self.assertIn('>Перевірити свій будинок</a>', blok)
        self.assertNotRegex(blok, r'\d{3}\s*грн|199', 'першим словом не ціна')
        self.assertIn('.ekran-karty--holovna .vau-lich { display: none; }', (self.sait / 'sait' / 'sait.css').read_text(encoding='utf-8'))
        self.assertNotIn('vstup-holovnoi', self.html('karta/index.html'), 'на /karta/ — як було (там працює ZAVDANNYA-174)')

    def test_rayon_vidminok(self):
        for f in (self.sait / 'rayon').glob('*/index.html'):
            h = f.read_text(encoding='utf-8')
            self.assertNotRegex(h, r'[УВ] \S+ський районі', f.parent.name)
            self.assertRegex(h, r'<p>[УВ] \S+(ському|цькому) районі за ', f.parent.name)
            self.assertNotRegex(h, r'href="/vulytsi/" aria-current', 'на районі шапка не підсвічує «Вулиці»')


    def test_shablon_nemaie_budynku(self):
        h = self.html('_404-budynok.html')
        self.assertRegex(h, r'<!--NEMAIE-BUDYNKU--><span class="mitka">будинок</span><h1>.*?</h1>.*?<!--/NEMAIE-BUDYNKU-->')
        self.assertIn('value="%%ZAPYT%%"', h)
        self.assertIn('/sait/poshuk.js', h)
        self.assertIn('noindex', h)
        self.assertNotIn('вулицю перейменовано', h, 'текст про вулиці — лише в загальній 404')

    def test_mistsevosti_v_danykh(self):
        m = json.loads(self.html('karta/mistsevosti.json'))
        self.assertEqual(m, [['Шулявка', [], [["Солом'янський", '/rayon/solomianskyi/']]]])

    def test_poshuk_u_brauzeri(self):
        try:
            from test_sait import BRAUZER
        except Exception:   # noqa: BLE001
            BRAUZER = None
        if not BRAUZER:
            self.skipTest('немає Playwright і Chromium')
        import functools
        import http.server
        import threading
        from playwright.sync_api import sync_playwright
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(http.server.SimpleHTTPRequestHandler,
                                                                                  directory=str(self.sait)))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        self.addCleanup(srv.shutdown)
        url = f'http://127.0.0.1:{srv.server_address[1]}'
        pw = sync_playwright().start()
        self.addCleanup(pw.stop)
        b = pw.chromium.launch(executable_path=BRAUZER, args=['--no-sandbox'])
        self.addCleanup(b.close)
        k = b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True, reduced_motion='reduce')
        k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
        s = k.new_page()
        pomylky = []
        s.on('pageerror', lambda e: pomylky.append(str(e)))

        def pidkazky(pole, z, selektor):
            s.click(pole)
            s.fill(pole, z)
            s.wait_for_timeout(900)
            return s.eval_on_selector_all(selektor, 'xs => xs.map(x => x.textContent)')

        s.goto(url + '/')
        self.assertEqual(s.get_attribute('#poshuk-karty', 'placeholder'), 'Адреса, вулиця або район')
        t = pidkazky('#poshuk-karty', 'хрещятик 22', '#pidkazky li')
        self.assertIn('Можливо, ви мали на увазі:', t)
        self.assertTrue(any('Хрещатик, 22' in x for x in t), t)
        t = pidkazky('#poshuk-karty', 'Шулявка', '#pidkazky li')
        self.assertTrue(any("Шулявка — Солом'янський район" in x for x in t), t)
        s.keyboard.press('Enter')
        s.wait_for_url('**/rayon/solomianskyi/')
        s.goto(url + '/')
        t = pidkazky('#poshuk-karty', 'Хрещатик', '#pidkazky li')
        self.assertFalse([x for x in t if 'Можливо' in x], 'точний збіг — без «можливо»')
        s.goto(url + '/miy-budynok/')
        t = pidkazky('#poshuk-vulytsi', 'хрещятик', '#poshuk-spysok li')
        self.assertIn('Можливо, ви мали на увазі:', t)
        self.assertTrue(any('вулиця Хрещатик' in x for x in t), t)
        t = pidkazky('#poshuk-vulytsi', 'шулявка', '#poshuk-spysok li')
        self.assertTrue(any("Шулявка — Солом'янський район" in x for x in t), t)
        # п. 5: адреса з поля входу — у кнопці ціни
        s.goto(url + '/dlia/orendaria/')
        pidkazky('#poshuk-vulytsi', 'Хрещатик 22', '#poshuk-spysok li')
        s.click('.vkhid-tsina a[href*="/oplata/"]')
        s.wait_for_url('**/oplata/**')
        self.assertIn('budynok=%2Fbudynok%2Fkhreshchatyk%2F22%2F', s.url)
        self.assertIn('dzherelo=vh-orendar', s.url)
        s.goto(url + '/dlia/orendaria/')
        pidkazky('#poshuk-vulytsi', 'Невідома 77', '#poshuk-spysok li')
        s.click('.vkhid-tsina a[href*="/oplata/"]')
        s.wait_for_url('**/oplata/**')
        self.assertIn('adresa=%D0%9D', s.url)
        self.assertNotIn('budynok=', s.url)
        s.goto(url + '/miy-budynok/')
        t = pidkazky('#poshuk-vulytsi', 'зззззз', '#poshuk-spysok li')
        self.assertEqual(t, ['Такої вулиці в даних немає. Перевірте назву або подивіться покажчик.'])
        self.assertEqual(pomylky, [])


if __name__ == '__main__':
    unittest.main()
