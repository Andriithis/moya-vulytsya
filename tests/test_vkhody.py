"""Сторінки-входи під рекламу (ZAVDANNYA-153): /dlia/<людина>/.

Запуск: python -m unittest tests.test_vkhody -v
Сайт збирається з тієї самої штучної бази, що й tests/test_sait.py. Перевірки в браузері (мітка джерела проходить від входу
до кнопки оплати на сторінці будинку) — коли є Playwright і Chrome (MV_CHROME=/шлях/до/chrome).
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'tests'))
import test_sait as TS  # noqa: E402

VKHODY = ('orendaria', 'pokuptsia', 'rieltora', 'osbb', 'yurysta', 'meshkantsia')
HOLOVNYI = {'orendaria': 'dovidka', 'pokuptsia': 'zvit', 'rieltora': 'rieltor', 'osbb': 'osbb', 'yurysta': 'spdovidka',
            'meshkantsia': 'dovidka'}
# AGENTS.md, розд. 4: прогнози словами, поради, як поводитися, службові слова — у тому, що бачать люди.
ZABORONENI_ZVOROTY = re.compile(r'найімовірніше|імовірно, буде|станеться знову|дивіться уважніше|будьте уважн|уникайте|'
                                r'не ходіть|бути уважніш|макет|конвеєр|медіана|MV-\d|ОСОБА_|небезпечн|безпечн|рейтинг|страшн',
                                re.I)


def zibraty(teka: Path, oplata: str = 'skoro') -> Path:
    import tsiny as T
    import zibraty_sait
    TS.stvoryty_bazu(teka / 'events.db')
    TS.stvoryty_pereimenuvannya(teka / 'pereim.csv')
    (teka / 'budynky.json').write_text(json.dumps(TS.BUDYNKY, ensure_ascii=False), encoding='utf-8')
    bulo = T.OPLATA['rezhym']
    T.OPLATA['rezhym'] = oplata
    try:
        zibraty_sait.zibraty_sait(teka / 'events.db', teka / 'sait', teka / 'pereim.csv', KORIN / 'data' / 'borders.json',
                                  budynky=teka / 'budynky.json')
    finally:
        T.OPLATA['rezhym'] = bulo
    return teka / 'sait'


@unittest.skipUnless(TS.YE_H3, 'немає бібліотеки h3 (pip install h3) — збирання сайту пропущено')
class Vkhody(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.sait = zibraty(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def tekst(self, slug: str) -> str:
        return (self.sait / 'dlia' / slug / 'index.html').read_text(encoding='utf-8')

    def test_shist_storinok_ne_dlia_google(self):
        sitemap = (self.sait / 'sitemap.xml').read_text(encoding='utf-8')
        for slug in VKHODY:
            t = self.tekst(slug)
            self.assertIn('<meta name="robots" content="noindex, follow">', t, slug)
            self.assertNotIn(f'/dlia/{slug}/', sitemap, slug)
            self.assertIn('<script src="/sait/vkhid.js"></script>', t, slug)
            self.assertIn('href="/sait/vkhid.css"', t, slug)
            self.assertIn(f'data-vkhid="vh-', t, slug)
        self.assertTrue((self.sait / 'sait' / 'vkhid.js').is_file())
        self.assertTrue((self.sait / 'sait' / 'vkhid.css').is_file())

    def test_pershyi_ekran_potreba_poshuk_tsina(self):
        """В6 (MV-158): спершу потреба (h1), потім пошук адреси (юристу — статті) і кнопка з ціною головного товару — усе
        в першій секції сторінки; ціна — з site/tsiny.py, кнопка несе мітку входу."""
        import tsiny as T
        for slug in VKHODY:
            t = self.tekst(slug)
            ekran = re.search(r'<section class="vkhid-ekran[^"]*">(.*?)</section>', t, re.S).group(1)
            self.assertIn('<h1>', ekran, slug)
            if slug == 'yurysta':
                self.assertIn('class="vkhid-statti"', ekran)
            else:
                self.assertIn('id="poshuk-vulytsi"', ekran, slug)
                self.assertIn('<script src="/sait/poshuk.js"></script>', t, slug)
            kl = HOLOVNYI[slug]
            self.assertIn(f'/oplata/?tovar={kl}&amp;dzherelo=vh-', ekran, slug)
            self.assertIn(T.tsina(kl).replace(' ', ' '), ekran, slug)

    def test_tsiny_lyshe_z_tablytsi_i_skoro(self):
        import tsiny as T
        dozvoleni = T.dozvoleni_sumy()
        for slug in VKHODY:
            t = self.tekst(slug)
            for n in re.findall(r'(\d[\d  ]*)(?: |\s)?грн', t):
                self.assertIn(int(re.sub(r'\D', '', n)), dozvoleni, f'{slug}: {n} грн')
            self.assertIn('knopka--skoro', t, slug)           # режим «скоро» — кнопки ведуть на пошту
            self.assertIn('Скоро — залиште пошту', t, slug)

    def test_bez_zaboronenykh_zvorotiv(self):
        for slug in VKHODY:
            tilo = re.sub(r'<[^>]+>', ' ', self.tekst(slug).split('<main', 1)[1])
            tilo += re.search(r'<title>([^<]*)</title>', self.tekst(slug)).group(1)
            m = ZABORONENI_ZVOROTY.search(tilo)
            self.assertIsNone(m, f'{slug}: {m and m.group(0)}')

    def test_urivok_zi_spravzhnikh_danykh(self):
        """Уривок — ті самі числа, що на відкритій сторінці будинку; номер будинку — лише в посиланні на неї."""
        import storinky_mv100 as M
        import storinky_vkhodiv as V
        t = self.tekst('orendaria')
        self.assertIn('Уривок зі справжніх даних', t)
        url = re.search(r'<a href="(/budynok/[^"]+/)">Відкрити сторінку цього будинку</a>', t).group(1)
        self.assertTrue((self.sait / url.strip('/') / 'index.html').is_file(), url)
        b = next(x for x in TS.BUDYNKY['budynky'] if f'/{M.slug_nomera(M.bez_kvartyry(x["nomer"]))}/' in url)
        urivok = re.search(r'<div class="kartka vkhid-urivok">(.*?)</div>\n?</section>|<div class="kartka vkhid-urivok">(.*)', t, re.S)
        tekst_urivka = re.sub(r'<[^>]+>', ' ', re.sub(r'href="[^"]*"', '', urivok.group(0)))
        self.assertIn(f'{sum(b["skarhy"].values())} ', tekst_urivka)
        self.assertNotRegex(tekst_urivka, rf'\b{re.escape(M.bez_kvartyry(b["nomer"]))}\b(?!\s*(?:м|звернен|подій))')
        self.assertIn('/zahlushka/zrazok.html', t)
        self.assertIn(V.VARIANT_ORENDARIA, V.VARIANTY_ORENDARIA)

    def test_yurysta_bez_danykh_sp_ne_vede_v_nikudy(self):
        """Без зведення «Судової практики» в збірці — лише «Усі статті» (сторінок статей немає)."""
        t = self.tekst('yurysta')
        self.assertNotIn('/sudova-praktyka/kupap/', t)
        self.assertIn('href="/sudova-praktyka/">Усі статті</a>', t)

    def test_oplata_tak(self):
        """Коли оплату ввімкнено — звичайні кнопки; «Судова практика» без даних лишається «скоро» (tsiny.BEZ_DANYKH)."""
        import storinky_vkhodiv as V
        import tsiny as T
        bulo = T.OPLATA['rezhym']
        T.OPLATA['rezhym'] = 'tak'
        try:
            t = V.storinka_vkhodu('orendaria', 'https://x.y', V.urivok(None, None, ''))
            y = V.storinka_vkhodu('yurysta', 'https://x.y', V.urivok_sp(None))
        finally:
            T.OPLATA['rezhym'] = bulo
        self.assertNotIn('knopka--skoro', t)
        self.assertNotIn('Оплата ще не працює', t)
        self.assertIn('<a class="knopka knopka--holovna" href="/oplata/?tovar=dovidka&amp;dzherelo=vh-orendar">', t)
        self.assertIn('knopka--skoro', y)

    def test_varianty_orendaria(self):
        """2–3 варіанти першого екрана орендаря (ZAVDANNYA-153) — усі з потребою, пошуком і кнопкою з ціною."""
        import storinky_vkhodiv as V
        for v in V.VARIANTY_ORENDARIA:
            t = V.storinka_vkhodu('orendaria', 'https://x.y', V.urivok(None, None, ''), variant=v)
            self.assertIn(f'vkhid-ekran--{v}', t)
            ekran = re.search(r'<section class="vkhid-ekran[^"]*">(.*?)</section>', t, re.S).group(1)
            for x in ('<h1>', 'id="poshuk-vulytsi"', '/oplata/?tovar=dovidka'):
                self.assertIn(x, ekran, (v, x))


@unittest.skipUnless(TS.BRAUZER, 'немає Playwright або Chrome/Edge, або h3 — перевірку в браузері пропущено')
class VkhodyUBrauzeri(unittest.TestCase):
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
        cls.b = cls.pw.chromium.launch(executable_path=TS.BRAUZER, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.b.close()
        cls.pw.stop()
        cls.server.shutdown()
        cls.tmp.cleanup()

    def test_mitka_vid_vkhodu_do_oplaty(self):
        """?dzherelo= з реклами → кнопки входу й сторінки будинку, куди привів пошук, несуть «vh-<людина>-<мітка>»."""
        k = self.b.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True)
        self.addCleanup(k.close)
        s = k.new_page()
        pomylky = []
        s.on('pageerror', lambda e: pomylky.append(str(e)))
        s.goto(f'{self.url}/dlia/orendaria/?dzherelo=TT-1121a!')
        href = s.locator('.vkhid-ekran a[href^="/oplata/"]').first.get_attribute('href')
        self.assertIn('dzherelo=vh-orendar-tt-1121a', href)
        # пошук адреси на першому екрані: поле видно без прокрутки
        pole = s.locator('#poshuk-vulytsi')
        self.assertTrue(pole.is_visible())
        self.assertLess(pole.bounding_box()['y'] + pole.bounding_box()['height'], 844)
        pole.fill('Хрещатик 22')
        s.wait_for_selector('#poshuk-spysok a')
        s.locator('#poshuk-spysok a').first.click()
        s.wait_for_load_state()
        self.assertIn('/budynok/', s.url)
        hrefs = s.locator('a[href^="/oplata/"]').evaluate_all('a => a.map(x => x.getAttribute("href"))')
        self.assertTrue(hrefs)
        for h in hrefs:
            self.assertIn('dzherelo=vh-orendar-tt-1121a', h)
        # /oplata/ передає мітку у форму пошти
        s.goto(self.url + hrefs[0])
        self.assertIn('vh-orendar-tt-1121a', s.locator('#oplata-poshta').get_attribute('href'))
        self.assertEqual(pomylky, [])

    def test_bez_mitky_kanal_vkhodu(self):
        k = self.b.new_context()
        self.addCleanup(k.close)
        s = k.new_page()
        s.goto(f'{self.url}/dlia/osbb/')
        self.assertIn('dzherelo=vh-osbb', s.locator('.vkhid-ekran a[href^="/oplata/"]').first.get_attribute('href'))
        # інша вкладка без входу — мітки немає
        s2 = self.b.new_context().new_page()
        s2.goto(f'{self.url}/miy-budynok/')
        self.assertIn('dzherelo=miy-budynok', s2.locator('a[href^="/oplata/"]').first.get_attribute('href'))
        s2.context.close()


if __name__ == '__main__':
    unittest.main()
