"""Правові тексти (ZAVDANNYA-103, ZAVDANNYA-130, MV-152): оферта, політика, «Хто ми», умови — межі, яких тримаємось.

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
        for slovo in ('Телеграм', 'застосунок', 'Стежу', 'сповіщень браузера чи телефона ми не надсилаємо', 'Уповноваженому',
                      'Геолокацію'):
            self.assertIn(slovo.lower(), t.lower(), slovo)

    def test_oferta_dani_i_onovlennia(self):
        t = tekst('oferta.html')
        for slovo in ('Судова практика', 'не перевірений факт', 'Оновлення', 'лише те, що дійшло до суду'):
            self.assertIn(slovo, t)

    def test_bez_zaboronenykh_sliv(self):
        for f in ('oferta.html', 'polityka.html', 'pro-nas.html', 'umovy.html'):
            t = tekst(f).replace('не оцінка безпеки', '').replace('не ставимо місцям оцінок', '').replace('за оцінку безпеки', '')
            self.assertIsNone(re.search(r'небезпечн|найгірш|рейтинг небезпеки', t, re.I), f)

    def test_avtora_ne_nazvano_nide(self):
        for f in ('oferta.html', 'polityka.html', 'pro-nas.html', 'umovy.html', 'zvernennya.html'):
            self.assertIsNone(re.search(r'поліц|Андрі|Микит|автор проєкту|власник проєкту', tekst(f), re.I), f)

    def test_umovy_bezkoshtovnoi_chastyny(self):
        t = tekst('umovy.html')
        for slovo in ('не оцінка безпеки', 'автоматично', 'переслідувати', 'не мають грошової вартості', '10 робочих днів',
                      '[ВЛАСНИК]', '[КОНТАКТ]', '[ДАТА]'):
            self.assertIn(slovo, t)

    def test_oferta_bez_obmezhennia_dlia_liudei(self):
        """MV-152, питання 9: обмеження відповідальності сумою — лише для підприємців і компаній, не для споживачів."""
        t = tekst('oferta.html')
        self.assertIn('Для людей, які купують для себе, такого обмеження немає.', t)
        for slovo in ('РНОКПП', '[ПЛАТІЖНИЙ СЕРВІС]', 'фіскальний чек', 'продовжується автоматично', 'один дотик',
                      'просите почати одразу'):
            self.assertIn(slovo, t)

    def test_polityka_kuky_i_stroky(self):
        t = tekst('polityka.html')
        for slovo in ('Кукі — лише два', '30 днів', '10 хвилин', '3 роки', 'пункт 44.3', 'стаття 29', 'відповідальна особа', '[ПЛАТІЖНИЙ СЕРВІС]'):
            self.assertIn(slovo, t)

    def test_umovy_u_zbyranni_i_vnyzu(self):
        import sys
        sys.path.insert(0, str(ZAHLUSHKA))
        import zibraty
        self.assertIn('umovy.html', zibraty.FAILY)
        self.assertIn('umovy.html', zibraty.STORINKY)
        for f in ('index.html', 'oferta.html', 'polityka.html', 'zvernennya.html', 'pro-nas.html', 'umovy.html'):
            pidval = (ZAHLUSHKA / f).read_text(encoding='utf-8').split('<footer', 1)[1]
            self.assertIn('href="umovy.html"', pidval, f)

    def test_vidpovidi_17_pytan(self):
        d = (ZAHLUSHKA.parents[1] / 'docs' / 'YURYST-CHERNETKY.md').read_text(encoding='utf-8')
        for n in range(1, 18):
            self.assertRegex(d, rf'\*\*{n}\. ', f'питання {n}')
        for mistse in ('[ВЛАСНИК]', '[КОД]', '[АДРЕСА]', '[КОНТАКТ]', '[САЙТ]', '[ДАТА]', '[НАЗВА ВЛАСНИКА ПРОЄКТУ]',
                       '[ПЛАТІЖНИЙ СЕРВІС]', '[СЕРВІС ПОШТИ]'):
            self.assertIn(mistse, d, 'місце є в списку для партнера')


if __name__ == '__main__':
    unittest.main()
