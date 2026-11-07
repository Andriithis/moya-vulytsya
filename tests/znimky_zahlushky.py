"""Знімки екрана заглушки 1280 px і 390 px (ZAVDANNYA-02, п. 11).

Запуск: python tests/znimky_zahlushky.py [тека-для-знімків]
За замовчуванням знімки йдуть у docs/znimky/zavdannya-02/.
Потрібні Playwright (pip install playwright) і Chrome / Chromium.
Сховище — локальна підміна (tests/zahlushka_pidmina.py), нічого не надсилається назовні.
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import zibraty  # noqa: E402
import zahlushka_pidmina  # noqa: E402
from test_zahlushka import CHROME  # noqa: E402


def main() -> int:
    from playwright.sync_api import sync_playwright
    if not CHROME:
        print('Немає Chrome / Chromium — знімків не буде.')
        return 1
    teka_znimkiv = Path(sys.argv[1]) if len(sys.argv) > 1 else KORIN / 'docs' / 'znimky' / 'zavdannya-02'
    teka_znimkiv.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    server, skh, url = zahlushka_pidmina.zapustyty(str(tmp))
    zibraty.zibraty(tmp / 'zahlushka', url, zahlushka_pidmina.PUBLICHNYI, {}, False)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])
            for shyryna in (1280, 390):
                k = b.new_context(viewport={'width': shyryna, 'height': 900 if shyryna > 600 else 844},
                                  device_scale_factor=1)
                s = k.new_page()
                for nazva, storinka in (('holovna', 'index.html'), ('polityka', 'polityka.html'),
                                        ('zrazok', 'zrazok.html')):
                    s.goto(f'{url}/zahlushka/{storinka}?dzherelo=znimok')
                    s.evaluate('document.fonts.ready')
                    s.wait_for_timeout(300)
                    s.screenshot(path=str(teka_znimkiv / f'{nazva}-{shyryna}.png'), full_page=True)
                # Форма після відправки.
                s.goto(f'{url}/zahlushka/index.html?dzherelo=znimok')
                s.evaluate('document.fonts.ready')
                s.fill('#kontakt', '@test_nik')
                s.check('#zghoda')
                s.click('#forma-knopka')
                s.wait_for_selector('#vdacha', state='visible')
                s.locator('#peredzamovlennya').screenshot(path=str(teka_znimkiv / f'forma-vidpravleno-{shyryna}.png'))
                # Помилка мережі.
                skh.zbii = True
                s.goto(f'{url}/zahlushka/index.html?dzherelo=znimok')
                s.fill('#kontakt', '@test_nik')
                s.check('#zghoda')
                s.click('#forma-knopka')
                s.wait_for_selector('#zboi', state='visible')
                s.locator('#peredzamovlennya').screenshot(path=str(teka_znimkiv / f'forma-pomylka-{shyryna}.png'))
                skh.zbii = False
                k.close()
            b.close()
    finally:
        server.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    for p in sorted(teka_znimkiv.glob('*.png')):
        print(p.relative_to(KORIN))
    return 0


if __name__ == '__main__':
    sys.exit(main())
