"""Запис екрана справжнього сайту для роликів (ZAVDANNYA-129, MV-151: «замість намальованих макетів — запис екрана сайту»).

    python video/vau/zapys_saitu.py <тека зібраного сайту> [--lyshe z1,z2] [--kadry 0,3,7]

Сайт збирає site/zibraty_sait.py з того самого випуску (тека поза git, напр. video/vyhid/sait). Рамка «телефона» —
video/vau/zapys.html: сайт у вікні 400×712 (телефонний вигляд сайту), зверху — логотип, джерело, «запис екрана сайту», гачок.
Час сторінки віртуальний: init-скрипт підміняє годинник, кадри анімації й таймери (performance.now, Date.now,
requestAnimationFrame, setTimeout/setInterval), і кожен кадр сайт проживає рівно 1/30 с — карта летить рівно, як у рушії.
Мережа (плитки, JSON сайту) — справжня: після кожного кроку чекаємо, доки сайт домалюється.

Виходить те саме, що в rushii.py: <id>.mp4 (1080×1920, звук), lehki/<id>.mp4, arkushi/<id>.jpg. Правила — perevirka.py.
"""
from __future__ import annotations

import argparse
import base64
import functools
import http.server
import json
import math
import re
import subprocess
import sys
import threading
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))
import perevirka  # noqa: E402
from rushii import arkush, ffmpeg, lehka  # noqa: E402
from stsenarii import KYIV, PROFIL  # noqa: E402

VYHID = TUT.parents[1] / 'video' / 'vyhid' / '129'
FPS = 30

VIRTUALNYI_CHAS = r"""
(() => {
  let now = 0; const start = 1763560000000;
  let rafs = []; let tid = 0; const timers = [];
  performance.now = () => now;
  Date.now = () => start + Math.floor(now);
  const D0 = Date; window.Date = class extends D0 { constructor(...a) { if (a.length) super(...a); else super(start + Math.floor(now)); } static now() { return start + Math.floor(now); } };
  window.requestAnimationFrame = cb => { rafs.push(cb); return rafs.length + 1e6 * Math.random(); };
  window.cancelAnimationFrame = () => {};
  window.setTimeout = (cb, ms, ...a) => { const id = ++tid; timers.push({ id, t: now + Math.max(0, +ms || 0), cb, a }); return id; };
  window.clearTimeout = id => { const i = timers.findIndex(x => x.id === id); if (i >= 0) timers.splice(i, 1); };
  window.setInterval = (cb, ms, ...a) => { const id = ++tid; const f = () => { timers.push({ id, t: now + Math.max(1, +ms || 1), cb: () => { f(); cb(...a); }, a: [] }); }; f(); return id; };
  window.clearInterval = id => { for (let i = timers.length - 1; i >= 0; i--) if (timers[i].id === id) timers.splice(i, 1); };
  window.__krok = dt => {
    const end = now + dt;
    for (let g = 0; g < 2000; g++) {
      timers.sort((a, b) => a.t - b.t);
      if (!timers.length || timers[0].t > end) break;
      const x = timers.shift(); now = Math.max(now, x.t);
      try { typeof x.cb === 'function' && x.cb(...x.a); } catch (e) { console.error(e); }
    }
    now = end;
    const cbs = rafs; rafs = [];
    cbs.forEach(cb => { try { cb(now); } catch (e) { console.error(e); } });
  };
})();
"""


class Obrobnyk(http.server.SimpleHTTPRequestHandler):
    """Корінь — зібраний сайт (адреси сайту абсолютні: /karta/…); /__vau/ — рамка й стилі рушія."""
    sait = Path('.')

    def log_message(self, *a):
        pass

    def translate_path(self, path):
        p = path.split('?', 1)[0]
        if p.startswith('/__vau/'):
            return str(TUT / p[len('/__vau/'):])
        if p.startswith('/site/sait/shryfty/'):          # шрифти для накладки (stsena.css посилається на ../../site/…)
            return str(TUT.parents[1] / p.lstrip('/'))
        return str(self.sait / p.lstrip('/'))

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


# ------------------------------------------------------------------ сценарії записів

