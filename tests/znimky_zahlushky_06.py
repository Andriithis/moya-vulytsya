"""Знімки екрана для ZAVDANNYA-06, 1280 px і 390 px — так само, як znimky_zahlushky.py.

Запуск: python tests/znimky_zahlushky_06.py [тека-для-знімків]
За замовчуванням знімки йдуть у tmp/znimky/zavdannya-06/.
Сховище — локальна підміна (tests/zahlushka_pidmina.py), нічого не надсилається назовні.

Знімки: оферта; звернення порожнє, з підказкою про помилку, після відправки і без мережі;
головна (щоб порівняти з затвердженою — вигляд не мав змінитися).
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


def zapovnyty(s):
    s.fill('#posylannya', 'Рішення № 1')
    s.check('input[value="mistse"]')
    s.fill('#poyasnennya', 'Подія сталася на сусідній вулиці.')
    s.fill('#kontakt', '@test_nik')
    s.check('#zghoda')


def main() -> int:
    from playwright.sync_api import sync_playwright
    if not CHROME:
        print('Немає Chrome / Chromium — знімків не буде.')
        return 1
    teka = Path(sys.argv[1]) if len(sys.argv) > 1 else KORIN / 'tmp' / 'znimky' / 'zavdannya-06'
    teka.mkdir(parents=True, exist_ok=True)
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

                def vidkryty(storinka):
                    s.goto(f'{url}/zahlushka/{storinka}?dzherelo=znimok')
                    s.evaluate('document.fonts.ready')
                    s.wait_for_timeout(300)

                for nazva, storinka in (('holovna', 'index.html'), ('oferta', 'oferta.html'),
                                        ('zvernennya', 'zvernennya.html')):
                    vidkryty(storinka)
                    s.screenshot(path=str(teka / f'{nazva}-{shyryna}.png'), full_page=True)
                # Звернення: підказка про помилку (без згоди).
                vidkryty('zvernennya.html')
                zapovnyty(s)
                s.uncheck('#zghoda')
                s.click('#zvernennya-knopka')
                s.screenshot(path=str(teka / f'zvernennya-bez-zghody-{shyryna}.png'), full_page=True)
                # Звернення після відправки.
                vidkryty('zvernennya.html')
                zapovnyty(s)
                s.click('#zvernennya-knopka')
                s.wait_for_selector('#vdacha', state='visible')
                s.screenshot(path=str(teka / f'zvernennya-vidpravleno-{shyryna}.png'), full_page=True)
                # Звернення без мережі (сторінка — з кешу браузера).
                s.evaluate('navigator.serviceWorker.ready.then(() => true)')
                s.reload()
                k.set_offline(True)
                vidkryty('zvernennya.html')
                zapovnyty(s)
                s.click('#zvernennya-knopka')
                s.wait_for_selector('#zboi', state='visible')
                s.screenshot(path=str(teka / f'zvernennya-bez-merezhi-{shyryna}.png'), full_page=True)
                k.set_offline(False)
                k.close()
            b.close()
    finally:
        server.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    for p in sorted(teka.glob('*.png')):
        print(p.relative_to(KORIN))
    return 0


if __name__ == '__main__':
    sys.exit(main())
