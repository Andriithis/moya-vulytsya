"""Знімки макета М5 (ZAVDANNYA-32): сім варіантів × ПК і телефон × світла й темна × місто, Поділ, квартали, картка;
плюс послідовність зуму місто → квартал і відео зуму для К1 і Б2.

Запуск (сервер макета працює на 8750): python maket/m5/znimky_m5.py [варіант]   або   ... zum
Знімки — у tmp/znimky/m5/ основної теки репозиторію (D:\\problem_orienting\\moya-vulytsya), не в git.
Браузер — Edge без вікна, WebGL програмний (swiftshader): плавність на знімках не показова, на відео — уповільнена.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

TUT = Path(__file__).resolve().parent
# Основна тека репозиторію (а не робоча копія git worktree): спільний каталог .git лежить у ній.
_git = subprocess.run(['git', 'rev-parse', '--path-format=absolute', '--git-common-dir'], cwd=TUT,
                      capture_output=True, text=True).stdout.strip()
KORIN = Path(_git).parent if _git else TUT.parents[1]
TEKA = KORIN / 'tmp' / 'znimky' / 'm5'
ADRESA = 'http://127.0.0.1:8750/m5/'
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
ARGUMENTY = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
EKRANY = {'pk': (1440, 900), 'telefon': (390, 844)}
# Камери у форматі адреси макета: зум/широта/довгота/поворот/нахил.
KAMERY = {
    'podil': {'pk': '#13.2/50.4655/30.5155/0/{p}', 'telefon': '#12.9/50.4655/30.5155/0/{p}'},
    'kvartaly': {'pk': '#14.6/50.4500/30.5230/0/{p}', 'telefon': '#14.6/50.4500/30.5230/0/{p}'},
}
# Варіант: (теми — перша за замовчуванням, нахил на Подолі й у кварталах).
VARIANTY = {'k1': (['svitla', 'temna'], 0), 'k2': (['svitla', 'temna'], 0), 'k3': (['svitla', 'temna'], 40),
            'a2': (['svitla', 'temna'], 0), 'b2': (['svitla', 'temna'], 45), 'v2': (['temna', 'svitla'], 45),
            'g': (['svitla', 'temna'], 0)}
ZUMY = [9.3, 9.6, 9.8, 10.0, 10.4, 11.4, 12.0, 12.2, 12.4, 12.6, 12.8, 13.6, 14.6]


_N = [0]


def ity(s, adresa: str) -> None:
    """Перехід із перезавантаженням: адреса, що відрізняється лише камерою після #, сторінку не перезавантажує."""
    _N[0] += 1
    zapyt, _, kamera = adresa.partition('#')
    s.goto(f'{zapyt}&n={_N[0]}' + (f'#{kamera}' if kamera else ''))


def chekaty(s, sek=1.5):
    s.wait_for_function('window.MAKET && MAKET.map && MAKET.map.loaded() && MAKET.stan.vyrosly', timeout=90000)
    s.wait_for_timeout(int(sek * 1000))


def kartka(s, w, h, ekran):
    """Клік по соті біля центру екрана; якщо там порожньо — трохи вбік (у 3D — по стовпчику під пальцем)."""
    for dx, dy in [(0, 0), (-60, 0), (60, 0), (0, -60), (-120, -60), (120, 60)]:
        s.mouse.click(w / 2 + dx, h / 2 + dy + (0 if ekran == 'pk' else -80))
        s.wait_for_timeout(1200)
        if not s.evaluate('document.getElementById("kartka").hidden'):
            return True
    return False


def osnovni(pw, tilky):
    zvit = {}
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    for v, (temy, p) in VARIANTY.items():
        if tilky and v != tilky:
            continue
        for ekran, (w, h) in EKRANY.items():
            kont = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1, reduced_motion='reduce',
                                 is_mobile=ekran == 'telefon', has_touch=ekran == 'telefon')
            s = kont.new_page()
            for tema in temy:
                pref = f'{v}-{ekran}-{tema}'
                ity(s, f'{ADRESA}?v={v}&tema={tema}')
                chekaty(s)
                s.screenshot(path=str(TEKA / f'{pref}-1misto.png'))
                for i, (nazva, kam) in enumerate(KAMERY.items(), 2):
                    ity(s, f'{ADRESA}?v={v}&tema={tema}' + kam[ekran].format(p=p))
                    chekaty(s)
                    s.screenshot(path=str(TEKA / f'{pref}-{i}{nazva}.png'))
                ity(s, f'{ADRESA}?v={v}&tema={tema}' + KAMERY['podil'][ekran].format(p=p))
                chekaty(s)
                ok = kartka(s, w, h, ekran)
                s.screenshot(path=str(TEKA / f'{pref}-4kartka.png'))
                # «Назад» закриває картку
                if ok:
                    s.go_back()
                    s.wait_for_timeout(600)
                zakryv = s.evaluate('document.getElementById("kartka").hidden')
                zvit[pref] = s.evaluate('({pomylky:MAKET.stan.pomylky, zaslony:MAKET.stan.zaslony})') | {
                    'kartka': ok, 'nazad_zakryv': zakryv}
            kont.close()
    b.close()
    return zvit


def zum(pw):
    """Послідовність зуму й відео для К1 і Б2 (ПК, світла)."""
    b = pw.chromium.launch(executable_path=EDGE, args=ARGUMENTY)
    for v, p in [('k1', 0), ('b2', 45)]:
        kont = b.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
        s = kont.new_page()
        for i, z in enumerate(ZUMY, 1):
            ity(s, f'{ADRESA}?v={v}#{z}/50.4600/30.5170/0/{p}')
            chekaty(s, 1.2)
            s.screenshot(path=str(TEKA / f'zum-{v}-{i:02d}-z{z}.png'))
        kont.close()
        # Відео: одна безперервна анімація камери місто → квартал, 10 с.
        vid = TEKA / f'_video_{v}'
        kont = b.new_context(viewport={'width': 1280, 'height': 800}, record_video_dir=str(vid),
                             record_video_size={'width': 1280, 'height': 800})
        s = kont.new_page()
        ity(s, f'{ADRESA}?v={v}#9.6/50.4600/30.5170/0/{p}')
        chekaty(s, 2)
        s.evaluate('MAKET.map.easeTo({zoom:14.6,center:[30.5170,50.4600],duration:10000,easing:t=>t})')
        s.wait_for_timeout(11500)
        kont.close()
        for f in vid.glob('*.webm'):
            shutil.move(str(f), TEKA / f'zum-{v}.webm')
        shutil.rmtree(vid, ignore_errors=True)
    b.close()


def main(arg: str | None = None) -> None:
    TEKA.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        if arg == 'zum':
            zum(pw)
        else:
            print(json.dumps(osnovni(pw, arg), ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else None)
