# -*- coding: utf-8 -*-
"""Розмітка трьох екранів (карта, будинок, район). Однакова для всіх стилів; стиль — CSS і налаштування карти."""
import json
from html import escape as e
import zmist as Z
from zmist import ch, vidm, NB

FM = '/w/node_modules/@fontsource'
LAT = 'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+2000-206F, U+2074, U+20AC, U+2122, U+2190-21FF, U+2212, U+2215, U+25A0-25FF'
CYR = 'U+0301, U+0400-045F, U+0490-0491, U+04B0-04B1, U+2116'


def shryfty(spysok):
    """spysok: [(rodyna, papka, [vagy], italic?)]"""
    out = []
    for rod, pap, vagy, it in spysok:
        for w in vagy:
            for styl in (['normal', 'italic'] if it else ['normal']):
                for sub, rng in (('latin', LAT), ('cyrillic', CYR)):
                    out.append(f"@font-face{{font-family:'{rod}';font-style:{styl};font-weight:{w};font-display:block;"
                               f"src:url({FM}/{pap}/files/{pap}-{sub}-{w}-{styl}.woff2) format('woff2');unicode-range:{rng}}}")
    return '\n'.join(out)


def shapka(S, tel, aktyvne):
    punkty = [('karta', 'Карта'), ('vulytsi', 'Вулиці'), ('budynok', 'Мій будинок'), ('rayon', 'Райони')]
    if not tel:
        punkty += [('osbb', 'Для ОСББ'), ('biznes', 'Для бізнесу'), ('ihry', 'Ігри')]
    nav = ''.join(f'<a class="{"aktyvne" if k == aktyvne else ""}">{t}</a>' for k, t in punkty)
    if tel:
        nav = ''.join(f'<a class="{"aktyvne" if k == aktyvne else ""}">{t}</a>' for k, t in punkty[:3]) + '<a class="shche">Меню</a>'
    return (f'<header class="shapka"><a class="znak">{S["znak"]}</a><nav class="menu">{nav}</nav>'
            f'<button class="tema" aria-label="Тема"><svg width="16" height="16" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" stroke-width="1.5"/><path d="M8 1.8 A6.2 6.2 0 0 1 8 14.2 Z" fill="currentColor"/></svg></button></header>')


def kolory_hrup(S):
    return S.get('hrupy_kol') or [h['svitla'] for h in Z.D['hrupy']]


def mitka_hrupy(S, k):
    i = Z.PORIADOK.index(k)
    return f'<i class="hr" style="--hk:{kolory_hrup(S)[i]}"></i>'


def grafik(S, znach, **kw):
    return Z.grafik(znach, S.get('grafik', 'bars'), kolir=kw.pop('kolir', 'var(--g-kolir)'), tiho=kw.pop('tiho', 'var(--g-tiho)'),
                    osnova='var(--g-osnova)', **kw)


def dzherela_html():
    return ('<p class="prymitka">Скарги 1551 — відкриті дані міста (КМДА, data.gov.ua, CC BY). Події — з рішень судів у Єдиному '
            'державному реєстрі судових рішень, станом на 21 листопада 2026. Колір показує кількість у даних, а не оцінку місця. '
            '<a>Як ми працюємо з даними</a> · <a>Видалити або виправити подію</a>.</p>')


def obhortka(S, tel, aktyvne, tilo, karta=False, dodatkovo=''):
    hd = [f'<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">',
          f'<style>{shryfty(S["shryfty"])}</style>', '<link rel="stylesheet" href="/gen/baza.css">',
          f'<style>{S["css"]}</style>']
    if karta:
        hd.append('<link rel="stylesheet" href="/w/node_modules/maplibre-gl/dist/maplibre-gl.css">'
                  '<script src="/w/node_modules/maplibre-gl/dist/maplibre-gl.js"></script><script src="/gen/dani.js"></script>'
                  f'<script>window.K={json.dumps(S["karta"], ensure_ascii=False)}</script>')
    tema = S.get('tema', 'svitla')
    return (f'<!doctype html><html lang="uk" data-prystrii="{"tel" if tel else "pk"}" data-styl="{S["kliuch"]}" data-t="{tema}">'
            f'<head>{"".join(hd)}<title>Моя вулиця</title></head><body class="{"je-karta" if karta else "je-storinka"}">'
            f'{S.get("dekor_verkh", "")}{shapka(S, tel, aktyvne)}{tilo}{dodatkovo}</body></html>')


