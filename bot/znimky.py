"""Знімки розмов бота й дописів каналів для docs/BOT-I-KANALY.md (ZAVDANNYA-97).

    python bot/znimky.py docs/znimky-97

Розмови — справжній вивід `bot/rozmova.py` і `bot/kanaly.py`, але на **штучному** покажчику з тестів
(`tests/test_bot.py`, INDEKS): репозиторій публічний, а справжні числа будинків ще не опубліковані.
Вигляд — схематичний чат Telegram на телефоні (390 px), не копія Telegram.
"""
from __future__ import annotations

import html
import sys
from datetime import date
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parent
sys.path.insert(0, str(TUT))
sys.path.insert(0, str(KORIN / 'tests'))
sys.path.insert(0, str(KORIN / 'site'))

import kanaly as K  # noqa: E402
import rozmova as R  # noqa: E402
import stezhennia as S  # noqa: E402
from test_bot import INDEKS  # noqa: E402

STYL = '''
*{box-sizing:border-box}body{margin:0;font:15px/1.4 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;background:#cfd8e6}
.shapka{background:#4b4fc4;color:#fff;padding:12px 16px;font-weight:600}.shapka small{display:block;font-weight:400;opacity:.8}
.chat{padding:10px 10px 16px;display:flex;flex-direction:column;gap:6px}
.m{max-width:86%;padding:8px 11px;border-radius:14px;white-space:pre-wrap;word-wrap:break-word;box-shadow:0 1px 1px rgba(0,0,0,.12)}
.ya{align-self:flex-end;background:#e1f7d3;border-bottom-right-radius:4px}.bot{align-self:flex-start;background:#fff;border-bottom-left-radius:4px}
.kn{align-self:flex-start;width:86%;display:flex;flex-direction:column;gap:4px;margin-top:-2px}
.kn div{display:flex;gap:4px}.kn span{flex:1;text-align:center;background:rgba(75,79,196,.14);color:#2b2f8f;border-radius:8px;
padding:7px 6px;font-size:14px;font-weight:500}.kn span.u::after{content:" ↗";font-size:11px}
.mitka{align-self:center;background:rgba(0,0,0,.18);color:#fff;font-size:12px;padding:2px 9px;border-radius:10px;margin:4px 0}
.poll b{display:block;margin-bottom:6px}.poll i{display:block;font-style:normal;border:1px solid #c9cde8;border-radius:8px;padding:5px 9px;margin:4px 0}
.poll i.ok{border-color:#3aa57a;background:#e3f6ee}.poll small{display:block;color:#666;margin-top:6px}
'''


def e(t: str) -> str:
    return html.escape(t)


def bulbashka(v: R.Vidpovid) -> str:
    kn = ''
    if v.knopky:
        kn = '<div class="kn">' + ''.join('<div>' + ''.join(
            f'<span class="{"u" if k.url else ""}">{e(k.tekst)}</span>' for k in ryad) + '</div>' for ryad in v.knopky) + '</div>'
    return f'<div class="m bot">{e(v.tekst)}</div>{kn}'


def storinka(nazva: str, pidpys: str, tilo: str) -> str:
    return (f'<!doctype html><meta charset="utf-8"><style>{STYL}</style>'
            f'<div class="shapka">{e(nazva)}<small>{e(pidpys)}</small></div><div class="chat">{tilo}</div>')


def rozmova(sc: str, kroky: list) -> str:
    b = R.Bot(INDEKS, S.Skhovyshche(), sc)
    tilo = [bulbashka(b.povidomlennia(1, '/start'))]
    ostannia = None
    for k in kroky:
        if k.startswith('!'):
            knopky = [x for ryad in ostannia.knopky for x in ryad]
            kn = knopky[int(k[1:]) - 1]
            tilo.append(f'<div class="mitka">натиснуто «{e(kn.tekst)}»</div>')
            ostannia = b.natysnuto(1, kn.dani, '2026-11-17')
        else:
            tilo.append(f'<div class="m ya">{e(k)}</div>')
            ostannia = b.povidomlennia(1, k)
        tilo.append(bulbashka(ostannia))
    return ''.join(tilo)


def nove() -> str:
    skh = S.Skhovyshche()
    b = R.Bot(INDEKS, skh, 'a')
    b.natysnuto(1, 's:' + R.kod('/budynok/khreshchatyk/22/'), '2026-11-17')
    import json
    i2 = json.loads(json.dumps(INDEKS))
    i2['misiatsi_1551'] = ['2025-12', '2026-11']
    i2['budynky'][1]['pv'] = 1
    v = R.Bot(i2, skh, 'a').nove(skh.usi()[0])
    return '<div class="mitka">понеділок, щотижневе повідомлення</div>' + bulbashka(v)


def kanal() -> str:
    h = K.Henerator(INDEKS)
    p = h.pachka(date(2026, 11, 23), 7)
    sh = [d for d in p if d['rayon'] == 'Шевченківський']
    tilo = []
    for d in sh:
        if d['typ'] not in ('istoriia', 'vhadai', 'tsyfry'):
            continue
        tilo.append(f'<div class="mitka">{K.DNI_TYZHNIA[date.fromisoformat(d["data"]).weekday()]}</div>')
        kn = [[R.Knopka(k['tekst'], url=k['url']) for k in ryad] for ryad in d['knopky']]
        if d['typ'] == 'vhadai':
            vars_ = ''.join(f'<i class="{"ok" if i == d["pravylna"] else ""}">{e(v)}</i>' for i, v in enumerate(d['varianty']))
            tilo.append(f'<div class="m bot poll"><b>{e(d["pytannia"])}</b>{vars_}<small>Вікторина · після відповіді: '
                        f'{e(d["poiasnennia"])}</small></div>')
            tilo.append(bulbashka(R.Vidpovid('', kn)).replace('<div class="m bot"></div>', ''))
        else:
            tilo.append(bulbashka(R.Vidpovid(d['tekst'], kn)))
    return ''.join(tilo)


ZNIMKY = {
    'bot-a-odna-vidpovid': ('Мій будинок · бот', 'сценарій А — «Одна відповідь»', lambda: rozmova('a', ['Хрещатик 22'])),
    'bot-b-krokamy': ('Мій будинок · бот', 'сценарій Б — «Кроками»', lambda: rozmova('b', ['Хрещатик 22', '!1'])),
    'bot-v-bilia-domu': ('Мій будинок · бот', 'сценарій В — «Біля дому»', lambda: rozmova('v', ['Хрещатик 22', '!1'])),
    'bot-ne-znaishov': ('Мій будинок · бот', 'коли адреси немає', lambda: rozmova('a', ['Хрещатик', 'Хрещатик 999', 'Садова 3'])),
    'bot-nove-bilia-domu': ('Мій будинок · бот', 'щотижня: нове біля дому', nove),
    'kanal-tyzhden': ('Моя вулиця · Шевченківський', 'районний канал, тиждень', kanal),
}


def main(argv=None) -> int:
    from playwright.sync_api import sync_playwright
    vykhid = Path((argv or sys.argv[1:] or ['docs/znimky-97'])[0])
    vykhid.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        st = br.new_page(viewport={'width': 390, 'height': 600}, device_scale_factor=2)
        for nazva, (zah, pidp, f) in ZNIMKY.items():
            st.set_content(storinka(zah, pidp, f()))
            st.screenshot(path=str(vykhid / f'{nazva}.png'), full_page=True)
            print(vykhid / f'{nazva}.png')
        br.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
