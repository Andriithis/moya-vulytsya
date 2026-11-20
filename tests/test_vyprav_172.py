"""ZAVDANNYA-172: правові сторінки в вигляді сайту (site/storinky_pravo.py), адреси оферти й умов, форма звернення.

Тести сервера продажу — site/worker/testy/vyprav_172.test.mjs (запускає tests/test_prodazh.py).
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(KORIN / 'site'), str(KORIN / 'site' / 'zahlushka')]

import storinky_pravo as P  # noqa: E402
import zibraty as zahlushka  # noqa: E402


class PravoviStorinky(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.teka = Path(cls.tmp.name) / 'zahlushka'
        zahlushka.zibraty(cls.teka, '', '', {}, False, None, skhovyshche='sait')
        cls.originaly = {n: (cls.teka / n).read_text(encoding='utf-8') for n in P.STORINKY}
        cls.zrobleno = P.zibraty(cls.teka, 'https://mv.test')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def tekst(self, n):
        return (self.teka / n).read_text(encoding='utf-8')

    def test_usi_pravovi_storinky_u_vyhliadi_saitu(self):
        self.assertEqual(sorted(self.zrobleno), sorted(P.STORINKY))
        for n in P.STORINKY:
            t = self.tekst(n)
            self.assertIn('<link rel="stylesheet" href="/sait/sait.css">', t, n)
            self.assertIn('<link rel="stylesheet" href="/sait/pravo.css">', t, n)
            self.assertIn('aria-label="Моя вулиця — на головну"', t, n)
            self.assertIn('data-tema-perem', t, n)                       # перемикач теми, як на сайті
            self.assertIn('href="/dostupnist/">Доступність', t, n)        # спільний підвал
            self.assertNotIn('<a href="index.html#peredzamovlennya">Передзамовлення</a>', t, n)   # шапка заглушки
            self.assertNotIn('href="index.html', t, n)
            self.assertIn(f'<link rel="canonical" href="https://mv.test/zahlushka/{n}">', t, n)
            # вміст сторінки — той самий
            main = re.search(r'<main class="storinka">\n?(.*?)</main>', self.originaly[n], re.S).group(1)
            h1 = re.search(r'<h1[^>]*>(.*?)</h1>', main).group(1)
            self.assertIn(h1, t, n)

    def test_zvernennya_zi_skryptamy_i_bez_indeksu_yak_bulo(self):
        t = self.tekst('zvernennya.html')
        for s in ('config.js', 'nadsylannya.js', 'zvernennya.js'):
            self.assertIn(f'<script src="/zahlushka/{s}"></script>', t)
        self.assertIn('id="adresa"', t)
        self.assertIn('Посилання на подію або номер рішення — якщо є', t)
        self.assertIn('id="vdacha-nomer"', t)

    def test_chynna_redaktsiia_i_korotki_adresy(self):
        for n in ('oferta.html', 'umovy.html'):
            dzherelo = (KORIN / 'site' / 'zahlushka' / n).read_text(encoding='utf-8')
            self.assertIn(f'Чинна редакція завжди тут: [САЙТ]/zahlushka/{n}', dzherelo)
        self.assertIn(('/oferta.html', '/zahlushka/oferta.html'), P.PERENAPRAVLENNIA)
        self.assertIn(('/umovy/', '/zahlushka/umovy.html'), P.PERENAPRAVLENNIA)


if __name__ == '__main__':
    unittest.main()


class DliaBiznesu(unittest.TestCase):
    """ZVIT-169, пп. 2–3: числа сторінки = числа копії; зразок CSV — лише формат; ціна не вигадана."""

    def test_zrazok_csv_lyshe_format_i_stovptsi_kopii(self):
        import storinky_mv100 as M
        t = M.zrazok_csv()
        self.assertTrue(t.startswith('﻿'))
        ryadky = t.lstrip('﻿').splitlines()
        self.assertEqual(ryadky[1].split(','), M.STOVPTSI_KOPII)
        self.assertNotIn('reyestr.court.gov.ua/files', t)          # Б-1: жодного справжнього посилання
        for r in M.ZRAZOK_CSV:
            self.assertTrue(r['opys'] == '' or r['opys'].startswith('‹'), 'опис — лише заглушка (MV-99)')
            self.assertTrue(r['adresa'] == '' or r['adresa'].startswith('‹'), 'адреса — лише заглушка')

    def test_stovptsi_yak_u_kopii_dani_edrsr(self):
        """Якщо поруч є dani-edrsr з копією для компанії — стовпці зразка ті самі (на CI — пропуск)."""
        kopiia = KORIN.parent / 'dani-edrsr' / 'src' / 'kopiia_biznesu.py'
        if not kopiia.exists():
            self.skipTest('немає dani-edrsr/src/kopiia_biznesu.py поруч')
        import storinky_mv100 as M
        t = kopiia.read_text(encoding='utf-8')
        blok = t[t.index("'podii': ["):t.index("'problemy': [")]
        self.assertEqual(re.findall(r"\('([a-z_]+)', '", blok), M.STOVPTSI_KOPII)

    def test_tsina_ne_vyhadana(self):
        import storinky_mv100 as M
        st = M.vitryna_biznes('https://mv.test', None, '', [], {'vsi': 10, 'z_mistsem': 7, 'rik_vid': 2019, 'rik_do': 2026, 'vidkryti': 6})
        self.assertIn('Ціну називаємо після запиту', st)
        self.assertNotRegex(st, r'від\s*\d[\d\s]*\s*грн')
        self.assertIn('у копії, роки подій 2019–2026', st)
        self.assertIn('з точною адресою й точкою', st)
        self.assertIn('href="/biznes/zrazok-podii.csv"', st)
        self.assertIn('href="#zapyt">Запит на доступ', st)


class DribneZvit169(unittest.TestCase):
    """ZVIT-169, п. 10: людські дати, без «докачуються» й «після повного Києва», «11 статей» — з даних."""

    def test_data_slovamy(self):
        import zibraty_sait as Z
        self.assertEqual(Z.data_slovamy('2026-11-17'), '17 листопада 2026')
        self.assertEqual(Z.data_slovamy('2026-11'), '2026-11')

    def test_bez_kukhni_v_tekstakh(self):
        sp = (KORIN / 'site' / 'storinky_sp.py').read_text(encoding='utf-8')
        self.assertNotIn('докачуються', sp)
        self.assertNotIn('після повного Києва', (KORIN / 'site' / 'zahlushka' / 'oferta.html').read_text(encoding='utf-8'))
        js = (KORIN / 'site' / 'sait' / 'sp.js').read_text(encoding='utf-8')
        self.assertNotIn('11 найчастіших', js)
        self.assertIn("querySelectorAll('.sp-stattia').length", js)

    def test_pidval_bez_koloru_na_storinkakh_bez_karty(self):
        import zibraty_sait as Z
        for shl, ye in (('/biznes/', False), ('/sudova-praktyka/kupap-130/', False), ('/vulytsi/', True)):
            st = Z.storinka(shlyakh=shl, title='т', opys='о', tilo='', adresa_saitu='https://mv.test')
            self.assertEqual('Колір і числа показують' in st, ye, shl)


class Dostupnist(unittest.TestCase):
    """ZVIT-171, п. 10: сторінка «Доступність» — чесно, без «відповідає закону»."""

    def test_storinka(self):
        import storinka_dostupnist as SD
        st = SD.storinka('https://mv.test')
        self.assertIn('<h1>Доступність</h1>', st)
        self.assertIn('Що перевірено', st)
        self.assertIn('Що ще не працює як слід', st)
        self.assertIn('/zahlushka/pro-nas.html', st)
        for zaboroneno in ('відповідає закону', 'відповідає вимогам', 'сертифіковано', 'повністю доступн'):
            self.assertNotIn(zaboroneno, st)
        self.assertIn('не висновок про відповідність будь-якому закону', st)
