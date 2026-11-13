"""Знімки «до/після» етапу В (ZAVDANNYA-42): виділена сота в темній, кнопка 2D/3D, назва району на телефоні,
підказка в полі пошуку, світлі пласкі соти біля Контрактової площі проти парків.

Запуск: python maket/m7/znimky_v.py <do|pislya> <адреса сторінки m7/>
Знімки — tmp/znimky/m7/v-<do|pislya>-<що>.png
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import znimky_m7 as Z  # noqa: E402

KOLY, ADRESA = sys.argv[1], sys.argv[2]
POD = {'pk': '#13.2/50.4655/30.5155/0/40', 'telefon': '#12.9/50.4655/30.5155/0/40'}
KONTRAKTOVA = '#15.3/50.4655/30.5170/0/40'


def znimok(s, nazva):
    s.screenshot(path=str(Z.TEKA / f'v-{KOLY}-{nazva}.png'))


with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=Z.EDGE, args=Z.ARGUMENTY)
    for ekran, (w, h) in Z.EKRANY.items():
        k = Z.novyi(b, ekran)
        s = k.new_page()
        for tema in ('svitla', 'temna'):
            Z.ity(s, f'{ADRESA}?napr=nich&vyd=v&tema={tema}' + POD[ekran])
            Z.chekaty(s)
            if ekran == 'pk':
                s.screenshot(path=str(Z.TEKA / f'v-{KOLY}-pk-{tema}-knopky.png'), clip={'x': 0, 'y': 0, 'width': 560, 'height': 140})
            else:
                s.screenshot(path=str(Z.TEKA / f'v-{KOLY}-telefon-{tema}-poshuk.png'), clip={'x': 0, 'y': 50, 'width': w, 'height': 80})
            Z.kartka(s, w, h, ekran)
            s.wait_for_timeout(700)
            znimok(s, f'{ekran}-{tema}-vydilennya')
            Z.ity(s, f'{ADRESA}?napr=nich&tema={tema}' + KONTRAKTOVA)
            Z.chekaty(s)
            znimok(s, f'{ekran}-{tema}-kontraktova')
        k.close()
    b.close()
print('ok')