def z1():
    """Запис 1: «Як знайти свою вулицю» — пошук на головній → переліт → сторінка вулиці (справжні числа сайту)."""
    return {
        'id': '129-z1-zapys-poshuk-vulytsi', 'tryvalist': 15,
        'meta': dict(nazva='Запис екрана: як знайти свою вулицю', hrupa='Як це працює', meta='спосіб користування → сторінка вулиці',
                     hachok='«Твоя вулиця — за 10 секунд» над справжнім сайтом', liniia='Мій будинок', kudy='/vulytsia/kadetskyi-hai/'),
        'start': '/',
        'tekst': [
            {'t0': 0, 't1': 2.6, 'styl': 'velykyi', 'tekst': 'Твоя вулиця —\n*за 10 секунд*', 'y': 340},
            {'t0': 2.7, 't1': 4.6, 'styl': 'velykyi', 'tekst': 'Введи назву —\n*вибери з підказки*', 'y': 340},
            {'t0': 4.7, 't1': 6.6, 'styl': 'velykyi', 'tekst': 'Карта летить\n*до твоєї вулиці*', 'y': 340},
            {'t0': 6.7, 't1': 8.7, 'styl': 'velykyi', 'tekst': 'Сторінка вулиці —\n*скільки й чого тут було*', 'y': 340},
            {'t0': 8.8, 't1': 10.8, 'styl': 'velykyi', 'tekst': 'Чим вулиця\n*відрізняється від Києва*', 'y': 340},
            {'t0': 10.9, 't1': 12.9, 'styl': 'velykyi', 'tekst': 'Дні й години —\n*коли саме*', 'y': 340},
            {'t0': 13.0, 't1': 14.0, 'styl': 'baner', 'zag': 'Знайди свою вулицю', 'knopka': 'Безкоштовно · ' + PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 0.9, 'dia': 'tap', 'sel': '#poshuk-karty'},
            {'t': 1.0, 'dia': 'pyshy', 'sel': '#poshuk-karty', 'tekst': 'Кадетський', 'tryv': 1.4},
            {'t': 3.2, 'dia': 'tap', 'sel': '#pidkazky li[data-j="0"]', 'pointerdown': True},
            {'t': 6.7, 'dia': 'goto', 'url': '/vulytsia/kadetskyi-hai/'},
            {'t': 7.6, 'dia': 'skrol', 'sel': '.stat, main h1', 'do_px': 250, 'tryv': 0.9},
            {'t': 8.8, 'dia': 'skrol', 'do_px': 640, 'tryv': 1.0},
            {'t': 9.9, 'dia': 'skrol', 'do_px': 900, 'tryv': 0.7},
            {'t': 10.9, 'dia': 'skrol', 'do_px': 1380, 'tryv': 1.2},
            {'t': 12.0, 'dia': 'skrol', 'do_px': 1560, 'tryv': 0.8},
        ],
        'zvuk': {'muzyka': {'styl': 'lofi', 'bpm': 96}, 'efekty': [{'t': 0.9, 'typ': 'klik', 'h': 1.0}, {'t': 3.2, 'typ': 'klik', 'h': 1.2},
                 {'t': 3.3, 'typ': 'vzhukh', 'v': 0.6}, {'t': 6.7, 'typ': 'svish'}, {'t': 13.0, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}]
                 + [{'t': round(1.0 + i * 0.14, 2), 'typ': 'druk', 'v': 0.45} for i in range(10)],
                 'holos': [{'t': 0.2, 'tekst': 'Твоя вулиця — за десять секунд.', 'holos': 'tetiana'},
                           {'t': 6.9, 'tekst': 'Сторінка вулиці: скільки й чого тут було.', 'holos': 'tetiana'}]},
        'pidpys': ['Запис екрана справжнього сайту «Моя вулиця». Числа вулиці — безкоштовно; події з адресами й описами — у підписці.'],
        'karta': [(0, 6.6)],
    }


