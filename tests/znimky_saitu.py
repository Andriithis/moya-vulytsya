"""Знімки сайту (ZAVDANNYA-10), 390 px і 1280 px: головна, карта, покажчик, три вулиці.

Запуск: python tests/znimky_saitu.py <зібраний-сайт> [тека-для-знімків]
Сайт збирає site/zibraty_sait.py з випуску бази. Тут він лише віддається локальним сервером.
Запити до підкладки (tiles.openfreemap.org) вимкнено навмисно: знімки однакові незалежно
від мережі — видно межу Києва з власного файлу і наші дані.
"""
from __future__ import annotations

import functools
import http.server
import sys
import threading
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_zahlushka import CHROME  # noqa: E402

ARGUMENTY_CHROME = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
STORINKY = [
    ('holovna', '/'),
    ('karta', '/karta/'),
    ('vulytsi', '/vulytsi/'),
    ('vulytsia-kadetskyi-hai', '/vulytsia/kadetskyi-hai/'),
    ('vulytsia-khreshchatyk', '/vulytsia/khreshchatyk/'),
    ('vulytsia-andriivskyi-uzviz', '/vulytsia/andriivskyi-uzviz/'),
]


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    sait = Path(argv[0]).resolve()
    teka = Path(argv[1]) if len(argv) > 1 else KORIN / 'tmp' / 'znimky' / 'zavdannya-10'
    teka.mkdir(parents=True, exist_ok=True)
    obrobnyk = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(sait))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), obrobnyk)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_address[1]}'
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=CHROME, args=ARGUMENTY_CHROME)
            for nazva_ekranu, shyryna, vysota, telefon in (('1280', 1280, 900, False), ('390', 390, 844, True)):
                k = b.new_context(viewport={'width': shyryna, 'height': vysota}, device_scale_factor=1,
                                  is_mobile=telefon, has_touch=telefon, color_scheme='light')
                k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
                s = k.new_page()
                for nazva, shlyakh in STORINKY:
                    s.goto(url + shlyakh)
                    s.wait_for_load_state('networkidle')
                    if s.query_selector('.karta, .karta-povna'):
                        s.wait_for_function('''() => { const k = window.MvKarta && MvKarta.karta; if (!k || !k.loaded()) return false;
                            const shar = k.getLayer('soty-L') ? 'soty-L' : 'soty';
                            return k.queryRenderedFeatures({layers: [shar]}).length > 0; }''', timeout=30000)
                        s.wait_for_timeout(1500)
                        s.evaluate('() => new Promise(r => { const k = MvKarta.karta; k.once("idle", r); k.triggerRepaint(); })')
                    if nazva in ('karta', 'holovna'):
                        s.screenshot(path=str(teka / f'{nazva}-{nazva_ekranu}.png'), full_page=nazva == 'holovna')
                    if nazva == 'karta':
                        # Натискаємо на шестикутник у центрі міста, щоб на знімку було видно картку.
                        natysnuty = '''() => { const k = MvKarta.karta; const p = k.project([30.5234, 50.4501]);
                            k.fire('click', {point: p, lngLat: k.unproject(p)}); }'''
                        s.evaluate(natysnuty)
                        s.wait_for_timeout(500)
                        s.screenshot(path=str(teka / f'karta-sota-{nazva_ekranu}.png'))
                        # Наближення: дрібні соти рівня 9.
                        s.click('#panel-zakryty')
                        s.evaluate('() => MvKarta.karta.jumpTo({center: [30.5234, 50.4501], zoom: 13.5})')
                        s.wait_for_function('''() => { const k = MvKarta.karta; return k.loaded() &&
                            k.queryRenderedFeatures({layers: ['soty-S']}).length > 0; }''', timeout=30000)
                        s.wait_for_timeout(500)
                        s.screenshot(path=str(teka / f'karta-nablyzhennia-{nazva_ekranu}.png'))
                        # 3D без ДТП (видно інші види), усі роки.
                        s.evaluate('() => MvKarta.karta.jumpTo({center: [30.52, 50.45], zoom: 10.6})')
                        if telefon:
                            s.click('#vydy-rozgornuty')
                        s.click('[data-hrupa="dtp"]')       # вимкнути ДТП — видно інші види
                        s.click('[data-period="A"]')
                        if telefon:
                            s.click('#vydy-rozgornuty')
                        s.click('#knopka-3d')
                        s.wait_for_timeout(1500)
                        s.screenshot(path=str(teka / f'karta-3d-{nazva_ekranu}.png'))
                        continue
                    if nazva not in ('karta', 'holovna'):
                        s.screenshot(path=str(teka / f'{nazva}-{nazva_ekranu}.png'), full_page=True)
                    if nazva == 'holovna':
                        s.fill('#poshuk-vulytsi', 'лобан')
                        s.wait_for_timeout(400)
                        s.screenshot(path=str(teka / f'holovna-poshuk-{nazva_ekranu}.png'))
                k.close()
            b.close()
    finally:
        server.shutdown()
    print(f'Знімки — у {teka}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
