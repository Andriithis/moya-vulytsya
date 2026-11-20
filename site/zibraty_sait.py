"""Збирання сайту «Моя вулиця» з випуску бази (ZAVDANNYA-10, MV-23).

    python site/zibraty_sait.py <events.db> <тека> [--pereimenuvannya CSV] [--mezhi-rayoniv JSON]
                                [--adresa-saitu https://…] [--koloda КОЛОДА]
                                [--perekazy perekazy.json] [--kandydaty-istorii kandydaty.json]

Що збирає (лише файли, без сервера — під Cloudflare Pages):
  /                         головна: пошук вулиці, входи в карту, покажчик, гру, звіт
  /karta/                   карта Києва шестикутниками H3 рівнів 7, 8, 9 (soty-<рівень>.json, poshuk.json поруч)
  /vulytsi/                 покажчик вулиць за абеткою; /vulytsi/<район>/ — за районами
  /vulytsia/<slug>/         сторінка кожної вулиці (узагальнене, безкоштовне)
  /vulytsia/<стара-назва>/  переадресація зі старої назви на нову (довідник перейменувань)
  /budynok/<вулиця>/<номер>/ сторінка будинку: скарги 1551 і події з рішень лише числом (з --budynky; MV-99, MV-100)
  /rayon/<район>/, /rayony/ сторінки районів
  /mistse/<slug>/, /mistsia/ публічні місця: метро, ТЦ, ринки, вокзали, парки, пляжі, мости — лише числа (ZAVDANNYA-124)
  /miy-budynok/, /osbb/, /sudova-praktyka/, /biznes/   вітрини (ZAVDANNYA-85)
  /sudova-praktyka/<kupap|kk>/<номер>/  сторінки статей (з --sudova-praktyka; ZAVDANNYA-111, MV-122)
  /oplata/                  оплата-заглушка «залиште пошту»; /vydalyty/, /pro-dani/ — видалення й про дані
  /doslidnykam/             «Дані для дослідників» — відкритий набір чисел (site/storinka_doslidnykam.py, ZAVDANNYA-158)
  /zahlushka/               заглушка з формою і грою (site/zahlushka/zibraty.py, без змін)
  sitemap.xml (більше 1 000 адрес — індекс і частини sitemap-<вид>[-N].xml: вулиці, будинки, райони, решта), robots.txt,
  404.html, _redirects (старі назви вулиць — 301 на нові)
  manifest.webmanifest      сайт як застосунок; /.well-known/assetlinks.json — підтвердження застосунку Android,
                            лише коли є відбиток ключа (android/twa-manifest.json, --android-vidbytok; ZAVDANNYA-144)

Повторний запуск на тому самому випуску дає ті самі файли: ні часу збирання, ні випадковостей.
Нічого не публікує.
"""
from __future__ import annotations

import argparse
import datetime
import functools
import html
import json
import re
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

DZHERELO = Path(__file__).resolve().parent
# Візуали публічних місць для медіа (MV-113): тека <slug>/ від brend/media/zrobyty_media.py — параметр --media (як колода, поза git)
MEDIA_PUBLICHNI = ('площа', 'вокзал', 'метро', 'ТЦ', 'ринок', 'парк', 'міст', 'пляж', 'острів')   # + пляж, острів — ZAVDANNYA-124
MEDIA_FAILY = (('kartka-1x1.png', 'Картка 1:1', '1080×1080'), ('kartka-16x9.png', 'Картка 16:9', '1920×1080'),
               ('slaidy.pdf', '8 слайдів', 'PDF'))
KORIN = DZHERELO.parent
sys.path.insert(0, str(DZHERELO / 'sait'))
sys.path.insert(0, str(DZHERELO / 'zahlushka'))

import dani as D  # noqa: E402

TSINA_DOVIDKY = 199             # MV-100: довідка про будинок (решта цін — storinky_mv100.TSINY)
ADRESA_SAITU = 'https://moya-vulytsya.pages.dev'   # умовна; справжній домен — на партнера (MV-23)
MEZHA_FAILIV = 20000            # межа Cloudflare Pages (безкоштовний план); більше — --mezha-failiv (платний план)
MEZHA_SITEMAP = 45000           # адрес в одному sitemap (стандарт — до 50 000)
ROZBYVATY_SITEMAP_VID = 1000    # більше адрес — індекс і частини за видом сторінок (ZAVDANNYA-154)
VYD_SITEMAP = {'budynok': 'budynky', 'vulytsia': 'vulytsi', 'vulytsi': 'vulytsi', 'rayon': 'rayony', 'rayony': 'rayony'}
MEZHA_PERENAPRAVLEN = 2000      # правил у `_redirects` (межа Cloudflare для простих правил)
# Вулиці з 1–2 подіями: сторінка є (на неї ведуть покажчик і карта), але пошуку Google її не даємо
# і в sitemap.xml не пишемо — «тонкі» сторінки шкодять усьому сайту в пошуку.
MIN_PODII_DLYA_POSHUKU = 3
RIVNI_MISIATSI_OKREMO = (8, 9)   # Т-12: місяці цих рівнів — у soty-<рівень>-m.json (ZAVDANNYA-125)
# MV-32: безкоштовно — останні 3 роки; старші — у підписці (сірі стовпчики з замком, без чисел).
PERIOD_VIDKRYTYI = f'{D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]}'
PERIOD_ZAMKNENYI = f'{D.STARI_ROKY[0]}–{D.STARI_ROKY[-1]}'
VYSOTA_ZAMKNENOHO = 36
ZAMOK_SVG = ('<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
             'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"></rect>'
             '<path d="M8 11V7a4 4 0 0 1 8 0v4"></path></svg>')
NBSP = ' '

CSP_BAZOVYI = ("default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data: blob:; "
               "worker-src 'self' blob:; child-src 'self' blob:; connect-src 'self' https://tiles.openfreemap.org; "
               "form-action 'self'; base-uri 'none'")
CSP = CSP_BAZOVYI
# Лічба відвідувань без кукі (ZAVDANNYA-132): Cloudflare Web Analytics — безкоштовно, без кукі й без збереження IP
# (за описом Cloudflare). Токен — публічний (видно в коді кожної сторінки), не секрет; без токена скрипта немає взагалі.
CF_SKRYPT = 'https://static.cloudflareinsights.com'
CF_CONNECT = 'https://cloudflareinsights.com'
ANALITYKA = ''
TOKEN_ANALITYKY = re.compile(r'^[0-9a-f]{32}$')


def csp_i_analityka(token: str) -> tuple[str, str]:
    """CSP сторінок і тег лічильника (порожній — без лічби)."""
    token = (token or '').strip()
    if not token:
        return CSP_BAZOVYI, ''
    if not TOKEN_ANALITYKY.match(token):
        raise SystemExit('Токен Cloudflare Web Analytics — 32 знаки 0-9a-f (Web Analytics → Add a site → «token»).')
    csp = CSP_BAZOVYI.replace("script-src 'self'", f"script-src 'self' {CF_SKRYPT}").replace(
        "connect-src 'self'", f"connect-src 'self' {CF_CONNECT}")
    return csp, (f'<script defer src="{CF_SKRYPT}/beacon.min.js" data-cf-beacon=\'{{"token": "{token}", "spa": false}}\'></script>\n')


def robots_txt(adresa_saitu: str) -> str:
    """Пошуковикам — усе публічне; службові адреси (оплата, кабінет, довідки, сервер, форма звернення) — ні."""
    zaboroneno = ['/zahlushka/zvernennya.html', '/oplata/', '/kabinet/', '/dovidka/', '/api/', '/prodazh/']
    return ('User-agent: *\nAllow: /\n' + ''.join(f'Disallow: {z}\n' for z in zaboroneno)
            + f'\nSitemap: {adresa_saitu}/sitemap.xml\n')

# ---------------------------------------------------------------- застосунок Android (ZAVDANNYA-144, MV-126)
# Налаштування оболонки — android/twa-manifest.json (одне джерело): назва пакета, кольори, ярлики, відбитки ключа.
TWA_MANIFEST = KORIN / 'android' / 'twa-manifest.json'
VIDBYTOK = re.compile(r'^([0-9A-F]{2}:){31}[0-9A-F]{2}$')


def android_nalashtuvannia() -> dict:
    return json.loads(TWA_MANIFEST.read_text(encoding='utf-8'))


def assetlinks(paket: str, vidbytky: list[str]) -> str:
    """/.well-known/assetlinks.json: застосунок `paket`, підписаний ключем із відбитком SHA-256, — «свій» для сайту.
    Без нього застосунок показує адресний рядок Chrome. Відбитки не секрет (файл публічний): ключ підпису Google
    Play (Play Console → Цілісність застосунку) і, для тестів поза Play, ключ завантаження партнера."""
    pogani = [v for v in vidbytky if not VIDBYTOK.match(v)]
    if pogani:
        raise SystemExit(f'Відбиток ключа Android — 32 пари шістнадцяткових цифр через двокрапку (AB:CD:…): {pogani}')
    return json.dumps([{'relation': ['delegate_permission/common.handle_all_urls'],
                        'target': {'namespace': 'android_app', 'package_name': paket,
                                   'sha256_cert_fingerprints': vidbytky}}], ensure_ascii=False, indent=2) + '\n'


