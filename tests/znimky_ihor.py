"""Знімки ігор у карті (ZAVDANNYA-117): комп'ютер 1280 px і телефон 390 px. Заодно проходить усі ігри дотиками по карті.

Запуск: python tests/znimky_ihor.py [тека-для-знімків] [зібраний-сайт] [--tema dark] [--lyshe 2,9,…]
--tema dark — темна тема (як у телефоні з темним налаштуванням, MV-131); --lyshe — лише знімки з цими номерами.
Без сайту — збирає демо: штучне місто (tests/shtuchne_misto.py) і демо-колода; для «Вулиці дня» дописує демо-загадку
(справжня — з повного випуску, ZAVDANNYA-114). Підкладку (tiles.openfreemap.org) вимкнено — знімки однакові без мережі.
День детектива задається параметром сторінки ?ihry-den=N&ihry-hodyna=H (режим перегляду: бали тоді не нараховуються).
Друкує помилки сторінки; є помилки — код виходу 1.
"""
from __future__ import annotations

import functools
import http.server
import json
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
from test_zahlushka import CHROME  # noqa: E402

ARG = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']


def demo_sait(teka: Path) -> Path:
    import zibraty_sait as Z
    baza = teka / 'events.db'
    subprocess.run([sys.executable, str(KORIN / 'tests' / 'shtuchne_misto.py'), str(baza)], check=True, capture_output=True)
    sait = teka / 'sait'
    Z.zibraty_sait(baza, sait, None, KORIN / 'data' / 'borders.json')
    (sait / 'vulytsia-demo.json').write_text(json.dumps(demo_vulytsia(sait), ensure_ascii=False), encoding='utf-8')
    return sait


