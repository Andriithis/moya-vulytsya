"""Збирання сайту «Моя вулиця» з випуску бази (ZAVDANNYA-10, MV-23).

    python site/zibraty_sait.py <events.db> <тека> [--pereimenuvannya CSV] [--mezhi-rayoniv JSON]
                                [--adresa-saitu https://…] [--koloda КОЛОДА]

Що збирає (лише файли, без сервера — під Cloudflare Pages):
  /                         головна: пошук вулиці, входи в карту, покажчик, гру, звіт
  /karta/                   карта Києва шестикутниками H3 рівня 9 (soty.json поруч)
  /vulytsi/                 покажчик вулиць за абеткою; /vulytsi/<район>/ — за районами
  /vulytsia/<slug>/         сторінка кожної вулиці (узагальнене, безкоштовне)
  /vulytsia/<стара-назва>/  переадресація зі старої назви на нову (довідник перейменувань)
  /zahlushka/               заглушка з формою і грою (site/zahlushka/zibraty.py, без змін)
  sitemap.xml, robots.txt, 404.html

Повторний запуск на тому самому випуску дає ті самі файли: ні часу збирання, ні випадковостей.
Нічого не публікує.
"""
from __future__ import annotations

import argparse
import html
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path

DZHERELO = Path(__file__).resolve().parent
KORIN = DZHERELO.parent
sys.path.insert(0, str(DZHERELO / 'sait'))
sys.path.insert(0, str(DZHERELO / 'zahlushka'))

import dani as D  # noqa: E402

TSINA_ANALIZU = 690             # MV-11
ADRESA_SAITU = 'https://moya-vulytsya.pages.dev'   # умовна; справжній домен — на партнера (MV-23)
MEZHA_FAILIV = 20000            # межа Cloudflare Pages
# Вулиці з 1–2 подіями: сторінка є (на неї ведуть покажчик і карта), але пошуку Google її не даємо
# і в sitemap.xml не пишемо — «тонкі» сторінки шкодять усьому сайту в пошуку.
MIN_PODII_DLYA_POSHUKU = 3
NBSP = ' '

CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data: blob:; "
       "worker-src 'self' blob:; child-src 'self' blob:; connect-src 'self' https://tiles.openfreemap.org; "
       "form-action 'self'; base-uri 'none'")

ZNAK = ('<svg aria-hidden="true" width="26" height="28" viewBox="0 0 26 28"><path class="lohotyp__soty" '
        'd="M13 1 L25 8 L25 20 L13 27 L1 20 L1 8 Z"></path><path class="lohotyp__vnutr" '
        'd="M13 9 L18 12 L18 17 L13 20 L8 17 L8 12 Z"></path></svg>')

RODOVYI_RAYONU = {}   # «Голосіївський» → «Голосіївський район»


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

