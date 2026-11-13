"""Рендер ролика «Моєї вулиці» з JSON-сценарію (ZAVDANNYA-11).

Одним рядком (з кореня репозиторію):
    python video/rendery.py video/stsenarii/tur-pechersk.json
Усі три шаблони:
    python video/rendery.py video/stsenarii/*.json

Параметри:
    --rezhym skhema|pidkladka   вигляд карти: без підкладки (за замовчуванням, працює без мережі)
                                або з вулицями OpenFreeMap (потрібна мережа до tiles.openfreemap.org)
    --vykhid TEKA               куди класти .mp4 (за замовчуванням video/vyhid/, у git не йде)
    --znimky TEKA               ще й зберегти 3 кадри-знімки (PNG) у цю теку
    --fps 30                    кадрів на секунду

Як працює: локальний вебсервер віддає `video/stsena.html`; безголовий Chrome відкриває його
в кадрі 1080×1920; для кожного кадру сторінка ставить камеру й картки (window.kadr), чекає,
доки карта домалюється, і рендер знімає екран; знімки йдуть потоком у ffmpeg
(H.264, -preset veryfast, 30 кадрів/с, yuv420p — це приймають TikTok, YouTube і Instagram).
Звуку немає (наступний крок).

Потрібно: Python-пакет playwright, Google Chrome або Chromium, ffmpeg.
"""
from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
TUT = KORIN / 'video'
SHYRYNA, VYSOTA = 1080, 1920
ARGUMENTY_CHROME = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader',
                    '--ignore-gpu-blocklist', '--hide-scrollbars']


def znaity_chrome():
    for n in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        s = shutil.which(n)
        if s:
            return s
    return None  # тоді playwright візьме власний Chromium, якщо встановлено


class TykhyiObrobnyk(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def server():
    obrobnyk = functools.partial(TykhyiObrobnyk, directory=str(KORIN))
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), obrobnyk)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def rendery(brauzer, port, stsenarii: Path, rezhym, vykhid: Path, znimky: Path | None, fps):
    S = json.loads(stsenarii.read_text(encoding='utf-8'))
    imia = stsenarii.stem + ('' if rezhym == 'skhema' else '-pidkladka')
    vykhid.mkdir(parents=True, exist_ok=True)
    mp4 = vykhid / f'{imia}.mp4'
    s = brauzer.new_page(viewport={'width': SHYRYNA, 'height': VYSOTA}, device_scale_factor=1)
    pomylky = []
    s.on('pageerror', lambda e: pomylky.append(str(e)))
    vidn = stsenarii.resolve().relative_to(TUT).as_posix()
    # сцена отримує лише підготовлений сценарій: номер будинку прибрано за правилом MV-60
    import perevirka
    hotovyi = json.dumps(perevirka.pidhotuvaty(S), ensure_ascii=False)
    s.route(f'**/video/{vidn}', lambda route: route.fulfill(status=200, content_type='application/json; charset=utf-8', body=hotovyi))
    s.goto(f'http://127.0.0.1:{port}/video/stsena.html?s={vidn}&rezhym={rezhym}')
    try:
        info = s.evaluate('() => window.gotovo')
    except Exception as e:  # напр., підкладка недоступна — коротко, без довгого сліду помилки
        sys.exit(f'{stsenarii.name}: {str(e).splitlines()[0]}')
    if pomylky:
        raise RuntimeError('; '.join(pomylky))
    tryv = info['tryvalist']
    n = int(round(tryv * fps))
    # моменти для знімків: індекси відрізків зі сценарію (поле "znimky"), кадр — під кінець відрізка
    momenty = []
    if znimky:
        znimky.mkdir(parents=True, exist_ok=True)
        vidrizky = s.evaluate('() => window.vidrizky()')
        for i in S.get('znimky', [1, 2, len(vidrizky) - 2]):
            v = vidrizky[i]
            momenty.append(round(max(v['t0'], v['t1'] - 0.45) * fps))

    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        sys.exit('Немає ffmpeg: встановіть (Windows: winget install ffmpeg; Linux: apt install ffmpeg)')
    p = subprocess.Popen([ffmpeg, '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(fps),
                          '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20',
                          '-pix_fmt', 'yuv420p', '-r', str(fps), '-movflags', '+faststart', str(mp4)],
                         stdin=subprocess.PIPE)
    # знімок через протокол Chrome напряму: учетверо швидше за звичайний screenshot
    cdp = s.context.new_cdp_session(s)
    pochatok = time.time()
    for k in range(n):
        s.evaluate('t => window.kadr(t)', k / fps)
        r = cdp.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 92, 'optimizeForSpeed': True})
        p.stdin.write(base64.b64decode(r['data']))
        if k in momenty:
            nomer = momenty.index(k) + 1
            r = cdp.send('Page.captureScreenshot', {'format': 'png'})
            (znimky / f'{imia}-{nomer}.png').write_bytes(base64.b64decode(r['data']))
        if k % (fps * 5) == 0:
            print(f'  {imia}: {k}/{n} кадрів', flush=True)
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError('ffmpeg завершився з помилкою')
    s.close()
    if pomylky:
        raise RuntimeError('; '.join(pomylky))
    sek = time.time() - pochatok
    print(f'{mp4}: {tryv:.1f} с ролика, {n} кадрів, рендер {sek:.0f} с')
    return mp4, tryv, sek


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('stsenarii', nargs='+', type=Path)
    a.add_argument('--rezhym', choices=['skhema', 'pidkladka'], default='skhema')
    a.add_argument('--vykhid', type=Path, default=TUT / 'vyhid')
    a.add_argument('--znimky', type=Path)
    a.add_argument('--fps', type=int, default=30)
    arg = a.parse_args()

    sys.path.insert(0, str(TUT))
    import perevirka  # noqa: E402
    zauvazhennia = []
    for st in arg.stsenarii:
        zauvazhennia += perevirka.pereviryty(json.loads(st.read_text(encoding='utf-8')), st.name)
    if zauvazhennia:
        sys.exit('Сценарій не пройшов перевірку:\n  ' + '\n  '.join(zauvazhennia))

    from playwright.sync_api import sync_playwright
    srv = server()
    try:
        with sync_playwright() as pw:
            ch = znaity_chrome()
            b = pw.chromium.launch(executable_path=ch, args=ARGUMENTY_CHROME) if ch else pw.chromium.launch(args=ARGUMENTY_CHROME)
            for st in arg.stsenarii:
                rendery(b, srv.server_address[1], st, arg.rezhym, arg.vykhid, arg.znimky, arg.fps)
            b.close()
    finally:
        srv.shutdown()


if __name__ == '__main__':
    main()
