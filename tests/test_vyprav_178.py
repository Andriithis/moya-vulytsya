"""ZAVDANNYA-178, п. 4: скільки читати довідку — правда.

Заміряно 20.11.2026 на пробному випуску 08.11 і скаргах 1551 (Оболонський 16, Хрещатик 22, Деміївська 45; docs/ZVIT-178.md):
три висновки зверху — 79–101 слово (≈ пів хвилини при 200 словах на хвилину), уся довідка в PDF — 3 сторінки, 769–922 слова
(≈ 4–5 хвилин). Тож «прочитати за 2–3 хвилини» про всю довідку — неправда; «за хвилину» кажемо лише про три висновки.

Запуск: python -m unittest tests.test_vyprav_178 -v
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
FAILY = [KORIN / 'site' / 'storinky_vkhodiv.py', KORIN / 'site' / 'storinky_mv100.py']


class ChasChytannia(unittest.TestCase):
    def test_ne_obitsiaiemo_vsiu_dovidku_za_2_3_khvylyny(self):
        for f in FAILY:
            t = f.read_text(encoding='utf-8')
            self.assertNotRegex(t, r'\d\s*[–-]\s*\d\s*хвилин', f'{f.name}: час читання всієї довідки — заміряно 4–5 хв')

    def test_khvylyna_lyshe_pro_try_vysnovky(self):
        """Кожна обіцянка «прочитати за хвилину» в описі довідки стоїть поруч зі словами «три висновки»."""
        for f in FAILY:
            for r in f.read_text(encoding='utf-8').splitlines():
                if re.search(r'(прочитати|читати)[^\'"]*за хвилину|висновки зверху, за хвилину', r):
                    self.assertIn('три висновки', r, f'{f.name}: «за хвилину» не про три висновки: {r.strip()}')

    def test_try_misttsia_vypravleno(self):
        import sys
        sys.path.insert(0, str(KORIN / 'site'))
        import storinky_vkhodiv as SV
        self.assertIn('головне — три висновки зверху: прочитати за хвилину перед переглядом',
                      SV.VKHODY['orendaria']['punkty']['dovidka'])
        self.assertIn('головне — три висновки зверху, за хвилину', SV.VKHODY['pokuptsia']['punkty']['dovidka'])
        mv = (KORIN / 'site' / 'storinky_mv100.py').read_text(encoding='utf-8')
        self.assertIn('уся довідка — 3 сторінки', mv)


if __name__ == '__main__':
    unittest.main()
