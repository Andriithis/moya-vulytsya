"""Перевірки набору для соцмереж (ZAVDANNYA-12): дані прикладів, правила перевірки,
тексти профілів, розміри готових картинок і пробне малювання в браузері.

Запуск: python -m unittest tests/test_brend.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'brend'))

import zrobyty  # noqa: E402

ROZMIRY_PNG = {
    'avatar/avatar-1024.png': (1024, 1024),
    'avatar/avatar-akcent-1024.png': (1024, 1024),
    'avatar/telegram-kanal-1024.png': (1024, 1024),
    'youtube/youtube-2560x1440.png': (2560, 1440),
    'facebook/facebook-1640x624.png': (1640, 624),
    'post-tsyfry/kadetskyi-hai.png': (1080, 1350),
    'post-istoriya/ryba-verbytskoho.png': (1080, 1350),
    'storis-vhadai/samokat-1-pytannya.png': (1080, 1920),
    'oblozhka-rolyka/vhadai.png': (1080, 1920),
}


class Perevirka(unittest.TestCase):
    def test_pryklady_bez_pomylok(self):
        for f in sorted(zrobyty.DANI.glob('*.json')):
            shablon, posty = zrobyty.zavantazhyty(f)
            for d in posty:
                self.assertEqual(zrobyty.perevirka(shablon, d), [], f'{f.name} / {d["nazva"]}')

    def test_zaboronene_slovo(self):
        p = zrobyty.perevirka('oblozhka-rolyka', {'zahalovok': 'Найнебезпечніша вулиця'})
        self.assertTrue(any('заборонене' in x for x in p))

    def test_rejtyng_i_emodzi(self):
        p = zrobyty.perevirka('oblozhka-rolyka', {'zahalovok': 'Рейтинг вулиць \U0001F525'})
        self.assertTrue(any('заборонене' in x for x in p))
        self.assertTrue(any('емодзі' in x for x in p))

    def test_nomer_budynku(self):
        d = {'tekst': 'т', 'mistse': 'вул. Антоновича, 176', 'rishennya_nomer': '1'}
        self.assertTrue(any('номера будинку' in x for x in zrobyty.perevirka('post-istoriya', d)))

    def test_bez_rishennya(self):
        d = {'tekst': 'т', 'mistse': 'вул. Антоновича'}
        self.assertTrue(any('rishennya_nomer' in x for x in zrobyty.perevirka('post-istoriya', d)))

    def test_chutlyva_katehoriya(self):
        d = {'tekst': 'Домашнє насильство', 'mistse': 'вул. Антоновича', 'rishennya_nomer': '1'}
        self.assertTrue(any('MV-4' in x for x in zrobyty.perevirka('post-istoriya', d)))

    def test_dovzhyna(self):
        d = {'tekst': 'а' * 300, 'mistse': 'вул. А', 'rishennya_nomer': '1'}
        self.assertTrue(any('знаків' in x for x in zrobyty.perevirka('post-istoriya', d)))

    def test_vidpovid_storis(self):
        d = {'tekst': 'т', 'vidpovid': {'mistse': 'вул. Богомольця, 7'}}
        p = zrobyty.perevirka('storis-vhadai', d)
        self.assertTrue(any('rishennya_nomer' in x for x in p))
        self.assertTrue(any('номера будинку' in x for x in p))


class NomerBudynkuMV60(unittest.TestCase):
    """MV-60: у пості номер будинку — лише для публічного місця; прибирає код, а не людина."""

    def test_istoriya_zhytlo_bez_nomera(self):
        d = zrobyty.pidhotuvaty('post-istoriya', {'tekst': 'т', 'mistse': 'вул. Антоновича, 176', 'rishennya_nomer': '1'})
        self.assertEqual(d['mistse'], 'вул. Антоновича')
        self.assertEqual(zrobyty.perevirka('post-istoriya', d), [])

    def test_istoriya_mahazyn_z_nomerom(self):
        d = zrobyty.pidhotuvaty('post-istoriya', {'tekst': 'У магазині взяли худі', 'mistse': 'вул. Антоновича, 176',
                                                  'typ_mistsia': 'mahazyn', 'rishennya_nomer': '1'})
        self.assertEqual(d['mistse'], 'вул. Антоновича, 176')
        self.assertEqual(zrobyty.perevirka('post-istoriya', d), [])

    def test_storis_vidpovid(self):
        d = zrobyty.pidhotuvaty('storis-vhadai', {'tekst': 'т', 'vidpovid': {'mistse': 'вул. Богомольця, 7',
                                                                            'rishennya_nomer': '1'}})
        self.assertEqual(d['vidpovid']['mistse'], 'вул. Богомольця')

    def test_nevidomyi_typ(self):
        d = {'tekst': 'т', 'mistse': 'вул. А', 'typ_mistsia': 'kvartyra', 'rishennya_nomer': '1'}
        self.assertTrue(any('typ_mistsia' in x for x in zrobyty.perevirka('post-istoriya', d)))

    def test_lyshe_te_shcho_diishlo_do_sudu(self):
        for f in ('post-istoriya', 'storis-vhadai', 'post-tsyfry'):
            html = (KORIN / 'brend' / 'shablony' / f'{f}.html').read_text(encoding='utf-8')
            self.assertIn('Лише те, що дійшло до суду', html, f)
        for f in ('post-istoriya', 'storis-vhadai'):
            self.assertIn('рішення суду № ', (KORIN / 'brend' / 'shablony' / f'{f}.html').read_text(encoding='utf-8'), f)


class TekstyProfiliv(unittest.TestCase):
    def test_dovzhyna_i_slova(self):
        md = (KORIN / 'brend' / 'teksty-profiliv.md').read_text(encoding='utf-8')
        rozdily = re.split(r'^## ', md, flags=re.M)
        znaideno = 0
        for r in rozdily:
            mezha = 80 if r.startswith('Коротко') else 150 if r.startswith('Довше') else None
            for t in re.findall(r'^> (.+)$', r, flags=re.M):
                znaideno += 1
                if mezha:
                    self.assertLessEqual(len(t), mezha, t)
                self.assertEqual(zrobyty.perevirka('oblozhka-rolyka', {'zahalovok': 'х', 'pidzahalovok': t[:90]}), [], t)
        self.assertGreaterEqual(znaideno, 6)


class HotoviKartynky(unittest.TestCase):
    def test_rozmiry(self):
        from PIL import Image
        for shlyakh, rozmir in ROZMIRY_PNG.items():
            f = zrobyty.HOTOVI / shlyakh
            self.assertTrue(f.exists(), f'немає {shlyakh} — запустіть python brend/zrobyty.py --vse')
            with Image.open(f) as img:
                self.assertEqual(img.size, rozmir, shlyakh)


def brauzer_ye() -> bool:
    try:
        import playwright  # noqa: F401
    except ImportError:
        return False
    return zrobyty.znayty_chrome() is not None


@unittest.skipUnless(brauzer_ye(), 'немає Playwright або Chrome — пробне малювання пропущено')
class Malyuvannya(unittest.TestCase):
    def test_pryklady_malyuyutsya_bez_vylaziv(self):
        with tempfile.TemporaryDirectory() as t, zrobyty.Malyar() as m:
            for f in sorted(zrobyty.DANI.glob('*.json')):
                shablon, posty = zrobyty.zavantazhyty(f)
                for d in posty[:1]:
                    kudy = Path(t) / f'{d["nazva"]}.png'
                    self.assertEqual(m.namalyuvaty(shablon, d, kudy), [], f'{f.name} / {d["nazva"]}')
                    self.assertTrue(kudy.exists())

    def test_zadovgyi_tekst_vylazyt(self):
        """Перевірка після малювання справді ловить текст, що не вміщується."""
        d = {'nazva': 'x', 'tekst': 'дуже довгий текст ' * 40, 'mistse': 'вул. А', 'rishennya_nomer': '1'}
        with tempfile.TemporaryDirectory() as t, zrobyty.Malyar() as m:
            self.assertNotEqual(m.namalyuvaty('post-istoriya', d, Path(t) / 'x.png'), [])


if __name__ == '__main__':
    unittest.main()
