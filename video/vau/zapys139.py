"""Запис справжньої карти сайту на весь кадр з плавним рухом камери й 3D (ZAVDANNYA-139, п. 5) — для порівняння з рушієм.

    python video/vau/zapys139.py <тека зібраного сайту> [--tema temna|svitla] [--kadry 0,2.5] [--vykhid video/vyhid/139]

Сайт збирає site/zibraty_sait.py з того самого випуску (тека поза git). На відміну від записів 129 (сайт у рамці
«телефона», дії пальцем) тут сторінка /karta/ займає весь кадр 1080×1920 (вікно 540×960 × 2), увімкнено 3D, а камеру
ставимо самі щокадру (MvKarta.karta.jumpTo) — як ключі камери в рушії. Час сторінки віртуальний (той самий init-скрипт, що в
zapys_saitu.py), тож рух рівний незалежно від швидкості машини. Кадр чекає, доки плитки й соти домалюються.
Виходить <id>.mp4 без звуку (зразок вигляду, не ролик). Нічого не публікує.
"""
from __future__ import annotations

import argparse
import base64
import http.server
import math
import subprocess
import sys
import threading
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))
from rushii import ffmpeg  # noqa: E402
from zapys_saitu import ZNIMOK  # noqa: E402
from zapys_saitu import VIRTUALNYI_CHAS, Obrobnyk  # noqa: E402

FPS = 30
TRYV = 5.0
# ті самі ключі, що в кліпах лабораторії: місто під нахилом → облітаємо центр
KAMERA = [(0.0, (30.53, 50.445), 10.6, 45, 10), (TRYV, (30.525, 50.452), 11.4, 60, -40)]
ARG_CPU = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--hide-scrollbars']


def io(k):
    return 4 * k ** 3 if k < 0.5 else 1 - (-2 * k + 2) ** 3 / 2


def kamera(t):
    (t0, c0, z0, p0, b0), (t1, c1, z1, p1, b1) = KAMERA
    k = io(min(1.0, max(0.0, (t - t0) / (t1 - t0))))
    return {'center': [c0[0] + (c1[0] - c0[0]) * k, c0[1] + (c1[1] - c0[1]) * k], 'zoom': z0 + (z1 - z0) * k,
            'pitch': p0 + (p1 - p0) * k, 'bearing': b0 + (b1 - b0) * k}


def zapysaty(brauzer, port, tema, kadry, vykhid: Path):
    imia = f'139-zapys_saitu-{tema}'
    kont = brauzer.new_context(viewport={'width': 540, 'height': 960}, device_scale_factor=2,
                               color_scheme='dark' if tema == 'temna' else 'light')
    kont.add_init_script(VIRTUALNYI_CHAS)
    s = kont.new_page()
    pomylky = []
    s.on('pageerror', lambda e: pomylky.append(str(e)))
    s.goto(f'http://127.0.0.1:{port}/karta/')

    def krok(dt_ms, chekaty_ms=0):
        s.evaluate('dt => window.__krok && window.__krok(dt)', dt_ms)
        if chekaty_ms:
            s.wait_for_timeout(chekaty_ms)

    def domaliuvaty(maks=40):
        for _ in range(maks):
            krok(1000 / FPS, 40)
            if s.evaluate('() => { const m = window.MvKarta && MvKarta.karta; return !!(m && m.loaded() && m.areTilesLoaded()); }'):
                break

    for _ in range(80):                                     # карта й соти завантажились
        krok(50, 80)
        if s.evaluate('() => !!(window.MvKarta && MvKarta.karta && MvKarta.karta.loaded())'):
            break
    if s.evaluate('() => !!document.querySelector("#f3d")'):
        s.evaluate('() => document.querySelector("#f3d").click()')      # 3D — як натискає людина
    for _ in range(40):
        krok(50, 60)
    n = int(round(TRYV * FPS))
    if kadry is None:
        vykhid.mkdir(parents=True, exist_ok=True)
        mp4 = vykhid / f'{imia}.mp4'
        p = subprocess.Popen([ffmpeg(), '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                              '-vf', 'scale=1080:1920', '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(mp4)],
                             stdin=subprocess.PIPE)
        cdp = kont.new_cdp_session(s)
    for k in range(n):
        t = k / FPS
        if kadry is not None and not any(abs(t - x) < 0.5 / FPS for x in kadry):
            continue
        s.evaluate('k => MvKarta.karta.jumpTo(k)', kamera(t))
        domaliuvaty()
        if kadry is not None:
            teka = vykhid / 'znimky'
            teka.mkdir(parents=True, exist_ok=True)
            s.screenshot(path=str(teka / f'{imia}-{t:05.2f}.png'))
            continue
        r = cdp.send('Page.captureScreenshot', ZNIMOK)
        p.stdin.write(base64.b64decode(r['data']))
        if k % (FPS * 2) == 0:
            print(f'  {imia}: {k}/{n}', flush=True)
    kont.close()
    if pomylky:
        print('помилки сторінки:', pomylky[:3])
    if kadry is None:
        p.stdin.close()
        p.wait()
        print(f'{mp4.name}: {TRYV} с', flush=True)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('sait', type=Path)
    a.add_argument('--tema', default='temna', choices=('temna', 'svitla'))
    a.add_argument('--kadry')
    a.add_argument('--vykhid', type=Path, default=TUT.parents[1] / 'video' / 'vyhid' / '139')
    a.add_argument('--gpu', action='store_true')
    arg = a.parse_args()
    Obrobnyk.sait = arg.sait.resolve()
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Obrobnyk)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    kadry = [float(x) for x in arg.kadry.split(',')] if arg.kadry else None
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars']
                               if arg.gpu else ARG_CPU)
        zapysaty(b, srv.server_address[1], arg.tema, kadry, arg.vykhid)
        b.close()
    srv.shutdown()


if __name__ == '__main__':
    main()
