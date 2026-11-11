"""Знімки екрана гри «Вгадай, де це було» (ZAVDANNYA-07), 390 px і 1280 px.

Запуск: python tests/znimky_hry.py [тека-для-знімків]
За замовчуванням знімки йдуть у tmp/znimky/zavdannya-07/.
Сайт збирається з демо-колодою; сховище — локальна підміна (tests/zahlushka_pidmina.py),
нічого не надсилається назовні. Запити до підкладки карти (tiles.openfreemap.org)
у знімках ВИМКНЕНО навмисно: знімки однакові незалежно від мережі, на них видно
межу Києва з власного файлу. Як виглядає підкладка — перевіряється в браузері з мережею.

Знімки: меню; завдання; відповідь (і низ відповіді на телефоні); кінець раунду;
картинка «Поділитися» (раунд і подія дня); подія дня — відповідь і повторний вхід;
темна тема на телефоні: меню, завдання, відповідь, кінець раунду.
"""
from __future__ import annotations

import base64
import shutil
import sys
import tempfile
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import zibraty  # noqa: E402
import zahlushka_pidmina  # noqa: E402
from test_zahlushka import CHROME  # noqa: E402

ARGUMENTY_CHROME = ['--no-sandbox', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
# Зсув відповіді від справжнього місця в пікселях карти — щоб очки в раунді були різні.
ZSUVY = [(6, -4), (40, 25), (-18, 60), (90, -70), (3, 2), (-30, -20), (140, 60), (12, -40), (-60, 10), (25, 15)]


def pochekaty_kartu(s):
    s.wait_for_function('() => !!(window.MvHraKarta && MvHraKarta.ostannia && MvHraKarta.ostannia.karta.loaded())', timeout=20000)
    s.wait_for_timeout(500)


def torknutysia_bilia_spravzhnoho(s, zsuv):
    """Тап по карті поруч зі справжнім місцем поточної події (зсув — у пікселях)."""
    t = s.evaluate('''() => { const st = MvHra.stan, p = st.spysok[st.i];
        const k = MvHraKarta.ostannia.karta, xy = k.project([p.lon, p.lat]);
        const r = document.getElementById('karta').getBoundingClientRect();
        return { x: r.left + xy.x, y: r.top + xy.y, w: r.width, h: r.height, l: r.left, t: r.top }; }''')
    if s.context.__dict__.get('_telefon'):          # на телефоні вся карта Києва дрібніша
        zsuv = (zsuv[0] / 4, zsuv[1] / 4)
    x = min(max(t['x'] + zsuv[0], t['l'] + 60), t['l'] + t['w'] - 60)
    y = min(max(t['y'] + zsuv[1], t['t'] + 60), t['t'] + t['h'] - 60)
    if s.context.__dict__.get('_telefon'):
        s.touchscreen.tap(x, y)
    else:
        s.mouse.click(x, y)
    s.wait_for_timeout(150)


def zberehty_kartku(s, shlyakh):
    dani = s.evaluate('() => MvHraKartka.namaluvaty(MvHra.daniKartky()).toDataURL("image/png")')
    Path(shlyakh).write_bytes(base64.b64decode(dani.split(',', 1)[1]))


def main() -> int:
    from playwright.sync_api import sync_playwright
    if not CHROME:
        print('Немає Chrome / Chromium — знімків не буде.')
        return 1
    teka = Path(sys.argv[1]) if len(sys.argv) > 1 else KORIN / 'tmp' / 'znimky' / 'zavdannya-07'
    teka.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp())
    server, skh, url = zahlushka_pidmina.zapustyty(str(tmp))
    zibraty.zibraty(tmp / 'zahlushka', url, zahlushka_pidmina.PUBLICHNYI, {}, False)
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=CHROME, args=ARGUMENTY_CHROME)
            for shyryna, tema in ((1280, 'light'), (390, 'light'), (390, 'dark')):
                telefon = shyryna < 600
                k = b.new_context(viewport={'width': shyryna, 'height': 844 if telefon else 860},
                                  device_scale_factor=2 if telefon else 1, color_scheme=tema,
                                  has_touch=telefon, is_mobile=telefon)
                k.__dict__['_telefon'] = telefon
                k.route('https://tiles.openfreemap.org/**', lambda r: r.abort())
                s = k.new_page()
                dod = '-temna' if tema == 'dark' else ''
                imya = lambda nazva: str(teka / f'{nazva}-{shyryna}{dod}.png')  # noqa: E731

                s.goto(f'{url}/zahlushka/hra/?nasinnya=znimok&dzherelo=znimok')
                s.evaluate('document.fonts.ready')
                s.wait_for_selector('#pochaty-raund')
                s.wait_for_timeout(300)
                s.screenshot(path=imya('menyu'), full_page=True)

                s.click('#pochaty-raund')
                pochekaty_kartu(s)
                s.screenshot(path=imya('zavdannya'))
                for i, zsuv in enumerate(ZSUVY):
                    if i:
                        s.click('#dali')
                        s.wait_for_timeout(250)
                    torknutysia_bilia_spravzhnoho(s, zsuv)
                    if i == 0:
                        s.screenshot(path=imya('zavdannya-poznachka'))
                    s.click('#vidpovisty')
                    if i == 1:
                        s.wait_for_timeout(1200)
                        s.screenshot(path=imya('vidpovid'))
                        if telefon:
                            s.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                            s.wait_for_timeout(300)
                            s.screenshot(path=imya('vidpovid-nyz'))
                            s.evaluate('window.scrollTo(0, 0)')
                s.click('#dali')
                s.wait_for_selector('#ekran-kinets:not([hidden])')
                s.wait_for_timeout(300)
                s.screenshot(path=imya('kinets'), full_page=True)
                if tema == 'light' and not telefon:
                    zberehty_kartku(s, teka / 'podilytysia-raund-1080x1350.png')

                if tema == 'light':
                    s.click('#do-menyu')
                    s.click('#pochaty-den')
                    pochekaty_kartu(s)
                    s.screenshot(path=imya('den-zavdannya'))
                    torknutysia_bilia_spravzhnoho(s, (35, -20))
                    s.click('#vidpovisty')
                    s.wait_for_timeout(1200)
                    s.screenshot(path=imya('den-vidpovid'))
                    if not telefon:
                        zberehty_kartku(s, teka / 'podilytysia-den-1080x1350.png')
                    # Повторний вхід того ж дня — показує вже зігране.
                    s.goto(f'{url}/zahlushka/hra/?dzherelo=znimok')
                    s.wait_for_selector('#pochaty-den')
                    s.wait_for_timeout(300)
                    s.screenshot(path=imya('menyu-den-zihrano'), full_page=True)
                    s.click('#pochaty-den')
                    pochekaty_kartu(s)
                    s.wait_for_timeout(500)
                    s.screenshot(path=imya('den-vzhe-zihrano'))
                k.close()
            b.close()
    finally:
        server.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print(f'Знімки — у {teka}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
