"""Гасла скрізь однакові (ZAVDANNYA-93, MV-52, MV-106, MV-107).

Старих гасел «Що суди розповіли про вашу вулицю» і «Карта подій за даними судів» немає в жодному живому файлі продукту;
нові — на головній, у заглушці, маніфесті, профілях мереж, обкладинках, на сторінках будинків і вітрині «Мій будинок».
Історичні документи (журнал рішень, звірки, завдання, звіти) можуть цитувати старі гасла — їх не перевіряємо.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))

STARI = ('що суди розповіли про вашу вулицю', 'карта подій за даними судів', 'що відбувається на вашій вулиці')
TEKY = ('site', 'brend', 'video', 'bot', 'avtopostynh', 'android', 'zvit_adresy')
ROZSHYRENNIA = {'.py', '.html', '.js', '.css', '.json', '.md', '.webmanifest', '.txt', '.xml', '.kt', '.yml', '.sql'}


class TestHasla(unittest.TestCase):
    def test_starykh_hasel_nemaye(self):
        znaideno = []
        for teka in TEKY:
            for f in (KORIN / teka).rglob('*'):
                if f.is_file() and f.suffix in ROZSHYRENNIA:
                    t = f.read_text(encoding='utf-8', errors='ignore').lower()
                    znaideno += [f'{f.relative_to(KORIN)}: «{s}»' for s in STARI if s in t]
        self.assertEqual(znaideno, [])

    def test_novi_hasla_na_mistsi(self):
        zahl = (KORIN / 'site/zahlushka/index.html').read_text(encoding='utf-8')
        self.assertIn('<h1>Що відбувається під боком</h1>', zahl)
        self.assertIn('Що болить вашому будинку', zahl)
        man = json.loads((KORIN / 'site/zahlushka/manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertTrue(man['description'].startswith('Що відбувається під боком'))
        self.assertIn('Що відбувається під боком', (KORIN / 'site/zibraty_sait.py').read_text(encoding='utf-8'))
        prof = (KORIN / 'brend/teksty-profiliv.md').read_text(encoding='utf-8')
        self.assertIn('> Моя вулиця — що відбувається під боком', prof)
        for f in ('facebook', 'youtube'):
            d = json.loads((KORIN / f'brend/dani/{f}.json').read_text(encoding='utf-8'))
            self.assertTrue(all(p['gaslo'] == 'Що відбувається під боком.' for p in d['posty']))

    def test_vitryny_i_budynok(self):
        import storinky_mv100 as M
        self.assertEqual(M.HASLO_BUDYNKU, 'Що болить вашому будинку')
        self.assertEqual(M.OPYS_BUDYNKU, 'Скарги мешканців і події з рішень судів — по кожному будинку')
        h = M.vitryna_miy_budynok('https://pryklad.ua', [])
        self.assertIn('<h1>Що болить вашому будинку</h1>', h)
        self.assertIn(M.OPYS_BUDYNKU, h)
        self.assertIn(M.MESEDZH['miy-budynok'], h)
        self.assertIn(M.MESEDZH['osbb'], M.vitryna_osbb('https://pryklad.ua'))
        self.assertIn(M.MESEDZH['sudova-praktyka'], M.vitryna_sudova('https://pryklad.ua'))
        self.assertIn(M.MESEDZH['biznes'], M.vitryna_biznes('https://pryklad.ua'))
        # сторінка будинку: гасло лінії з описом дрібно над блоком довідки
        src = (KORIN / 'site/storinky_mv100.py').read_text(encoding='utf-8')
        self.assertIn('<section class="rozdil">{haslo_budynku()}<h2>Довідка про будинок</h2>', src)


if __name__ == '__main__':
    unittest.main()