def storinka(*, shlyakh: str, title: str, opys: str, tilo: str, adresa_saitu: str, aktyvne: str = '',
             skrypty: tuple[str, ...] = (), dodatkovo_head: str = '', mapa: bool = False, indeksuvaty: bool = True,
             pered_main: str = '') -> str:
    menyu = [('karta/', 'Карта'), ('vulytsi/', 'Вулиці'), ('zahlushka/hra/', 'Грати'), ('zahlushka/zrazok.html', 'Зразок звіту')]
    punkty = []
    for i, (h, n) in enumerate(menyu):
        klas = ' class="lyshe-komp"' if i == 3 else ''
        cur = ' aria-current="page"' if h == aktyvne else ''
        punkty.append(f'<a{klas} href="/{h}"{cur}>{n}</a>')
    css_mapy = '<link rel="stylesheet" href="/sait/biblioteka/maplibre-gl.css">\n' if mapa else ''
    js = ''.join(f'<script src="{s}"></script>\n' for s in skrypty)
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
<meta name="theme-color" content="#0B6B6B">
<link rel="icon" type="image/png" sizes="192x192" href="/zahlushka/ikony/ikona-192.png">
<link rel="preload" href="/sait/shryfty/manrope-cyrillic-800-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="/sait/shryfty/inter-cyrillic-400-normal.woff2" as="font" type="font/woff2" crossorigin>
{css_mapy}<link rel="stylesheet" href="/sait/sait.css">
{dodatkovo_head}</head>
<body>
<header class="shapka">
<div class="shapka__vnutri">
<a class="lohotyp" href="/">{ZNAK}<span class="lohotyp__nazva">Моя вулиця</span></a>
<nav class="menyu" aria-label="Розділи">{''.join(punkty)}</nav>
</div>
</header>
{pered_main}<main class="storinka">
{tilo}
</main>
<footer class="pidval">
<div class="pidval__vnutri">
<p>Дані — з рішень судів у Єдиному державному реєстрі судових рішень. Це лише те, що дійшло до суду, а не всі події на вулиці.</p>
<p>Колір і числа показують, скільки подій у даних, а не те, наскільки тут «страшно». Ми не стверджуємо причин і не прогнозуємо.</p>
<p><a href="/zahlushka/zvernennya.html">Виправити або прибрати подію</a> · <a href="/zahlushka/polityka.html">Політика конфіденційності</a> · <a href="/zahlushka/oferta.html">Оферта</a> · Карта: <a href="https://www.openstreetmap.org/copyright">© учасники OpenStreetMap</a></p>
</div>
</footer>
{js}</body>
</html>
'''


def lehenda() -> str:
    klitynky = ''.join(f'<i class="d{i}"></i>' for i in range(1, 6))
    return (f'<div class="lehenda"><span>менше</span><span class="lehenda__shkala" aria-hidden="true">{klitynky}</span>'
            f'<span>більше подій</span><span>Темніше — більше подій у даних, не «небезпечніше».</span></div>')


# ---------------------------------------------------------------- сторінка вулиці

def ryadok_vydu(x: dict) -> str:
    tut = x['chastka']
    misto = x['chastka_misto']
    shkala = max(tut, misto) or 1
    raz = x['lq']
    raz_t = f'{raz:.1f}'.replace('.', ',')
    return f'''<div class="kartka vyd">
<div class="vyd__nazva">{e(x['vyd'])}</div>
<div class="vyd__ryad"><span>ця вулиця</span><span class="vyd__smuha vyd__smuha--tut"><i style="width:{tut / shkala * 100:.0f}%"></i></span><b>{vidsotok(tut)}</b></div>
<div class="vyd__ryad"><span>Київ</span><span class="vyd__smuha vyd__smuha--misto"><i style="width:{misto / shkala * 100:.0f}%"></i></span><b>{vidsotok(misto)}</b></div>
<p class="prymitka">{podii_slovo(x['n'])} на вулиці. Частка серед подій вулиці в {raz_t} раза більша, ніж по Києву.</p>
</div>'''


def kontur_soty(k: str) -> list:
    kontur = [[round(lon, 5), round(lat, 5)] for lat, lon in D.h3.cell_to_boundary(k)]
    return kontur + [kontur[0]]


def klas_shkaly(n: int, maks: int) -> int:
    if n <= 0 or maks <= 0:
        return 0
    return min(5, 1 + int(4 * n / maks)) if maks > 1 else 5


def storinka_vulytsi(dn: D.Dani, v: D.Vulytsia, pr: dict, adresa_saitu: str, susidy: list) -> str:
    rayon = v.rayony.most_common(1)[0][0] if v.rayony else None
    inshi_rayony = [r for r, _ in v.rayony.most_common()[1:] if v.rayony[r] >= 3]
    vsogo = pr['vsogo']
    roky_t = (f'{pr["pershyi_rik"]}–{pr["ostannii_rik"]}' if pr['pershyi_rik'] and pr['ostannii_rik'] and pr['pershyi_rik'] != pr['ostannii_rik']
              else str(pr['ostannii_rik'] or ''))
    rayon_t = f'{rayon} район' if rayon else 'Київ'
    title = f'{v.nazva}, Київ — {podii_slovo(vsogo)} у даних судів | Моя вулиця'
    vydy_t = ', '.join(x['vyd'].lower() for x in pr['vyriznennia'][:2])
    opys = (f'{v.nazva} ({rayon_t}): {podii_slovo(vsogo)} з судових рішень'
            + (f' за {roky_t}' if roky_t else '') + '. Роки, дні й години' + (f', що вирізняє вулицю: {vydy_t}' if vydy_t else '') + '.')

    chastyny = []
    kryhty = [f'<a href="/">Головна</a><span aria-hidden="true">›</span><a href="/vulytsi/">Вулиці</a>']
    if rayon:
        kryhty.append(f'<span aria-hidden="true">›</span><a href="/vulytsi/{slug_rayonu(rayon)}/">{e(rayon)}</a>')
    chastyny.append(f'<nav class="kryhty" aria-label="Де ви">{"".join(kryhty)}</nav>')
    dodatkovi_rayony = f' Частково — {", ".join(e(r) for r in inshi_rayony)}.' if inshi_rayony else ''
    chastyny.append(f'''<section class="zaholovok">