# ------------------------------------------------------------------ карта
def ekran_karty(S, tel):
    s = Z.sota()
    hr = ''.join(f'<li>{mitka_hrupy(S, k)}<span>{e(n)}</span><b>{ch(v)}</b></li>' for n, v, k in s['hrupy'][:5])
    ramp = S['karta']['ramp']
    ramp5 = [ramp[2 * i + 1] for i in range(5)] if len(ramp) == 10 else ramp
    legenda = ''.join(f'<i style="background:{c}"></i>' for c in ramp5)
    legenda = S.get('legenda') or f'<div class="legenda"><span>менше подій</span><span class="legenda-shkala">{legenda}</span><span>більше</span><span class="legenda-pr"><i></i>проблема</span></div>'
    zamk = list(range(2016, 2024))
    kartka = f'''<aside class="kartka-soty" aria-label="Сота">
<div class="k-zag"><h2>{e(s["nazva"])}</h2><span class="k-pidpys">{s["pidpys"]}</span><button class="k-zakryty" aria-label="Закрити">×</button></div>
<div class="k-chyslo"><b class="chyslo">{ch(s["n"])}</b><span>{vidm(s["n"], ("подія", "події", "подій"))} за 2024–2026<br><em>у {s["raz"]} раза більше за типову соту</em></span></div>
<section class="k-rozdil"><h3>Найбільше тут</h3><ul class="k-hrupy">{hr}</ul></section>
<section class="k-rozdil"><h3>За роками · усі види</h3>{grafik(S, s["roky"], w=330, h=74, zamk=zamk)}
<p class="k-prym">2016–2023 — у підписці · 2026 — неповний рік</p></section>
<p class="k-pik"><b>Найчастіше: {s["pik"]}</b> — за 2024–2026, де відомий час</p>
<section class="k-rozdil"><h3>Повторюється тут</h3><p class="k-problema">{e(s["problemy"][0])}</p></section>
<p class="k-zamok">{ch(s["n"])} {vidm(s["n"], ("подія", "події", "подій"))} з адресами й описами — у підписці</p>
<div class="k-knopky"><a class="knopka knopka--holovna">Що саме тут було — підписка</a><a class="knopka">Аналіз адреси</a></div>
</aside>'''
    tilo = f'''<main class="ekran-karty"><div id="map"></div><div id="pidpysy"></div>
<div class="verkh"><label class="poshuk"><span class="poshuk-znak">{S.get("poshuk_znak", "⌕")}</span><input placeholder="Вулиця, будинок або район"></label>
<div class="filtr"><span>Усі події</span><span class="filtr-period">2024–2026</span><span class="filtr-str">▾</span></div></div>
{legenda}
{kartka}
<p class="dzherela">Підкладка: © OpenStreetMap, OpenFreeMap · події: ЄДРСР, ДСА України (CC BY) · {ch(Z.D["vsogo"])} подій</p>
</main><script src="/gen/karta.js"></script>'''
    return obhortka(S, tel, 'karta', tilo, karta=True)


