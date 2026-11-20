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
