"""Один вигляд скрізь (MV-58, ZAVDANNYA-47): бренд, ролики, заглушка й гра — у «Індиго й м'яті»,
IBM Plex Sans і з кнопками-клавішами, як сайт (docs/STYL.md).

Перевіряє: немає старих шрифтів (Manrope, Inter, Fixel) і старих кольорів (бірюза, бежеве тло, помаранчевий);
змінні CSS збігаються з тими, що збирач сайту рахує з site/sait/kolory.json; шрифти Plex і ліцензія на місці;
клавіші мають межу mezha і бортик.

Запуск: python -m unittest tests/test_vyhliad_mv58.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))

import zibraty_sait  # noqa: E402

# Усі видимі людям файли поза сайтом-картою.
FAILY = [
    *sorted((KORIN / 'brend' / 'shablony').glob('*')),
    KORIN / 'brend' / 'zrobyty.py',
    KORIN / 'video' / 'stsena.css', KORIN / 'video' / 'stsena.js', KORIN / 'video' / 'stsena.html',
    *[p for p in sorted((KORIN / 'site' / 'zahlushka').glob('*')) if p.suffix in ('.css', '.html', '.js', '.webmanifest')],
    *[p for p in sorted((KORIN / 'site' / 'hra').glob('*')) if p.suffix in ('.css', '.html', '.js')],
]
STARI_SHRYFTY = re.compile(r'\b(Manrope|Inter|Fixel)\b')
# Бірюза, бежеве тло, старі сірі, помаранчевий attention і стара темна тема гри.
STARI_KOLORY = {'0B6B6B', '064848', 'D7EBEA', 'F1F7F6', 'E3F0EF', '9CCBC7', '4FA39D', 'F7F6F2', 'E3E1DA', 'C9C6BD',
                '1B1F24', '3D434C', '5B616B', 'B45309', 'FBEBDD', 'F0A257', '5CB8AF', '111517', '1A2023'}
# Спільні змінні: у цих файлах вони мусять мати рівно ті значення, що й на сайті.
SPILNI = ['ground', 'surface', 'surface-tint', 'ink', 'ink-2', 'muted', 'line', 'line-strong', 'mezha', 'bort',
          'accent', 'accent-strong', 'accent-soft', 'on-accent', 'vyd', 'pk-1', 'pk-2',
          'data-1', 'data-2', 'data-3', 'data-4', 'data-5']


def zminni_saitu(tema: str) -> dict:
    ryadok = zibraty_sait.kolory_css().split('\n')[1 if tema == 'svitla' else 2]
    return dict(re.findall(r'--([\w-]+):(#[0-9A-F]{6})', ryadok))


def zminni_bloku(css: str, pochatok: str) -> dict:
    i = css.index(pochatok)
    blok = css[i:css.index('}', i)]
    return {k: v.upper() for k, v in re.findall(r'--([\w-]+):\s*(#[0-9A-Fa-f]{6})', blok)}


class StaryiVyhliad(unittest.TestCase):
    def test_nemaie_starykh_shryftiv(self):
        for f in FAILY:
            t = f.read_text(encoding='utf-8')
            self.assertIsNone(STARI_SHRYFTY.search(t), f'{f.relative_to(KORIN)}: старий шрифт')

    def test_nemaie_starykh_koloriv(self):
        for f in FAILY:
            t = f.read_text(encoding='utf-8')
            stari = {h.upper() for h in re.findall(r'#([0-9A-Fa-f]{6})\b', t)} & STARI_KOLORY
            self.assertEqual(stari, set(), f'{f.relative_to(KORIN)}: старі кольори')

    def test_ikonky_novi(self):
        from PIL import Image
        with Image.open(KORIN / 'site' / 'zahlushka' / 'ikony' / 'ikona-maskable-512.png') as im:
            self.assertEqual(im.convert('RGB').getpixel((4, 4)), (0xF4, 0xF5, 0xFB))
            self.assertEqual(im.convert('RGB').getpixel((256, 120)), (0x44, 0x47, 0xA6))


class ZminniYakNaSaiti(unittest.TestCase):
    def pereviryty(self, f: Path, pochatok: str, tema: str):
        css = f.read_text(encoding='utf-8')
        u_faili, sait = zminni_bloku(css, pochatok), zminni_saitu(tema)
        for n in SPILNI:
            self.assertIn(n, u_faili, f'{f.name} ({tema}): немає --{n}')
            self.assertEqual(u_faili[n], sait[n], f'{f.name} ({tema}): --{n}')

    def test_brend(self):
        self.pereviryty(KORIN / 'brend' / 'shablony' / 'brend.css', ':root {', 'svitla')

    def test_video(self):
        self.pereviryty(KORIN / 'video' / 'stsena.css', ':root {', 'svitla')

    def test_hra_obydvi_temy(self):
        f = KORIN / 'site' / 'hra' / 'hra.css'
        self.pereviryty(f, ':root {', 'svitla')
        self.pereviryty(f, '@media (prefers-color-scheme: dark) {', 'temna')

    def test_kartynka_hry(self):
        """Картинка «Поділитися» малюється на полотні — кольори в hra-kartka.js теж мають бути з сайту."""
        t = (KORIN / 'site' / 'hra' / 'hra-kartka.js').read_text(encoding='utf-8')
        s = zminni_saitu('svitla')
        for n, imia in (('ground', 'ground'), ('ink', 'ink'), ('accent', 'accent'), ('accentSoft', 'accent-soft')):
            self.assertRegex(t, rf"\b{n}: '{s[imia]}'")

    def test_zahlushka(self):
        css = (KORIN / 'site' / 'zahlushka' / 'styli.css').read_text(encoding='utf-8')
        s = zminni_saitu('svitla')
        for n in ('ground', 'ink', 'accent', 'accent-strong', 'mezha', 'bort'):
            self.assertIn(s[n], css, f'styli.css: немає кольору {n}')


class ShryftyIKlavishi(unittest.TestCase):
    def test_shryfty_plex_na_mistsi(self):
        for f in (KORIN / 'brend' / 'shablony' / 'brend.css', KORIN / 'video' / 'stsena.css',
                  KORIN / 'site' / 'zahlushka' / 'styli.css'):
            css = f.read_text(encoding='utf-8')
            shliakhy = re.findall(r'url\(([^)]+\.woff2)\)', css)
            self.assertTrue(shliakhy, f.name)
            for s in shliakhy:
                self.assertIn('ibm-plex-sans', s)
                self.assertTrue((f.parent / s).resolve().is_file(), f'{f.name}: {s}')
        for teka in ('brend/shryfty', 'site/zahlushka/shryfty', 'site/sait/shryfty'):
            self.assertTrue((KORIN / teka / 'OFL-IBM-Plex-Sans.txt').is_file(), teka)
        hra = (KORIN / 'site' / 'hra' / 'hra.css').read_text(encoding='utf-8')
        self.assertIn('url(../shryfty/ibm-plex-sans-cyrillic-400-normal.woff2)', hra)

    def test_klavishi(self):
        bort = re.compile(r'box-shadow:\s*0 3px 0 (var\(--bort\)|#585B69)')
        for f, klasy in ((KORIN / 'site' / 'hra' / 'hra.css', ['.knopka {', '.rezhym {']),
                         (KORIN / 'site' / 'zahlushka' / 'styli.css', ['.poshuk__knopka, .knopka-povna'])):
            css = f.read_text(encoding='utf-8')
            for k in klasy:
                blok = css[css.index(k):css.index('}', css.index(k))]
                self.assertRegex(blok, r'border:\s*1\.5px solid (var\(--mezha\)|#76798C)', f'{f.name} {k}')
                self.assertRegex(blok, bort, f'{f.name} {k}')
        self.assertIn('box-shadow: 0 3px 0 var(--bort)', (KORIN / 'brend' / 'shablony' / 'brend.css').read_text(encoding='utf-8'))
        self.assertIn('box-shadow: 0 6px 0 var(--bort)', (KORIN / 'video' / 'stsena.css').read_text(encoding='utf-8'))


if __name__ == '__main__':
    unittest.main()