# ------------------------------------------------------------------ будинок
def ekran_budynku(S, tel):
    b = Z.budynok()
    kryhty = f'<nav class="kryhty"><a>Головна</a><a>{b["rayon"]} район</a><a>{b["vulytsia"]}</a><span>буд. <span class="zakryto">██</span></span></nav>'
    mx = max([n for _, n in b['skarhy']] + [1])
    ryady = ''.join(
        f'<div class="smuha-ryad"><span class="smuha-nazva">{e(Z.z_velykoi(t))}</span>'
        f'<span class="smuha"><i style="width:{100 * n / mx:.0f}%"></i></span><b>{n}</b>'
        f'<span class="smuha smuha--sus"><i style="width:{100 * b["susidy"].get(t, 0) / mx:.0f}%"></i></span><b class="sus">{b["susidy"].get(t, 0)}</b></div>'
        for t, n in b['skarhy'])
    shapka_t = ''.join(f'<th>{r}</th>' for r in (2024, 2025, 2026))
    tab = ''.join(f'<tr><th>{mitka_hrupy(S, k)}{e(Z.HR[k]["nazva"])}</th>' + ''.join(
        f'<td>{b["roky"][r].get(k, "") or "·"}</td>' for r in (2024, 2025, 2026)) + '</tr>' for k in b['hrupy'])
    tilo = f'''<main class="storinka storinka--budynok">{kryhty}
<section class="zaholovok"><span class="mitka">{b["rayon"]} район · будинок</span>
<h1>{e(b["vulytsia"])}, <span class="zakryto">██</span></h1>
<p class="vstup">{e(b["abz"])}</p><p class="onovleno">Оновлено: листопад 2026</p></section>
<section class="chysla"><div class="chyslo-blok"><b class="chyslo">{b["skarh"]}</b><span>звернень до 1551 за 12 місяців</span></div>
<div class="chyslo-blok"><b class="chyslo">{b["podii"]}</b><span>подій з рішень судів за 2024–2026</span></div></section>
<section class="rozdil"><h2>Скарги 1551 за 12 місяців</h2>
<p class="rozdil-pidpys">{Z.z_velykoi(b["period"])}. Це звернення людей до гарячої лінії міста, а не перевірені факти. Сусідні — скільки
звернень цієї теми зазвичай має один будинок у радіусі 400{NB}м: половина з {b["susidiv"]} сусідніх будинків має менше, половина — більше.</p>
<div class="smuhy"><div class="smuha-shapka"><span>Тема</span><span>цей будинок</span><span></span><span>сусідні</span><span></span></div>{ryady}</div>
<p class="prymitka">Текстів звернень, дат і статусів тут немає — вони в довідці про будинок.</p></section>
<section class="rozdil"><h2>Події з рішень судів — лише числом</h2>
<p class="rozdil-pidpys">Подія — випадок, який описано в рішенні суду, з адресою цього будинку. Це не всі події: лише те, що дійшло до суду. 2026 — неповний рік.</p>
<table class="tabl"><thead><tr><th>Група</th>{shapka_t}</tr></thead><tbody>{tab}</tbody></table>
<p class="rozdil-pidpys">Події за 2023 рік з адресою будинку теж є — у підписці.</p></section>
<section class="rozdil rozdil--prodazh"><p class="haslo">{S.get("haslo", "Що болить вашому будинку — у фактах.")}</p><h2>Довідка про будинок</h2>
<p>Що саме сталося біля будинку за 3 роки — з описами, датами й посиланнями на рішення; скарги 1551 — з текстами; що повторюється поруч.</p>
<div class="knopky"><a class="knopka knopka--holovna">Довідка — 199{NB}грн</a><a class="knopka">Повний звіт — 299{NB}грн</a></div>
<p class="prymitka">Повний звіт «перед купівлею» — ще й події за 10 років, рік за роком, порівняння зі схожими будинками й карта будинку та вулиці.</p></section>
<section class="rozdil"><h2>Де це й що поруч</h2><div class="knopky knopky--dribni"><a class="knopka">Показати місце на карті</a><a class="knopka">{e(b["vulytsia"])} — уся вулиця</a><a class="knopka">{b["rayon"]} район</a></div></section>
{dzherela_html()}</main>'''
    return obhortka(S, tel, 'budynok', tilo)


