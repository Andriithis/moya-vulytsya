"""Рендер роликів рушія «Вау» (ZAVDANNYA-127): сценарій JSON → MP4 1080×1920 зі звуком, легка копія й аркуш кадрів.

    python video/vau/rushii.py video/vyhid/kesh/stsenarii/*.json            # усе
    python video/vau/rushii.py <сценарій.json> --kadry 0.5,3,7.2           # лише кадри-знімки (швидка перевірка)
    python video/vau/rushii.py <сценарій.json> --bez-zvuku

Що виходить (теки не в git, video/vyhid/):
    <id>.mp4            — повний ролик 1080×1920, 30 кадрів/с, H.264 + AAC, гучність ≈ −14 LUFS (як у TikTok)
    lehki/<id>.mp4      — легка копія 540×960, ≤ 3 МБ (для перегляду з телефона, гілка rolyky-127)
    arkushi/<id>.jpg    — аркуш кадрів: кадр кожні 0,5 с, зліва направо, згори вниз
    <id>.srt            — субтитри голосу (якщо є голос)

Як працює: локальний вебсервер віддає video/vau/stsena.html; безголовий Chromium з відеокартою (ANGLE D3D11; без неї —
SwiftShader) ставить кадр функцією window.kadr(t), чекає, доки карта домалюється, знімок іде потоком у ffmpeg.
Звук — video/vau/zvuk.py (власна музика й ефекти з синусоїд і шуму, голос Piper). ffmpeg — системний або з
пакета imageio-ffmpeg (pip install imageio-ffmpeg).
"""
from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import math
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
VYHID = KORIN / 'video' / 'vyhid'
W, H = 1080, 1920
ARG_GPU = ['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars']
ARG_CPU = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--hide-scrollbars']


def ffmpeg() -> str:
    s = shutil.which('ffmpeg')
    if s:
        return s
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        sys.exit('Немає ffmpeg: pip install imageio-ffmpeg або встановіть ffmpeg')


class Tykhyi(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


def server():
    s = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Tykhyi, directory=str(KORIN)))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def vidkryty(brauzer, port, shliakh: Path):
    s = brauzer.new_page(viewport={'width': W, 'height': H}, device_scale_factor=1)
    pomylky = []
    s.on('pageerror', lambda e: pomylky.append(str(e)))
    vidn = shliakh.resolve().relative_to(KORIN).as_posix()
    s.goto(f'http://127.0.0.1:{port}/video/vau/stsena.html?s=/{vidn}')
    info = s.evaluate('() => window.gotovo')
    if pomylky:
        raise RuntimeError('; '.join(pomylky))
    return s, info, pomylky


def rendery(brauzer, port, shliakh: Path, fps=30, zvuk_=True, kadry=None, vykhid=VYHID):
    S = json.loads(shliakh.read_text(encoding='utf-8'))
    imia = S['id']
    if (S.get('zvuk') or {}).get('holos') and zvuk_:
        # позначка — за голосом, яким ролик озвучується зараз (MV_HOLOS): сценарій могли зібрати з іншим (ZAVDANNYA-175)
        sys.path.insert(0, str(TUT))
        import holos_servis
        if S.get('holos_poznaka') != holos_servis.poznaka():
            S['holos_poznaka'] = holos_servis.poznaka()
            shliakh.write_text(json.dumps(S, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    s, info, pomylky = vidkryty(brauzer, port, shliakh)
    tryv = float(S['tryvalist'])
    if kadry is not None:
        teka = vykhid / 'znimky'
        teka.mkdir(parents=True, exist_ok=True)
        for t in kadry:
            s.evaluate('t => window.kadr(t)', t)
            s.screenshot(path=str(teka / f'{imia}-{t:05.2f}.png'))
        s.close()
        return None
    vykhid.mkdir(parents=True, exist_ok=True)
    tykho = vykhid / f'{imia}-bez-zvuku.mp4'
    ff = ffmpeg()
    p = subprocess.Popen([ff, '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(fps), '-c:v', 'mjpeg', '-i', '-',
                          '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-r', str(fps),
                          '-movflags', '+faststart', str(tykho)], stdin=subprocess.PIPE)
    cdp = s.context.new_cdp_session(s)
    n = int(round(tryv * fps))
    pochatok = time.time()
    for k in range(n):
        s.evaluate('t => window.kadr(t)', k / fps)
        r = cdp.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 93, 'optimizeForSpeed': True})
        p.stdin.write(base64.b64decode(r['data']))
        if k % (fps * 5) == 0:
            print(f'  {imia}: {k}/{n}', flush=True)
    p.stdin.close()
    if p.wait() != 0:
        raise RuntimeError('ffmpeg: помилка відео')
    s.close()
    if pomylky:
        raise RuntimeError('; '.join(pomylky))
    mp4 = vykhid / f'{imia}.mp4'
    if zvuk_ and S.get('zvuk'):
        sys.path.insert(0, str(TUT))
        import zvuk
        wav = vykhid / 'kesh' / f'{imia}.wav'
        wav.parent.mkdir(parents=True, exist_ok=True)
        zv = zvuk.zibraty(S, wav)
        if zv.get('srt'):
            (vykhid / f'{imia}.srt').write_text(zv['srt'], encoding='utf-8')
        subprocess.run([ff, '-y', '-loglevel', 'error', '-i', str(tykho), '-i', str(wav), '-c:v', 'copy',
                        '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11', '-ar', '48000', '-c:a', 'aac', '-b:a', '192k',
                        '-shortest', '-movflags', '+faststart', str(mp4)], check=True)
        tykho.unlink()
    else:
        tykho.replace(mp4)
    sek = time.time() - pochatok
    lehka(mp4, vykhid / 'lehki' / f'{imia}.mp4', tryv)
    arkush(mp4, vykhid / 'arkushi' / f'{imia}.jpg', tryv)
    print(f'{mp4.name}: {tryv:.1f} с, {n} кадрів, рендер {sek:.0f} с', flush=True)
    return mp4