def z2():
    """Запис 2: «Наближ — і соти розкриються» — головна карта сайту: 3D, наближення колесом до центру."""
    return {
        'id': '129-z2-zapys-karta-soty', 'tryvalist': 12,
        'meta': dict(nazva='Запис екрана: карта — наближ, і соти розкриються', hrupa='Як це працює', meta='спосіб користування картою',
                     hachok='«Це справжня карта. Наближ — і соти розкриються»', liniia='Безкоштовна карта', kudy='/karta/'),
        'start': '/',
        'tekst': [
            {'t0': 0, 't1': 1.8, 'styl': 'velykyi', 'tekst': 'Це справжня карта\n*судових рішень Києва*', 'y': 340},
            {'t0': 1.9, 't1': 3.9, 'styl': 'velykyi', 'tekst': 'Натисни *3D*', 'y': 340},
            {'t0': 4.0, 't1': 5.9, 'styl': 'velykyi', 'tekst': 'Наближ —\n*соти дрібнішають*', 'y': 340},
            {'t0': 6.0, 't1': 8.4, 'styl': 'velykyi', 'tekst': 'Вище й темніше —\n*більше подій у даних*', 'y': 340},
            {'t0': 8.5, 't1': 10.4, 'styl': 'velykyi', 'tekst': 'Торкнись соти —\n*що тут було*', 'y': 340},
            {'t0': 10.6, 't1': 11.6, 'styl': 'baner', 'zag': 'Карта Києва — безкоштовно', 'knopka': PROFIL, 'y': 1180},
        ],
        'dii': [
            {'t': 2.1, 'dia': 'tap', 'sel': '#f3d'},
            {'t': 4.0, 'dia': 'kolo', 'xy': [200, 380], 'dy': -2600, 'tryv': 3.6},
            {'t': 8.6, 'dia': 'tap_xy', 'xy': [150, 300]},
        ],
        'zvuk': {'muzyka': {'styl': 'epik', 'bpm': 100, 'drop': 4.0}, 'efekty': [{'t': 2.1, 'typ': 'klik', 'h': 1.1}, {'t': 4.0, 'typ': 'rizer', 'v': 0.6},
                 {'t': 8.6, 'typ': 'klik', 'h': 1.3}, {'t': 8.7, 'typ': 'pop', 'h': 1.2}, {'t': 10.6, 'typ': 'dzvin', 'h': 0.8, 'v': 0.5}]},
        'pidpys': ['Запис екрана справжнього сайту «Моя вулиця»: карта подій Києва з рішень судів. Колір і висота — кількість даних, не оцінка місця.'],
        'karta': [(0, 12)],
    }


ZAPYSY = {'z1': z1, 'z2': z2}


def perevir(Z: dict) -> list[str]:
    """Ті самі правила, що й у рушія: слова, банер ≤ 1 с, гачок у кадрі 0, нове кожні ≤ 2 с, голос з позначкою."""
    S = {'id': Z['id'], 'tryvalist': Z['tryvalist'], 'tema': 'temna', 'tekst': Z['tekst'], 'kamera': [{'t': 0, 'c': list(KYIV), 'z': 11}],
         'zvuk': Z['zvuk'], 'pidpys_publikatsii': Z['pidpys'], 'holos_poznaka': 'Голос згенеровано' if Z['zvuk'].get('holos') else None,
         'ui': [{'t0': 0, 't1': Z['tryvalist'], 'typ': 'sait'}, {'t0': 0, 't1': Z['tryvalist'], 'typ': 'ramka'}],
         'novynky': [d['t'] for d in Z['dii']] + [d['t'] + x * 1.5 for d in Z['dii'] if d.get('tryv')
                                                   for x in range(1, int(d['tryv'] / 1.5) + 1)]}   # наближення/прокрутка — рух сайту
    meta = dict(Z['meta'], pravyla=129, kintsivka=PROFIL, pidpys=' '.join(Z['pidpys']))
    return perevirka.pereviryty(S, meta)


