"""Три зразки «Нове біля дому» на ШТУЧНИХ даних (ZAVDANNYA-119, п. 4) — `docs/znimky-119/`.

    python lyst/lyst_zrazky.py [--teka docs/znimky-119]

Репозиторій публічний, тож справжніх подій тут немає: вулиці, місця й перекази вигадані, номерів будинків немає
(MV-25, MV-60). Числа нічого не означають. Знімки — Playwright (Chromium, що стоїть у середовищі), без мережі.
"""
from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))

import lyst as L  # noqa: E402
import lyst_kanaly as LK  # noqa: E402

ZRAZOK = 'Зразок на штучних даних: вулиці, місця й події вигадані'
LA, LO = 50.4500, 30.5200            # «Дім»
LA2, LO2 = 50.4600, 30.4900          # «Робота»


def _p(i, data, hrupa, mistse, dla, dlo, perekaz=None, vidkr=1):
    z = {'id': f'zrazok/{i}|x', 'data': data, 'hrupa': hrupa, 'mistse': mistse, 'tochnist': 'cross',
         'lat': LA + dla, 'lon': LO + dlo, 'url': f'https://example.org/rishennia/zrazok-{i}', 'vidkr': vidkr}
    if perekaz:
        z['perekaz'] = perekaz
    return z


def strichka(tykha: bool = False) -> dict:
    t = {'vid': '2026-11-09', 'do': '2026-11-16'}
    if tykha:
        return {'tyzhden': t, 'podii': [], 'skarhy': [], 'problemy': []}
    podii = [
        _p(1, '2026-10-28', 'dtp', 'перехрестя вулиці Зразкової й провулку Пробного', 0.0010, 0.0008,
           'Водій легковика, повертаючи ліворуч, не пропустив зустрічне авто; обидві машини пошкоджено, люди не постраждали.'),
        _p(2, '2026-10-19', 'vod', 'вулиця Зразкова', -0.0012, 0.0004,
           'Водія зупинили на вулиці вночі; огляд показав алкогольне сп’яніння.'),
        _p(3, '2026-09-30', 'kra', 'ст. м. Зразкова', 0.0005, -0.0015,
           'Чоловік забрав телефон, який пасажирка залишила на лаві біля входу до метро.'),
        _p(4, '2026-08-14', 'por', 'сквер Пробний', -0.0006, -0.0020),
    ]
    podii.append(dict(_p(5, '2026-10-02', 'kra', 'провулок Тестовий', 0, 0,
                         'Чоловік виніс із магазину кілька пляшок олії, не заплативши на касі.'),
                      lat=LA2 + 0.0007, lon=LO2 + 0.0003))
    skarhy = [{'k': f'z|{i}', 'pidpys': 'вигадана адреса', 'lat': LA + d, 'lon': LO - d, 'hrupy': h} for i, (d, h) in enumerate(
        [(0.0003, {'ліфт': 4, 'тепло': 2}), (0.0008, {'тепло': 5, 'вода': 1}), (-0.0010, {'сміття': 3}),
         (0.0015, {'двір': 2, 'тепло': 1})])]
    skarhy.append({'k': 'z|r', 'pidpys': 'вигадана адреса', 'lat': LA2, 'lon': LO2 + 0.001, 'hrupy': {'дороги': 2}})
    problemy = [{'id': 'zr1', 'hrupa': 'dtp', 'lat': LA + 0.0011, 'lon': LO + 0.0009, 'podii': 27,
                 'nazva': 'перехрестя вулиці Зразкової й провулку Пробного'}]
    return {'tyzhden': t, 'podii': podii, 'skarhy': skarhy, 'problemy': problemy}


def pidpysnyk(platno: bool = True) -> L.Pidpysnyk:
    a = [L.Adresa('вулиця Зразкова', LA, LO, 'Дім'), L.Adresa('провулок Тестовий', LA2, LO2, 'Робота')]
    return L.Pidpysnyk('zrazok', 'pidpyska' if platno else 'bezkoshtovno', a if platno else a[:1])


