"""Знімки макета М7 (ZAVDANNYA-42, етап А): кожен напрям × ПК і телефон × світла й темна × місто, Поділ, квартал,
картка; кадр ролика 1080×1920; відео відгуку на дотик; перевірка помилок карти.

Запуск (сервер макета — тека `maket` на 8761):
  python maket/m7/znimky_m7.py                 — усі напрями
  python maket/m7/znimky_m7.py biryuza nich    — лише названі
  python maket/m7/znimky_m7.py dotyk           — відео відгуку на дотик (наведення, натиск, картка, «жива» сота)
  python maket/m7/znimky_m7.py slipi           — копії знімків без назв напрямів (для незалежного оцінювача)
Знімки — у tmp/znimky/m7/ основної теки репозиторію (не в git). Браузер — Edge без вікна, WebGL програмний
(swiftshader): плавність на відео уповільнена й не показова.
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TUT = Path(__file__).resolve().parent
_git = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=TUT,
                      capture_output=True, text=True).stdout.strip()
KORIN = Path(_git).parent if _git else TUT.parents[1]
TEKA = KORIN / 'tmp' / 'znimky' / 'm7'
ADRESA = 'http://127.0.0.1:8761/m7/'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
ARGUMENTY = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
EKRANY = {'pk': (1440, 900), 'telefon': (390, 844)}
KAMERY = {
    '1misto': {'pk': '', 'telefon': ''},
    '2podil': {'pk': '#13.2/50.4655/30.5155/0/40', 'telefon': '#12.9/50.4655/30.5155/0/40'},
    '3kvartal': {'pk': '#15.2/50.4640/30.5160/0/40', 'telefon': '#15.0/50.4640/30.5160/0/40'},
}
NAPRYAMY = [k for k in json.loads((TUT / 'napryamy.json').read_text(encoding='utf-8')) if not k.startswith('_')]
GOTOVO = 'window.MAKET && MAKET.map && MAKET.map.loaded() && MAKET.stan.pidkladka'
_N = [0]


def ity(s, adresa: str) -> None:
    _N[0] += 1
    zapyt, _, kamera = adresa.partition('#')
    s.goto(f'{zapyt}{"&" if "?" in zapyt else "?"}n={_N[0]}' + (f'#{kamera}' if kamera else ''))


def chekaty(s, sek=2.0):
    s.wait_for_function(GOTOVO, timeout=90000)
    s.wait_for_timeout(int(sek * 1000))


def kartka(s, w, h, ekran):
    for dx, dy in [(0, 0), (-60, 0), (60, 0), (0, -60), (-120, -60), (120, 60)]:
        s.mouse.click(w / 2 + dx - (120 if ekran == 'pk' else 0), h / 2 + dy + (0 if ekran == 'pk' else -80))
        s.wait_for_timeout(1200)
        if not s.evaluate('document.getElementById("kartka").hidden'):
            return True
    return False


def novyi(b, ekran, ruh=False, video=None):
    w, h = EKRANY[ekran] if ekran in EKRANY else ekran
    opts = dict(viewport={'width': w, 'height': h}, device_scale_factor=1,
                reduced_motion='no-preference' if ruh else 'reduce',
                is_mobile=ekran == 'telefon', has_touch=ekran == 'telefon')
    if video:
        opts |= dict(record_video_dir=str(video), record_video_size={'width': w, 'height': h})
    return b.new_context(**opts)


def osnovni(pw, napryamy):
    zvit = {}
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    for n in napryamy:
        for ekran, (w, h) in EKRANY.items():
            kont = novyi(b, ekran)
            s = kont.new_page()
            for tema in ('svitla', 'temna'):
                pref = f'{n}-{ekran}-{tema}'
                for nazva, kam in KAMERY.items():
                    ity(s, f'{ADRESA}?napr={n}&tema={tema}' + kam[ekran])
                    chekaty(s)
                    s.screenshot(path=str(TEKA / f'{pref}-{nazva}.png'))
                ity(s, f'{ADRESA}?napr={n}&tema={tema}' + KAMERY['2podil'][ekran])
                chekaty(s)
                ok = kartka(s, w, h, ekran)
                s.wait_for_timeout(500)
                s.screenshot(path=str(TEKA / f'{pref}-4kartka.png'))
                zvit[pref] = {'kartka': ok, 'pomylky': s.evaluate('MAKET.stan.pomylky')}
            kont.close()
        kont = novyi(b, (1080, 1920))
        s = kont.new_page()
        ity(s, f'{ADRESA}?napr={n}&kadr=1')
        chekaty(s, 2.5)
        s.screenshot(path=str(TEKA / f'{n}-kadr-1080x1920.png'))
        zvit[f'{n}-kadr'] = {'pomylky': s.evaluate('MAKET.stan.pomylky')}
        kont.close()
        print(n, 'готово', flush=True)
    b.close()
    return zvit


def dotyk(pw):
    """Відео: курсор водить по сотах (наведення), натиск вершини, картка з'являється, виділена сота «дихає»."""
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    for tema in ('svitla', 'temna'):
        vid = TEKA / f'_video_dotyk_{tema}'
        kont = novyi(b, (1280, 800), ruh=True, video=vid)
        s = kont.new_page()
        ity(s, f'{ADRESA}?napr=biryuza&tema={tema}#13.6/50.4600/30.5170/0/45')
        chekaty(s, 2)
        for x in range(380, 900, 40):
            s.mouse.move(x, 420 + (x % 80))
            s.wait_for_timeout(120)
        s.mouse.click(640, 420)
        s.wait_for_timeout(3500)
        kont.close()
        for f in vid.glob('*.webm'):
            shutil.move(str(f), TEKA / f'dotyk-{tema}.webm')
        shutil.rmtree(vid, ignore_errors=True)
    b.close()


def slipi():
    """Копії знімків під випадковими кодами — оцінювач не знає, чий напрям. Ключ — _klyuch-slipi.json."""
    teka = TEKA / 'slipi'
    shutil.rmtree(teka, ignore_errors=True)
    teka.mkdir()
    kody = [f'N{i}' for i in range(1, len(NAPRYAMY) + 1)]
    random.Random(42).shuffle(kody)
    klyuch = dict(zip(kody, NAPRYAMY))
    for kod, n in klyuch.items():
        for f in TEKA.glob(f'{n}-*.png'):
            shutil.copy(f, teka / f.name.replace(n, kod, 1))
    (TEKA / '_klyuch-slipi.json').write_text(json.dumps(klyuch, ensure_ascii=False, indent=1), encoding='utf-8')


def main(arg: list[str]) -> None:
    TEKA.mkdir(parents=True, exist_ok=True)
    if arg == ['slipi']:
        return slipi()
    with sync_playwright() as pw:
        if arg == ['dotyk']:
            dotyk(pw)
        else:
            print(json.dumps(osnovni(pw, arg or NAPRYAMY), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1:])