def zapysaty(brauzer, port, Z: dict, kadry=None, vykhid=VYHID):
    zauv = perevir(Z)
    if zauv:
        raise SystemExit(f"{Z['id']}: " + '; '.join(zauv))
    holos = bool(Z['zvuk'].get('holos'))
    S_ov = {'tekst': Z['tekst'], 'dzherelo': 'Справжній сайт · дані — рішення судів (ЄДРСР)', 'holos_poznaka': 'Голос згенеровано' if holos else None,
            'paltsi': []}
    kont = brauzer.new_context(viewport={'width': 540, 'height': 960}, device_scale_factor=2, color_scheme='dark')
    kont.add_init_script(VIRTUALNYI_CHAS)
    s = kont.new_page()
    pomylky = []
    s.on('pageerror', lambda e: pomylky.append(str(e)))
    s.goto(f'http://127.0.0.1:{port}/__vau/zapys.html')
    s.evaluate('s => window.zapusk(s)', S_ov)
    s.evaluate('u => { document.getElementById("sait").src = u; }', Z['start'])
    sait = lambda: s.frames[1]

    def krok(dt_ms, chekaty_ms):
        s.evaluate('dt => { const f = document.getElementById("sait").contentWindow; if (f.__krok) f.__krok(dt); window.__krok(dt); }', dt_ms)
        if chekaty_ms:
            s.wait_for_timeout(chekaty_ms)

    def rozihrity(sekund):
        for _ in range(int(sekund * 20)):
            krok(50, 60)

    s.wait_for_timeout(1500)
    rozihrity(4)
    n = int(round(Z['tryvalist'] * FPS))
    teka_z = vykhid.parent / 'znimky'
    if kadry is None:
        vykhid.mkdir(parents=True, exist_ok=True)
        tykho = vykhid / f"{Z['id']}-bez-zvuku.mp4"
        p = subprocess.Popen([ffmpeg(), '-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', str(FPS), '-c:v', 'mjpeg', '-i', '-',
                              '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(tykho)],
                             stdin=subprocess.PIPE)
    cdp = kont.new_cdp_session(s)
    dii = sorted(Z['dii'], key=lambda d: d['t'])
    aktyvni = []
    for k in range(n):
        t = k / FPS
        for d in [d for d in dii if d['t'] <= t and not d.get('_zrobleno')]:
            d['_zrobleno'] = True
            vykonaty(s, sait, d, t, S_ov, krok)
            if d['dia'] in ('pyshy', 'skrol', 'kolo'):
                aktyvni.append(d)
        for d in list(aktyvni):
            k_ = min(1.0, (t - d['t']) / d['tryv'])
            if d['dia'] == 'pyshy':
                sait().evaluate('([sel, v]) => { const e = document.querySelector(sel); if (e.value !== v) { e.value = v; e.dispatchEvent(new Event("input", {bubbles: true})); } }',
                                [d['sel'], d['tekst'][:max(1, math.ceil(len(d['tekst']) * k_))]])
            elif d['dia'] == 'skrol':
                y = d['_z'] + (d['do_px'] - d['_z']) * (1 - (1 - k_) ** 3)
                sait().evaluate('y => window.scrollTo(0, y)', y)
            elif d['dia'] == 'kolo':
                s.mouse.move(70 + d['xy'][0], 272 + d['xy'][1])
                s.mouse.wheel(0, d['dy'] / (d['tryv'] * FPS))
            if k_ >= 1:
                aktyvni.remove(d)
        karta = any(a <= t <= b for a, b in Z.get('karta', []))
        krok(1000 / FPS, 140 if karta else 30)
        s.evaluate('t => window.kadrZapysu(t)', t)
        if kadry is not None:
            if any(abs(t - x) < 0.5 / FPS for x in kadry):
                teka_z.mkdir(parents=True, exist_ok=True)
                s.screenshot(path=str(teka_z / f"{Z['id']}-{t:05.2f}.png"))
            continue
        r = cdp.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 93})
        p.stdin.write(base64.b64decode(r['data']))
        if k % (FPS * 5) == 0:
            print(f"  {Z['id']}: {k}/{n}", flush=True)
    kont.close()
    if pomylky:
        print('помилки сторінки:', pomylky[:3])
    if kadry is not None:
        return None
    p.stdin.close()
    p.wait()
    import zvuk
    S_zv = {'tryvalist': Z['tryvalist'], 'zvuk': Z['zvuk']}
    wav = vykhid / 'kesh' / f"{Z['id']}.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    zv = zvuk.zibraty(S_zv, wav)
    if zv.get('srt'):
        (vykhid / f"{Z['id']}.srt").write_text(zv['srt'], encoding='utf-8')
    mp4 = vykhid / f"{Z['id']}.mp4"
    subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-i', str(tykho), '-i', str(wav), '-c:v', 'copy', '-af', 'loudnorm=I=-14:TP=-1.5:LRA=11',
                    '-ar', '48000', '-c:a', 'aac', '-b:a', '192k', '-shortest', '-movflags', '+faststart', str(mp4)], check=True)
    tykho.unlink()
    lehka(mp4, vykhid / 'lehki' / mp4.name, Z['tryvalist'])
    arkush(mp4, vykhid / 'arkushi' / f"{Z['id']}.jpg", Z['tryvalist'])
    # сценарій для перевірки звуку (sluhaty --stsenarii) і каталогу
    kesh = vykhid.parent / 'kesh' / 'stsenarii'
    kesh.mkdir(parents=True, exist_ok=True)
    (kesh / f"{Z['id']}.json").write_text(json.dumps({'id': Z['id'], 'tryvalist': Z['tryvalist'], 'zvuk': Z['zvuk'], 'tekst': Z['tekst'],
                                                       'pidpys_publikatsii': Z['pidpys'], 'meta': Z['meta']}, ensure_ascii=False), encoding='utf-8')
    print(f"{mp4.name}: {Z['tryvalist']} с", flush=True)
    return mp4


