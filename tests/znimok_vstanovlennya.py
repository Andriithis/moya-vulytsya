"""Знімок головної в звичайному (не безголовому) Chrome з кнопкою «Встановити» в адресному рядку.

Кнопку малює сам Chrome поза сторінкою, тому звичайний знімок сторінки її не бачить:
скрипт запускає Chrome на віртуальному екрані і знімає весь екран.
Запуск: xvfb-run -a -s "-screen 0 1280x900x24" python tests/znimok_vstanovlennya.py [файл.png]
Потрібні Playwright, Chrome, Xvfb і ImageMagick (команда import).
"""
import subprocess, sys, tempfile, time
from pathlib import Path
KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka')); sys.path.insert(0, str(KORIN / 'tests'))
import zibraty, zahlushka_pidmina
from test_zahlushka import CHROME
from playwright.sync_api import sync_playwright
tmp = Path(tempfile.mkdtemp())
server, skh, url = zahlushka_pidmina.zapustyty(str(tmp))
zibraty.zibraty(tmp / 'zahlushka', url, zahlushka_pidmina.PUBLICHNYI, {}, False)
vykhid = sys.argv[1] if len(sys.argv) > 1 else str(KORIN / 'tmp' / 'znimky' / 'zavdannya-06' / 'holovna-knopka-vstanovlennya-1280.png')
with sync_playwright() as pw:
    k = pw.chromium.launch_persistent_context(tempfile.mkdtemp(), executable_path=CHROME, headless=False,
        args=['--no-sandbox', '--window-size=1280,900', '--window-position=0,0', '--disable-features=Translate', '--lang=uk'], no_viewport=True)
    s = k.pages[0] if k.pages else k.new_page()
    s.goto(f'{url}/zahlushka/index.html?dzherelo=znimok')
    s.evaluate('navigator.serviceWorker.ready.then(() => true)')
    time.sleep(6)
    cdp = k.new_cdp_session(s)
    print('installabilityErrors', cdp.send('Page.getInstallabilityErrors'))
    subprocess.run(['import', '-window', 'root', vykhid], check=True)
    k.close()
server.shutdown()