POS = {'stezhu': 'https://moya-vulytsya.pages.dev/stezhu/', 'vidpyska': 'https://moya-vulytsya.pages.dev/vidpyska/',
       'vidpyska_telegram': 'https://moya-vulytsya.pages.dev/vidpyska/', 'pidpyska': 'https://moya-vulytsya.pages.dev/oplata/'}


def chat(vmist: dict, pidpys: str) -> str:
    """Схема повідомлення Telegram (не копія застосунку): текст і кнопки під ним."""
    e = html.escape
    kn = ''.join(f'<div style="margin:6px 0 0;padding:9px;border-radius:10px;background:#EDEFFE;color:#4447A6;'
                 f'text-align:center;font:600 14px/20px {L.SHRYFT}">{e(k["text"])}</div>'
                 for r in vmist['reply_markup']['inline_keyboard'] for k in r)
    return (f'<div style="flex:1;min-width:0"><p style="margin:0 0 8px;font:600 13px/18px {L.SHRYFT};color:#5F6275">'
            f'{e(pidpys)}</p><div style="background:#FFFFFF;border:1px solid #DFE1E9;border-radius:16px;padding:14px;'
            f'font:15px/22px {L.SHRYFT};color:#1C1E2D;white-space:pre-wrap">{e(vmist["text"])}</div>{kn}</div>')


SHRYFTY = ''.join(
    f"@font-face{{font-family:'IBM Plex Sans';font-weight:{w};src:url('{(TUT.parent / 'site' / 'sait' / 'shryfty' / f'ibm-plex-sans-{a}-{w}-normal.woff2').as_uri()}')}}"
    for w in (400, 600, 700) for a in ('cyrillic', 'latin'))


def zibraty(teka: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright
    teka.mkdir(parents=True, exist_ok=True)
    l1 = L.zibraty(strichka(), pidpysnyk())
    l2 = L.zibraty(strichka(tykha=True), pidpysnyk())
    l3p = L.zibraty(strichka(), pidpysnyk())
    l3b = L.zibraty(strichka(), pidpysnyk(platno=False))
    for l in (l1, l2, l3p, l3b):
        for t in L.usi_teksty(l, POS):
            assert not L.vady_tekstu(t), L.vady_tekstu(t)
    storinky = {
        'lyst-1-tyzhden': L.html_lysta(l1, POS, ZRAZOK),
        'lyst-2-tykhyi-tyzhden': L.html_lysta(l2, POS, ZRAZOK),
        'lyst-3-telegram': ('<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"></head><body style="margin:0;'
                            f'background:#F4F5FB"><div style="padding:20px;font:13px/18px {L.SHRYFT};color:#5F6275;'
                            f'text-align:center">{html.escape(ZRAZOK)}</div><div style="display:flex;gap:20px;'
                            'padding:0 20px 24px;max-width:980px">'
                            + chat(LK.telegram_vmist(l3p, POS), 'Telegram · підписка: повна версія')
                            + chat(LK.telegram_vmist(l3b, POS), 'Telegram · безкоштовно: одна адреса, лише числа')
                            + '</div></body></html>'),
    }
    out = []
    with sync_playwright() as pw:
        b = pw.chromium.launch(**({'executable_path': '/opt/pw-browsers/chromium'} if Path('/opt/pw-browsers/chromium').exists() else {}))
        for imia, h in storinky.items():
            s = b.new_page(viewport={'width': 1020 if 'telegram' in imia else 640, 'height': 400}, device_scale_factor=2)
            s.set_content(h)
            s.add_style_tag(content=SHRYFTY)          # лише для знімка: шрифт сайту з site/sait/shryfty/
            s.wait_for_timeout(300)
            f = teka / f'{imia}.png'
            s.screenshot(path=str(f), full_page=True)
            (teka / f'{imia}.html').write_text(h, encoding='utf-8')
            out.append(f)
        b.close()
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--teka', type=Path, default=TUT.parent / 'docs' / 'znimky-119')
    for f in zibraty(ap.parse_args().teka):
        print(f)
