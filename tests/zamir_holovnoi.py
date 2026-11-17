"""Замір головної з картою (ZAVDANNYA-125, борг Т-12): що вантажиться й коли карта готова.

    python tests/zamir_holovnoi.py <зібраний-сайт> [--json вихід.json]

Профілі: комп'ютер 1280 px без обмежень мережі; телефон 390 px з імітацією повільного мобільного інтернету
(1,6 Мбіт/с, затримка 150 мс, процесор уповільнено вчетверо — як «Slow 4G» інструментів Chrome).
Підкладку (tiles.openfreemap.org) вимкнено — міряємо лише файли сайту. Локальний сервер не стискає: «КБ» — як лежить,
поруч — оцінка після стиснення gzip (Cloudflare стискає JSON і JS сам, docs/HOSTYNG.md).
Друкує таблицю: файли до готовності карти, разом, час до готовності; і чи догружаються дрібні соти при наближенні.
"""
from __future__ import annotations

import functools
import gzip
import http.server
import json
import sys
import threading
import time
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_zahlushka import CHROME  # noqa: E402

PROFILI = [('комп\'ютер 1280', dict(viewport={'width': 1280, 'height': 860}), None),
           ('телефон 390, повільний інтернет', dict(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True),
            {'offline': False, 'downloadThroughput': 1.6e6 / 8, 'uploadThroughput': 0.75e6 / 8, 'latency': 150})]


def zamir(sait: Path) -> list[dict]:
    from playwright.sync_api import sync_playwright
    obr = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(sait))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), obr)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_address[1]}'
    rez = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
            for nazva, kw, merezha in PROFILI:
                k = b.new_context(device_scale_factor=1, color_scheme='light', **kw)
                k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
                s = k.new_page()
                cdp = k.new_cdp_session(s)
                cdp.send('Network.enable')
                cdp.send('Network.setCacheDisabled', {'cacheDisabled': True})
                if merezha:
                    cdp.send('Network.emulateNetworkConditions', merezha)
                    cdp.send('Emulation.setCPUThrottlingRate', {'rate': 4})
                faily, urly = [], {}
                cdp.on('Network.responseReceived', lambda e: urly.__setitem__(e['requestId'], e['response']['url']))
                def hotovyi(e):
                    u = urly.get(e['requestId'], '')
                    if u.startswith(url):
                        shliakh = u[len(url):].split('?')[0]
                        f = sait / shliakh.lstrip('/')
                        f = f / 'index.html' if f.is_dir() else f
                        g = len(gzip.compress(f.read_bytes())) if f.is_file() else 0
                        faily.append((shliakh, int(e['encodedDataLength']), g, time.time()))
                cdp.on('Network.loadingFinished', hotovyi)
                t0 = time.time()
                s.goto(url + '/?vau=0')
                s.wait_for_function('() => window.MvKarta && MvKarta.gotovo', timeout=180000)
                hotovo = time.time() - t0
                s.wait_for_timeout(1500)
                do_hotovnosti = [f for f in faily if f[3] - t0 <= hotovo + 0.05]
                pislia = len(faily)
                # Наближення до кварталу: дрібні соти мають з'явитися
                s.evaluate('() => MvKarta.karta.jumpTo({ center: [30.5234, 50.4501], zoom: 13.2 })')
                s.wait_for_timeout(500)
                try:
                    s.wait_for_function('() => !MvKarta.stan.chekaie || !MvKarta.stan.chekaie.S', timeout=120000)
                except Exception:
                    pass
                s.wait_for_timeout(2500)
                soty_s = s.evaluate("() => MvKarta.karta.querySourceFeatures('k-hex-S').length")
                rez.append({'profil': nazva, 'hotovo_s': round(hotovo, 2),
                            'faily': [(f[0], f[1], f[2]) for f in do_hotovnosti],
                            'razom_kb': round(sum(f[1] for f in do_hotovnosti) / 1024),
                            'razom_gzip_kb': round(sum(f[2] for f in do_hotovnosti) / 1024),
                            'pislia_nablyzhennia': [(f[0], f[1]) for f in faily[pislia:]], 'soty_S_na_karti': soty_s})
                k.close()
            b.close()
    finally:
        server.shutdown()
    return rez


def main(argv: list[str]) -> int:
    sait = Path(argv[0])
    rez = zamir(sait)
    for r in rez:
        print(f"\n== {r['profil']}: готово за {r['hotovo_s']} с; до готовності {r['razom_kb']} КБ (gzip ≈ {r['razom_gzip_kb']} КБ)")
        for f, n, g in sorted(r['faily'], key=lambda x: -x[1]):
            if n > 20 * 1024:
                print(f'   {f:55s} {n // 1024:6d} КБ  gzip ≈ {g // 1024} КБ')
        print(f"   після наближення до 13: {[(f, n // 1024) for f, n in r['pislia_nablyzhennia'] if n > 1024]}; сот рівня 9 на карті: {r['soty_S_na_karti']}")
    if '--json' in argv:
        Path(argv[argv.index('--json') + 1]).write_text(json.dumps(rez, ensure_ascii=False, indent=1), encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
