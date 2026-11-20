"""Продуктові ролики ZAVDANNYA-155 (video/vau/zapys155.py): розмиття номерів будинків і тексти роликів.

Запуск: python -m unittest tests/test_rolyky155.py
Браузер, сервер продажу й база випуску тут не потрібні: модуль не імпортуємо (він тягне рушій), а читаємо його текст.
"""
from __future__ import annotations

import ast
import importlib.util
import re
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
FAIL = KORIN / 'video' / 'vau' / 'zapys155.py'
DZHERELO = FAIL.read_text(encoding='utf-8')


def perevirka():
    spec = importlib.util.spec_from_file_location('vau_perevirka_155', KORIN / 'video' / 'vau' / 'perevirka.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def rx_rozmyttia() -> re.Pattern:
    """Той самий вираз, що розмиває номер у браузері (JS), — у Python (синтаксис тут збігається)."""
    js = re.search(r'const RX = /(.+)/g;', DZHERELO).group(1)
    return re.compile(js.replace('\\/', '/'))


def rozmyte(t: str) -> list[str]:
    return [m.group(3) for m in rx_rozmyttia().finditer(t)]


class Rozmyttia(unittest.TestCase):
    """MV-25: номер житлового будинку в кадрі — під розмиттям; числа даних — ні."""

    def test_nomery_budynkiv(self):
        self.assertEqual(rozmyte('вул. Приозерна, 10'), ['10'])
        self.assertEqual(rozmyte('Берестейський проспект, 20 — 1 довідка'), ['20'])
        self.assertEqual(rozmyte('просп. Академіка Палладіна, 22-а · ДТП'), ['22-а'])
        self.assertEqual(rozmyte('бульвар Лесі Українки, 24'), ['24'])
        self.assertEqual(rozmyte('вулиця Іринська, 5/7.'), ['5/7'])
        self.assertEqual(rozmyte('шосе Столичне, 101Б'), ['101Б'])

    def test_chysla_danykh_ne_chipaie(self):
        for t in ('1588 скарг 1551 про будинок і двір', 'тут 408 · у сусідніх 0', 'ДТП на вулиці — 10.',
                  'у 2024, 2025 і 2026 роках', 'Звернень до 1551: 186 з 16 будинків', 'у радіусі 300 м',
                  'двір, 408 скарг', 'за рік, 12 разів', 'проти 2,5 %', 'Оплата, 199 грн'):
            self.assertEqual(rozmyte(t), [], t)

    def test_karty_rozmyti(self):
        self.assertIn('.leaflet-container', DZHERELO)
        self.assertIn('filter:blur(9px)', DZHERELO)


class Teksty(unittest.TestCase):
    """Усе, що бачить і чує людина в роликах 155: без заборонених слів, чутливих тем і номерів будинків."""

    def test_ryadky(self):
        P = perevirka()
        ryadky = [n.value for n in ast.walk(ast.parse(DZHERELO)) if isinstance(n, ast.Constant) and isinstance(n.value, str)
                  and re.search('[а-яіїє]', n.value)]
        self.assertGreater(len(ryadky), 50)
        for t in ryadky:
            if t.startswith(('Продуктові ролики', 'Один сценарій', '/__vau/', 'Рушій:', 'Стан ')) or '\n    ' in t:
                continue          # докстрінги з поясненнями для людини, що запускає, — не в кадрі
            for nazva, rx in (('заборонене', P.ZABORONENI), ('чутливе', P.CHUTLYVI), ('номер будинку', P.NOMER_BUDYNKU)):
                self.assertIsNone(rx.search(t), f'{nazva}: {t[:80]}')

    def test_pachka_i_kintsivka(self):
        self.assertIn("PACHKA = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6']", DZHERELO)
        for k in ('p1', 'p2', 'p3', 'p4', 'p5', 'p6'):
            self.assertRegex(DZHERELO, rf"def {k}\(stan, P, ix\)")
        self.assertEqual(DZHERELO.count("'styl': 'baner'"), 6)        # кожен ролик закінчується банером ≤ 1 с


if __name__ == '__main__':
    unittest.main()
