"""Знімки макета М4 (ZAVDANNYA-28): три варіанти × ПК і телефон × місто, Поділ, квартали, картка, теми.

Запуск (сервер макета вже працює на 8740): python maket/m4/znimky_m4.py
Знімки — у tmp/znimky/m4/ (у git не йдуть). Браузер — Edge без вікна, WebGL програмний (swiftshader).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

KORIN = Path(__file__).resolve().parents[2]
TEKA = KORIN / 'tmp' / 'znimky' / 'm4'
ADRESA = 'http://127.0.0.1:8740/m4/'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
ARGUMENTY = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
EKRANY = {'pk': (1440, 900), 'telefon': (390, 844)}
# Камери: зум/широта/довгота/кут/нахил — у форматі хеша MapLibre.
KAMERY = {
    'podil': {'pk': '#13.2/50.4655/30.5155/0/{p}', 'telefon': '#12.9/50.4655/30.5155/0/{p}'},
    'kvartaly': {'pk': '#14.6/50.4500/30.5230/0/{p}', 'telefon': '#14.6/50.4500/30.5230/0/{p}'},
}
VARIANTY = {'a': ['svitla', 'temna'], 'b': ['svitla', 'temna'], 'v': ['temna', 'svitla']}


def chekaty(s, sek=1.5):
    s.wait_for_function('window.MAKET && MAKET.map && MAKET.map.loaded() && MAKET.stan.vyrosly', timeout=60000)
    s.wait_for_timeout(int(sek * 1000))


def main(tilky: str | None = None) -> None:
    TEKA.mkdir(parents=True, exist_ok=True)
    zvit = {}
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
        for v, temy in VARIANTY.items():
            if tilky and v != tilky:
                continue
            for ekran, (w, h) in EKRANY.items():
                kont = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1,
                                     reduced_motion='reduce', is_mobile=ekran == 'telefon', has_touch=ekran == 'telefon')
                s = kont.new_page()
                for tema in temy:
                    pref = f'{v}-{ekran}-{tema}'
                    s.goto(f'{ADRESA}?v={v}&tema={tema}')
                    chekaty(s)
                    s.screenshot(path=str(TEKA / f'{pref}-misto.png'))
                    p = 50 if v != 'a' else 0
                    for nazva, kam in KAMERY.items():
                        s.goto(f'{ADRESA}?v={v}&tema={tema}' + kam[ekran].format(p=p))
                        chekaty(s)
                        s.screenshot(path=str(TEKA / f'{pref}-{nazva}.png'))
                    # Картка: клік у центр екрана на Подолі (у 3D — по стовпчику під пальцем).
                    s.goto(f'{ADRESA}?v={v}&tema={tema}' + KAMERY['podil'][ekran].format(p=p))
                    chekaty(s)
                    s.mouse.click(w / 2, h / 2 + (0 if ekran == 'pk' else -80))
                    s.wait_for_timeout(1200)
                    s.screenshot(path=str(TEKA / f'{pref}-kartka.png'))
                    zvit[pref] = s.evaluate('({pomylky:MAKET.stan.pomylky, kartka:!document.getElementById("kartka").hidden})')
                # Шрифти: картка в кожному з трьох шрифтів (лише перша тема варіанта).
                for f in '123':
                    s.goto(f'{ADRESA}?v={v}&f={f}&tema={temy[0]}' + KAMERY['podil'][ekran].format(p=50 if v != 'a' else 0))
                    chekaty(s)
                    s.mouse.click(w / 2, h / 2 + (0 if ekran == 'pk' else -80))
                    s.wait_for_timeout(1200)
                    s.screenshot(path=str(TEKA / f'{v}-{ekran}-shryft{f}-kartka.png'))
                kont.close()
        b.close()
    print(json.dumps(zvit, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