<span class="mitka">{e(rayon_t)}</span>
<h1>{e(v.nazva)}</h1>
<p>{podii_slovo(vsogo)} у даних судів{(" за " + roky_t) if roky_t else ""}.{dodatkovi_rayony}</p>
</section>''')

    # Коротко: числа
    vsogo_rokiv = sum(pr['roky'].values())
    ostannii = pr['roky'].get(D.ROKY[-1], 0)
    chysla = [(chyslo(vsogo), 'подій у даних'), (chyslo(pr['mists']), 'різних місць на вулиці')]
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

    # Роки
    maks = max(pr['roky'].values()) or 1
    stovpchyky = ''.join(
        f'<div class="rik"><span class="rik__chyslo">{chyslo(n) if n else ""}</span>'
        f'<span class="rik__stovpchyk" style="height:{max(2, round(n / maks * 140))}px"></span><span>{r}</span></div>'
        for r, n in pr['roky'].items())
    pidpys_rokiv = 'Більшість рішень за 2016–2023 ще завантажується, тому старі роки поки неповні.'
    if pr['poza_rokamy']:
        pidpys_rokiv += f' Ще {podii_slovo(pr["poza_rokamy"])} — без дати або раніше 2016.'
    roky_tablytsia = ''.join(f'<tr><th scope="row">{r}</th><td>{n}</td></tr>' for r, n in pr['roky'].items())
    chastyny.append(f'''<section class="rozdil"><h2>Події за роками</h2>
<p class="rozdil__pidpys">{pidpys_rokiv}</p>
<div class="kartka"><div class="roky" aria-hidden="true">{stovpchyky}</div>
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
<div class="dva-stovptsi"><div class="karta-ramka"><div id="karta-vulytsi" class="karta" aria-label="Карта вулиці {e(v.nazva)}"></div>
<p class="karta__zboi" hidden>Підкладка карти не завантажилася — видно межу Києва й шестикутники.</p>
<noscript><p class="karta-bez-js">Щоб побачити карту, увімкніть JavaScript.</p></noscript></div>
<div class="kartka zamok" aria-disabled="true"><p class="zamok__nazva">Події по будинках цієї вулиці — у підписці</p>
<p class="prymitka">Скільки подій біля кожного будинку, що саме сталося й коли. На безкоштовній сторінці — лише вулиця загалом.</p></div></div>
<script type="application/json" id="soty-vulytsi">{json.dumps(soty_vulytsi, separators=(",", ":"))}</script></section>''')

    # Історія
    if pr['istoriia']:
        ist = pr['istoriia']
        dzherelo = f' <a href="{e(ist["url"])}" rel="nofollow noopener" target="_blank">Рішення суду</a>.' if ist.get('url') else ''
        chastyny.append(f'''<section class="rozdil"><h2>Одна історія з вулиці</h2>
<div class="kartka istoriia"><span class="mitka mitka--chernetka">Чернетка, перепише ШІ</span>
<blockquote>{e(ist["tekst"])}</blockquote>
<p>{e(ist["vyd"])}{", " + str(ist["rik"]) + " рік" if ist.get("rik") else ""}. Уривок з рішення суду; імена й номери квартир прибрано.{dzherelo}</p></div></section>''')

    # Дії
    chastyny.append(f'''<section class="rozdil"><h2>Що далі</h2>