def web_manifest(n: dict) -> str:
    """/manifest.webmanifest — опис сайту як застосунку (назва, іконки, кольори, ярлики) з тих самих налаштувань, що й
    оболонка. Позначки dzherelo=dodatok тут немає: встановлений із браузера сайт — це сайт, не застосунок Google Play."""
    def bez_dodatku(url: str) -> str:
        return re.sub(r'[?&]dzherelo=dodatok$', '', url.replace('?dzherelo=dodatok&', '?').replace('&dzherelo=dodatok', ''))
    ikona = '/zahlushka/ikony/'
    return json.dumps({
        'id': '/', 'name': n['name'], 'short_name': n['launcherName'], 'lang': 'uk', 'dir': 'ltr',
        'description': 'Що відбувається під боком: скарги мешканців і події з рішень судів — по кожному будинку.',
        'start_url': '/', 'scope': '/', 'display': 'standalone',
        'background_color': n['backgroundColor'], 'theme_color': n['themeColor'],
        'icons': [{'src': ikona + 'ikona-192.png', 'sizes': '192x192', 'type': 'image/png', 'purpose': 'any'},
                  {'src': ikona + 'ikona-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'any'},
                  {'src': ikona + 'ikona-maskable-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'maskable'},
                  {'src': ikona + 'ikona-monochrome-512.png', 'sizes': '512x512', 'type': 'image/png', 'purpose': 'monochrome'}],
        'shortcuts': [{'name': s['name'], 'short_name': s['shortName'], 'url': bez_dodatku(s['url']),
                       'icons': [{'src': ikona + 'ikona-192.png', 'sizes': '192x192', 'type': 'image/png'}]}
                      for s in n.get('shortcuts', [])],
        'related_applications': [{'platform': 'play', 'id': n['packageId'],
                                  'url': f'https://play.google.com/store/apps/details?id={n["packageId"]}'}],
        'prefer_related_applications': False,
    }, ensure_ascii=False, indent=2) + '\n'


def android_faily(vykhid: Path, vidbytky: list[str] | None = None) -> int:
    """Маніфест сайту завжди; assetlinks.json — лише коли є хоч один відбиток (з налаштувань оболонки або параметра)."""
    n = android_nalashtuvannia()
    zapysaty(vykhid / 'manifest.webmanifest', web_manifest(n))
    vsi = [f['value'] for f in n.get('fingerprints', [])] + list(vidbytky or [])
    vsi = list(dict.fromkeys(v.strip().upper() for v in vsi if v.strip()))
    if vsi:
        zapysaty(vykhid / '.well-known' / 'assetlinks.json', assetlinks(n['packageId'], vsi))
    return len(vsi)


SONTSE = ('<svg class="ik-sontse" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
          'stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="4"></circle><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4'
          'M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"></path></svg>')
MISYATS = ('<svg class="ik-misyats" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" '
           'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5Z"></path></svg>')
# День/ніч: значок показує, що буде (місяць — увімкнути ніч); підпис ставить sait/tema.js.
KNOPKA_TEMY = f'<button type="button" class="znachok klav" data-tema-perem aria-label="Нічна тема">{MISYATS}{SONTSE}</button>'
ZNAK = ('<svg aria-hidden="true" width="26" height="28" viewBox="0 0 26 28"><path class="lohotyp__soty" '
        'd="M13 1 L25 8 L25 20 L13 27 L1 20 L1 8 Z"></path><path class="lohotyp__vnutr" '
        'd="M13 9 L18 12 L18 17 L13 20 L8 17 L8 12 Z"></path></svg>')

RODOVYI_RAYONU = {}   # «Голосіївський» → «Голосіївський район»

# ---------------------------------------------------------------- кольори «Індиго й м'ята» (MV-58)

def oklch_hex(c) -> str:
    """OKLCH [L, C, h] → #RRGGBB (ті самі формули, що й у макеті М7)."""
    import math
    L, C, h = c
    a, b = C * math.cos(math.radians(h)), C * math.sin(math.radians(h))
    l_ = (L + 0.3963377774 * a + 0.2158037573 * b) ** 3
    m_ = (L - 0.1055613458 * a - 0.0638541728 * b) ** 3
    s_ = (L - 0.0894841775 * a - 1.291485548 * b) ** 3
    rgb = (4.0767416621 * l_ - 3.3077115913 * m_ + 0.2309699292 * s_,
           -1.2684380046 * l_ + 2.6097574011 * m_ - 0.3413193965 * s_,
           -0.0041960863 * l_ - 0.7034186147 * m_ + 1.707614701 * s_)

    def f(x):
        x = 12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055
        return f'{round(min(1, max(0, x)) * 255):02X}'
    return '#' + ''.join(f(x) for x in rgb)


def zmishaty(a: str, b: str, k: float) -> str:
    ra, rb = [int(a[i:i + 2], 16) for i in (1, 3, 5)], [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(x + (y - x) * k):02X}' for x, y in zip(ra, rb))


@functools.lru_cache(maxsize=1)
def kolory_tem() -> dict:
    """Кольори обох тем з site/sait/kolory.json (напрям «Індиго й м'ята» макета М7) — уже в sRGB."""
    dzh = json.loads((DZHERELO / 'sait' / 'kolory.json').read_text(encoding='utf-8'))
    tem = {}
    for t in ('svitla', 'temna'):
        k = {n: (None if v is None else [oklch_hex(x) for x in v] if isinstance(v[0], list) else oklch_hex(v))
             for n, v in dzh[t].items()}
        tem[t] = k
    return tem


def kolory_css() -> str:
    """CSS-змінні обох тем. Світла — за замовчуванням; темна — html[data-t="temna"] (ставить sait/tema.js)."""
    tem = kolory_tem()
    blok = {}
    for t, k in tem.items():
        temna = t == 'temna'
        v = {
            'ground': k['ground'], 'surface': k['surface'], 'surface-tint': k['tint'], 'ink': k['ink'], 'ink-2': k['ink2'],
            'muted': k['muted'], 'line': k['line'], 'line-strong': zmishaty(k['line'], k['mezha'], 0.4), 'mezha': k['mezha'],
            'bort': zmishaty(k['ground'], '#000000', 0.55) if temna else zmishaty(k['mezha'], '#000000', 0.25),
            'accent': k['accent'], 'accent-strong': zmishaty(k['accent'], '#FFFFFF' if temna else '#000000', 0.25),
            'accent-soft': k['accentSoft'], 'on-accent': k['onAccent'], 'data-city': k['muted'],
            'vyd': k['vyd'], 'pk-1': k['pk'][0], 'pk-2': k['pk'][1],
            'karta-tlo': k['bg'], 'karta-park': k['park'], 'karta-voda': k['water'], 'karta-budynky': k['building'],
            'karta-doroha': k['road'] or 'none', 'karta-pidpys': k['label'], 'karta-oreol': k['halo'],
        }
        for i, c in enumerate(k['sc'], 1):
            v[f'sc-{i}'] = c
            v[f'data-{i}'] = c          # шкала сторінок вулиць — та сама, що й на карті
        blok[t] = ''.join(f'--{n}:{c};' for n, c in v.items())
    return ('/* Кольори — напрям «Індиго й м’ята» (MV-58), з site/sait/kolory.json; збирач пише їх сюди. */\n'
            f':root{{color-scheme:light;{blok["svitla"]}}}\n'
            f'html[data-t="temna"]{{color-scheme:dark;{blok["temna"]}}}\n')


def e(t) -> str:
    return html.escape(str(t), quote=True)


def chyslo(n: int) -> str:
    return f'{n:,}'.replace(',', NBSP)


def vidminok(n: int, formy: tuple[str, str, str]) -> str:
    m10, m100 = n % 10, n % 100
    if m10 == 1 and m100 != 11:
        return formy[0]
    if 2 <= m10 <= 4 and not 12 <= m100 <= 14:
        return formy[1]
    return formy[2]


def podii_slovo(n: int) -> str:
    return f'{chyslo(n)} {vidminok(n, ("подія", "події", "подій"))}'


def vidsotok(x: float) -> str:
    v = x * 100
    return (f'{v:.0f}' if v >= 10 else f'{v:.1f}'.replace('.', ',')) + '%'


def slug_rayonu(r: str) -> str:
    return D.translit(r)


# ---------------------------------------------------------------- рамка сторінки

MISIATSI = ('січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень',
            'жовтень', 'листопад', 'грудень')


def onovleno(versiia: str) -> str:
    """Рядок «Оновлено: листопад 2026» з дати випуску (ZAVDANNYA-88, п. 3); дата не розпізнана — порожньо."""
    m = re.match(r'^(\d{4})-(\d{2})', versiia or '')
    if not m or not 1 <= int(m.group(2)) <= 12:
        return ''
    return (f'<p class="onovleno"><time datetime="{e(versiia)}">Оновлено: {MISIATSI[int(m.group(2)) - 1]} {m.group(1)}</time></p>')


def og_kartynka(adresa_saitu: str, url: str, alt: str) -> str:
    """Мітки картинки для поширення (Open Graph і X): 1200 × 630 PNG, лише числа (site/kartynky.py)."""
    return (f'<meta property="og:image" content="{e(adresa_saitu + url)}">\n'
            '<meta property="og:image:type" content="image/png">\n'
            '<meta property="og:image:width" content="1200">\n<meta property="og:image:height" content="630">\n'
            f'<meta property="og:image:alt" content="{e(alt)}">\n'
            '<meta name="twitter:card" content="summary_large_image">\n')


def storinka(*, shlyakh: str, title: str, opys: str, tilo: str, adresa_saitu: str, aktyvne: str = '',
             skrypty: tuple[str, ...] = (), dodatkovo_head: str = '', mapa: bool = False, indeksuvaty: bool = True,
             pered_main: str = '', kartynka: tuple[str, str] | None = None) -> str:
    # Вітрини (MV-99): на телефоні в шапці — карта, вулиці, «Мій будинок»; решта — під «Ще» і в підвалі.
    menyu = [('karta/', 'Карта', 0), ('vulytsi/', 'Вулиці', 0), ('miy-budynok/', 'Мій будинок', 0), ('osbb/', 'Для ОСББ', 1),
             ('sudova-praktyka/', 'Судова практика', 1), ('biznes/', 'Для бізнесу', 1), ('karta/?ihry', 'Ігри', 1)]
    punkty, shche = [], []
    for h, n, lyshe_komp in menyu:
        klas = ' class="lyshe-komp"' if lyshe_komp else ''
        cur = ' aria-current="page"' if h == aktyvne else ''
        punkty.append(f'<a{klas} href="/{h}"{cur}>{n}</a>')
        if lyshe_komp:
            shche.append(f'<a href="/{h}"{cur}>{n}</a>')
    # Д-5 (ZAVDANNYA-114): на телефоні решта вітрин — під «Ще» (розкривний список без скриптів).
    punkty.append('<details class="menyu__shche"><summary>Ще</summary><div class="menyu__spysok">' + ''.join(shche) + '</div></details>')
    # Д-1 (ZAVDANNYA-110): Google обрізає заголовки за ≈ 70 знаків і описи за ≈ 170 — довгим знімаємо « | Моя вулиця»
    # (назва сайту є в og:site_name), опис скорочуємо по слову.
    if len(title) > 70 and title.endswith(' | Моя вулиця'):
        title = title[:-len(' | Моя вулиця')]
    if len(opys) > 170:
        opys = opys[:169].rsplit(' ', 1)[0].rstrip(',;:—–-') + '…'
    css_mapy = '<link rel="stylesheet" href="/sait/biblioteka/maplibre-gl.css">\n' if mapa else ''
    # Екран карти (головна, /karta/): скрипти з defer — не тримають малювання першого екрана (ZAVDANNYA-164); порядок той самий.
    defer = ' defer' if pered_main else ''
    js = ''.join(f'<script src="{s}"{defer}></script>\n' for s in skrypty + ('/sait/vkhid.js',))   # мітка входу з реклами (ZAVDANNYA-153)
    robots = '' if indeksuvaty else '<meta name="robots" content="noindex, follow">\n'
    return f'''<!doctype html>
<html lang="uk" data-koren="/">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<meta http-equiv="Content-Security-Policy" content="{CSP}">
<title>{e(title)}</title>
<meta name="description" content="{e(opys)}">
{robots}<link rel="canonical" href="{e(adresa_saitu + shlyakh)}">
<meta property="og:type" content="website">
<meta property="og:locale" content="uk_UA">
<meta property="og:site_name" content="Моя вулиця">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(opys)}">
<meta property="og:url" content="{e(adresa_saitu + shlyakh)}">
{og_kartynka(adresa_saitu, *kartynka) if kartynka else ''}<meta name="theme-color" content="{kolory_tem()['svitla']['ground']}">
<link rel="icon" type="image/png" sizes="192x192" href="/zahlushka/ikony/ikona-192.png">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="preload" href="/sait/shryfty/ibm-plex-sans-cyrillic-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/sait/shryfty/ibm-plex-sans-cyrillic-700-normal.woff2" as="font" type="font/woff2" crossorigin>
<script src="/sait/tema.js"></script>
{css_mapy}<link rel="stylesheet" href="/sait/sait.css">
{dodatkovo_head}</head>
<body{' class="z-kartoyu"' if pered_main else ''}>
<header class="shapka">
<div class="shapka__vnutri">
<a class="lohotyp" href="/" aria-label="Моя вулиця — на головну">{ZNAK}<span class="lohotyp__nazva">Моя вулиця</span></a>
<nav class="menyu" aria-label="Розділи">{''.join(punkty)}</nav>
{'' if pered_main else KNOPKA_TEMY}
</div>
</header>
{pered_main}<main class="storinka">
{tilo}
</main>
<footer class="pidval">
<div class="pidval__vnutri">
<p>Дані — з рішень судів у Єдиному державному реєстрі судових рішень. Це лише те, що дійшло до суду, а не всі події на вулиці.</p>
<p>Колір і числа показують лише кількість подій у даних — це не оцінка вулиці, будинку чи району. Ми не стверджуємо причин і не прогнозуємо.</p>
<p><a href="/miy-budynok/">Мій будинок</a> · <a href="/osbb/">Для ОСББ</a> · <a href="/sudova-praktyka/">Судова практика</a> · <a href="/biznes/">Для бізнесу</a> · <a href="/rayony/">Райони</a> · <a href="/karta/?ihry">Ігри</a></p>
<p><a href="/pro-dani/">Як ми працюємо з даними</a> · <a href="/doslidnykam/">Дані для дослідників</a> · <a href="/vydalyty/">Видалити або виправити подію</a> · <a href="/zahlushka/polityka.html">Політика конфіденційності</a> · <a href="/zahlushka/oferta.html">Оферта</a> · Карта: <a href="https://www.openstreetmap.org/copyright">© учасники OpenStreetMap</a></p>
</div>
</footer>
{js}{ANALITYKA}</body>
</html>
'''


# ---------------------------------------------------------------- сторінка вулиці

def ryadok_vydu(x: dict) -> str:
    tut = x['chastka']
    misto = x['chastka_misto']
    shkala = max(tut, misto) or 1
    raz = x['lq']
    raz_t = f'{raz:.1f}'.replace('.', ',')
    return f'''<div class="kartka vyd">
<div class="vyd__nazva">{e(x['vyd'])}</div>
<div class="vyd__ryad"><span>ця вулиця</span><span class="vyd__smuha vyd__smuha--tut"><i data-shyr="{tut / shkala * 100:.0f}"></i></span><b>{vidsotok(tut)}</b></div>
<div class="vyd__ryad"><span>Київ</span><span class="vyd__smuha vyd__smuha--misto"><i data-shyr="{misto / shkala * 100:.0f}"></i></span><b>{vidsotok(misto)}</b></div>
<p class="prymitka">{podii_slovo(x['n'])} на вулиці. Частка серед подій вулиці в {raz_t} раза більша, ніж по Києву.</p>
</div>'''


def kontur_soty(k: str) -> list:
    kontur = [[round(lon, 5), round(lat, 5)] for lat, lon in D.h3.cell_to_boundary(k)]
    return kontur + [kontur[0]]


def klas_shkaly(n: int, maks: int) -> int:
    if n <= 0 or maks <= 0:
        return 0
    return min(5, 1 + int(4 * n / maks)) if maks > 1 else 5


def abzats_vulytsi(v: D.Vulytsia, pr: dict, roky_t: str) -> str:
    """Абзац людською мовою з чисел (ROLYKY-I-SOTSMEREZHI, розд. 5, п. 4): без вигадок і оцінок."""
    vsogo = pr['vsogo']
    t = f'{e(v.nazva[:1].upper() + v.nazva[1:])}: за {roky_t} у даних судів — {podii_slovo(vsogo)}'
    if pr.get('naichastishe'):
        t += '. Найчастіше — ' + ' і '.join(f'{e(n.lower())} ({chyslo(k)})' for n, k in pr['naichastishe'][:2])
    t += '.'
    if pr['vyriznennia']:
        t += ' Частіше, ніж у середньому по Києву, — ' + ', '.join(e(x['vyd'].lower()) for x in pr['vyriznennia'][:2]) + '.'
    return t


def media_mistsia(media: Path | None, v: D.Vulytsia) -> dict | None:
    """MV-113: візуал для медіа — лише для публічного місця, чия сторінка — ця (площа на сторінці «вулиці»); інакше None"""
    if not media: return None
    f = media / v.slug / 'vizual.json'
    if not f.exists(): return None
    d = json.loads(f.read_text(encoding='utf-8'))
    if d.get('typ') not in MEDIA_PUBLICHNI or v.typ not in MEDIA_PUBLICHNI or d.get('storinka') != f'/vulytsia/{v.slug}/':
        return None
    if any(not (media / v.slug / n).exists() for n, _, _ in MEDIA_FAILY): return None
    return d


def blok_media(d: dict, slug: str, baza: str | None = None) -> str:
    """MV-113: «Для медіа» — завантажити картку чи слайди безкоштовно; умови: підпис і посилання на цю сторінку.
    baza — де лежать файли (сторінка площі — /vulytsia/<slug>/media, публічного місця — /mistse/<slug>/media)."""
    baza = baza or f'/vulytsia/{slug}/media'
    faily = ''.join(f'<li><a class="knopka" href="{baza}/{n}" download>{e(t)} <span>· {e(r)}</span></a></li>'
                    for n, t, r in MEDIA_FAILY)
    return f'''<section class="rozdil" id="dlia-media"><h2>Для медіа</h2>
<p class="rozdil__pidpys">Пишете про це місце? Візьміть готовий візуал: скільки подій у колі {d['radius']} м, порівняння з типовим
колом Києва, з чого складаються події, роки й години — {e(d['period'])}. Безкоштовно.</p>
<a href="{baza}/kartka-16x9.png"><img class="media-pryklad" src="{baza}/kartka-16x9.png" width="960" height="540"
 loading="lazy" alt="{e(d['nazva'])}: {d['podii']} подій з рішень судів у колі {d['radius']} м — картка для медіа"></a>
<ul class="media-faily">{faily}</ul>
<p class="prymitka"><b>Умови:</b> {e(d['umovy'])} Числа — станом на
{e('.'.join(reversed(d['versiia'].split('-'))))}; оновлюються з кожним випуском.</p></section>'''


def blok_sudova_praktyka(statti_vulytsi: dict, sp_statti: dict | None) -> str:
    """«Як суди Києва вирішують такі справи» (ZAVDANNYA-135): до 3 статей «Судової практики», за якими на вулиці ≥ 3 подій
    за відкриті роки, — посилання на безкоштовні сторінки статей. Лише число подій і назва статті; без порад і оцінок."""
    if not sp_statti:
        return ''
    ryady = sorted(((n, k) for k, n in (statti_vulytsi or {}).items() if k in sp_statti and n >= 3), key=lambda x: (-x[0], x[1]))[:3]
    if not ryady:
        return ''
    li = ''.join(f'<li><a href="/sudova-praktyka/{k.replace("-", "/", 1)}/">{e(sp_statti[k]["nazva"])} — ст.{NBSP}{e(sp_statti[k]["nomer"])} '
                 f'{e(sp_statti[k]["kodeks"])}</a><small>{podii_slovo(n)} тут</small></li>' for n, k in ryady)
    return (f'<section class="rozdil"><h2>Як суди Києва вирішують такі справи</h2>'
            f'<p class="rozdil__pidpys">Найчастіші статті в подіях цієї вулиці за {PERIOD_VIDKRYTYI}. На сторінці статті — чим закінчуються '
            f'такі справи в судах Києва: частки рішень і покарань, строки. Без імен і без порад.</p>'
            f'<ul class="spysok-vulyts">{li}</ul></section>')


def storinka_vulytsi(dn: D.Dani, v: D.Vulytsia, pr: dict, adresa_saitu: str, susidy: list, budynky: list | None = None,
                     media: dict | None = None, mistsia: list | None = None, sp_statti: dict | None = None) -> str:
    rayon = v.rayony.most_common(1)[0][0] if v.rayony else None
    inshi_rayony = [r for r, _ in v.rayony.most_common()[1:] if v.rayony[r] >= 3]
    vsogo = pr['vsogo']
    roky_t = PERIOD_VIDKRYTYI
    rayon_t = f'{rayon} район' if rayon else 'Київ'
    # ZAVDANNYA-154: шаблони під запити людей — site/zaholovky.py
    import zaholovky as ZH
    title = ZH.title_vulytsi(v.nazva, rayon, podii_slovo(vsogo), roky_t)
    vydy_t = ', '.join(x['vyd'].lower() for x in pr['vyriznennia'][:2])
    opys = ZH.opys_vulytsi(v.nazva, rayon_t, podii_slovo(vsogo), roky_t,
                           f'{chyslo(len(budynky))} {vidminok(len(budynky), ("будинок", "будинки", "будинків"))}' if budynky else None,
                           vydy_t or None)
    chastyny = []
    kryhty_p = [('/', 'Головна'), ('/vulytsi/', 'Вулиці')]
    if rayon:
        kryhty_p.append((f'/rayon/{slug_rayonu(rayon)}/', f'{rayon} район'))
    kryhty_p.append(('', v.nazva))
    kryhty = [f'<a href="/">Головна</a><span aria-hidden="true">›</span><a href="/vulytsi/">Вулиці</a>']
    if rayon:
        kryhty.append(f'<span aria-hidden="true">›</span><a href="/rayon/{slug_rayonu(rayon)}/">{e(rayon)} район</a>')
    chastyny.append(f'<nav class="kryhty" aria-label="Де ви">{"".join(kryhty)}</nav>')
    dodatkovi_rayony = f' Частково — {", ".join(e(r) for r in inshi_rayony)}.' if inshi_rayony else ''
    chastyny.append(f'''<section class="zaholovok">
<span class="mitka">{e(rayon_t)}</span>
<h1>{e(v.nazva)}</h1>
<p>{abzats_vulytsi(v, pr, roky_t)}{dodatkovi_rayony}</p>
{onovleno(dn.versiia)}</section>''')

    # Коротко: числа
    ostannii = pr['roky'].get(D.ROKY[-1], 0)
    chysla = [(chyslo(vsogo), f'подій за {roky_t}'), (chyslo(pr['mists']), 'різних місць на вулиці')]
    if pr['z_chasom']:
        chysla.append((chyslo(pr['z_chasom']), 'з відомим днем і годиною'))
    chysla.append((chyslo(ostannii), f'у {D.ROKY[-1]} році (рік ще триває)'))
    chastyny.append('<section class="chysla" aria-label="Коротко">' + ''.join(
        f'<div class="kartka chyslo-blok"><b class="chyslo">{a}</b><span>{b}</span></div>' for a, b in chysla) + '</section>')

    # Чим відрізняється
    if pr['vyriznennia']:
        chastyny.append('<section class="rozdil"><h2>Чим вулиця відрізняється від Києва</h2>'
                        '<p class="rozdil__pidpys">Види подій, частка яких тут помітно більша, ніж по місту. '
                        'Це порівняння часток у даних, а не оцінка вулиці. Види, яких менше 5, не показуємо.</p>'
                        '<div class="sitka">' + ''.join(ryadok_vydu(x) for x in pr['vyriznennia']) + '</div></section>')
    elif vsogo >= 5:
        chastyny.append('<section class="rozdil"><h2>Чим вулиця відрізняється від Києва</h2>'
                        '<p class="rozdil__pidpys">Помітних відмінностей у видах подій немає: розподіл схожий на київський '
                        'або подій кожного виду менше 5.</p></section>')

    # Роки: останні 3 — з числами; старші — сірі стовпчики з замком, без чисел (MV-32, макет М7).
    maks = max(pr['roky'].values(), default=0) or 1
    stovpchyky = ''.join(
        f'<div class="rik rik--zamok"><span class="rik__chyslo">{ZAMOK_SVG}</span>'
        f'<span class="rik__stovpchyk" data-vys="{VYSOTA_ZAMKNENOHO}"></span><span>{r}</span></div>'
        for r in D.STARI_ROKY) if pr['stari'] else ''
    stovpchyky += ''.join(
        f'<div class="rik"><span class="rik__chyslo">{chyslo(n) if n else ""}</span>'
        f'<span class="rik__stovpchyk" data-vys="{max(2, round(n / maks * 140))}"></span><span>{r}</span></div>'
        for r, n in pr['roky'].items())
    pidpys_rokiv = f'Безкоштовно — {roky_t}; {D.ROKY[-1]} — неповний рік.'
    if pr['stari']:
        pidpys_rokiv += f' Події за {PERIOD_ZAMKNENYI} на цій вулиці теж є — у підписці.'
    roky_tablytsia = (f'<tr><th scope="row">{PERIOD_ZAMKNENYI}</th><td>у підписці</td></tr>' if pr['stari'] else '') + ''.join(
        f'<tr><th scope="row">{r}</th><td>{n}</td></tr>' for r, n in pr['roky'].items())
    chastyny.append(f'''<section class="rozdil"><h2>Події за роками</h2>
<p class="rozdil__pidpys">{pidpys_rokiv}</p>
<div class="kartka"><div class="roky{' roky--usi' if pr['stari'] else ''}" aria-hidden="true">{stovpchyky}</div>
<table class="prykhovano"><caption>Події за роками</caption><tbody>{roky_tablytsia}</tbody></table></div></section>''')

    # Ритм
    if pr['z_chasom'] >= 10:
        mk = max(max(r) for r in pr['rytm'])
        hodyny = ''.join(f'<span class="rytm__hod">{h:02d}</span>' for h in range(0, 24, 3))
        ryady = ''
        for d, ryad in enumerate(pr['rytm']):
            ryady += f'<span>{D.DNI[d]}</span>' + ''.join(
                f'<span class="rytm__klitynka d{klas_shkaly(n, mk)}" title="{D.DNI[d]}, {h * 3:02d}:00–{h * 3 + 2:02d}:59 — {n}"></span>'
                for h, n in enumerate(ryad))
        chastyny.append(f'''<section class="rozdil"><h2>Дні й години</h2>
<p class="rozdil__pidpys">Коли ставалися події з відомим часом ({podii_slovo(pr["z_chasom"])}). Клітинка — 3 години; темніше — більше подій.</p>
<div class="kartka"><div class="rytm" role="img" aria-label="Події за днями тижня і годинами"><span></span>{hodyny}{ryady}</div></div></section>''')

    # Карта і будинки
    maks_soty = max((n for _, n in pr['soty']), default=1)
    soty_vulytsi = {'type': 'FeatureCollection', 'features': [
        {'type': 'Feature', 'properties': {'n': n, 'k': klas_shkaly(n, maks_soty) or 1},
         'geometry': {'type': 'Polygon', 'coordinates': [kontur_soty(k)]}} for k, n in pr['soty']]}
    chastyny.append(f'''<section class="rozdil"><h2>Де на вулиці</h2>
<p class="rozdil__pidpys">Шестикутник — близько 0,1 км²; темніше — більше подій у даних. Окремих будинків і описів подій тут немає.</p>
<div class="dva-stovptsi"><div class="karta-ramka"><div id="karta-vulytsi" class="karta" role="region" aria-label="Карта вулиці {e(v.nazva)}"></div>
<p class="karta__zboi" hidden>Підкладка карти не завантажилася — видно межу Києва й шестикутники.</p>
<noscript><p class="karta-bez-js">Щоб побачити карту, увімкніть JavaScript.</p></noscript></div>
<div class="kartka zamok" aria-disabled="true"><p class="zamok__nazva">Що саме сталося біля кожного будинку — у довідці й підписці</p>
<p class="prymitka">Описи подій і коли. Числа по будинку й скарги 1551 — безкоштовно на сторінках будинків{" нижче" if budynky else ""}.</p></div></div>
<script type="application/json" id="soty-vulytsi">{json.dumps(soty_vulytsi, separators=(",", ":"))}</script></section>''')

    # Історія (ZAVDANNYA-110, Б-1): лише переказ ШІ, перевірений програмою (sait/perekazy.py); без дати, години,
    # суми й посилання на рішення — на відкритих сторінках описів справ і посилань на рішення немає.
    if pr['istoriia']:
        ist = pr['istoriia']
        chastyny.append(f'''<section class="rozdil"><h2>Одна історія з вулиці</h2>
<div class="kartka istoriia"><span class="mitka">Переказ ШІ</span>
<blockquote>{e(ist["tekst"])}</blockquote>
<p>{e(ist["vyd"])}{", " + str(ist["rik"]) + " рік" if ist.get("rik") else ""}. Переказ рішення суду простими словами: без імен, дат і адрес, нічого не додано.</p></div></section>''')

    # Будинки вулиці (MV-99, MV-100): лише посилання; числа — на сторінках будинків.
    if budynky:
        chastyny.append(f'''<section class="rozdil"><h2>Будинки вулиці</h2>
<p class="rozdil__pidpys">Сторінка будинку — скарги 1551 за 12 місяців і події з рішень судів числом. Будинки без скарг і подій у даних сторінки не мають.</p>
<ul class="spysok-vulyts spysok-bud">{"".join(f'<li><a href="{b["url"]}">{e(b["nomer"])}</a></li>' for b in budynky)}</ul></section>''')

    # Публічні місця біля вулиці (ZAVDANNYA-124): посилання на їхні сторінки — лише назва й число
    if mistsia:
        import storinky_mistsia as SM
        chastyny.append(SM.blok_mists(mistsia, 'Публічні місця біля вулиці'))

    sp = blok_sudova_praktyka(pr.get('statti'), sp_statti)
    if sp:
        chastyny.append(sp)
    # Дії
    if media:
        chastyny.append(blok_media(media, v.slug))
    chastyny.append(f'''<section class="rozdil"><h2>Що далі</h2>
<div class="diyi">
<a class="knopka knopka--holovna" href="/miy-budynok/">Довідка про будинок — {TSINA_DOVIDKY}{NBSP}грн</a>
<a class="knopka" href="/karta/?hra=vulytsia">Вулиця дня</a>
<a class="knopka" href="/zahlushka/?dzherelo=vulytsia-misto#peredzamovlennya">Ваша вулиця в іншому місті — повідомимо</a>
</div></section>''')

    if susidy:
        chastyny.append('<section class="rozdil"><h2>Вулиці поруч</h2><ul class="spysok-vulyts">' + ''.join(
            f'<li><a href="/vulytsia/{s}/">{e(n)}</a><small>{chyslo(k)}</small></li>' for s, n, k in susidy) + '</ul></section>')

    chastyny.append('<p class="prymitka">Дані — з рішень судів, які дійшли до реєстру; це не всі події на вулиці. '
                    f'Події без точної адреси сюди не потрапили. Домашнє насильство рахуємо нарівні з іншими подіями — лише числом. Статеві '
                    f'злочини й справи щодо дітей на сторінках вулиць не рахуємо — лише в загальному числі великих сот на карті Києва. '
                    f'Дані станом на {e(dn.versiia)}.</p>')

    # schema.org/Place
    tsentr = None
    if pr['soty']:
        tsentry = [D.h3.cell_to_latlng(k) for k, _ in pr['soty']]
        lat = round(sorted(t[0] for t in tsentry)[len(tsentry) // 2], 4)
        lon = round(sorted(t[1] for t in tsentry)[len(tsentry) // 2], 4)
        tsentr = {'@type': 'GeoCoordinates', 'latitude': lat, 'longitude': lon}
    place = {'@context': 'https://schema.org', '@type': 'Place', 'name': f'{v.nazva}, Київ',
             'url': f'{adresa_saitu}/vulytsia/{v.slug}/',
             'address': {'@type': 'PostalAddress', 'streetAddress': v.nazva, 'addressLocality': 'Київ', 'addressCountry': 'UA'}}
    if rayon:
        place['containedInPlace'] = {'@type': 'Place', 'name': f'{rayon} район, Київ'}
    if tsentr:
        place['geo'] = tsentr
    place['dateModified'] = dn.versiia
    import storinky_mv100 as M
    head = M.ld_skrypt(place, M.kryhty_ld(kryhty_p, adresa_saitu))
    return storinka(shlyakh=f'/vulytsia/{v.slug}/', title=title, opys=opys, tilo='\n'.join(chastyny),
                    adresa_saitu=adresa_saitu, aktyvne='vulytsi/', dodatkovo_head=head,
                    kartynka=(f'/vulytsia/{v.slug}/kartynka.png', alt_vulytsi(v, vsogo, roky_t, budynky)),
                    indeksuvaty=vsogo >= MIN_PODII_DLYA_POSHUKU,
                    # Т-12 (ZAVDANNYA-114): бібліотеку карти й її стилі karta.js довантажує, коли людина догортає до карти.
                    skrypty=('/sait/karta.js',))


def vulytsi_poruch(dn: D.Dani, vulytsi: list, n: int = 8) -> dict:
    """ZAVDANNYA-154: вулиці, що поруч на карті: найбільше спільних сот рівня 9 (≈ 0,1 км²) разом із сусідніми сотами.
    Лише події за відкриті роки, як на самій сторінці. slug → [Vulytsia]."""
    if D.h3 is None:
        return {}
    soty = {}
    za_sotoyu = defaultdict(set)
    for v in vulytsi:
        s = {D.h3.latlng_to_cell(dn.podii[i].lat, dn.podii[i].lon, 9) for i in v.nedavni if dn.podii[i].lat is not None}
        soty[v.slug] = s
        for k in s:
            za_sotoyu[k].add(v.slug)
    za_slugom = {v.slug: v for v in vulytsi}
    rez = {}
    for v in vulytsi:
        rakhunok = Counter()
        for k in soty[v.slug]:
            for k2 in D.h3.grid_disk(k, 1):
                for s in za_sotoyu.get(k2, ()):
                    if s != v.slug:
                        rakhunok[s] += 1
        rez[v.slug] = [za_slugom[s] for s, _ in sorted(rakhunok.items(), key=lambda x: (-x[1], x[0]))[:n]]
    return rez


def alt_vulytsi(v: D.Vulytsia, vsogo: int, roky_t: str, budynky: list | None) -> str:
    return (f'{v.nazva}: {podii_slovo(vsogo)} з рішень судів за {roky_t}'
            + (f', {chyslo(len(budynky))} {vidminok(len(budynky), ("будинок", "будинки", "будинків"))} зі своєю сторінкою'
               if budynky else ''))


def kartynka_vulytsi(v: D.Vulytsia, vsogo: int, budynky: list | None, kolory: dict) -> bytes:
    import kartynky as K
    rayon = v.rayony.most_common(1)[0][0] if v.rayony else None
    chysla = [(chyslo(vsogo), f'{vidminok(vsogo, ("подія", "події", "подій"))} з рішень судів за {PERIOD_VIDKRYTYI}')]
    if budynky:
        chysla.append((chyslo(len(budynky)), f'{vidminok(len(budynky), ("будинок", "будинки", "будинків"))} зі своєю сторінкою'))
    return K.kartynka(f'{rayon} район · вулиця' if rayon else 'Київ · вулиця', v.nazva, chysla, kolory)


def storinka_pereadresatsii(stara: str, tsili: list, dn: D.Dani, adresa_saitu: str, slug: str = '') -> str:
    if len(tsili) == 1:
        v = dn.vulytsi[tsili[0]]
        url = f'/vulytsia/{v.slug}/'
        tilo = (f'<section class="zaholovok"><h1>{e(stara)} — тепер {e(v.nazva)}</h1>'
                f'<p>Вулицю перейменовано. Переходимо на сторінку <a href="{url}">{e(v.nazva)}</a>.</p></section>')
        head = f'<meta http-equiv="refresh" content="0; url={url}">\n'
        return storinka(shlyakh=url, title=f'{stara} — тепер {v.nazva} | Моя вулиця',
                        opys=f'{stara} у Києві перейменовано на «{v.nazva}». Події й будинки — на сторінці нової назви.', tilo=tilo, adresa_saitu=adresa_saitu,
                        dodatkovo_head=head, indeksuvaty=False)
    spysok = ''.join(f'<li><a href="/vulytsia/{s}/">{e(dn.vulytsi[s].nazva)}</a></li>' for s in tsili)
    tilo = (f'<section class="zaholovok"><h1>{e(stara)}</h1><p>У Києві було кілька вулиць з цією назвою; '
            f'їх перейменовано по-різному. Оберіть:</p></section><ul class="spysok-vulyts">{spysok}</ul>')
    # ZAVDANNYA-154: канонічна — на саму себе (сторінка вибору поза пошуком; не «видає себе» за покажчик)
    return storinka(shlyakh=f'/vulytsia/{slug}/' if slug else '/vulytsi/', title=f'{stara} — перейменовано | Моя вулиця',
                    opys=f'{stara} у Києві перейменовано по-різному: оберіть нову назву вулиці зі списку.', tilo=tilo, adresa_saitu=adresa_saitu, indeksuvaty=False)


# ---------------------------------------------------------------- покажчик, головна, карта

LITERY = 'АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЮЯ'


def kliuch_abetky(nazva: str) -> tuple:
    t = nazva.replace("'", '').replace('ʼ', '')
    return tuple((LITERY.find(b.upper()) if b.upper() in LITERY else 100 + ord(b)) for b in t)


def holovne_slovo(v: D.Vulytsia) -> str:
    """За чим шукати в абетці: «Хрещатик» для «вулиця Хрещатик»."""
    return v.korotka


def spysok_vulyts(vs: list) -> str:
    return '<ul class="spysok-vulyts">' + ''.join(
        f'<li><a href="/vulytsia/{v.slug}/">{e(v.nazva)}</a><small>{chyslo(len(v.nedavni))}</small></li>' for v in vs) + '</ul>'


def storinka_pokazhchyka(vulytsi: list, rayony: list, adresa_saitu: str, rayon: str | None = None) -> str:
    vs = sorted(vulytsi, key=lambda v: (kliuch_abetky(holovne_slovo(v)), v.slug))
    potochna = ' aria-current="page"'
    rayony_html = '<nav class="rayony" aria-label="Райони">' + (
        f'<a href="/vulytsi/"{"" if rayon else potochna}>Усі</a>') + ''.join(
        f'<a href="/vulytsi/{slug_rayonu(r)}/"{potochna if r == rayon else ""}>{e(r)}</a>' for r in rayony) + '</nav>'
    hrupy = defaultdict(list)
    for v in vs:
        b = holovne_slovo(v)[:1].upper()
        hrupy[b if b in LITERY else '#'].append(v)
    poriadok = sorted(hrupy, key=lambda b: LITERY.find(b) if b in LITERY else 99)
    abetka = '<nav class="abetka" aria-label="Абетка">' + ''.join(f'<a href="#l-{i}">{e(b)}</a>' for i, b in enumerate(poriadok)) + '</nav>'
    sektsii = ''.join(f'<h2 class="bukva" id="l-{i}">{e(b)}</h2>{spysok_vulyts(hrupy[b])}' for i, b in enumerate(poriadok))
    nazva = f'Вулиці: {rayon} район' if rayon else 'Вулиці Києва'
    shlyakh = f'/vulytsi/{slug_rayonu(rayon)}/' if rayon else '/vulytsi/'
    tilo = f'''<nav class="kryhty" aria-label="Де ви"><a href="/">Головна</a><span aria-hidden="true">›</span>{"<a href='/vulytsi/'>Вулиці</a>" if rayon else "Вулиці"}</nav>
<section class="zaholovok"><h1>{e(nazva)}</h1>
<p>{chyslo(len(vs))} {vidminok(len(vs), ("вулиця", "вулиці", "вулиць"))} з подіями в даних судів. Поруч із назвою — скільки подій за {PERIOD_VIDKRYTYI}.</p></section>
<form class="poshuk" role="search" action="/vulytsi/"><label class="prykhovano" for="poshuk-vulytsi">Вулиця або вулиця й номер будинку</label>
<input id="poshuk-vulytsi" type="search" autocomplete="off" placeholder="Вулиця або адреса, наприклад: Хрещатик 22">
<ul class="poshuk__spysok" id="poshuk-spysok" hidden></ul></form>
{rayony_html}
{abetka}
<section class="rozdil">{sektsii}</section>
<p class="prymitka">Назви звели до однієї: «просп. В. Лобановського» і «проспект Валерія Лобановського» — одна сторінка. Старі назви ведуть на нові.</p>'''
    opys = (f'Покажчик вулиць Києва ({rayon} район) з кількістю подій у даних судів.' if rayon
            else 'Покажчик вулиць Києва за абеткою й районами: скільки подій із судових рішень на кожній вулиці.')
    return storinka(shlyakh=shlyakh, title=f'{nazva} — події в даних судів | Моя вулиця', opys=opys, tilo=tilo,
                    adresa_saitu=adresa_saitu, aktyvne='vulytsi/', skrypty=('/sait/poshuk.js',))


def holovna(dn: D.Dani, vulytsi: list, rayony: list, adresa_saitu: str, sudova_praktyka: bool = False,
            zastavka: dict | None = None) -> str:
    """Головна — одразу карта Києва з пошуком (AGENTS.md, розд. 3: без вступу), під нею — входи."""
    tilo = f'''<section class="vstup-ryad">
<div><h1 class="h-mala">Що відбувається під боком</h1>
<p class="prymitka">{chyslo(len(vulytsi))} вулиць Києва зі своєю сторінкою: скільки подій, коли, яких видів. Дані станом на {e(dn.versiia)};
безкоштовно — {PERIOD_VIDKRYTYI}, {PERIOD_ZAMKNENYI} — у підписці.</p></div>
</section>
<section class="vkhody" aria-label="Куди далі">
<a class="vkhid" href="/vulytsi/"><span class="mikro">Покажчик</span><b>Усі вулиці</b><span>за абеткою й районами</span></a>
<a class="vkhid" href="/karta/?ihry"><span class="mikro">Ігри на карті</span><b>Детектив тижня</b><span>щодня слід на карті, у неділю — розкриття</span></a>
<a class="vkhid" href="/miy-budynok/"><span class="mikro">Мій будинок</span><b>Що болить вашому будинку</b><span>скарги 1551 і події біля будинку; довідка — {TSINA_DOVIDKY}{NBSP}грн</span></a>
</section>
<section class="vkhody" aria-label="Розділи">
<a class="vkhid" href="/osbb/"><span class="mikro">Для ОСББ</span><b>Будинок щомісяця</b><span>звернення мешканців до 1551</span></a>
<a class="vkhid" href="/sudova-praktyka/"><span class="mikro">Судова практика</span><b>Суди за статтями</b><span>{"чим закінчуються справи" if sudova_praktyka else "скоро"}</span></a>
<a class="vkhid" href="/biznes/"><span class="mikro">Для бізнесу</span><b>Дані на місяць або рік</b><span>набори й доступ</span></a>
</section>
<section class="rozdil"><h2 class="mikro">Вулиці за районами</h2>
<nav class="rayony" aria-label="Райони">{"".join(f'<a href="/rayon/{slug_rayonu(r)}/">{e(r)}</a>' for r in rayony)}</nav></section>'''
    import storinky_mv100 as M
    ld = M.ld_skrypt({'@context': 'https://schema.org', '@type': 'WebSite', 'name': 'Моя вулиця', 'url': adresa_saitu + '/',
                      'inLanguage': 'uk'},
                     {'@context': 'https://schema.org', '@type': 'Organization', 'name': 'Моя вулиця', 'url': adresa_saitu + '/',
                      'logo': adresa_saitu + '/zahlushka/ikony/ikona-192.png'})
    return storinka(shlyakh='/', title='Моя вулиця — що відбувається під боком: вулиці й будинки Києва', dodatkovo_head=ld + predzavantazhennia(zastavka),
                    opys='Що відбувається під боком: скарги мешканців і події з рішень судів — на кожній вулиці й по кожному будинку Києва. Карта, покажчик вулиць, гра.',
                    tilo=tilo, adresa_saitu=adresa_saitu, pered_main=ekran_karty(dn),
                    skrypty=('/sait/karta.js',))


def soty_geojson(dn: D.Dani, riven: int) -> dict:
    """Файл сот одного рівня для карти. Колір і шкалу рахує сторінка під обрану групу й період.

    Властивості: id; числа груп за останні 3 роки (dor3 … all3; MV-32: чисел за старші роки тут немає);
    y — події за кожен з останніх 3 років; o — 1, якщо в соті є й старші події (лише прапорець «у підписці»); h — година-пік; p — чинні проблеми (назва сценарію, без адреси);
    t — «що страждає» по групах ({група: [[що, скільки]]}, лише ≥ 5 подій); a — скільки подій з адресами й описами (для рядка про підписку);
    r — район, у якому центр соти; u — вулиці (лише на рівні 9)."""
    features = []
    for k in sorted(dn.soty[riven]):
        s = dn.soty[riven][k]
        vl = {'id': k}
        for kl, n in sorted(s['chysla'].items()):
            vl[kl] = n
        vl['y'] = [s['roky'].get(r, 0) for r in D.VIDKRYTI_ROKY]
        # m — місяці (ZAVDANNYA-105): {група: [[номер місяця від січня першого відкритого року, скільки], …]}, лише непорожні.
        if s['misiatsi']:
            vl['m'] = {h: sorted([i, n] for i, n in lich.items()) for h, lich in sorted(s['misiatsi'].items())}
        if s['stari']:
            vl['o'] = 1
        pik = D.hodyna_pik(s['hodyny'])
        if pik:
            vl['h'] = pik
        if s['problemy']:
            vl['p'] = [f'{n} ({st})' if st else n for n, st in s['problemy'][:3]]
        tsili = {}
        for h, lich in sorted(s['tsili'].items()):
            top = [[nazva, n] for nazva, n in sorted(lich.items(), key=lambda x: (-x[1], x[0])) if n >= 5][:2]
            if top:
                tsili[h] = top
        if tsili:
            vl['t'] = tsili
        vl['a'] = s['z_adresoyu']
        if dn.rayony is not None:
            lat, lon = D.h3.cell_to_latlng(k)
            r = dn.rayony.rayon(lat, lon)
            if r:
                vl['r'] = r
        if riven == 9:
            vl['u'] = [[sl, dn.vulytsi[sl].nazva] for sl, n in sorted(s['vulytsi'].items(), key=lambda x: (-x[1], x[0]))[:4]
                       if sl in dn.vulytsi and dn.vulytsi[sl].podii]
        features.append({'type': 'Feature', 'properties': vl, 'geometry': {'type': 'Polygon', 'coordinates': [kontur_soty(k)]}})
    return {'type': 'FeatureCollection', 'features': features}


IK_HRUP = {   # значки груп подій з макета М7 (лінійні, 24×24; ключі — brend/hrupy.json); для насильства — долоня, не кров і не зброя
    'dtp': '<path d="M5 15v-3l2-5h10l2 5v3"/><path d="M4 15h16v3H4z"/><circle cx="7.5" cy="18" r="1.3"/><circle cx="16.5" cy="18" r="1.3"/>',
    'vod': '<path d="M8 3 5 21M16 3l3 18M12 4v3M12 11v3M12 18v2"/>',
    'por': '<circle cx="9" cy="8" r="3"/><circle cx="17" cy="9" r="2.3"/><path d="M3 20c0-3.5 2.7-6 6-6s6 2.5 6 6M15.5 14.3c2.9.2 5 2.3 5 5.2"/>',
    'kra': '<path d="M4 10 12 4l8 6v10H4Z"/><path d="M10 20v-5h4v5"/>',
    'nar': '<rect x="3" y="9" width="18" height="6" rx="3" transform="rotate(-35 12 12)"/><path d="m9.6 8.6 4.8 6.8"/>',
    'alk': '<path d="M10 2.5h4M10.5 2.5v4.5L8 10v11h8V10l-2.5-3V2.5"/><path d="M8 14h8"/>',
    'nas': '<path d="M8 12V5.5a1.5 1.5 0 0 1 3 0V11M11 10V4.5a1.5 1.5 0 0 1 3 0V11M14 10.5V6a1.5 1.5 0 0 1 3 0v8a7 7 0 0 1-12.5 4.3L3 15.5a1.5 1.5 0 0 1 2.4-1.8L8 16"/>',
}


def svg_html(vmist: str, r: int = 18, sh: float = 1.75) -> str:
    """Лінійний значок; самозакривні теги SVG розгортаємо — так сторінку пропускає суворий розбір HTML."""
    import re as _re
    vmist = _re.sub(r'<(\w+)([^<>]*?)/>', r'<\1\2></\1>', vmist)
    return (f'<svg width="{r}" height="{r}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="{sh}" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{vmist}</svg>')


DZHERELA_KARTY = ('Підкладка: <a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © '
                  '<a href="https://openmaptiles.org" target="_blank" rel="noopener">OpenMapTiles</a> · дані © '
                  '<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> (ODbL) · події: '
                  '<a href="https://reyestr.court.gov.ua" target="_blank" rel="noopener">ЄДРСР</a>, ДСА України '
                  '(<a href="https://creativecommons.org/licenses/by/4.0/deed.uk" target="_blank" rel="noopener">CC BY</a>)')


# Ігри в карті (ZAVDANNYA-117): значок «Ігри» — сота з зірочкою; дані ігор — /ihry/*.json (збирає zibraty_ihry).
IHRY_IK = svg_html('<path d="M12 3 19.8 7.5V16.5L12 21 4.2 16.5V7.5Z"/><path d="m12 8.6 1.1 2.3 2.5.3-1.8 1.7.5 2.5-2.3-1.2-2.3 1.2.5-2.5-1.8-1.7 2.5-.3Z"/>', 22)
SKRYPTY_IHOR = ('/sait/hra-yadro.js', '/sait/vulytsia-yadro.js', '/sait/ihry-yadro.js', '/sait/litopys-yadro.js', '/sait/litopys.js',
                '/sait/kariera-yadro.js', '/sait/kariera.js',
                '/sait/ihry.js')   # «Літопис міста» (ZAVDANNYA-141) і «Кваліфікуй: кар'єра» (ZAVDANNYA-152) — у панелі ігор
IHRY_DANI: dict = {}


def dani_ihor() -> str:
    return ''.join(f' data-{k}="{e(v)}"' for k, v in sorted(IHRY_DANI.items()))


def ekran_karty(dn: D.Dani) -> str:
    """Карта на весь екран у вигляді макета М7 (MV-58): угорі ліворуч — рядок пошуку зі значками 3D/2D, день/ніч і «ⓘ»,
    під ним — фільтр «Усі події ▾»; картка соти — «в повітрі» праворуч (телефон — шторка); джерела — правий нижній кут
    (телефон — у «ⓘ»). Легенди й «+/−» немає. Поведінка зуму — як у карті Києва (S-К.4, S-К.6, S-К.13, S-К.18, S-К.21)."""
    import tsiny as T
    hrupy = ''.join(
        f'<li><label><input type="checkbox" data-hrupa="{k}" checked>{svg_html(IK_HRUP[k])}<span>{e(n)}</span></label></li>'
        for k, n in D.HRUPY)
    znak = ('<svg width="24" height="24" viewBox="0 0 24 24" aria-hidden="true"><path class="lohotyp__soty" '
            'd="M12 1.5 21.1 6.75V17.25L12 22.5 2.9 17.25V6.75Z"></path><path class="lohotyp__vnutr" d="M12 8 15.5 10V14L12 16 8.5 14V10Z"></path></svg>')
    filtr_ik = svg_html('<path d="M4 6h16M7 12h10M10 18h4"/>', 18, 2)
    info_ik = svg_html('<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><circle cx="12" cy="7.6" r=".6" fill="currentColor"/>', 22)
    kub = svg_html('<path d="M12 3 20 7.5V16.5L12 21 4 16.5V7.5Z"/><path d="M4 7.5 12 12 20 7.5M12 12V21"/>', 20)
    # Ігри на карті (≈ 215 КБ скриптів) першому екрану не потрібні: karta.js вантажить їх після завантаження сторінки,
    # з живою картою або з першим натиском «Ігри» (ZAVDANNYA-164).
    return f'''<section class="ekran-karty" aria-label="Карта Києва" data-ihry="{' '.join(SKRYPTY_IHOR)}">
<div id="karta-mista" class="karta-povna" data-soty-7="/karta/soty-7.json" data-soty-8="/karta/soty-8.json" data-soty-9="/karta/soty-9.json" data-soty-8-m="/karta/soty-8-m.json" data-soty-9-m="/karta/soty-9-m.json" data-poshuk="/karta/poshuk.json" data-versiia="{e(dn.versiia)}"></div>
<div class="zastavka" aria-hidden="true"></div>
<noscript><p class="karta-bez-js">Щоб побачити карту, увімкніть JavaScript. Без нього — <a href="/vulytsi/">покажчик вулиць</a>.</p></noscript>
<p class="karta__zboi" hidden>Підкладка карти не завантажилася — видно соти й межу Києва.</p>
<div class="verkh-ryad">
<form class="plashka verkh" role="search" action="/vulytsi/"><span class="znak">{znak}</span>
<label class="prykhovano" for="poshuk-karty">Вулиця, будинок або район</label>
<input id="poshuk-karty" type="search" autocomplete="off" spellcheck="false" placeholder="Вулиця, будинок або район" aria-controls="pidkazky" aria-autocomplete="list" aria-expanded="false" role="combobox">
</form>
<button id="f3d" class="znachok klav" type="button" aria-label="Зараз 3D (об’ємно). Натисніть — пласка карта 2D"><span class="zn-v">{kub}<small>3D</small></span></button>
<button id="ftema" class="znachok klav" type="button" data-tema-perem aria-label="Нічна тема">{MISYATS}{SONTSE}</button>
<button id="fihry" class="znachok klav" type="button" aria-label="Ігри на карті" title="Ігри" aria-expanded="false" aria-controls="ihry">{IHRY_IK}</button>
<button id="finfo" class="znachok klav" type="button" aria-label="Як читати карту" title="Як читати карту" aria-expanded="false" aria-controls="info">{info_ik}</button>
</div>
<ul id="pidkazky" class="plashka" role="listbox" aria-label="Знайдені місця" hidden></ul>
<a class="haslo-karty plashka klav" href="/miy-budynok/?dzherelo=holovna"><b>Що болить вашому будинку?</b><span>Довідка — {T.tsina("dovidka")}</span></a>
<div id="filtr" class="filtr">
<button type="button" class="f-knopka klav" aria-expanded="false" aria-controls="f-spysok">{filtr_ik}<span id="f-pidpys">Усі події</span><span aria-hidden="true">▾</span></button>
<div id="f-spysok" class="f-spysok plashka" hidden>
<ul aria-label="Види подій">
<li class="f-usi"><label><input type="checkbox" data-usi checked><span>Усі події</span></label></li>
{hrupy}
</ul>
<div class="f-period" role="group" aria-label="Період">
<button type="button" class="seg" data-period="3" aria-pressed="true">{PERIOD_VIDKRYTYI}</button><button type="button" class="seg seg--zamok" disabled title="Усі роки — у підписці">{ZAMOK_SVG} Усі роки</button>
</div>
</div>
</div>
<section id="info" class="plashka" hidden aria-label="Як читати карту">
<button class="i-x" type="button" aria-label="Закрити">×</button>
<h2>Як читати карту</h2>
<p>Кожна сота — ділянка міста. Колір показує лише, <b>скільки подій є в даних</b>, — це не оцінка місця. Лише те, що дійшло до суду, а не всі події.</p>
<h3>Колір соти (на цьому масштабі)</h3>
<div class="shkala" id="shkala"></div>
<p>Число подій — у підказці при наведенні й у картці соти (натисніть на соту). Великі соти — близько 5 і 0,7 км², при наближенні — близько 0,1 км².</p>
<p>Безкоштовно — лише числа по сотах за {PERIOD_VIDKRYTYI}, без адрес і описів; {PERIOD_ZAMKNENYI} — у підписці. Домашнє насильство — нарівні з іншими подіями; статеві злочини й справи щодо дітей входять лише в число великих сот у групі «{D.HR.NAZVA['nas']}».</p>
<h3>Як рухатись</h3>
<p>Коліщатко або два пальці — ближче й далі; подвійний клік — ближче; клавіші + і −. Права кнопка або два пальці вгору-вниз — нахил.</p>
<h3>Джерела</h3>
<p>{DZHERELA_KARTY}</p>
</section>
<div id="tykha" class="tykha" hidden>будинки — у підписці</div>
<div id="dzherela" class="dzherela">{DZHERELA_KARTY}</div>
<aside id="kartka" class="plashka kartka-soty" hidden aria-label="Картка соти"></aside>
<aside id="ihry" class="plashka panel-ihor" hidden aria-label="Ігри на карті"{dani_ihor()}></aside>
<div id="ihry-zaproshennia" class="plashka ihry-zaproshennia" role="status" hidden><button type="button" class="z-tekst"></button><button type="button" class="z-x" aria-label="Закрити запрошення">×</button></div>
<div id="pidkazka" class="pidkazka-toast" role="status" aria-live="polite"></div>
</section>
'''


def poshuk_karty(dn: D.Dani, vulytsi: list, tsentry: dict) -> dict:
    """Пошук на карті — з даних сайту, без геокодера (MV-58): вулиці зі своєю сторінкою (назва, варіанти назв і старі
    назви з довідника перейменувань, центр соти вулиці з найбільшою кількістю подій) і райони (межі).
    Ні адрес, ні описів подій тут немає — лише назви вулиць і центри сот."""
    stari = defaultdict(list)
    for stara, tsili in dn.zvedennia.pereimenuvannia:
        for s in tsili:
            stari[s].append(stara)
    vs, buly = [], set()
    for v in sorted(vulytsi, key=lambda v: (-len(v.nedavni), v.slug)):
        # Дві сторінки з однаковою назвою (зведення назв не певне) — у пошуку лише та, де більше подій;
        # інша лишається в покажчику вулиць.
        if v.slug not in tsentry or v.nazva in buly:
            continue
        buly.add(v.nazva)
        inshi = sorted(set(v.varianty) | set(stari.get(v.slug, [])))
        vs.append([v.nazva, v.rayony.most_common(1)[0][0] if v.rayony else '', v.slug, *tsentry[v.slug], len(v.nedavni),
                   ' '.join(inshi)])
    rayony = []
    if dn.rayony is not None:
        for nazva in sorted(dn.rayony.mezhi, key=kliuch_abetky):
            r = dn.rayony.mezhi[nazva]
            rayony.append([nazva, round(min(x[1][2] for x in r), 4), round(min(x[1][0] for x in r), 4),
                           round(max(x[1][3] for x in r), 4), round(max(x[1][1] for x in r), 4)])
    return {'versiia': dn.versiia, 'vulytsi': vs, 'rayony': rayony}


def predzavantazhennia(zastavka: dict | None) -> str:
    """Картинку першого екрана браузер бере одразу з заголовка, а не після стилів (ZAVDANNYA-164). Тему людина могла
    обрати сама (вона в пам'яті браузера) — тут угадуємо за темою системи; не вгадали — завантажиться ще й друга."""
    if not zastavka:
        return ''
    import zastavka as Z
    umovy = {'telefon': f'(max-width:{Z.TELEFON_DO}px)', 'komp': f'(min-width:{Z.TELEFON_DO + 0.02}px)'}
    sys_tema = {'svitla': '(prefers-color-scheme:light)', 'temna': '(prefers-color-scheme:dark)'}
    return ''.join(f'<link rel="preload" as="image" href="{e(url)}" media="{umovy[v]} and {sys_tema[t]}" fetchpriority="high">\n'
                   for (v, t), url in sorted(zastavka.items()))


def storinka_karty(dn: D.Dani, adresa_saitu: str, zastavka: dict | None = None) -> str:
    tilo = '''<section class="rozdil vuzko"><h1 class="h-mala">Карта Києва: події з судових рішень</h1>
<p class="prymitka">Великі соти — близько 5 і 0,7 км², при наближенні — близько 0,1 км². Безкоштовно — лише числа по сотах, без адрес і описів.
Домашнє насильство — нарівні з іншими подіями; статеві злочини й справи щодо дітей входять лише в число великих сот у групі «''' + D.HR.NAZVA['nas'] + '''».
''' + D.HR.NAZVA['nas'] + ''' показуємо лише числом. Дані — це те, що дійшло до суду, а не всі події.</p></section>'''
    return storinka(shlyakh='/karta/', title='Карта Києва — події з судових рішень | Моя вулиця', dodatkovo_head=predzavantazhennia(zastavka),
                    opys='Карта Києва шестикутниками: скільки подій із судових рішень у кожній частині міста, яких видів і коли.',
                    tilo=tilo, adresa_saitu=adresa_saitu, aktyvne='karta/', pered_main=ekran_karty(dn),
                    skrypty=('/sait/karta.js',))


def storinka_404(adresa_saitu: str) -> str:
    tilo = ('<section class="zaholovok"><h1>Такої сторінки немає</h1><p>Можливо, вулицю перейменовано або в даних поки немає подій. '
            'Спробуйте <a href="/vulytsi/">покажчик вулиць</a> або <a href="/karta/">карту Києва</a>.</p></section>')
    return storinka(shlyakh='/404.html', title='Сторінку не знайдено | Моя вулиця', opys='Сторінку не знайдено.',
                    tilo=tilo, adresa_saitu=adresa_saitu, indeksuvaty=False)


def storinka_hra_pereadresatsiia(tsil: str) -> str:
    return f'''<!doctype html>
<html lang="uk"><head><meta charset="utf-8"><meta name="robots" content="noindex, follow">
<meta http-equiv="refresh" content="0; url={e(tsil)}"><link rel="canonical" href="{e(tsil)}">
<title>Ігри тепер на карті — Моя вулиця</title></head>
<body><p>Ігри тепер граються просто на карті: <a href="{e(tsil)}">відкрити</a>.</p></body></html>
'''


def zibraty_ihry(dn: D.Dani, vykhid: Path, koloda: Path | None, baza: Path | None = None, mezhi: Path | None = None) -> dict:
    """Дані ігор у карті (ZAVDANNYA-117) у /ihry/: справи детектива (кожна — через перевірку site/ihry/detektyv.py; не
    проходить — збирання падає), «Кваліфікуй» (без уривків рішень), налаштування балів, колода гри «Вгадай» (та сама, що й
    у заглушці: справжня або демо) і «Вулиця дня» (якщо з цього випуску вийшла хоч одна загадка)."""
    sys.path.insert(0, str(DZHERELO / 'ihry'))
    sys.path.insert(0, str(DZHERELO / 'hra'))
    import detektyv as DT
    import vulytsia_dnia as VD
    import koloda as KH_
    IHRY_DANI.clear()
    tsil = vykhid / 'ihry'
    spravy = []
    for f in sorted((DZHERELO / 'ihry' / 'spravy').glob('*.json')):
        s = DT.prochytaty(f)
        try:
            DT.perevirka(s)
            DT.zvirka_osm(s)        # координати — з еталона OpenStreetMap (ZAVDANNYA-123)
        except DT.PomylkaSpravy as pomylka:
            raise SystemExit(f'Справа детектива не проходить перевірку: {pomylka}') from pomylka
        spravy.append(DT.dlia_saitu(s))
    zapysaty(tsil / 'detektyv.json', json.dumps({'spravy': spravy}, ensure_ascii=False, separators=(',', ':')))
    if spravy:   # ZAVDANNYA-176: після останнього тижня картки «Детектива» немає — кажемо вголос, до якого дня є справи
        ost = max(datetime.date.fromisoformat(x['tyzhden']) for x in spravy) + datetime.timedelta(days=6)
        print(f'Детектив тижня: справ {len(spravy)}, остання — до {ost.isoformat()}; далі картку гри сховано, доки не буде нової справи')
    IHRY_DANI['spravy'] = '/ihry/detektyv.json'
    kv = json.loads((DZHERELO / 'ihry' / 'kvalifikuy.json').read_text(encoding='utf-8'))
    for s in kv['spravy']:
        s.pop('uryvky', None)
    kv.pop('dzherelo_poroha', None)   # службова примітка для перевірки (ZAVDANNYA-123), на сайт не йде
    zapysaty(tsil / 'kvalifikuy.json', json.dumps(kv, ensure_ascii=False, separators=(',', ':')))
    IHRY_DANI['kvalifikuy'] = '/ihry/kvalifikuy.json'
    # «Кваліфікуй: кар'єра» (ZAVDANNYA-152): справи з випуску й текстів (kariera.py, поза git); немає — гра на зачатку kvalifikuy.json
    kar = DZHERELO / 'ihry' / 'kariera' / 'kariera.json'
    if kar.exists():
        _kar_perevirka(kar)   # ZAVDANNYA-176: ім'я, «кв. N», номер протоколу, обірване речення — сайт не збирається
        shutil.copyfile(kar, tsil / 'kariera.json')
        IHRY_DANI['kariera'] = '/ihry/kariera.json'
    shutil.copyfile(DZHERELO / 'ihry' / 'nalashtuvannia.json', tsil / 'nalashtuvannia.json')
    IHRY_DANI['nalashtuvannia'] = '/ihry/nalashtuvannia.json'
    gotova = KH_.pidhotuvaty(KH_.prochytaty(koloda or KH_.DEMO))
    if gotova['podii']:
        zapysaty(tsil / 'koloda.json', json.dumps(gotova, ensure_ascii=False, separators=(',', ':')))
        IHRY_DANI['koloda'] = '/ihry/koloda.json'
        vd = VD.zibraty_z_dani(dn, gotova)
        if vd['zahadky']:
            zapysaty(tsil / 'vulytsia-dnia.json', json.dumps(vd, ensure_ascii=False, separators=(',', ':')))
            IHRY_DANI['vulytsia'] = '/ihry/vulytsia-dnia.json'
        # «Літопис міста» (ZAVDANNYA-141): з тієї самої колоди; рідкість — за частотами випуску (без конвеєра поруч — за колодою).
        if mezhi and mezhi.exists():
            sys.path.insert(0, str(DZHERELO / 'ihry' / 'litopys'))
            import litopys as LT
            lt = LT.zibraty_z_dani(dn, gotova, LT.chastoty_vydiv(baza) if baza else {},
                                   json.loads(mezhi.read_text(encoding='utf-8')))
            if lt['vulytsi'] and lt['podii']:
                zapysaty(tsil / 'litopys.json', json.dumps(lt, ensure_ascii=False, separators=(',', ':')))
                IHRY_DANI['litopys'] = '/ihry/litopys.json'
    return dict(IHRY_DANI)


# ---------------------------------------------------------------- збирання

def zapysaty_bajty(shlyakh: Path, dani: bytes) -> None:
    shlyakh.parent.mkdir(parents=True, exist_ok=True)
    shlyakh.write_bytes(dani)


def zapysaty(shlyakh: Path, tekst: str) -> None:
    shlyakh.parent.mkdir(parents=True, exist_ok=True)
    shlyakh.write_text(tekst, encoding='utf-8', newline='\n')


def kopiyuvaty_spilne(vykhid: Path) -> None:
    sait = vykhid / 'sait'
    (sait / 'shryfty').mkdir(parents=True, exist_ok=True)
    for f in ('karta.js', 'poshuk.js', 'tema.js', 'oplata.js', 'sp.js', 'sp.css', 'budynok-pole.js', 'vkhid.js', 'vkhid.css',
              'biznes.js', 'biznes.css'):
        shutil.copyfile(DZHERELO / 'sait' / f, sait / f)
    for f in ('hra-yadro.js', 'vulytsia-yadro.js'):          # спільне ядро ігор (ZAVDANNYA-117)
        shutil.copyfile(DZHERELO / 'hra' / f, sait / f)
    for f in ('ihry-yadro.js', 'ihry.js'):
        shutil.copyfile(DZHERELO / 'ihry' / f, sait / f)
    for f in ('litopys-yadro.js', 'litopys.js'):             # «Літопис міста» в панелі ігор (ZAVDANNYA-141)
        shutil.copyfile(DZHERELO / 'ihry' / 'litopys' / f, sait / f)
    for f in ('kariera-yadro.js', 'kariera.js'):             # «Кваліфікуй: кар'єра» в панелі ігор (ZAVDANNYA-152)
        shutil.copyfile(DZHERELO / 'ihry' / 'kariera' / f, sait / f)
    # Кольори обох тем — на початок стилів (одна сторінка стилів, без зайвого запиту); ігри в карті — у кінець.
    zapysaty(sait / 'sait.css', kolory_css() + (DZHERELO / 'sait' / 'sait.css').read_text(encoding='utf-8')
             + '\n' + (DZHERELO / 'ihry' / 'ihry.css').read_text(encoding='utf-8')
             + '\n' + (DZHERELO / 'ihry' / 'litopys' / 'litopys.css').read_text(encoding='utf-8')
             + '\n' + (DZHERELO / 'ihry' / 'kariera' / 'kariera.css').read_text(encoding='utf-8'))
    for f in sorted((DZHERELO / 'sait' / 'shryfty').iterdir()):   # IBM Plex Sans і ліцензія OFL поруч
        shutil.copyfile(f, sait / 'shryfty' / f.name)
    (sait / 'biblioteka').mkdir(exist_ok=True)
    for f in sorted((DZHERELO / 'hra' / 'biblioteka').iterdir()):
        shutil.copyfile(f, sait / 'biblioteka' / f.name)
    shutil.copyfile(DZHERELO / 'hra' / 'mezha-kyieva.geojson', sait / 'mezha-kyieva.geojson')


def zibraty_sait(baza: Path, vykhid: Path, pereimenuvannya: Path | None, mezhi_rayoniv: Path | None,
                 adresa_saitu: str = ADRESA_SAITU, koloda: Path | None = None,
                 zvit_zvedennia: Path | None = None, budynky: Path | None = None,
                 mezha_failiv: int | None = None, khostynh: str = 'pages', perekazy: Path | None = None,
                 kandydaty_istorii: Path | None = None, media: Path | None = None, sudova_praktyka: Path | None = None,
                 prodazh: dict | None = None, oplata: str = 'skoro', zapovnennya: dict | None = None,
                 dlya_publikatsiyi: bool = False, cf_analityka: str = '', domen: str = '',
                 android_vidbytky: list[str] | None = None) -> dict:
    """android_vidbytky — додаткові відбитки ключа застосунку для /.well-known/assetlinks.json (ZAVDANNYA-144; основні —
    у android/twa-manifest.json, поле fingerprints).
    khostynh: 'pages' — кожна сторінка файлом (межа 20 000); 'workers' — будинки в пачках (site/khostynh.py).
    oplata (ZAVDANNYA-132): 'skoro' — на кнопках оплати «Скоро — залиште пошту»; 'tak' — звичайні кнопки (продаж увімкнено).
    prodazh — {'d1', 'servis', 'adresa', 'poshta'} для Workers: з базою D1 форми сайту пишуться в неї (не в Supabase).
    zapovnennya — дані партнера для оферти й політики ([ВЛАСНИК] тощо); dlya_publikatsiyi — зупинитися, якщо щось не заповнено.
    cf_analityka — публічний токен Cloudflare Web Analytics (лічба відвідувань без кукі); domen — свій домен для Workers."""
    import khostynh as KH
    import tsiny as T
    if oplata not in T.REZHYMY_OPLATY:
        raise SystemExit(f'Невідомий режим оплати {oplata!r}: {", ".join(T.REZHYMY_OPLATY)}')
    if oplata == 'tak' and not (prodazh and prodazh.get('servis')):
        raise SystemExit('Оплата «tak» працює лише з сервером продажу: --khostynh workers --d1 … --platizhnyi-servis …')
    T.OPLATA['rezhym'] = oplata
    global CSP, ANALITYKA
    CSP, ANALITYKA = csp_i_analityka(cf_analityka)
    # Сторінки пишуть і інші модулі через `import zibraty_sait` — коли збирач запущено як скрипт, це інший об'єкт модуля.
    import zibraty_sait as _Z
    _Z.CSP, _Z.ANALITYKA = CSP, ANALITYKA
    if khostynh not in KH.VARIANTY:
        raise SystemExit(f'Невідомий варіант хостингу {khostynh!r}: {", ".join(KH.VARIANTY)}')
    if mezha_failiv is None:
        mezha_failiv = KH.MEZHA_FAILIV[khostynh]
    adresa_saitu = adresa_saitu.rstrip('/')
    dn = D.zibraty_dani(baza, pereimenuvannya, mezhi_rayoniv)
    import perekazy as PK
    dn.perekazy = PK.prochytaty(perekazy)
    if vykhid.exists():
        shutil.rmtree(vykhid)
    vykhid.mkdir(parents=True)
    kopiyuvaty_spilne(vykhid)
    vidbytkiv_android = android_faily(vykhid, android_vidbytky)

    vulytsi = [v for v in dn.vulytsi.values() if v.podii]
    vulytsi.sort(key=lambda v: v.slug)
    rayony = sorted({v.rayony.most_common(1)[0][0] for v in vulytsi if v.rayony}, key=kliuch_abetky)
    za_rayonom = defaultdict(list)
    for v in vulytsi:
        if v.rayony:
            za_rayonom[v.rayony.most_common(1)[0][0]].append(v)

    import storinky_mv100 as M
    bud = M.Budynky(budynky, dn, vulytsi) if budynky else None
    kolory = kolory_tem()['svitla']

    adresy = ['/', '/karta/', '/vulytsi/']
    # Публічні місця (ZAVDANNYA-124): спершу список — щоб вулиці й райони посилались на сторінки місць.
    import mistsia as MS
    import storinky_mistsia as SM
    mistsia = MS.zibraty(dn)
    mistsia_vulytsi, mistsia_rayonu = defaultdict(list), defaultdict(list)
    for m in mistsia.values():
        if m.vulytsia:
            mistsia_vulytsi[m.vulytsia].append(m)
        if m.rayon:
            mistsia_rayonu[m.rayon].append(m)
    tsentry_vulyts = {}
    kand_istorii, istorii = {}, 0
    # «Судова практика» (ZAVDANNYA-135): які сторінки статей будуть — щоб сторінки вулиць вели лише на наявні
    sp_statti = None
    if sudova_praktyka:
        import storinky_sp as SP
        sp_statti = {f'{SP.SLUG[s["kodeks"]]}-{s["nomer"]}': s for s in SP.prochytaty(sudova_praktyka)['statti']}
    media_mists = 0
    poruch_vulyts = vulytsi_poruch(dn, vulytsi)
    for v in vulytsi:
        pr = D.profil_vulytsi(dn, v)
        if pr['kandydaty_istorii']:
            kand_istorii[v.slug] = pr['kandydaty_istorii']
        istorii += bool(pr['istoriia'])
        if pr['soty']:
            # Куди летіти з пошуку: центр соти вулиці, де найбільше подій (центр соти, не адреса).
            k = max(pr['soty'], key=lambda x: (x[1], x[0]))[0]
            lat, lon = D.h3.cell_to_latlng(k)
            tsentry_vulyts[v.slug] = (round(lon, 5), round(lat, 5))
        rayon = v.rayony.most_common(1)[0][0] if v.rayony else None
        # ZAVDANNYA-154: спершу вулиці поруч на карті (спільні соти), до 8; замало — доповнюємо сусідами за абеткою в районі
        susidy = [(x.slug, x.nazva, len(x.nedavni)) for x in poruch_vulyts.get(v.slug, [])]
        if rayon and len(susidy) < 4:
            kandydaty = sorted(za_rayonom[rayon], key=lambda x: (kliuch_abetky(x.korotka), x.slug))
            i = kandydaty.index(v)
            vikno = kandydaty[max(0, i - 4):i] + kandydaty[i + 1:i + 5]
            bachyly = {s for s, _, _ in susidy}
            susidy += [(x.slug, x.nazva, len(x.nedavni)) for x in vikno if x.slug not in bachyly][:8 - len(susidy)]
        b_vul = bud.za_vulytseyu.get(v.slug) if bud else None
        md = media_mistsia(media, v)
        if md:      # MV-113: файли візуалу — поруч зі сторінкою місця
            shutil.copytree(media / v.slug, vykhid / 'vulytsia' / v.slug / 'media', dirs_exist_ok=True)
            media_mists += 1
        zapysaty(vykhid / 'vulytsia' / v.slug / 'index.html', storinka_vulytsi(dn, v, pr, adresa_saitu, susidy, b_vul, md, mistsia_vulytsi.get(v.slug), sp_statti))
        zapysaty_bajty(vykhid / 'vulytsia' / v.slug / 'kartynka.png', kartynka_vulytsi(v, pr['vsogo'], b_vul, kolory))
        if len(v.nedavni) >= MIN_PODII_DLYA_POSHUKU:
            adresy.append(f'/vulytsia/{v.slug}/')

    if kandydaty_istorii:   # для кроку перекладів ШІ (dani-edrsr/src/perekazy_istorii.py)
        zapysaty(kandydaty_istorii, json.dumps({'versiia': dn.versiia, 'vulytsi': kand_istorii}, ensure_ascii=False,
                                               indent=0, sort_keys=True))

    # Переадресації зі старих назв.
    zainiati = {v.slug for v in dn.vulytsi.values()}
    pereadresatsii = 0
    perenapravlennia = []
    for stara, tsili in dn.zvedennia.pereimenuvannia:
        tsili = [t for t in tsili if dn.vulytsi[t].podii]
        slug = D.translit(' '.join(w for w in stara.split(' ') if w != 'вулиця'))
        if not tsili or not slug or slug in zainiati:
            continue
        zainiati.add(slug)
        zapysaty(vykhid / 'vulytsia' / slug / 'index.html', storinka_pereadresatsii(stara, tsili, dn, adresa_saitu, slug))
        pereadresatsii += 1
        if len(tsili) == 1:     # ZAVDANNYA-154: справжня переадресація 301 (Cloudflare `_redirects`); сторінка — запасна
            perenapravlennia.append((f'/vulytsia/{slug}/', f'/vulytsia/{tsili[0]}/'))

    # Покажчик.
    zapysaty(vykhid / 'vulytsi' / 'index.html', storinka_pokazhchyka(vulytsi, rayony, adresa_saitu))
    for r in rayony:
        # Д-6 (ZAVDANNYA-110): у покажчику району — лише вулиці з подіями за відкриті роки (без «0»)
        zapysaty(vykhid / 'vulytsi' / slug_rayonu(r) / 'index.html',
                 storinka_pokazhchyka([v for v in za_rayonom[r] if v.nedavni], rayony, adresa_saitu, r))
        adresy.append(f'/vulytsi/{slug_rayonu(r)}/')
    # Т-2 (ZAVDANNYA-110): у пошук — і старі назви з довідника перейменувань («Червоноармійська» → Велика Васильківська).
    stari_nazvy = defaultdict(set)
    for stara, tsili in dn.zvedennia.pereimenuvannia:
        for t in tsili:
            stari_nazvy[t].add(stara)
    pokazhchyk = [[v.slug, v.nazva, v.rayony.most_common(1)[0][0] if v.rayony else '', len(v.nedavni),
                   ' '.join(sorted(set(v.varianty) | stari_nazvy.get(v.slug, set())))]
                  for v in sorted(vulytsi, key=lambda v: (kliuch_abetky(v.korotka), v.slug))]
    zapysaty(vykhid / 'vulytsi' / 'pokazhchyk.json', json.dumps(pokazhchyk, ensure_ascii=False, separators=(',', ':')))
    if bud:   # Т-2: будинки для пошуку «вулиця номер» — окремий файл, сторінка вантажить його, лише коли в запиті є номер
        za_vul = defaultdict(list)
        for b in bud.spysok:
            za_vul[(b['vulytsia'], b['vulytsia_slug'] or '')].append([b['nomer'], b['url']])
        budynky_poshuku = [[n, s, ' '.join(sorted(stari_nazvy.get(s, set()))), sorted(bs, key=lambda x: x[1])]
                           for (n, s), bs in sorted(za_vul.items())]
        zapysaty(vykhid / 'vulytsi' / 'budynky.json', json.dumps(budynky_poshuku, ensure_ascii=False, separators=(',', ':')))

    # Ігри в карті (ZAVDANNYA-117): дані ігор — до сторінок з картою (панель знає, які ігри є).
    zibraty_ihry(dn, vykhid, koloda, baza, mezhi_rayoniv)

    # Карта і головна.
    if D.h3 is None:
        raise SystemExit('Немає бібліотеки h3 (pip install h3) — карту шестикутників не зібрати.')
    soty_rivniv = {}
    for riven in (7, 8, 9):
        soty = soty_geojson(dn, riven)
        soty_rivniv[riven] = soty
        # Т-12 (ZAVDANNYA-125): місяці («Роки оживають», смуга «рік · місяць») рівнів 8 і 9 — окремим файлом: сторінка бере
        # їх лише тоді, коли вони потрібні (видно цей рівень під час «оживання» чи людина обрала рік або місяць).
        # Рівень 7 лишає місяці в собі: з нього рахується лічильник подій і останній місяць смуги.
        if riven in RIVNI_MISIATSI_OKREMO:
            misiatsi = {f['properties']['id']: f['properties'].pop('m') for f in soty['features'] if 'm' in f['properties']}
            zapysaty(vykhid / 'karta' / f'soty-{riven}-m.json',
                     json.dumps({'versiia': dn.versiia, 'riven': riven, 'm': misiatsi}, ensure_ascii=False,
                                separators=(',', ':'), sort_keys=True))
        zapysaty(vykhid / 'karta' / f'soty-{riven}.json',
                 json.dumps({'versiia': dn.versiia, 'riven': riven, 'roky': D.ROKY, 'soty': soty},
                            ensure_ascii=False, separators=(',', ':'), sort_keys=True))
    # Перший екран головної й /karta/ — картинка карти з сотами цього випуску (ZAVDANNYA-164, MV-176); її стилі — у sait.css.
    import zastavka as Z
    css_zastavky, fayly_zastavky = Z.zibraty(soty_rivniv, kolory_tem(), vykhid / 'karta')
    with open(vykhid / 'sait' / 'sait.css', 'a', encoding='utf-8') as f:
        f.write('\n' + css_zastavky)
    zapysaty(vykhid / 'karta' / 'poshuk.json', json.dumps(poshuk_karty(dn, vulytsi, tsentry_vulyts), ensure_ascii=False,
                                                          separators=(',', ':')))
    zapysaty(vykhid / 'karta' / 'index.html', storinka_karty(dn, adresa_saitu, fayly_zastavky))
    zapysaty(vykhid / 'index.html', holovna(dn, vulytsi, rayony, adresa_saitu, bool(sudova_praktyka), fayly_zastavky))
    zapysaty(vykhid / '404.html', storinka_404(adresa_saitu))

    # Будинки, райони, вітрини, оплата-заглушка, видалення, про дані (ZAVDANNYA-85).
    pachky = KH.Pachky(len(bud.spysok)) if (bud and khostynh == 'workers') else None
    adresy += M.zibraty_vse(dn, rayony, za_rayonom, bud, vykhid, adresa_saitu, pachky, len(vulytsi), mistsia_rayonu)
    import storinka_doslidnykam as SD   # «Дані для дослідників» (ZAVDANNYA-158)
    adresy += SD.zibraty(vykhid, adresa_saitu)
    a_mists, media_mists_m, _ = SM.zibraty(dn, vykhid, adresa_saitu, bud, media, mistsia)
    adresy += a_mists
    media_mists += media_mists_m
    if pachky is not None:
        pachky.zapysaty(vykhid)
    # «Судова практика» (ZAVDANNYA-111): з зведенням dani-edrsr — справжній розділ замість вітрини «скоро».
    sp_storinok = 0
    if sudova_praktyka:
        import storinky_sp as SP
        novi = [a for a in SP.zibraty(sudova_praktyka, vykhid, adresa_saitu) if a not in adresy]
        adresy += novi
        sp_storinok = len(novi)
    import storinky_vkhodiv as V   # сторінки-входи під рекламу (ZAVDANNYA-153): noindex, не в sitemap
    V.zibraty(vykhid, adresa_saitu, bud, dn.versiia, D.period_podii(dn), sudova_praktyka)

    # Заглушка з грою — її власним збирачем, без змін.
    import zibraty as zahlushka
    if koloda:   # Б-4 (ZAVDANNYA-110): справжня колода — лише через перевірку для публікації, без обходу
        K = zahlushka.koloda_hry
        try:
            K.dlya_publikatsiyi(K.pidhotuvaty(K.prochytaty(koloda)))
        except K.PomylkaKolody as pomylka:
            raise SystemExit(f'Колоду гри не можна публікувати: {pomylka}') from pomylka
    # Форми заглушки: на Workers з базою — у базу сайту (ZAVDANNYA-132); інакше — Supabase зі змінних середовища (MV-8).
    import os
    skhovyshche = 'sait' if (khostynh == 'workers' and prodazh and prodazh.get('d1')) else 'supabase'
    try:
        nezapovneni = zahlushka.zibraty(vykhid / 'zahlushka', os.environ.get('MV_SUPABASE_URL', ''),
                                        os.environ.get('MV_SUPABASE_PUBLICHNYI_KLYUCH', ''), zapovnennya or {},
                                        dlya_publikatsiyi, koloda, skhovyshche=skhovyshche)
    except zahlushka.PomylkaZbyrannya as pomylka:
        raise SystemExit(f'Сторінки оферти й форм: {pomylka}') from pomylka
    if ANALITYKA:      # лічба відвідувань і на сторінках заглушки (оферта, політика, форми)
        for f in sorted((vykhid / 'zahlushka').rglob('*.html')):
            tekst = f.read_text(encoding='utf-8')
            if "script-src 'self'" not in tekst or '</body>' not in tekst:
                continue     # сторінки без скриптів (зразок довідки) і переадресації — без лічби
            tekst = re.sub(r"connect-src 'none'|connect-src 'self'", lambda m: f"connect-src 'self' {CF_CONNECT}", tekst, count=1)
            tekst = tekst.replace("script-src 'self'", f"script-src 'self' {CF_SKRYPT}", 1).replace('</body>', ANALITYKA + '</body>', 1)
            f.write_text(tekst, encoding='utf-8')
    # ZAVDANNYA-154: канонічна адреса й на сторінках заглушки (оферта, політика, «Хто ми»…) — її збирач адреси сайту не знає
    for f in sorted((vykhid / 'zahlushka').glob('*.html')):
        tekst = f.read_text(encoding='utf-8')
        if 'rel="canonical"' in tekst or '</title>' not in tekst or 'http-equiv="refresh"' in tekst:
            continue
        shl = '/zahlushka/' + ('' if f.name == 'index.html' else f.name)
        f.write_text(tekst.replace('</title>\n', f'</title>\n<link rel="canonical" href="{e(adresa_saitu + shl)}">\n', 1),
                     encoding='utf-8')
    adresy.append('/zahlushka/')
    # Стара сторінка гри — переадресація на гру в карті (ZAVDANNYA-117, MV-129).
    for stara, tsil in (('index.html', '/karta/?hra=vgadai'), ('vulytsia.html', '/karta/?hra=vulytsia')):
        if (vykhid / 'zahlushka' / 'hra' / stara).exists():
            zapysaty(vykhid / 'zahlushka' / 'hra' / stara, storinka_hra_pereadresatsiia(tsil))

    # Для пошуку Google.
    lastmod = dn.versiia if len(dn.versiia) == 10 else ''
    lm = f'<lastmod>{lastmod}</lastmod>' if lastmod else ''

    def urlset(chastyna):
        return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + ''.join(f'<url><loc>{html.escape(adresa_saitu + a)}</loc>{lm}</url>\n' for a in chastyna) + '</urlset>\n')
    if len(adresy) <= min(MEZHA_SITEMAP, ROZBYVATY_SITEMAP_VID):
        zapysaty(vykhid / 'sitemap.xml', urlset(adresy))
    else:
        # ZAVDANNYA-154: індекс і частини за видом сторінок (будинки, вулиці, решта), кожна до MEZHA_SITEMAP адрес — у Search
        # Console видно, скільки саме будинків чи вулиць Google узяв у пошук.
        vydy = defaultdict(list)
        for a in adresy:
            vydy[VYD_SITEMAP.get(a.split('/')[1], 'inshe')].append(a)
        nazvy = []
        for vyd in ('vulytsi', 'budynky', 'rayony', 'inshe'):
            chastyny = [vydy[vyd][i:i + MEZHA_SITEMAP] for i in range(0, len(vydy[vyd]), MEZHA_SITEMAP)]
            for i, ch in enumerate(chastyny, 1):
                nazva = f'sitemap-{vyd}.xml' if len(chastyny) == 1 else f'sitemap-{vyd}-{i}.xml'
                zapysaty(vykhid / nazva, urlset(ch))
                nazvy.append(nazva)
        zapysaty(vykhid / 'sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                 + ''.join(f'<sitemap><loc>{html.escape(adresa_saitu)}/{n}</loc>{lm}</sitemap>\n' for n in nazvy) + '</sitemapindex>\n')
    zapysaty(vykhid / 'robots.txt', robots_txt(adresa_saitu))
    # ZAVDANNYA-154: старі назви вулиць — 301 на нові (Cloudflare Pages і Workers читають `_redirects`; межа — 2 000 правил)
    if perenapravlennia:
        ryadky = []
        for z, na in sorted(perenapravlennia)[:MEZHA_PERENAPRAVLEN // 2]:
            ryadky += [f'{z} {na} 301', f'{z.rstrip("/")} {na} 301']
        zapysaty(vykhid / '_redirects', '# Старі назви вулиць → нові (зібрано site/zibraty_sait.py)\n' + '\n'.join(ryadky) + '\n')

    failiv = sum(1 for p in vykhid.rglob('*') if p.is_file())
    zv = dn.zvedennia
    zvit = {
        'versiia': dn.versiia, 'vulyts': len(vulytsi), 'variantiv_nazv': len(zv.varianty),
        'zlyto_variantiv': sum(max(0, len(v.varianty) - 1) for v in vulytsi),
        'sumnivnykh': len(zv.sumnivni), 'neodnoznachnykh': len(zv.neodnoznachni),
        'pereadresatsii': pereadresatsii, 'sot_riven_8': len(dn.soty[8]), 'sot_riven_9': len(dn.soty[9]), 'failiv': failiv,
        'budynkiv': len(bud.spysok) if bud else 0,
        'budynkiv_u_poshuku': sum(1 for b in bud.spysok if M.Budynky.indeksuvaty(b)) if bud else 0,
        'adres_u_sitemap': len(adresy), 'khostynh': khostynh,
        'pachok_budynkiv': pachky.n if pachky is not None else 0,
        'istorii_vulyts': istorii, 'perekaziv_u_faili': len(dn.perekazy), 'sudova_praktyka_u_sitemap': sp_storinok,
        'media_mists': media_mists,
        'mistsia': len(mistsia),
        'oplata': oplata, 'formy': skhovyshche, 'nezapovneno': len(nezapovneni), 'analityka': bool(ANALITYKA),
        'android_vidbytkiv': vidbytkiv_android,
    }
    if khostynh == 'workers':
        zvit['teka_workera'] = str(KH.pidhotuvaty_worker(vykhid, pachky.n if pachky is not None else 1, prodazh=prodazh,
                                                         oplata=oplata, domen=domen))
    if zvit_zvedennia:
        import csv
        zvit_zvedennia.parent.mkdir(parents=True, exist_ok=True)
        with open(zvit_zvedennia, 'w', encoding='utf-8', newline='') as f:
            w = csv.writer(f)
            w.writerow(['variant', 'storinka', 'nazva', 'podii_variantu', 'sumnivno'])
            sumn = {x[0]: x[2] for x in zv.sumnivni}
            for v in vulytsi:
                for var, n in sorted(v.varianty.items()):
                    w.writerow([var, v.slug, v.nazva, n, sumn.get(var, '')])
    if failiv >= mezha_failiv:
        raise SystemExit(f'Файлів {failiv} — більше межі {mezha_failiv} (Cloudflare, безкоштовно — 20 000 файлів; '
                         f'варіант --khostynh workers складає будинки в пачки; платний план — --mezha-failiv 100000; '
                         f'docs/HOSTYNG.md).')
    return zvit


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Зібрати сайт «Моя вулиця» з випуску бази.')
    p.add_argument('baza', type=Path, help='events-<дата>.db')
    p.add_argument('vykhid', type=Path, help='тека, куди зібрати сайт (буде перезаписана)')
    p.add_argument('--pereimenuvannya', type=Path, help='dani-edrsr/config/pereimenuvannia-kyiv.csv')
    p.add_argument('--mezhi-rayoniv', type=Path, default=KORIN / 'data' / 'borders.json')
    p.add_argument('--adresa-saitu', default=ADRESA_SAITU, help='адреса сайту для sitemap.xml і canonical')
    p.add_argument('--koloda', type=Path, help='справжня колода гри (без неї — демо-колода)')
    p.add_argument('--zvit-zvedennia', type=Path, help='куди записати таблицю зведення назв (CSV) для перевірки')
    p.add_argument('--budynky', type=Path, help='зведення будинків з dani-edrsr (src/budynky_sait.py) — сторінки будинків')
    p.add_argument('--khostynh', choices=('pages', 'workers'), default='pages',
                   help='pages — кожна сторінка файлом; workers — будинки в пачках для Cloudflare Workers (docs/HOSTYNG.md)')
    p.add_argument('--perekazy', type=Path, help='перекази ШІ для історій вулиць (dani-edrsr/src/perekazy_istorii.py); '
                   'без них блоку «Одна історія з вулиці» немає')
    p.add_argument('--kandydaty-istorii', type=Path, help='куди записати події-кандидати історій вулиць (вхід кроку переказів)')
    p.add_argument('--sudova-praktyka', type=Path, help='зведення «Судової практики» з dani-edrsr (src/sudova_praktyka.py sait) — '
                   'розділ і сторінки статей; без нього — вітрина «скоро»')
    p.add_argument('--media', type=Path, help='візуали публічних місць для медіа (brend/media/zrobyty_media.py, тека <slug>/ на місце); '
                   'без них блоку «Для медіа» немає')
    p.add_argument('--mezha-failiv', type=int, help='межа кількості файлів (план хостингу; без ключа — 20 000)')
    p.add_argument('--d1', '--prodazh-d1', dest='prodazh_d1',
                   help='ідентифікатор бази Cloudflare D1: форми сайту й «скоро» (і продаж з --oplata tak); docs/ZAPUSK-SAITU.md')
    p.add_argument('--oplata', choices=('skoro', 'tak'), default='skoro',
                   help='skoro — «Скоро — залиште пошту» на кнопках оплати (типово); tak — справжній продаж (потрібен --platizhnyi-servis)')
    p.add_argument('--platizhnyi-servis', choices=('liqpay', 'mono', 'test'), help='платіжний сервіс для продажу')
    p.add_argument('--zapovnennya', type=Path, help='JSON з даними партнера для оферти й політики ({"ВЛАСНИК": "…", …})')
    p.add_argument('--dlya-publikatsiyi', action='store_true', help='зупинитися, якщо в оферті чи політиці лишилось [НЕЗАПОВНЕНЕ]')
    p.add_argument('--cf-analityka', default='', help='публічний токен Cloudflare Web Analytics (лічба відвідувань без кукі)')
    p.add_argument('--android-vidbytok', action='append', default=[],
                   help='відбиток SHA-256 ключа застосунку Android (AB:CD:…) для /.well-known/assetlinks.json; можна кілька разів '
                        '(ZAVDANNYA-144; постійні — у android/twa-manifest.json, fingerprints)')
    p.add_argument('--domen', default='', help='свій домен для Workers (напр. moyavulytsya.com.ua) — прив\'язка під час викладки')
    p.add_argument('--poshta-servis', choices=('zahlushka', 'http-json'), default='zahlushka', help='сервіс листів')
    p.add_argument('--karta-r2', action='store_true', help='карта підписника зі сховища R2 moya-vulytsya-karta (лише з --oplata tak; '
                   'docs/PLATNA-CHASTYNA.md, розд. 2)')
    p.add_argument('--biznes-r2', action='store_true', help='«Для бізнесу»: копії бази для компаній зі сховища R2 '
                   'moya-vulytsya-biznes (docs/BIZNES-DOSTUP.md)')
    a = p.parse_args(argv)
    prodazh = None
    if a.prodazh_d1 or a.platizhnyi_servis:
        if a.khostynh != 'workers':
            p.error('база D1 і продаж працюють лише з --khostynh workers')
        prodazh = {'d1': a.prodazh_d1, 'servis': a.platizhnyi_servis if a.oplata == 'tak' else None,
                   'adresa': a.adresa_saitu, 'poshta': a.poshta_servis, 'karta': a.karta_r2, 'biznes': a.biznes_r2}
    zapovnennya = json.loads(a.zapovnennya.read_text(encoding='utf-8')) if a.zapovnennya else None
    zvit = zibraty_sait(a.baza, a.vykhid, a.pereimenuvannya, a.mezhi_rayoniv, a.adresa_saitu, a.koloda,
                        a.zvit_zvedennia, a.budynky, a.mezha_failiv, a.khostynh, a.perekazy, a.kandydaty_istorii,
                        media=a.media, sudova_praktyka=a.sudova_praktyka, prodazh=prodazh, oplata=a.oplata,
                        zapovnennya=zapovnennya, dlya_publikatsiyi=a.dlya_publikatsiyi, cf_analityka=a.cf_analityka,
                        domen=a.domen, android_vidbytky=a.android_vidbytok)
    for k, v in zvit.items():
        print(f'{k}: {v}')
    return 0



def _kar_perevirka(kar: Path) -> None:
    """Справи «кар'єри» перед публікацією — тією самою перевіркою, що й збирач (site/ihry/kariera/kariera.py, ZAVDANNYA-176)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location('kariera_perevirka', DZHERELO / 'ihry' / 'kariera' / 'kariera.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    bidy = mod.perevirka(json.loads(kar.read_text(encoding='utf-8')))
    if bidy:
        raise SystemExit(f"kariera.json: справи не годяться для показу ({len(bidy)}): " +
                         '; '.join(f'{d} {p}: «{u}»' for d, p, u in bidy[:10]) + ' — перезберіть kariera.py')

if __name__ == '__main__':
    sys.exit(main())
