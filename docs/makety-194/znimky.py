# -*- coding: utf-8 -*-
"""ZAVDANNYA-194: знімки макетів. Комп'ютер (1366 px) — уся сторінка одним файлом; телефон (375 × 812, ×2) — кожен екран
окремим файлом `<сторінка>-telefon-01.png`, `-02.png`… (як гортає людина).

    python docs/makety-194/znimky.py [сторінка ...]
"""
import math
import sys
from pathlib import Path

from PIL import Image
from playwright.sync_api import sync_playwright

TUT = Path(__file__).resolve().parent
STORINKY = ['podilskyi', 'darnytskyi', 'st-m-zhytomyrska', 'vokzalna-ploshcha', 'kradizhky-podilskyi', 'dtp-darnytskyi',
            'narkotyky-kyiv']
VYS = 812

if __name__ == '__main__':
    tsili = sys.argv[1:] or STORINKY
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path='/opt/pw-browsers/chromium') if Path('/opt/pw-browsers/chromium').is_file() else pw.chromium.launch()
        pk = b.new_page(viewport={'width': 1366, 'height': 900})
        tel = b.new_page(viewport={'width': 375, 'height': VYS}, device_scale_factor=2)
        for s in tsili:
            url = (TUT / f'{s}.html').as_uri()
            for f in TUT.glob(f'{s}-telefon-*.png'):
                f.unlink()
            pk.goto(url); pk.wait_for_load_state('networkidle')
            pk.screenshot(path=str(TUT / f'{s}-pk.png'), full_page=True)
            tel.goto(url); tel.wait_for_load_state('networkidle')
            vsogo = tel.evaluate('document.documentElement.scrollHeight')
            n = math.ceil(vsogo / VYS)
            for i in range(n):
                y = min(i * VYS, vsogo - VYS)
                tel.screenshot(path=str(TUT / f'{s}-telefon-{i + 1:02d}.png'), full_page=True,
                               clip={'x': 0, 'y': y, 'width': 375, 'height': VYS})
            print(s, 'телефон:', vsogo, 'px,', n, 'екранів')
        b.close()
    # менше місця в git: 256 кольорів (текст і графіки не страждають)
    for s in tsili:
        for f in TUT.glob(f'{s}-*.png'):
            Image.open(f).convert('RGB').quantize(256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE).save(f, optimize=True)