<div class="diyi">
<a class="knopka knopka--holovna" href="/zahlushka/?dzherelo=vulytsia#peredzamovlennya">Звіт по адресі — {TSINA_ANALIZU}{NBSP}грн</a>
<a class="knopka" href="/zahlushka/hra/">Грати</a>
<a class="knopka" href="/zahlushka/?dzherelo=vulytsia-misto#peredzamovlennya">Ваша вулиця в іншому місті — повідомимо</a>
</div></section>''')

    if susidy:
        chastyny.append('<section class="rozdil"><h2>Інші вулиці району</h2><ul class="spysok-vulyts">' + ''.join(
            f'<li><a href="/vulytsia/{s}/">{e(n)}</a><small>{chyslo(k)}</small></li>' for s, n, k in susidy) + '</ul></section>')

    chastyny.append('<p class="prymitka">Дані — з рішень судів, які дійшли до реєстру; це не всі події на вулиці. '
                    f'Події без точної адреси сюди не потрапили. Справи про домашнє насильство, статеві злочини й справи щодо дітей '
                    f'на сторінках вулиць не показуємо зовсім — лише в загальному числі на карті Києва. Дані станом на {e(dn.versiia)}.</p>')

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
    ld = json.dumps(place, ensure_ascii=False, sort_keys=True).replace('</', '<\\/')
    head = f'<script type="application/ld+json">{ld}</script>\n'
    return storinka(shlyakh=f'/vulytsia/{v.slug}/', title=title, opys=opys, tilo='\n'.join(chastyny),
                    adresa_saitu=adresa_saitu, aktyvne='vulytsi/', mapa=True, dodatkovo_head=head,
                    indeksuvaty=vsogo >= MIN_PODII_DLYA_POSHUKU,
                    skrypty=('/sait/biblioteka/maplibre-gl-csp.js', '/sait/karta.js'))


def storinka_pereadresatsii(stara: str, tsili: list, dn: D.Dani, adresa_saitu: str) -> str:
    if len(tsili) == 1:
        v = dn.vulytsi[tsili[0]]
        url = f'/vulytsia/{v.slug}/'
        tilo = (f'<section class="zaholovok"><h1>{e(stara)} — тепер {e(v.nazva)}</h1>'
                f'<p>Вулицю перейменовано. Переходимо на сторінку <a href="{url}">{e(v.nazva)}</a>.</p></section>')
        head = f'<meta http-equiv="refresh" content="0; url={url}">\n'
        return storinka(shlyakh=url, title=f'{stara} — тепер {v.nazva} | Моя вулиця',
                        opys=f'{stara} у Києві перейменовано на «{v.nazva}».', tilo=tilo, adresa_saitu=adresa_saitu,
                        dodatkovo_head=head, indeksuvaty=False)
    spysok = ''.join(f'<li><a href="/vulytsia/{s}/">{e(dn.vulytsi[s].nazva)}</a></li>' for s in tsili)
    tilo = (f'<section class="zaholovok"><h1>{e(stara)}</h1><p>У Києві було кілька вулиць з цією назвою; '
            f'їх перейменовано по-різному. Оберіть:</p></section><ul class="spysok-vulyts">{spysok}</ul>')
    return storinka(shlyakh='/vulytsi/', title=f'{stara} — перейменовано | Моя вулиця',
                    opys=f'{stara} у Києві перейменовано.', tilo=tilo, adresa_saitu=adresa_saitu, indeksuvaty=False)


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
        f'<li><a href="/vulytsia/{v.slug}/">{e(v.nazva)}</a><small>{chyslo(len(v.podii))}</small></li>' for v in vs) + '</ul>'


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
<p>{chyslo(len(vs))} {vidminok(len(vs), ("вулиця", "вулиці", "вулиць"))} з подіями в даних судів. Поруч із назвою — скільки подій.</p></section>
<form class="poshuk" role="search" action="/vulytsi/"><label class="prykhovano" for="poshuk-vulytsi">Назва вулиці</label>
<input id="poshuk-vulytsi" type="search" autocomplete="off" placeholder="Назва вулиці, наприклад: Хрещатик">
<ul class="poshuk__spysok" id="poshuk-spysok" hidden></ul></form>
{rayony_html}
{abetka}
<section class="rozdil">{sektsii}</section>
<p class="prymitka">Назви звели до однієї: «просп. В. Лобановського» і «проспект Валерія Лобановського» — одна сторінка. Старі назви ведуть на нові.</p>'''
    opys = (f'Покажчик вулиць Києва ({rayon} район) з кількістю подій у даних судів.' if rayon
            else 'Покажчик вулиць Києва за абеткою й районами: скільки подій із судових рішень на кожній вулиці.')
    return storinka(shlyakh=shlyakh, title=f'{nazva} — події в даних судів | Моя вулиця', opys=opys, tilo=tilo,
                    adresa_saitu=adresa_saitu, aktyvne='vulytsi/', skrypty=('/sait/poshuk.js',))


