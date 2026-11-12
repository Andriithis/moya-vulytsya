"""Знімки й відео макета М6 (ZAVDANNYA-36): К3 × ПК і телефон × світла й темна × місто, Поділ, квартали, картка;
кожен «вау» окремо; послідовність і відео зуму; відео першого відкриття; частки шкали на чотирьох наборах даних.

Запуск (сервер макета працює на 8760, тека `maket`):
  python maket/m6/znimky_m6.py            — основні знімки + перевірка, що плашки не зсуваються
  python maket/m6/znimky_m6.py vau        — «вау» окремо (знімки посередині й наприкінці) і відео першого відкриття
  python maket/m6/znimky_m6.py zum        — зум 9,3 → 14,6 знімками (густо в 12,0–12,8) і відео
  python maket/m6/znimky_m6.py chastky    — таблиця часток (2024–2026, ×5, ×20, нерівні)
Знімки — у tmp/znimky/m6/ основної теки репозиторію (D:\\problem_orienting\\moya-vulytsya), не в git.
Браузер — Edge без вікна, WebGL програмний (swiftshader): плавність на відео уповільнена й не показова.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TUT = Path(__file__).resolve().parent
_git = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=TUT,
                      capture_output=True, text=True).stdout.strip()
KORIN = Path(_git).parent if _git else TUT.parents[1]
TEKA = KORIN / 'tmp' / 'znimky' / 'm6'
ADRESA = 'http://127.0.0.1:8760/m6/'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
ARGUMENTY = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
EKRANY = {'pk': (1440, 900), 'telefon': (390, 844)}
KAMERY = {
    'podil': {'pk': '#13.2/50.4655/30.5155/0/40', 'telefon': '#12.9/50.4655/30.5155/0/40'},
    'kvartaly': {'pk': '#14.6/50.4500/30.5230/0/40', 'telefon': '#14.6/50.4500/30.5230/0/40'},
}
ZUMY = [9.3, 9.6, 9.8, 10.0, 10.4, 11.4, 12.0, 12.1, 12.2, 12.3, 12.4, 12.5, 12.6, 12.7, 12.8, 13.6, 14.0, 14.6]
PLASHKY = ['#lehenda', '#verkh', '#f3d', '#ftema', '#porivn', '.maplibregl-ctrl-bottom-right']
GOTOVO = 'window.MAKET && MAKET.map && MAKET.map.loaded() && MAKET.stan.vyrosly && MAKET.stan.pryletily'

_N = [0]


def ity(s, adresa: str) -> None:
    """Перехід із перезавантаженням: адреса, що відрізняється лише камерою після #, сторінку не перезавантажує."""
    _N[0] += 1
    zapyt, _, kamera = adresa.partition('#')
    s.goto(f'{zapyt}{"&" if "?" in zapyt else "?"}n={_N[0]}' + (f'#{kamera}' if kamera else ''))


def chekaty(s, sek=1.5):
    s.wait_for_function(GOTOVO, timeout=90000)
    s.wait_for_timeout(int(sek * 1000))


def mistsya(s):
    """Положення плашок на екрані (видимі), щоб порівняти до й після відкриття картки."""
    return s.evaluate('''sel=>Object.fromEntries(sel.map(q=>{const e=document.querySelector(q); if(!e) return [q,null];
      const r=e.getBoundingClientRect(), v=getComputedStyle(e).visibility!=='hidden'&&getComputedStyle(e).display!=='none';
      return [q,{x:Math.round(r.x),y:Math.round(r.y),w:Math.round(r.width),vydno:v}]}))''', PLASHKY)


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


def osnovni(pw):
    zvit = {}
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    for ekran, (w, h) in EKRANY.items():
        kont = novyi(b, ekran)
        s = kont.new_page()
        for tema in ('svitla', 'temna'):
            pref = f'k3-{ekran}-{tema}'
            ity(s, f'{ADRESA}?tema={tema}')
            chekaty(s)
            s.screenshot(path=str(TEKA / f'{pref}-1misto.png'))
            for i, (nazva, kam) in enumerate(KAMERY.items(), 2):
                ity(s, f'{ADRESA}?tema={tema}' + kam[ekran])
                chekaty(s)
                s.screenshot(path=str(TEKA / f'{pref}-{i}{nazva}.png'))
            ity(s, f'{ADRESA}?tema={tema}' + KAMERY['podil'][ekran])
            chekaty(s)
            do = mistsya(s)
            ok = kartka(s, w, h, ekran)
            s.wait_for_timeout(600)
            pislya = mistsya(s)
            s.screenshot(path=str(TEKA / f'{pref}-4kartka.png'))
            if ok:
                s.go_back()
                s.wait_for_timeout(600)
            zakryto = mistsya(s)
            zsuv = [q for q in PLASHKY if do[q] and pislya[q] and (do[q]['x'], do[q]['y']) != (pislya[q]['x'], pislya[q]['y'])]
            povernulos = all(do[q] == zakryto[q] for q in PLASHKY)
            ukryti = [q for q in PLASHKY if do[q] and do[q]['vydno'] and not pislya[q]['vydno']]
            zvit[pref] = s.evaluate('({pomylky:MAKET.stan.pomylky, zaslony:MAKET.stan.zaslony})') | {
                'kartka': ok, 'nazad_zakryv': s.evaluate('document.getElementById("kartka").hidden'),
                'zsunulys': zsuv, 'skhovani_pid_kartkoyu': ukryti, 'povernulys': povernulos}
        # шрифти: місто з картою, щоб порівняти Plex і Arsenal з Fixel
        for f in ('plex', 'arsenal'):
            ity(s, f'{ADRESA}?f={f}' + KAMERY['podil'][ekran])
            chekaty(s)
            kartka(s, w, h, ekran)
            s.screenshot(path=str(TEKA / f'shryft-{f}-{ekran}.png'))
        kont.close()
    b.close()
    return zvit