def lehka(mp4: Path, kudy: Path, tryv: float, mb: float = 2.85):
    """540×960 (ZAVDANNYA-138; було 480×854), ≤ 3 МБ: бітрейт відео — з довжини (аудіо 64 кбіт/с)."""
    kudy.parent.mkdir(parents=True, exist_ok=True)
    vsogo = mb * 8 * 1024 / max(tryv, 1)            # кбіт/с на все
    v = int(min(1400, max(250, vsogo - 72)))
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(mp4), '-vf', 'scale=540:960:flags=lanczos',
                    '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{v}k', '-maxrate', f'{int(v * 1.25)}k',
                    '-bufsize', f'{v * 2}k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '64k', '-ac', '1',
                    '-movflags', '+faststart', str(kudy)], check=True)
    if kudy.stat().st_size > 3 * 1024 * 1024:       # рідко: ще раз, тихіше
        lehka(mp4, kudy, tryv, mb * 0.8)


def arkush(mp4: Path, kudy: Path, tryv: float):
    """Аркуш кадрів: кожні 0,5 с, 10 у ряд, кадр 162×288."""
    kudy.parent.mkdir(parents=True, exist_ok=True)
    n = max(1, int(math.ceil(tryv * 2)))
    riady = int(math.ceil(n / 10))
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(mp4), '-vf',
                    f'fps=2,scale=162:288,tile=10x{riady}:padding=4:color=0x11142A', '-frames:v', '1', '-q:v', '4',
                    str(kudy)], check=True)


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('stsenarii', nargs='+', type=Path)
    a.add_argument('--fps', type=int, default=30)
    a.add_argument('--bez-zvuku', action='store_true')
    a.add_argument('--kadry', help='лише знімки в ці моменти, напр. 0.5,3,7')
    a.add_argument('--cpu', action='store_true', help='без відеокарти (SwiftShader)')
    a.add_argument('--vykhid', type=Path, default=VYHID)
    arg = a.parse_args()
    from playwright.sync_api import sync_playwright
    srv = server()
    port = srv.server_address[1]
    kadry = [float(x) for x in arg.kadry.split(',')] if arg.kadry else None
    nevdachi = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=ARG_CPU if arg.cpu else ARG_GPU)
        for f in arg.stsenarii:
            try:
                rendery(b, port, f, arg.fps, not arg.bez_zvuku, kadry, arg.vykhid)
            except Exception as e:  # один зіпсований сценарій не зупиняє ніч рендеру
                print(f'ПОМИЛКА {f.name}: {e}', flush=True)
                nevdachi.append(f.name)
        b.close()
    srv.shutdown()
    if nevdachi:
        sys.exit('не вийшло: ' + ', '.join(nevdachi))


if __name__ == '__main__':
    main()