def holovna(dn: D.Dani, vulytsi: list, rayony: list, adresa_saitu: str) -> str:
    """Головна — одразу карта Києва з пошуком (AGENTS.md, розд. 3: без вступу), під нею — входи."""
    tilo = f'''<section class="vstup-ryad">
<div><h1 class="h-mala">Що суди розповіли про вашу вулицю</h1>
<p class="prymitka">{chyslo(len(vulytsi))} вулиць Києва зі своєю сторінкою: скільки подій, коли, яких видів. Дані станом на {e(dn.versiia)};
рішення за 2016–2023 ще завантажуються.</p></div>
</section>
<section class="vkhody" aria-label="Куди далі">
<a class="vkhid" href="/vulytsi/"><span class="mikro">Покажчик</span><b>Усі вулиці</b><span>за абеткою й районами</span></a>
<a class="vkhid" href="/zahlushka/hra/"><span class="mikro">Гра</span><b>Вгадай, де це було</b><span>опис події — ваша точка на карті</span></a>
<a class="vkhid" href="/zahlushka/?dzherelo=holovna#peredzamovlennya"><span class="mikro">Звіт по адресі</span><b>{TSINA_ANALIZU}{NBSP}грн</b><span>будинок, район і місто, 10 років</span></a>
</section>
<section class="rozdil"><h2 class="mikro">Вулиці за районами</h2>
<nav class="rayony" aria-label="Райони">{"".join(f'<a href="/vulytsi/{slug_rayonu(r)}/">{e(r)}</a>' for r in rayony)}</nav></section>'''
    return storinka(shlyakh='/', title='Моя вулиця — що суди розповіли про вашу вулицю у Києві',
                    opys='Карта Києва з подіями із судових рішень: скільки, коли, яких видів — на кожній вулиці. Покажчик вулиць, гра.',
                    tilo=tilo, adresa_saitu=adresa_saitu, mapa=True, pered_main=ekran_karty(dn, True),
                    skrypty=('/sait/biblioteka/maplibre-gl-csp.js', '/sait/karta.js', '/sait/poshuk.js'))


def soty_geojson(dn: D.Dani, riven: int) -> dict:
    """Файл сот одного рівня для карти. Колір і шкалу рахує сторінка під обрану групу й період.

    Властивості: id; числа груп «<група><період>» (dor3, dorA … allA; 3 — останні 3 роки, A — усі);
    y — події за роками 2016–2026; h — година-пік; p — чинні проблеми (назва сценарію, без адреси);
    t — «що страждає» по групах ({група: [[що, скільки]]}, лише ≥ 5 подій); a — скільки подій з адресами й описами (для рядка про підписку);
    u — вулиці (лише на рівні 9)."""
    features = []
    for k in sorted(dn.soty[riven]):
        s = dn.soty[riven][k]
        vl = {'id': k}
        for kl, n in sorted(s['chysla'].items()):
            vl[kl] = n
        vl['y'] = [s['roky'].get(r, 0) for r in D.ROKY]
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
        if riven == 9:
            vl['u'] = [[sl, dn.vulytsi[sl].nazva] for sl, n in sorted(s['vulytsi'].items(), key=lambda x: (-x[1], x[0]))[:4]
                       if sl in dn.vulytsi and dn.vulytsi[sl].podii]
        features.append({'type': 'Feature', 'properties': vl, 'geometry': {'type': 'Polygon', 'coordinates': [kontur_soty(k)]}})
    return {'type': 'FeatureCollection', 'features': features}