def vykonaty(s, sait, d, t, S_ov, krok):
    dia = d['dia']
    if dia in ('tap', 'tap_xy'):
        xy = s.evaluate('sel => window.dePalets(sel)', d['sel']) if dia == 'tap' else [(70 + d['xy'][0]) * 2, (272 + d['xy'][1]) * 2]
        if xy:
            s.evaluate('f => window.dodatyPalets(f)', {'t': t, 'x': xy[0], 'y': xy[1]})
        if dia == 'tap':
            if d.get('pointerdown'):
                sait().evaluate('sel => { const e = document.querySelector(sel); if (e) e.dispatchEvent(new PointerEvent("pointerdown", {bubbles: true})); }', d['sel'])
            else:
                sait().evaluate('sel => { const e = document.querySelector(sel); if (e) { e.focus && e.focus(); e.click(); } }', d['sel'])
        else:
            s.mouse.click(70 + d['xy'][0], 272 + d['xy'][1])
            for _ in range(12):
                krok(50, 60)
            kartka = sait().evaluate('() => (document.querySelector("#kartka") || {}).innerText || ""')
            # насильство в ролики не йде (dani.py, MV-69): картка соти з таким рядком — інша сота
            if re.search(r'[Нн]асильств|статев|дит', kartka):
                raise SystemExit(f"{d['xy']}: у картці соти є чутливий рядок — вибрати іншу соту")
    elif dia == 'goto':
        s.evaluate('u => { document.getElementById("sait").src = u; }', d['url'])
        s.wait_for_timeout(1200)
        for _ in range(10):
            krok(50, 80)
    elif dia == 'skrol':
        d['_z'] = sait().evaluate('() => window.scrollY')


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('sait', type=Path)
    a.add_argument('--lyshe')
    a.add_argument('--kadry')
    a.add_argument('--vykhid', type=Path, default=VYHID)
    arg = a.parse_args()
    Obrobnyk.sait = arg.sait.resolve()
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Obrobnyk)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from playwright.sync_api import sync_playwright
    kadry = [float(x) for x in arg.kadry.split(',')] if arg.kadry else None
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True, args=['--use-angle=d3d11', '--enable-gpu', '--ignore-gpu-blocklist', '--hide-scrollbars'])
        for k in (arg.lyshe.split(',') if arg.lyshe else sorted(ZAPYSY)):
            zapysaty(b, srv.server_address[1], ZAPYSY[k](), kadry, arg.vykhid)
        b.close()
    srv.shutdown()


if __name__ == '__main__':
    main()
