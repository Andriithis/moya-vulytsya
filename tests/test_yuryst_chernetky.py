"""Чернетки для юриста (ZAVDANNYA-103): оферта, політика, «Хто ми» — межі, яких тримаємось.

Запуск: python -m unittest tests/test_yuryst_chernetky.py
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ZAHLUSHKA = Path(__file__).resolve().parents[1] / 'site' / 'zahlushka'


def tekst(nazva: str) -> str:
    t = (ZAHLUSHKA / nazva).read_text(encoding='utf-8')
    t = re.sub(r'<!--.*?-->', '', t, flags=re.S)
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', t))


class Chernetky(unittest.TestCase):
    def test_pro_nas_lyshe_partner_i_proiekt(self):
        t = tekst('pro-nas.html')
        for mistse in ('[ВЛАСНИК]', '[КОД]', '[АДРЕСА]', '[КОНТАКТ]'):
            self.assertIn(mistse, t)
        self.assertIsNone(re.search(r'поліц|Андрі|автор проєкту|власник проєкту', t, re.I), 'на «Хто ми» — лише партнер і проєкт')
        for l in ('ODbL', 'CC BY', 'Єдиний державний реєстр судових рішень', '10 робочих днів'):
            self.assertIn(l, t)

    def test_polityka_vsia_posluha(self):
        t = tekst('polityka.html')
        for slovo in ('Телеграм', 'застосунок', 'Стежу', 'Сповіщення', 'Уповноваженому', 'Геолокацію'):
            self.assertIn(slovo.lower(), t.lower(), slovo)

    def test_oferta_dani_i_onovlennia(self):
        t = tekst('oferta.html')
        for slovo in ('Судова практика', 'не перевірений факт', 'Оновлення', 'лише те, що дійшло до суду'):
            self.assertIn(slovo, t)
        self.assertNotIn('Google Play', t, 'у застосунку на старті не продаємо (docs/ANDROID.md)')

    def test_bez_zaboronenykh_sliv(self):
        for f in ('oferta.html', 'polityka.html', 'pro-nas.html'):
            t = tekst(f).replace('не оцінка безпеки', '').replace('не ставимо місцям оцінок', '')
            self.assertIsNone(re.search(r'небезпечн|найгірш|рейтинг небезпеки', t, re.I), f)


if __name__ == '__main__':
    unittest.main()