def ekran_karty(dn: D.Dani, z_poshukom: bool) -> str:
    """Карта на весь екран: панель керування праворуч (телефон — смуга внизу), картка соти ліворуч
    (телефон — шторка на пів екрана). Поведінка — як у навчальній карті Києва (S-К.4, S-К.6, S-К.13,
    S-К.18, S-К.21); вигляд — лише наш."""
    vsogo = sum(s['chysla']['allA'] for s in dn.soty[8].values())
    ostannii = D.ROKY[-1] - D.OSTANNI_ROKY + 1
    hrupy = ''.join(
        f'<li><button type="button" class="vyd-perem" data-hrupa="{k}" aria-pressed="true">'
        f'<i class="vyd-krapka vyd-{k}" aria-hidden="true"></i><span>{e(n)}</span><b data-chyslo="{k}"></b></button></li>'
        for k, n in D.HRUPY)
    poshuk = ''
    if z_poshukom:
        poshuk = ('<form class="poshuk poshuk--karta" role="search" action="/vulytsi/"><label class="prykhovano" for="poshuk-vulytsi">Назва вулиці</label>'
                  '<input id="poshuk-vulytsi" type="search" autocomplete="off" placeholder="Знайти вулицю">'
                  '<ul class="poshuk__spysok" id="poshuk-spysok" hidden></ul></form>')
    return f'''<section class="ekran-karty" aria-label="Карта Києва">
<div id="karta-mista" class="karta-povna" data-soty-8="/karta/soty-8.json" data-soty-9="/karta/soty-9.json"></div>
<noscript><p class="karta-bez-js">Щоб побачити карту, увімкніть JavaScript. Без нього — <a href="/vulytsi/">покажчик вулиць</a>.</p></noscript>
<p class="karta__zboi" hidden>Підкладка карти не завантажилася — видно межу Києва й соти.</p>
<aside class="keruvannia" id="keruvannia" aria-label="Що показати">
<p class="mikro">Київ · події з рішень судів</p>
<p class="keruvannia__vsogo"><b class="chyslo-velyke" id="vsogo-podii">{chyslo(vsogo)}</b> <span id="vsogo-pidpys">подій на карті</span></p>
{poshuk}
<div class="keruvannia__period" role="group" aria-label="Період">
<button type="button" class="seg" data-period="3" aria-pressed="true">{ostannii}–{D.ROKY[-1]}</button><button type="button" class="seg" data-period="A" aria-pressed="false">Усі роки</button>
</div>
<button type="button" class="keruvannia__rozgornuty" id="vydy-rozgornuty" aria-expanded="false" aria-controls="vydy">Види подій</button>
<ul class="vydy" id="vydy" aria-label="Види подій">{hrupy}</ul>
<p class="keruvannia__poiasnennia">Колір — вид, якого в соті помітно більше, ніж у середньому по Києву. Прозоріше — менше подій у даних, не «небезпечніше».</p>
</aside>
<button type="button" class="knopka-3d" id="knopka-3d" aria-pressed="false" aria-label="Показати стовпчиками">3D</button>
<aside class="kartka-soty" id="panel" hidden aria-live="polite" aria-label="Шестикутник">
<button class="kartka-soty__zakryty" id="panel-zakryty" type="button" aria-label="Закрити">×</button>
<div id="panel-vmist"></div>
</aside>
<div class="pidkazka-soty" id="pidkazka" hidden></div>
</section>
'''


def storinka_karty(dn: D.Dani, adresa_saitu: str) -> str:
    tilo = '''<section class="rozdil vuzko"><h1 class="h-mala">Карта Києва: події з судових рішень</h1>
<p class="prymitka">Великі соти — близько 0,7 км², при наближенні — близько 0,1 км². Безкоштовно — лише числа по сотах, без адрес і описів.
Справи про домашнє насильство, статеві злочини й справи щодо дітей входять лише в число великих сот у групі «Насильство».
Насильство показуємо лише числом. Дані — це те, що дійшло до суду, а не всі події.</p></section>'''
    return storinka(shlyakh='/karta/', title='Карта Києва — події з судових рішень | Моя вулиця',
                    opys='Карта Києва шестикутниками: скільки подій із судових рішень у кожній частині міста, яких видів і коли.',
                    tilo=tilo, adresa_saitu=adresa_saitu, aktyvne='karta/', mapa=True, pered_main=ekran_karty(dn, False),
                    skrypty=('/sait/biblioteka/maplibre-gl-csp.js', '/sait/karta.js'))


def storinka_404(adresa_saitu: str) -> str:
    tilo = ('<section class="zaholovok"><h1>Такої сторінки немає</h1><p>Можливо, вулицю перейменовано або в даних поки немає подій. '
            'Спробуйте <a href="/vulytsi/">покажчик вулиць</a> або <a href="/karta/">карту Києва</a>.</p></section>')
    return storinka(shlyakh='/404.html', title='Сторінку не знайдено | Моя вулиця', opys='Сторінку не знайдено.',
                    tilo=tilo, adresa_saitu=adresa_saitu, indeksuvaty=False)