def vau(pw):
    """Кожен «вау» окремо (ПК, обидві теми; хвиля й переліт — ще й телефон) і відео першого відкриття."""
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    for tema in ('svitla', 'temna'):
        for ekran in ('pk', 'telefon'):
            kont = novyi(b, ekran, ruh=True)
            s = kont.new_page()
            # Світло — статичне: місто й Поділ
            ity(s, f'{ADRESA}?tema={tema}&vau=svitlo')
            chekaty(s)
            s.screenshot(path=str(TEKA / f'vau-svitlo-{ekran}-{tema}-1misto.png'))
            ity(s, f'{ADRESA}?tema={tema}&vau=svitlo' + KAMERY['podil'][ekran])
            chekaty(s)
            s.screenshot(path=str(TEKA / f'vau-svitlo-{ekran}-{tema}-2podil.png'))
            # Хвиля і переліт — посередині й наприкінці (перше відкриття — без камери в адресі)
            for v, sered in (('khvylya', 450), ('perelit', 1400)):
                ity(s, f'{ADRESA}?tema={tema}&vau={v}')
                s.wait_for_function('window.MAKET && MAKET.map && MAKET.map.loaded()', timeout=90000)
                s.wait_for_timeout(sered)
                s.screenshot(path=str(TEKA / f'vau-{v}-{ekran}-{tema}-1seredyna.png'))
                chekaty(s, 1)
                s.screenshot(path=str(TEKA / f'vau-{v}-{ekran}-{tema}-2kinets.png'))
            kont.close()
    # Відео першого відкриття: кожен окремо й усі три разом (ПК, світла; усі разом — ще й темна і телефон)
    for nazva, par, ekran in (('khvylya', 'vau=khvylya', 'pk'), ('perelit', 'vau=perelit', 'pk'),
                              ('usi', 'vau=khvylya,svitlo,perelit', 'pk'),
                              ('usi-temna', 'vau=khvylya,svitlo,perelit&tema=temna', 'pk'),
                              ('usi-telefon', 'vau=khvylya,svitlo,perelit', 'telefon')):
        vid = TEKA / f'_video_{nazva}'
        kont = novyi(b, ekran, ruh=True, video=vid)
        s = kont.new_page()
        ity(s, f'{ADRESA}?{par}')
        chekaty(s, 2)
        kont.close()
        for f in vid.glob('*.webm'):
            shutil.move(str(f), TEKA / f'vidkryttya-{nazva}.webm')
        shutil.rmtree(vid, ignore_errors=True)
    b.close()


def zum(pw):
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    for tema in ('svitla', 'temna'):
        kont = novyi(b, 'pk')
        s = kont.new_page()
        for i, z in enumerate(ZUMY, 1):
            ity(s, f'{ADRESA}?tema={tema}#{z}/50.4600/30.5170/0/40')
            chekaty(s, 1.2)
            s.screenshot(path=str(TEKA / f'zum-{tema}-{i:02d}-z{z}.png'))
        kont.close()
        vid = TEKA / f'_video_zum_{tema}'
        kont = novyi(b, (1280, 800), video=vid)
        s = kont.new_page()
        ity(s, f'{ADRESA}?tema={tema}#9.6/50.4600/30.5170/0/40')
        chekaty(s, 2)
        s.evaluate('MAKET.map.easeTo({zoom:14.6,center:[30.5170,50.4600],duration:12000,easing:t=>t})')
        s.wait_for_timeout(13500)
        kont.close()
        for f in vid.glob('*.webm'):
            shutil.move(str(f), TEKA / f'zum-{tema}.webm')
        shutil.rmtree(vid, ignore_errors=True)
    b.close()


def chastky(pw):
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    kont = novyi(b, 'pk')
    s = kont.new_page()
    vyhid = {}
    for d in ('', 'x5', 'x20', 'nerivni'):
        for tema in ('svitla', 'temna'):
            ity(s, f'{ADRESA}?dani={d}&tema={tema}')
            chekaty(s, .5)
            vyhid[f'{d or "2024-2026"}-{tema}'] = s.evaluate('MAKET.chastky()')
        if d:
            ity(s, f'{ADRESA}?dani={d}')
            chekaty(s)
            s.screenshot(path=str(TEKA / f'dani-{d}-pk-svitla-1misto.png'))
    b.close()
    return vyhid


def main(arg: str | None = None) -> None:
    TEKA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        if arg == 'zum':
            zum(pw)
        elif arg == 'vau':
            vau(pw)
        elif arg == 'chastky':
            print(json.dumps(chastky(pw), ensure_ascii=False))
        else:
            print(json.dumps(osnovni(pw), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
