"""Знімки прикладів настрою (ZAVDANNYA-42, етап А, п. 1) — лише для внутрішнього порівняння, у tmp/znimky/m7/nastrii/."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

TEKA = Path(r'D:\problem_orienting\moya-vulytsya\tmp\znimky\m7\nastrii')
EDGE = r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
PRYKLADY = [l.split(' ', 1) for l in Path(sys.argv[1]).read_text(encoding='utf-8').splitlines() if l.strip()]
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path=EDGE, args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'])
    k = b.new_context(viewport={'width': 1440, 'height': 900}, locale='en-US')
    for nazva, url in PRYKLADY:
        s = k.new_page()
        try:
            s.goto(url, timeout=45000, wait_until='domcontentloaded')
            s.wait_for_timeout(7000)
            s.screenshot(path=str(TEKA / f'{nazva}.png'))
            print('OK', nazva, s.title()[:70])
        except Exception as e:
            print('ПОМИЛКА', nazva, str(e)[:90])
        s.close()