# ---------------------------------------------------------------- збирання

def zapysaty(shlyakh: Path, tekst: str) -> None:
    shlyakh.parent.mkdir(parents=True, exist_ok=True)
    shlyakh.write_text(tekst, encoding='utf-8', newline='\n')


def kopiyuvaty_spilne(vykhid: Path) -> None:
    sait = vykhid / 'sait'
    (sait / 'shryfty').mkdir(parents=True, exist_ok=True)
    for f in ('sait.css', 'karta.js', 'poshuk.js'):
        shutil.copyfile(DZHERELO / 'sait' / f, sait / f)
    for f in sorted((DZHERELO / 'zahlushka' / 'shryfty').iterdir()):
        shutil.copyfile(f, sait / 'shryfty' / f.name)
    (sait / 'biblioteka').mkdir(exist_ok=True)
    for f in sorted((DZHERELO / 'hra' / 'biblioteka').iterdir()):
        shutil.copyfile(f, sait / 'biblioteka' / f.name)
    shutil.copyfile(DZHERELO / 'hra' / 'mezha-kyieva.geojson', sait / 'mezha-kyieva.geojson')


def zibraty_sait(baza: Path, vykhid: Path, pereimenuvannya: Path | None, mezhi_rayoniv: Path | None,
                 adresa_saitu: str = ADRESA_SAITU, koloda: Path | None = None,
                 zvit_zvedennia: Path | None = None) -> dict:
    adresa_saitu = adresa_saitu.rstrip('/')
    dn = D.zibraty_dani(baza, pereimenuvannya, mezhi_rayoniv)
    if vykhid.exists():
        shutil.rmtree(vykhid)
    vykhid.mkdir(parents=True)
    kopiyuvaty_spilne(vykhid)

    vulytsi = [v for v in dn.vulytsi.values() if v.podii]
    vulytsi.sort(key=lambda v: v.slug)
    rayony = sorted({v.rayony.most_common(1)[0][0] for v in vulytsi if v.rayony}, key=kliuch_abetky)
    za_rayonom = defaultdict(list)
    for v in vulytsi:
        if v.rayony:
            za_rayonom[v.rayony.most_common(1)[0][0]].append(v)

    adresy = ['/', '/karta/', '/vulytsi/']
    for v in vulytsi:
        pr = D.profil_vulytsi(dn, v)
        rayon = v.rayony.most_common(1)[0][0] if v.rayony else None
        susidy = []
        if rayon:
            kandydaty = sorted(za_rayonom[rayon], key=lambda x: (kliuch_abetky(x.korotka), x.slug))
            i = kandydaty.index(v)
            vikno = kandydaty[max(0, i - 4):i] + kandydaty[i + 1:i + 5]
            susidy = [(x.slug, x.nazva, len(x.podii)) for x in vikno]
        zapysaty(vykhid / 'vulytsia' / v.slug / 'index.html', storinka_vulytsi(dn, v, pr, adresa_saitu, susidy))
        if len(v.podii) >= MIN_PODII_DLYA_POSHUKU:
            adresy.append(f'/vulytsia/{v.slug}/')

    # Переадресації зі старих назв.
    zainiati = {v.slug for v in dn.vulytsi.values()}
    pereadresatsii = 0
    for stara, tsili in dn.zvedennia.pereimenuvannia:
        tsili = [t for t in tsili if dn.vulytsi[t].podii]
        slug = D.translit(' '.join(w for w in stara.split(' ') if w != 'вулиця'))
        if not tsili or not slug or slug in zainiati:
            continue
        zainiati.add(slug)
        zapysaty(vykhid / 'vulytsia' / slug / 'index.html', storinka_pereadresatsii(stara, tsili, dn, adresa_saitu))
        pereadresatsii += 1

    # Покажчик.
    zapysaty(vykhid / 'vulytsi' / 'index.html', storinka_pokazhchyka(vulytsi, rayony, adresa_saitu))
    for r in rayony:
        zapysaty(vykhid / 'vulytsi' / slug_rayonu(r) / 'index.html', storinka_pokazhchyka(za_rayonom[r], rayony, adresa_saitu, r))
        adresy.append(f'/vulytsi/{slug_rayonu(r)}/')
    pokazhchyk = [[v.slug, v.nazva, v.rayony.most_common(1)[0][0] if v.rayony else '', len(v.podii),
                   ' '.join(sorted(v.varianty))] for v in sorted(vulytsi, key=lambda v: (kliuch_abetky(v.korotka), v.slug))]
    zapysaty(vykhid / 'vulytsi' / 'pokazhchyk.json', json.dumps(pokazhchyk, ensure_ascii=False, separators=(',', ':')))

    # Карта і головна.
    if D.h3 is None:
        raise SystemExit('Немає бібліотеки h3 (pip install h3) — карту шестикутників не зібрати.')
    for riven in (8, 9):
        zapysaty(vykhid / 'karta' / f'soty-{riven}.json',
                 json.dumps({'versiia': dn.versiia, 'riven': riven, 'roky': D.ROKY, 'soty': soty_geojson(dn, riven)},
                            ensure_ascii=False, separators=(',', ':'), sort_keys=True))
    zapysaty(vykhid / 'karta' / 'index.html', storinka_karty(dn, adresa_saitu))
    zapysaty(vykhid / 'index.html', holovna(dn, vulytsi, rayony, adresa_saitu))
    zapysaty(vykhid / '404.html', storinka_404(adresa_saitu))

    # Заглушка з грою — її власним збирачем, без змін.
    import zibraty as zahlushka
    zahlushka.zibraty(vykhid / 'zahlushka', '', '', {}, False, koloda)
    adresy.append('/zahlushka/')

    # Для пошуку Google.
    lastmod = dn.versiia if len(dn.versiia) == 10 else ''
    zapysaty(vykhid / 'sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
             + ''.join(f'<url><loc>{html.escape(adresa_saitu + a)}</loc>{f"<lastmod>{lastmod}</lastmod>" if lastmod else ""}</url>\n'
                       for a in adresy) + '</urlset>\n')
    zapysaty(vykhid / 'robots.txt', f'User-agent: *\nAllow: /\nDisallow: /zahlushka/zvernennya.html\n\nSitemap: {adresa_saitu}/sitemap.xml\n')

    failiv = sum(1 for p in vykhid.rglob('*') if p.is_file())
    zv = dn.zvedennia
    zvit = {
        'versiia': dn.versiia, 'vulyts': len(vulytsi), 'variantiv_nazv': len(zv.varianty),
        'zlyto_variantiv': sum(max(0, len(v.varianty) - 1) for v in vulytsi),
        'sumnivnykh': len(zv.sumnivni), 'neodnoznachnykh': len(zv.neodnoznachni),
        'pereadresatsii': pereadresatsii, 'sot_riven_8': len(dn.soty[8]), 'sot_riven_9': len(dn.soty[9]), 'failiv': failiv,
    }
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
    if failiv >= MEZHA_FAILIV:
        raise SystemExit(f'Файлів {failiv} — більше межі Cloudflare Pages ({MEZHA_FAILIV}).')
    return zvit


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Зібрати сайт «Моя вулиця» з випуску бази.')
    p.add_argument('baza', type=Path, help='events-<дата>.db')
    p.add_argument('vykhid', type=Path, help='тека, куди зібрати сайт (буде перезаписана)')
    p.add_argument('--pereimenuvannya', type=Path, help='dani-edrsr/dovidnyky/pereimenuvannya-kyiv.csv')
    p.add_argument('--mezhi-rayoniv', type=Path, default=KORIN / 'data' / 'borders.json')
    p.add_argument('--adresa-saitu', default=ADRESA_SAITU, help='адреса сайту для sitemap.xml і canonical')
    p.add_argument('--koloda', type=Path, help='справжня колода гри (без неї — демо-колода)')
    p.add_argument('--zvit-zvedennia', type=Path, help='куди записати таблицю зведення назв (CSV) для перевірки')
    a = p.parse_args(argv)
    zvit = zibraty_sait(a.baza, a.vykhid, a.pereimenuvannya, a.mezhi_rayoniv, a.adresa_saitu, a.koloda,
                        a.zvit_zvedennia)
    for k, v in zvit.items():
        print(f'{k}: {v}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