# ------------------------------------------------------------------ район
def ekran_rayonu(S, tel):
    r = Z.rayon()
    bloky = []
    for g in r['hrupy']:
        vydy = ''.join(f'<li><span>{e(v)}</span><b>{p}{NB}%</b></li>' for v, p in g['vydy'])
        dyn = grafik(S, g['roky'], w=300, h=64, pidpysy=True)
        bloky.append(f'''<article class="hrupa hrupa--{g["k"]}" style="--hk-t:{kolory_hrup(S)[Z.PORIADOK.index(g["k"])]}"><header class="hrupa-zag">{mitka_hrupy(S, g["k"])}<h3>{e(g["nazva"])}</h3></header>
<div class="hrupa-chysla"><div><b class="chyslo chyslo--s">{ch(g["n"])}</b><span>за 2024–2026</span></div><div><b class="chyslo chyslo--s">{ch(g["ost"])}</b><span>за 2025 рік</span></div></div>
<div class="hrupa-dyn">{dyn}<p class="hrupa-trend"><span class="trend trend--{ {"росте": "vgoru", "менше": "vnyz"}.get(g["tr"], "rivno") }">{e(g["tr"])}</span> {e(g["trend"])}</p></div>
<ul class="hrupa-vydy"><li class="hrupa-vydy-zag">Найчастіше</li>{vydy}</ul></article>''')
    mx = max(n for _, n in r['skarhy'])
    sk = ''.join(f'<div class="smuha-ryad smuha-ryad--1"><span class="smuha-nazva">{e(Z.z_velykoi(t))}</span>'
                 f'<span class="smuha"><i style="width:{100 * n / mx:.0f}%"></i></span><b>{ch(n)}</b></div>' for t, n in r['skarhy'])
    rech = ''.join(f'<li>{e(x)}</li>' for x in r['rech'])
    tilo = f'''<main class="storinka storinka--rayon"><nav class="kryhty"><a>Головна</a><a>Райони</a><span>{r["nazva"]} район</span></nav>
<section class="zaholovok"><span class="mitka">Київ · район</span><h1>{r["nazva"]} район</h1><ol class="holovne">{rech}</ol></section>
<section class="chysla chysla--3"><div class="chyslo-blok"><b class="chyslo">{ch(r["vsogo"])}</b><span>подій з точною адресою за 2024–2026</span></div>
<div class="chyslo-blok"><b class="chyslo">{r["problem_n"]}</b><span>проблеми — місця, де однотипне повторюється</span></div>
<div class="chyslo-blok"><b class="chyslo">{ch(r["budynkiv"])}</b><span>будинків зі своєю сторінкою</span></div></section>
<section class="rozdil rozdil--poshuk"><h2>Перевірити свій будинок у цьому районі</h2><label class="poshuk poshuk--velykyi"><span class="poshuk-znak">{S.get("poshuk_znak", "⌕")}</span><input placeholder="Вулиця й номер будинку"></label></section>
<section class="rozdil"><h2>Сім груп подій</h2><p class="rozdil-pidpys">Завжди в тому самому порядку. Число — події з точною адресою в районі; графік — 2016–2026, останній рік неповний. Це кількість у даних, а не оцінка району.</p>
<div class="hrupy-sitka">{"".join(bloky)}</div></section>
<section class="rozdil"><h2>Скарги 1551 за темами</h2><p class="rozdil-pidpys">{Z.z_velykoi(Z.period_1551())}; звернення людей, не перевірені факти.</p><div class="smuhy">{sk}</div></section>
<section class="rozdil rozdil--prodazh"><h2>Далі — про ваш будинок</h2><div class="knopky"><a class="knopka knopka--holovna">Стежити за районом — лист щотижня</a><a class="knopka">Які проблеми біля вашого будинку</a><a class="knopka">Для ОСББ</a></div></section>
{dzherela_html()}</main>'''
    return obhortka(S, tel, 'rayon', tilo)