def demo_vulytsia(sait: Path) -> dict:
    """Демо «Вулиці дня» з вулиць штучного міста (на демо-колоді загадок не виходить): одна загадка — Хрещатик, позначена
    як спальний район (щоб на знімку були всі підказки робочої версії ZAVDANNYA-114). Повертає назви для спроб."""
    p = json.loads((sait / 'karta' / 'poshuk.json').read_text(encoding='utf-8'))
    vul = [[v[2], v[0], v[0].split(' ')[0] if v[0].split(' ')[0] in ('вулиця', 'проспект', 'бульвар') else 'вулиця', v[1],
            v[5], 'ДТП', v[4], v[3], ''] for v in p['vulytsi'] if v[1]]
    tsil = next((v for v in vul if 'Хрещатик' in v[1]), vul[0])
    inshi = [v[1] for v in vul if v[0] != tsil[0]][:2]
    d = {'versiia': 2, 'demo': True, 'sprob': 7, 'roky': '2024–2026', 'vulytsi': vul,
         'zahadky': [{'slug': tsil[0], 'spalnyi': True, 'chastyna': 'північно-західна частина району',
                      'zvuzhennia': {'vsi': len(vul), 'rayon': 28, 'vyrizn': 6, 'n': 2, 'typ': 1},
                      'podiia': {'vyd': 'ДТП', 'rik': 2025, 'opys': 'Демо: водій не пропустив пішохода на переході.',
                                 'url': '', 'nomer': ''}}]}
    (sait / 'ihry' / 'vulytsia-dnia.json').write_text(json.dumps(d, ensure_ascii=False), encoding='utf-8')
    for f in ('index.html', 'karta/index.html'):
        t = (sait / f).read_text(encoding='utf-8')
        (sait / f).write_text(t.replace('data-spravy=', 'data-vulytsia="/ihry/vulytsia-dnia.json" data-spravy='), encoding='utf-8')
    return {'tsil': tsil[1], 'inshi': inshi}


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    tema = 'light'
    if '--tema' in argv:
        i = argv.index('--tema'); tema = argv[i + 1]; argv = argv[:i] + argv[i + 2:]
    lyshe = None
    if '--lyshe' in argv:
        i = argv.index('--lyshe'); lyshe = set(argv[i + 1].split(',')); argv = argv[:i] + argv[i + 2:]
    teka = Path(argv[0]) if argv else KORIN / 'docs' / 'znimky-117'
    teka.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.TemporaryDirectory()
    sait = Path(argv[1]).resolve() if len(argv) > 1 else demo_sait(Path(tmp.name))
    obr = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(sait))
    http.server.SimpleHTTPRequestHandler.log_message = lambda *a: None
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), obr)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_address[1]}'
    pomylky: list[str] = []
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=CHROME, args=ARG)
            for ekran, w, h, tel in (('1280', 1280, 860, False), ('390', 390, 844, True)):
                k = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=2, is_mobile=tel, has_touch=tel,
                                  color_scheme=tema)
                k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
                s = k.new_page()
                s.on('pageerror', lambda e: pomylky.append(f'{ekran}: {e}'))
                s.on('console', lambda m: m.type == 'error' and 'ERR_FAILED' not in m.text and pomylky.append(f'{ekran}: {m.text}'))

                def zaity(shlyakh: str) -> None:
                    s.goto(url + shlyakh)
                    s.wait_for_function('() => window.MvKarta && MvKarta.gotovo', timeout=40000)
                    s.wait_for_timeout(900)

                def dotyk(lat: float, lon: float) -> None:
                    s.evaluate('''([la, lo]) => { const k = MvKarta.karta; const p = k.project([lo, la]);
                        k.fire('click', {point: p, lngLat: k.unproject(p)}); }''', [lat, lon])
                    s.wait_for_timeout(700)

                def znimok(nazva: str) -> None:
                    if lyshe is not None and nazva.split('-')[0] not in lyshe:
                        return
                    s.wait_for_timeout(400)
                    s.screenshot(path=str(teka / f'{nazva}-{ekran}{"-temna" if tema == "dark" else ""}.png'))

                # 1. Меню ігор
                zaity('/karta/?ihry&ihry-den=4')
                znimok('1-menyu')
                # 2. Детектив, четвер: знайти слід 1 дотиком біля «Святошина», подати версію
                s.evaluate('() => localStorage.clear()')
                zaity('/karta/?hra=detektyv&ihry-den=4')
                s.click('[data-i="shukaty"][data-n="1"]')
                dotyk(50.4500, 30.30)          # мимо
                dotyk(50.4580, 30.3905)        # «Святошин»
                s.select_option('[data-pole="de"]', 'sviatoshyn')
                s.select_option('[data-pole="shcho"]', 'hrabizh')
                s.select_option('[data-pole="koly"]', 'vechir')
                s.select_option('[data-pole="pole"]', 'telefon')
                s.click('[data-i="versiia"]')
                s.click('[data-i="pokazaty-mistsia"]')
                s.wait_for_timeout(1500)
                znimok('2-detektyv-slid')
                # 3. Неділя після 20:00 — розкриття
                zaity('/karta/?hra=detektyv&ihry-den=7&ihry-hodyna=21')
                s.evaluate('() => { const p = document.getElementById("ihry"); p.scrollTop = document.querySelector(".i-rozkr").offsetTop - 64; window.scrollTo(0, 0); }')
                znimok('3-detektyv-rozkryttia')
                # 4. «Вгадай, де це було» на карті
                zaity('/karta/?hra=vgadai&ihry-den=2')
                s.click('[data-i="vgadai-start"][data-typ="den"]')
                s.wait_for_timeout(500)
                znimok('4-vgadai-podiia')
                dotyk(50.4501, 30.5234)
                s.wait_for_timeout(1200)
                znimok('5-vgadai-rezultat')
                # 5. «Кваліфікуй», режим для студентів
                zaity('/karta/?hra=kvalifikuy&ihry-den=2')
                s.click('[data-r="student"]')
                s.click('[data-i="kv-start"]')
                znimok('6-kvalifikuy-sprava')
                s.click('.i-var >> nth=0')
                ch = s.query_selector('.i-ch label')
                if ch:
                    ch.click()
                s.click('[data-i="kv-vidpovid"]')
                znimok('7-kvalifikuy-vidpovid')
                # 6. Бали й спроби
                zaity('/karta/?hra=bali&ihry-den=2')
                znimok('8-bali')
                # 7. «Вулиця дня» на карті: дві невдалі спроби (відкриваються підказки спального району), потім фінал
                s.evaluate('() => localStorage.clear()')
                zaity('/karta/?hra=vulytsia&ihry-den=2')
                vd = json.loads((sait / 'vulytsia-demo.json').read_text(encoding='utf-8')) if (sait / 'vulytsia-demo.json').exists() else None
                if vd and s.query_selector('#i-vul'):
                    for nazva in vd['inshi']:
                        s.fill('#i-vul', nazva)
                        s.wait_for_timeout(250)
                        s.press('#i-vul', 'Enter')
                        s.wait_for_timeout(1200)
                    znimok('9-vulytsia-pidkazky')
                    s.fill('#i-vul', vd['tsil'])
                    s.wait_for_timeout(250)
                    s.press('#i-vul', 'Enter')
                    s.wait_for_timeout(1800)
                    s.evaluate('() => { const p = document.getElementById("ihry"); const k = document.querySelector(".i-vd-kin"); if (k) p.scrollTop = k.offsetTop - 64; }')
                    znimok('9-vulytsia-final')
                else:
                    znimok('9-vulytsia')
                # 8. Тихе запрошення: після третього дотику до карти
                s.evaluate('() => { localStorage.clear(); sessionStorage.clear(); }')
                zaity('/karta/?ihry-den=3&ihry-zaproshennia')
                for _ in range(3):           # три дотики до карти (лише подія дотику — без відкриття картки соти)
                    s.dispatch_event('.maplibregl-canvas', 'pointerdown')
                    s.wait_for_timeout(250)
                s.wait_for_selector('#ihry-zaproshennia:not([hidden])', timeout=5000)
                znimok('0-zaproshennia')
                k.close()
            b.close()
    finally:
        server.shutdown()
        tmp.cleanup()
    for p in pomylky:
        print('ПОМИЛКА', p)
    print(f'Знімки: {teka}')
    return 1 if pomylky else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
