"""Перевірки макета М5 (ZAVDANNYA-32): сім варіантів, одна бірюзова шкала, плавний перехід сот, межі плашок 3:1.

Запуск: python -m unittest tests.test_maket_m5 -v
Перевіряє сторінку maket/m5/index.html; дані — спільні з М1 (maket/m1/dani.json).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.test_maket_m4 import ZABORONENI_SLOVA, kontrast

KORIN = Path(__file__).resolve().parents[1]
MAKET = KORIN / 'maket' / 'm5'


def stopy(html: str, nazva: str) -> dict[str, list[tuple[float, float]]]:
    """Розбирає `const FADE={XL:[[0,1],...],L:[...]}` у словник рівень → [(зум, значення)]."""
    m = re.search(r'const ' + nazva + r'=\{(.+?)\};', html)
    vyhid = {}
    for riv, tilo in re.findall(r'(\w+):\[((?:\[[\d.]+,[\d.]+\],?)+)\]', m.group(1)):
        vyhid[riv] = [(float(a), float(b)) for a, b in re.findall(r'\[([\d.]+),([\d.]+)\]', tilo)]
    return vyhid


class StorinkaM5(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (MAKET / 'index.html').read_text(encoding='utf-8')

    def test_nemaye_zaboronenykh_sliv(self):
        self.assertIsNone(ZABORONENI_SLOVA.search(self.html))

    def test_simka_variantiv(self):
        for k in ('k1', 'k2', 'k3', 'a2', 'b2', 'v2', 'g'):
            self.assertRegex(self.html, r'\b' + k + r':\{n:')
        for t in ('Як карта Києва', 'Київ, прозоріше', 'Київ + вершини', 'Спокійна', 'Вершини', 'Нічне місто', 'Нахил'):
            self.assertIn(t, self.html)

    def test_shryft_fixel_za_zamovchuvannyam(self):
        self.assertIn('--sans:Fixel', self.html)
        self.assertIn('data-shr="manrope"', self.html)
        self.assertNotIn('eUkraine', self.html)

    def test_odna_shkala_bez_koloriv_vydiv(self):
        # кольори груп з даних (HRUPY[i][2]) на карту не йдуть — лише SHKALA
        self.assertNotRegex(self.html, r'HRUPY\[[^\]]+\]\[2\]')
        self.assertEqual(len(re.findall(r'const SHKALA=', self.html)), 1)

    def test_plavnyi_perekhid_bez_provalu(self):
        """Сусідні рівні перекриваються: новий з'являється раніше, ніж старий зникає (як у карті Києва)."""
        for nazva in ('FADE', 'MN'):
            st = stopy(self.html, nazva)
            for staryi, novyi in (('XL', 'L'), ('L', 'S')):
                kinets = st[staryi][-1][0]                                            # старий зник
                poyava = [z for z, v in st[novyi] if v == 1][0]                       # новий повний
                pochatok = st[novyi][0][0]                                            # новий почав
                self.assertLess(pochatok, kinets, (nazva, staryi))
                self.assertLessEqual(poyava, kinets + .01, (nazva, staryi))

    def test_bez_avtonakhylu_i_bez_hash_maplibre(self):
        self.assertNotIn('hash:true', self.html)
        self.assertNotIn('pitch3d', self.html)
        self.assertIn("addEventListener('popstate'", self.html)
        self.assertIn('history.pushState', self.html)

    def test_mezhi_plashok_3_do_1(self):
        svitla = re.search(r':root\{[^}]*--mezha:(#[0-9A-F]{6})', self.html).group(1)
        temna = re.search(r'body\[data-t=temna\]\{[^}]*--mezha:(#[0-9A-F]{6})', self.html).group(1)
        for tlo in ('#F7F6F2', '#FFFFFF', '#E9EBE0', '#D5DEDD'):
            self.assertGreaterEqual(kontrast(svitla, tlo), 3.0, tlo)
        for tlo in ('#111517', '#1A2023', '#2B2F36', '#0C1012', '#22262C'):
            self.assertGreaterEqual(kontrast(temna, tlo), 3.0, tlo)

    def test_zaslony_i_chysla(self):
        self.assertIn("'icon-opacity':0", self.html)
        self.assertIn("id:'k-numt-'", self.html)

    def test_rukh_i_dostupnist(self):
        self.assertIn('prefers-reduced-motion', self.html)
        self.assertNotRegex(self.html, r'transition:\s*all')
        self.assertNotIn('maximum-scale', self.html)
        self.assertIn('font:400 16px/24px var(--sans)', self.html)

    def test_lokalni_fajly_ye(self):
        for shlyakh in re.findall(r"url\(([^)]+\.woff2)\)", self.html):
            self.assertTrue((MAKET / shlyakh).resolve().is_file(), shlyakh)
        self.assertTrue((MAKET / '../m1/vendor/maplibre-gl-6.10.0/maplibre-gl.mjs').resolve().is_file())


if __name__ == '__main__':
    unittest.main()
