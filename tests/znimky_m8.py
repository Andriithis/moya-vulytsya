"""Знімки справжнього сайту у вигляді М7 (ZAVDANNYA-45): місто, Поділ, квартал, картка, пошук, сторінка вулиці;
ПК і телефон; світла й темна. Відео пошуку з перельотом.

Запуск (сайт зібрано site/zibraty_sait.py і віддано локальним сервером, напр. на 8763):
  python tests/znimky_m8.py [адреса] [тека]
  python tests/znimky_m8.py http://127.0.0.1:8763 D:\\problem_orienting\\moya-vulytsya\\tmp\\znimky\\m8
Браузер — Edge або Chrome без вікна (MV_CHROME — шлях), WebGL програмний (swiftshader): плавність на відео уповільнена.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
EDGE = [os.environ.get('MV_CHROME'), r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
        r'C:\Program Files\Microsoft\Edge\Application\msedge.exe', shutil.which('google-chrome'), shutil.which('chromium')]
ARGUMENTY = ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--no-sandbox']
EKRANY = {'pk': (1440, 900, False), 'telefon': (390, 844, True)}
KAMERY = {   # ті самі місця, що й у знімках М7
    '1misto': {'pk': '', 'telefon': ''},
    '2podil': {'pk': '#13.2/50.4655/30.5155/0/40', 'telefon': '#12.9/50.4655/30.5155/0/40'},
    '3kvartal': {'pk': '#15.2/50.4640/30.5160/0/40', 'telefon': '#15.0/50.4640/30.5160/0/40'},
}
GOTOVO = '() => window.MvKarta && MvKarta.karta && MvKarta.gotovo && MvKarta.karta.loaded()'


def brauzer() -> str | None:
    return next((p for p in EDGE if p and Path(p).is_file()), None)


def spokii(s, mezha_ms: int = 20000) -> None:
    """Чекати, доки карта домалює підкладку (подія idle), але не довше межі — програмний WebGL повільний."""
    s.evaluate('''(m) => new Promise(r => { const k = MvKarta.karta; if (k.loaded() && !k.isMoving()) return r();
        const t = setTimeout(r, m); k.once('idle', () => { clearTimeout(t); r(); }); })''', mezha_ms)


def chekaty(s, sek: float = 2.5) -> None:
    s.wait_for_function(GOTOVO, timeout=90000)
    spokii(s)
    s.wait_for_timeout(int(sek * 1000))


def natysnuty_sotu(s, ekran: str) -> bool:
    """Клік у середину однієї з вершин (як людина), доки не відкриється картка."""
    # Найближчі до середини вільної частини карти (ліворуч від картки) — як у знімках М7.
    for k in s.evaluate('''(pk) => { const id = MvKarta.colG(), W = innerWidth - (pk ? 400 : 0), H = innerHeight * (pk ? 0.55 : 0.35);
            return MvKarta.vershyny(id).map(k => { const p = MvKarta.karta.project(MvKarta.tsentr(id, k)); return [p.x, p.y]; })
              .sort((a, b) => Math.hypot(a[0] - W / 2, a[1] - H) - Math.hypot(b[0] - W / 2, b[1] - H)).slice(0, 40); }''', ekran == 'pk'):
        x, y = k
        w, h = s.viewport_size['width'], s.viewport_size['height']
        if not (40 < x < w - (420 if ekran == 'pk' else 40) and 150 < y < h * (0.9 if ekran == 'pk' else 0.5)):
            continue
        s.mouse.click(x, y)
        s.wait_for_timeout(900)
        if not s.evaluate('document.getElementById("kartka").hidden'):
            return True
    return False


def main(argv: list[str]) -> int:
    from playwright.sync_api import sync_playwright
    adresa = (argv[0] if argv else 'http://127.0.0.1:8763').rstrip('/')
    teka = Path(argv[1]) if len(argv) > 1 else KORIN / 'tmp' / 'znimky' / 'm8'
    teka.mkdir(parents=True, exist_ok=True)
    pomylky = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=brauzer(), args=ARGUMENTY)
        for tema in ('svitla', 'temna'):
            for ekran, (w, h, tel) in EKRANY.items():
                k = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1, is_mobile=tel, has_touch=tel,
                                  color_scheme='light', reduced_motion='reduce')
                k.add_init_script(f"try {{ localStorage.setItem('mv-tema', '{tema}'); }} catch (e) {{}}")
                s = k.new_page()
                s.on('console', lambda m: m.type == 'error' and pomylky.append(f'{s.url}: {m.text[:160]}'))
                s.on('pageerror', lambda e: pomylky.append(str(e)))
                for nazva, kam in KAMERY.items():
                    s.goto(adresa + '/' + kam[ekran])
                    s.reload()
                    chekaty(s)
                    s.screenshot(path=str(teka / f'{ekran}-{tema}-{nazva}.png'))
                # Картка: на Подолі натиснути вершину.
                s.goto(adresa + '/' + KAMERY['2podil'][ekran]); s.reload(); chekaty(s)
                if not natysnuty_sotu(s, ekran):
                    pomylky.append(f'{ekran}-{tema}: картка не відкрилася')
                s.wait_for_timeout(600)
                s.screenshot(path=str(teka / f'{ekran}-{tema}-4kartka.png'))
                # Пошук: «Хрещатик» → переліт → картка.
                s.goto(adresa + '/'); s.reload(); chekaty(s, 1.5)
                s.click('#poshuk-karty')
                s.keyboard.type('хрещ', delay=60)
                s.wait_for_timeout(700)
                s.screenshot(path=str(teka / f'{ekran}-{tema}-5poshuk.png'))
                s.keyboard.press('Enter')
                s.wait_for_timeout(2500)
                s.wait_for_function('() => !document.getElementById("kartka").hidden', timeout=15000)
                spokii(s)
                s.wait_for_timeout(800)
                s.screenshot(path=str(teka / f'{ekran}-{tema}-6poshuk-kartka.png'))
                # Фільтр відкрито.
                s.keyboard.press('Escape'); s.wait_for_timeout(300)
                s.click('.f-knopka'); s.wait_for_timeout(300)
                s.screenshot(path=str(teka / f'{ekran}-{tema}-7filtr.png'))
                s.click('.f-knopka')
                s.click('#finfo'); s.wait_for_timeout(300)
                s.screenshot(path=str(teka / f'{ekran}-{tema}-8info.png'))
                # Сторінка вулиці.
                s.goto(adresa + '/vulytsia/khreshchatyk/')
                s.wait_for_function('() => window.MvKarta && MvKarta.karta && MvKarta.karta.loaded()', timeout=60000)
                spokii(s)
                s.wait_for_timeout(1000)
                s.screenshot(path=str(teka / f'{ekran}-{tema}-9vulytsia.png'), full_page=True)
                k.close()
        # Відео пошуку з перельотом (ПК, світла, рух як у звичайній системі).
        k = b.new_context(viewport={'width': 1280, 'height': 800}, record_video_dir=str(teka / 'video'),
                          record_video_size={'width': 1280, 'height': 800})
        s = k.new_page()
        s.goto(adresa + '/'); chekaty(s, 2)
        s.click('#poshuk-karty'); s.keyboard.type('андріївський', delay=90); s.wait_for_timeout(900)
        s.keyboard.press('Enter'); s.wait_for_timeout(4000)
        s.click('#poshuk-karty'); s.fill('#poshuk-karty', ''); s.keyboard.type('оболонський', delay=90); s.wait_for_timeout(900)
        s.keyboard.press('Enter'); s.wait_for_timeout(3500)
        video = s.video.path()
        k.close()
        shutil.move(video, teka / 'poshuk-perelit.webm')
        shutil.rmtree(teka / 'video', ignore_errors=True)
        b.close()
    print('Помилки:', pomylky or 'немає')
    print(f'Знімки — у {teka}')
    return 1 if pomylky else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
