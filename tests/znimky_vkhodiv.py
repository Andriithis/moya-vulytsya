"""Знімки сторінок-входів (ZAVDANNYA-153): три варіанти першого екрана орендаря й шість входів — телефон 390 px
і комп'ютер 1280 px, перший екран без прокрутки.

Запуск: MV_CHROME=/шлях/до/chrome python tests/znimky_vkhodiv.py [тека]   (за замовчуванням — docs/znimky-153)
Сайт збирається зі штучної бази tests/test_sait.py (числа в уривку — штучні; на справжньому випуску — справжні).
"""
from __future__ import annotations

import functools
import http.server
import re
import sys
import tempfile
import threading
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'tests'))
import test_vkhody as TV  # noqa: E402
import test_sait as TS  # noqa: E402


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    import storinky_vkhodiv as V
    teka = Path(argv[0]) if argv else KORIN / 'docs' / 'znimky-153'
    teka.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        sait = TV.zibraty(Path(tmp))
        # варіанти екрана орендаря — тією самою функцією, з тим самим уривком, що на зібраній сторінці (варіант «b»)
        t = (sait / 'dlia' / 'orendaria' / 'index.html').read_text(encoding='utf-8')
        ur = re.search(r'<div class="vkhid-ekran__prava">(.*?)</div></section>', t, re.S).group(1)
        for v in V.VARIANTY_ORENDARIA:
            (sait / 'dlia' / f'orendaria-{v}').mkdir(parents=True, exist_ok=True)
            (sait / 'dlia' / f'orendaria-{v}' / 'index.html').write_text(
                V.storinka_vkhodu('orendaria', 'https://moya-vulytsya.pages.dev', ur, variant=v), encoding='utf-8')
        http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(
            http.server.SimpleHTTPRequestHandler, directory=str(sait)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        url = f'http://127.0.0.1:{server.server_address[1]}'
        storinky = [(f'orendar-variant-{v}', f'/dlia/orendaria-{v}/') for v in V.VARIANTY_ORENDARIA]
        storinky += [(f'vkhid-{s}', f'/dlia/{s}/') for s in V.VKHODY if s != 'orendaria']
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=TS.BRAUZER, args=['--no-sandbox'])
            for nazva, shl in storinky:
                for prystrii, vp, mob in (('telefon', (390, 844), True), ('komp', (1280, 800), False)):
                    k = b.new_context(viewport={'width': vp[0], 'height': vp[1]}, device_scale_factor=2,
                                      is_mobile=mob, has_touch=mob)
                    s = k.new_page()
                    s.goto(url + shl)
                    s.wait_for_load_state('networkidle')
                    f = teka / f'{nazva}-{prystrii}.jpg'
                    s.screenshot(path=str(f), type='jpeg', quality=78)
                    print(f)
                    k.close()
            b.close()
        server.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
