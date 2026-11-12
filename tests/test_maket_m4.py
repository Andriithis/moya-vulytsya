"""Перевірки макета М4 (ZAVDANNYA-28): три вигляди, нова шкала, шрифти.

Запуск: python -m unittest tests.test_maket_m4 -v
Перевіряє сторінку maket/m4/index.html; дані — спільні з М1 (maket/m1/dani.json, їх перевіряє test_maket_m1).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
MAKET = KORIN / 'maket' / 'm4'
ZABORONENI_SLOVA = re.compile(r'небезпечн|безпечн|ризик|рейтинг|індекс', re.I)


def lum(h: str) -> float:
    v = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    v = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in v]
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]


def kontrast(a: str, b: str) -> float:
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def l_star(h: str) -> float:
    y = lum(h)
    return 116 * y ** (1 / 3) - 16 if y > 0.008856 else 903.3 * y


class StorinkaM4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (MAKET / 'index.html').read_text(encoding='utf-8')
        m = re.search(r"const SHKALA=\{svitla:\[([^\]]+)\],temna:\[([^\]]+)\]\}", cls.html)
        cls.svitla = re.findall(r"#[0-9A-F]{6}", m.group(1))
        cls.temna = re.findall(r"#[0-9A-F]{6}", m.group(2))

    def test_nemaye_zaboronenykh_sliv(self):
        self.assertIsNone(ZABORONENI_SLOVA.search(self.html))

    def test_try_varianty_i_try_shryfty(self):
        for v in ('data-var="a"', 'data-var="b"', 'data-var="v"', 'Спокійна', 'Вершини', 'Нічне місто'):
            self.assertIn(v, self.html)
        for f in ('data-shr="1"', 'data-shr="2"', 'data-shr="3"', 'eUkraine', 'Fixel', 'Manrope'):
            self.assertIn(f, self.html)

    def test_shkala_svitla(self):
        self.assertEqual(len(self.svitla), 5)
        # найсвітліший крок — щонайменше 2:1 до тла підкладки й поверхні
        self.assertGreaterEqual(kontrast(self.svitla[0], '#F7F6F2'), 2.0)
        ls = [l_star(c) for c in self.svitla]
        for a, b in zip(ls, ls[1:]):
            self.assertGreaterEqual(a - b, 8)

    def test_shkala_temna(self):
        self.assertEqual(len(self.temna), 5)
        self.assertGreaterEqual(kontrast(self.temna[0], '#111517'), 2.0)
        ls = [l_star(c) for c in self.temna]
        for a, b in zip(ls, ls[1:]):
            self.assertGreaterEqual(b - a, 8)

    def test_spilni_vyp_3d(self):
        self.assertIn('const KLITYNKA=.87;', self.html)          # проміжок 13 %
        self.assertIn('Math.floor(L_*.98)', self.html)           # обрізання на p98
        self.assertIn('Math.sqrt(x/G.p98)', self.html)           # висота за коренем
        self.assertIn('Math.round(45+5*', self.html)             # нахил 45–50°
        self.assertIn("anchor:'map'", self.html)

    def test_rukh_i_dostupnist(self):
        self.assertIn('prefers-reduced-motion', self.html)
        self.assertIn(', T=800;', self.html)
        self.assertNotRegex(self.html, r'transition:\s*all')
        self.assertIn('font:400 16px/24px var(--sans)', self.html)   # поле пошуку 16 px
        self.assertNotIn('user-scalable=no', self.html)
        self.assertNotIn('maximum-scale', self.html)

    def test_spilni_elementy(self):
        for t in ('будинки — у підписці', 'більше подій', 'менше', 'Лише те, що дійшло до суду', 'Види подій'):
            self.assertIn(t, self.html)

    def test_lokalni_fajly_ye(self):
        for shlyakh in re.findall(r"url\(([^)]+\.woff2)\)", self.html):
            self.assertTrue((MAKET / shlyakh).resolve().is_file(), shlyakh)
        self.assertTrue((MAKET / '../m1/vendor/maplibre-gl-6.10.0/maplibre-gl.mjs').resolve().is_file())
        self.assertTrue((MAKET / 'shryfty' / 'OFL-Fixel.txt').is_file())
        self.assertTrue((MAKET / 'shryfty' / 'LICENSE-e-Ukraine.txt').is_file())


if __name__ == '__main__':
    unittest.main()
