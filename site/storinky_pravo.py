"""Правові сторінки й форма звернення — у вигляді сайту (ZAVDANNYA-172; ZVIT-169, п. 6).

Тексти оферти, політики, умов, «Хто ми» й форми звернення живуть у site/zahlushka/*.html і збираються її збирачем
(site/zahlushka/zibraty.py: місця [ВЛАСНИК], ціни {{tsina.*}}, перевірка для публікації). Раніше вони так і лишались у
вигляді заглушки — інша шапка («Передзамовлення»), інший підвал, без меню й перемикача теми: людина з «Для бізнесу» чи з
оплати опинялась «ніби на іншому сайті» саме тоді, коли вирішує, чи довіряти.

Тут уже зібрану сторінку заглушки загортаємо в оболонку сайту (zibraty_sait.storinka: шапка з меню, тема, підвал):
вміст <main> — той самий, адреса та сама (/zahlushka/<файл>.html — на неї посилаються оферта, листи й форми),
скрипти форми звернення — ті самі, дозвіл з'єднань (CSP) — сайту, плюс сховище форм, якщо воно було в сторінці.
Стилі вмісту — /sait/pravo.css (класи заглушки на змінних кольорів сайту).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

import zibraty_sait as Z

STORINKY = ('oferta.html', 'polityka.html', 'umovy.html', 'pro-nas.html', 'zvernennya.html')

# Короткі адреси правових сторінок → чинна адреса (ZVIT-169, п. 5: «…/oferta.html» в оферті вела на 404).
PERENAPRAVLENNIA = [(f'/{n}{k}', f'/zahlushka/{n}.html') for n in ('oferta', 'umovy', 'polityka') for k in ('', '/', '.html')]


def _vytiahnuty(tekst: str, vzirets: str) -> str:
    m = re.search(vzirets, tekst, re.S)
    return m.group(1) if m else ''


def perebuduvaty(tekst: str, nazva_failu: str, adresa_saitu: str) -> str:
    """Зібрана сторінка заглушки → та сама сторінка в оболонці сайту."""
    title = html.unescape(_vytiahnuty(tekst, r'<title>(.*?)</title>'))
    title = re.sub(r'\s+—\s+Моя вулиця$', '', title) + ' | Моя вулиця'
    opys = html.unescape(_vytiahnuty(tekst, r'<meta name="description" content="([^"]*)"'))
    tilo = _vytiahnuty(tekst, r'<main class="storinka">\n?(.*?)</main>')
    if not tilo:
        raise ValueError(f'{nazva_failu}: немає <main class="storinka">')
    # посилання на головну заглушки й на передзамовлення — на головну сайту
    tilo = re.sub(r'href="index\.html(#[^"]*)?"', 'href="/"', tilo)
    # хто надає сервіс — у підвалі заглушки; на сайті підвал спільний, тож рядок іде в кінець вмісту
    vlasnyk = _vytiahnuty(tekst, r'<footer class="pidval">\s*<span>(?:<span[^>]*>)?([^<·]+?)(?:</span>)?\s*·')
    if vlasnyk.strip():
        tilo += f'\n<p class="pravo__khto">Сервіс надає: {vlasnyk.strip()}. <a href="pro-nas.html">Хто ми й як написати</a></p>'
    skrypty = tuple('/zahlushka/' + s for s in re.findall(r'<script src="([a-z0-9_.-]+\.js)"></script>', tekst))
    indeksuvaty = 'noindex' not in tekst
    st = Z.storinka(shlyakh=f'/zahlushka/{nazva_failu}', title=title, opys=opys,
                    tilo=f'<div class="pravo">\n{tilo}</div>', adresa_saitu=adresa_saitu, skrypty=skrypty,
                    dodatkovo_head='<link rel="stylesheet" href="/sait/pravo.css">\n', indeksuvaty=indeksuvaty)
    # форми заглушки без сервера сайту пишуть у Supabase — цю адресу лишаємо в дозволі з'єднань
    if 'supabase.co' in _vytiahnuty(tekst, r'http-equiv="Content-Security-Policy" content="([^"]*)"'):
        st = st.replace('connect-src ', 'connect-src https://*.supabase.co ', 1)
    return st


def zibraty(teka_zahlushky: Path, adresa_saitu: str) -> list[str]:
    """Переписує правові сторінки в теці зібраної заглушки. Повертає імена переписаних файлів."""
    zrobleno = []
    for n in STORINKY:
        f = teka_zahlushky / n
        if not f.exists():
            continue
        f.write_text(perebuduvaty(f.read_text(encoding='utf-8'), n, adresa_saitu), encoding='utf-8')
        zrobleno.append(n)
    return zrobleno
