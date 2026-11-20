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


if __name__ == '__main__':
    unittest.main()
