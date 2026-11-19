"""Знімки «Судової практики» (ZAVDANNYA-135): ПК 1280 і телефон 390.

  python tests/znimky_sudova_praktyka.py <sudova-praktyka.json> <тека довідок a/b/c> [тека знімків]

Збирає розділ «Судова практика» (лише його й спільні файли сайту) у тимчасову теку, кладе таблиці юриста в «сховище» на
диску (site/prodazh/praktyka_r2.py --do-teky) і запускає справжній сервер продажу місцево (site/worker/testy/sp_proba.mjs,
тестова оплата). Довідки — готові файли генератора dani-edrsr/src/sp_dovidka.py (a.html, b.html, c.html).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'prodazh'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

STORINKY = [
    ('1-pokazhchyk-poshuk', '/sudova-praktyka/?q=п%27яний%20за%20кермом'),
    ('2-stattia-130', '/sudova-praktyka/kupap/130/'),
    ('3-zamovlennia', '/oplata/?tovar=spdovidka&stattia=kupap-130&sud=Голосіївський&chastyna=1'),
    ('7-yurist', '/__yurist'),
]


def main(argv: list[str]) -> int:
    import storinky_sp as SP
    import zibraty_sait as Z
    import praktyka_r2
    from playwright.sync_api import sync_playwright
    dzherelo, dovidky = Path(argv[0]), Path(argv[1])
    teka = Path(argv[2]) if len(argv) > 2 else KORIN / 'docs' / 'znimky-sudova-praktyka-135'
    teka.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as t:
        sait, r2 = Path(t) / 'sait', Path(t) / 'r2'
        Z.kopiyuvaty_spilne(sait)
        SP.zibraty(dzherelo, sait, 'https://pryklad.ua')
        praktyka_r2.main([str(dzherelo), '--do-teky', str(r2)])
        for v in ('a', 'b', 'c'):
            shutil.copy(dovidky / f'{v}.html', sait / f'dovidka-{v}.html')
        port = 8798
        srv = subprocess.Popen(['node', str(KORIN / 'site' / 'worker' / 'testy' / 'sp_proba.mjs'), str(port), str(sait), str(r2)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            srv.stdout.readline()
            url = f'http://127.0.0.1:{port}'
            storinky = STORINKY + [(f'{4 + i}-dovidka-{v}', f'/dovidka-{v}.html') for i, v in enumerate('abc')]
            with sync_playwright() as p:
                from test_zahlushka import CHROME
                b = p.chromium.launch(executable_path=CHROME or '/opt/pw-browsers/chromium', args=['--no-sandbox'])
                for nazva_ekranu, shyr, vys in (('pk', 1280, 900), ('telefon', 390, 844)):
                    k = b.new_context(viewport={'width': shyr, 'height': vys}, device_scale_factor=2)
                    s = k.new_page()
                    for nazva, shl in storinky:
                        s.goto(url + shl, wait_until='networkidle')
                        s.wait_for_timeout(300)
                        s.screenshot(path=str(teka / f'{nazva}-{nazva_ekranu}.png'), full_page=True)
                        print(nazva, nazva_ekranu, s.title())
                    k.close()
                b.close()
        finally:
            srv.terminate()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
