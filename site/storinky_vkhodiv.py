"""Сторінки-входи під рекламу й ролики (ZAVDANNYA-153; компас `docs/KOMPAS.md`, розд. 0 і 5; В6 MV-158).

Одна людина — одна сторінка. Спершу яскрава потреба, потім продукт: на першому екрані — потреба словами людини, пошук
адреси (у юриста — пошук статті), уривок зі справжніх даних, ціна й кнопка. Сторінки — під рекламу, тому не для пошуку
Google (noindex, не в sitemap): Google приводить на сторінки будинків і вітрини.

  /dlia/orendaria/    орендар           → довідка про будинок 199
  /dlia/pokuptsia/    покупець          → повний звіт «перед купівлею» 299
  /dlia/rieltora/     рієлтор           → підписка рієлтора 799/міс
  /dlia/osbb/         правління ОСББ    → 1 490/рік
  /dlia/yurysta/      юрист і людина зі справою → «Судова практика» (довідка 199, юристу 490/міс)
  /dlia/meshkantsia/  загальний вхід для роликів «вау» → своя вулиця й будинок, довідка 199, підписка 399

Мітка джерела: реклама веде на `/dlia/<людина>/?dzherelo=<мітка ролика>`; `sait/vkhid.js` запам'ятовує в цій вкладці
«vh-<людина>-<мітка>» і ставить її в кожну кнопку оплати далі (сторінка будинку, вітрина), тож сервер продажу записує її
каналом пошти «скоро» чи замовлення (site/worker/prodazh/formy.js, kanal). Без скриптів кнопки несуть «vh-<людина>».

Правила: ціни — лише з `site/tsiny.py`; у режимі «скоро» кнопки ведуть на пошту (`T.knopka_oplaty`); уривок — числа з
відкритої сторінки будинку (MV-100: скарги 1551 і події лише числом), без номера будинку в тексті (номер — лише в
посиланні на його відкриту сторінку); жодних порад, прогнозів і оцінок (AGENTS.md, розд. 4).
"""
from __future__ import annotations

from pathlib import Path

import tsiny as T
import zibraty_sait as Z
import storinky_mv100 as M

e, chyslo, NBSP = Z.e, Z.chyslo, Z.NBSP

PREFIKS = 'vh'          # мітка входу: «vh-<людина>[-<мітка реклами>]», ≤ 25 знаків (канал сервера — ≤ 40 з «oplata-<товар>-»)

# Варіант першого екрана орендаря (2–3 варіанти — знімки в docs/znimky-153/; вибір — центральний чат, MV-158).
VARIANTY_ORENDARIA = ('a', 'b', 'c')
VARIANT_ORENDARIA = 'b'

PRYKLAD_PROSHUKU = 'Вулиця й будинок: Хрещатик 22'

# Хто → що. `tovary` — перший головний; усе з site/tsiny.py.
VKHODY = {
    'orendaria': {
        'kod': 'orendar', 'mitka': 'Перед орендою · Київ',
        'h1': 'Знімаєте квартиру? Подивіться, що болить будинку, — ще до договору',
        'pidpys': 'Скарги сусідів до 1551 — опалення, вода, ліфт — і події з рішень судів з адресою будинку. '
                  'Сторінка будинку безкоштовна, довідка — {dovidka}.',
        'tovary': ('dovidka', 'try'),
        'punkty': {
            'dovidka': ['скарги 1551 за 12 місяців: теми, місяці, статуси простими словами',
                        'порівняння з сусідніми будинками', 'події з рішень судів біля будинку й на вулиці — коротко',
                        'прочитати за 2–3 хвилини перед переглядом'],
            'try': ['три квартири на вибір — три довідки', 'дешевше, ніж три окремо'],
        },
        'title': 'Перед орендою квартири в Києві — що болить будинку | Моя вулиця',
        'opys': 'Перед орендою: скарги сусідів до 1551 і події з рішень судів по будинку. Сторінка будинку безкоштовна, довідка — {dovidka}.',
    },
    'pokuptsia': {
        'kod': 'pokupets', 'mitka': 'Перед купівлею · Київ',
        'h1': 'Купуєте житло? Подивіться, що було з будинком і вулицею за всі роки даних',
        'pidpys': 'Повний звіт «перед купівлею»: скарги 1551 будинку, події з рішень судів рік за роком, що повторюється на '
                  'вулиці й поруч, порівняння зі схожими будинками — {zvit}.',
        'tovary': ('zvit', 'dovidka'),
        'punkty': {
            'zvit': ['усе з довідки про будинок', '{podii}', 'рік за роком і що повторюється на вулиці',
                     'порівняння зі схожими будинками, карта будинку й вулиці'],
            'dovidka': ['коротше: скарги 1551 і події поруч', 'прочитати за 2–3 хвилини'],
        },
        'title': 'Перед купівлею житла в Києві — повний звіт про будинок | Моя вулиця',
        'opys': 'Перед купівлею: скарги 1551 і події з рішень судів по будинку й вулиці рік за роком. Повний звіт — {zvit}.',
    },
    'rieltora': {
        'kod': 'rieltor', 'mitka': 'Для рієлторів · Київ',
        'h1': '«А що тут за будинок?» — відповідь клієнтові за хвилину',
        'pidpys': 'Довідка про будинок перед показом: скарги 1551, порівняння із сусідами, події з рішень судів поруч. '
                  'Підписка рієлтора — {rieltor}, 5 довідок на будь-які адреси.',
        'tovary': ('rieltor', 'dovidka'),
        'punkty': {
            'rieltor': ['5 довідок на місяць — на будь-які адреси Києва', 'для показів і листування з клієнтом',
                        'можна зберегти файлом PDF і надіслати'],
            'dovidka': ['одна адреса, разово'],
        },
        'title': 'Для рієлторів: довідка про будинок за хвилину | Моя вулиця',
        'opys': 'Рієлторам: довідка про будинок перед показом — скарги 1551, сусіди, події з рішень судів. 5 довідок на місяць — {rieltor}.',
    },
    'osbb': {
        'kod': 'osbb', 'mitka': 'Для правлінь ОСББ · Київ',
        'h1': 'Що болить вашому будинку — щомісяця, у порівнянні із сусідами',
        'pidpys': 'Звернення мешканців до 1551 за місяць і за рік — теми й статуси — поруч із сусідніми будинками. '
                  'Для зборів, розмови з управителем і звіту мешканцям — {osbb}.',
        'tovary': ('osbb',),
        'punkty': {
            'osbb': ['щомісяця — довідка про ваш будинок: звернення 1551 за місяць і за рік, теми й статуси',
                     'порівняння з сусідніми будинками',
                     'оплата карткою; рахунок для юридичної особи — на запит, виставляє партнер проєкту'],
        },
        'title': 'Для ОСББ: скарги 1551 вашого будинку щомісяця | Моя вулиця',
        'opys': 'Для правлінь ОСББ: звернення мешканців до 1551 щомісяця, у порівнянні із сусідніми будинками. {osbb}.',
    },
    'yurysta': {
        'kod': 'yurist', 'mitka': 'Судова практика · Київ',
        'h1': 'Як суди Києва вирішують справи за вашою статтею',
        'pidpys': 'Скільки справ, чим закінчуються, скільки тривають — з рішень районних судів Києва. Довідка по своєму суду '
                  'й статті — {spdovidka}; юристу всі суди й фільтри — {spyurist}.',
        'tovary': ('spdovidka', 'spyurist'),
        'punkty': {
            'spdovidka': ['ваша стаття у вашому суді: результати й покарання частками', 'роки й строки, де дані точні',
                          'без імен суддів і людей'],
            'spyurist': ['усі суди Києва й фільтри', '3 довідки «стаття × суд» на місяць — для клієнтів'],
        },
        'title': 'Судова практика Києва за вашою статтею | Моя вулиця',
        'opys': 'Як суди Києва вирішують справи за статтями КУпАП і КК: частки результатів, покарання, строки. Довідка — {spdovidka}.',
    },
    'meshkantsia': {
        'kod': 'meshk', 'mitka': 'Моя вулиця · Київ',
        'h1': 'Ви бачили місто з даних. Тепер — ваша вулиця',
        'pidpys': 'Введіть свою вулицю й номер будинку: скарги 1551 і події з рішень судів — безкоштовно, числом. '
                  'Що саме й де — у довідці ({dovidka}) і підписці ({pidpyska}).',
        'tovary': ('dovidka', 'pidpyska'),
        'punkty': {
            'dovidka': ['скарги 1551 за 12 місяців: теми, місяці, статуси', 'порівняння з сусідніми будинками',
                        'події з рішень судів біля будинку й на вулиці — коротко'],
            'pidpyska': None,      # перелік — T.pidpyska_daie(), один для всього сайту
        },
        'title': 'Ваша вулиця в даних: скарги 1551 і події з рішень судів | Моя вулиця',
        'opys': 'Своя вулиця й будинок у Києві: скарги 1551 і події з рішень судів — безкоштовно, числом. Довідка — {dovidka}.',
    },
}
POPULIARNI_STATTI = (('kupap', '130', 'Керування напідпитку'), ('kupap', '124', 'ДТП з пошкодженням авто'),
                     ('kupap', '173-2', 'Домашнє насильство'), ('kk', '185', 'Крадіжка'), ('kk', '309', 'Наркотики без мети збуту'))


def tsiny_slovamy() -> dict:
    return {k: T.tsina(k) for k in T.TSINY}


def dzherelo(slug: str) -> str:
    return f'{PREFIKS}-{VKHODY[slug]["kod"]}'


def knopka(slug: str, kl: str, holovna: bool) -> str:
    return T.knopka_oplaty(f'/oplata/?tovar={kl}&amp;dzherelo={dzherelo(slug)}',
                           f'{e(T.TOVARY[kl])} — {T.tsina(kl)}', holovna)


# ---------------------------------------------------------------- уривок зі справжніх даних

def pryklad_budynku(bud) -> dict | None:
    """Будинок для уривка: зі скаргами (≥ 3), порівнянням із сусідами й подіями — «середній» за кількістю скарг, не той,
    де найбільше (чесний приклад, а не страшилка). Детерміновано: та сама вибірка — той самий будинок."""
    if not bud:
        return None
    kandydaty = [b for b in bud.spysok if b['skarh'] >= 3 and b['susidy'] and b['vulytsia_slug']]
    if not kandydaty:
        return None
    z_podiiamy = [b for b in kandydaty if b['podii_vidkr']] or kandydaty
    z_podiiamy.sort(key=lambda b: (b['skarh'], b['slug']))
    return z_podiiamy[len(z_podiiamy) // 2]


def urivok(b: dict | None, bud, versiia: str) -> str:
    """Уривок довідки: три найчастіші теми 1551 «тут · у сусідів» і події числом — ті самі числа, що на відкритій
    сторінці будинку. Номер будинку — лише в посиланні на неї (у тексті — вулиця)."""
    zrazok = '<a href="/zahlushka/zrazok.html">Зразок повного звіту</a>'
    if not b:
        return (f'<div class="kartka vkhid-urivok"><p class="mikro">Що буде в довідці</p><ul class="spysok-tekst">'
                '<li>теми звернень 1551 по місяцях і статуси</li><li>порівняння з сусідніми будинками</li>'
                f'<li>події з рішень судів поруч — з посиланням на кожне рішення</li></ul><p class="prymitka">{zrazok}.</p></div>')
    sus = b['susidy'] or {}
    top = list(b['skarhy'].items())[:3]
    maks = max([n for _, n in top] + [sus.get(h, 0) for h, _ in top] + [1])
    ryady = ''.join(
        f'<div class="por__ryad"><span class="por__nazva">{e(M.z_velykoi(h))}</span>'
        f'<span class="por__smuha"><i class="sh-{M.shyryna(n, maks)} por--tut"></i></span><b>{chyslo(n)}</b>'
        + (f'<span class="por__smuha"><i class="sh-{M.shyryna(sus[h], maks)} por--sus"></i></span><b class="por__sus">{M.chyslo_m(sus[h])}</b>'
           if h in sus else '<span class="por__smuha"></span><b class="por__sus">—</b>') + '</div>'
        for h, n in top)
    roky = f'{M.D.VIDKRYTI_ROKY[0]}–{M.D.VIDKRYTI_ROKY[-1]}'
    podii = (f'Подій з рішень судів з адресою будинку за {roky}: {chyslo(b["podii_vidkr"])}.' if b['podii_vidkr']
             else f'Подій з рішень судів з адресою будинку за {roky} у даних немає.')
    return f'''<div class="kartka vkhid-urivok">
<p class="mikro">Уривок зі справжніх даних · будинок: {e(b["vulytsia"])}</p>
<p class="vkhid-urivok__z"><b>{M.skarhy_slovo(b["skarh"])}</b> до 1551 за 12 місяців. Найчастіші теми — тут і в сусідніх будинках у радіусі {bud.r_susidy}{NBSP}м (зазвичай):</p>
<div class="por"><div class="por__shapka" aria-hidden="true"><span>Тема</span><span>цей будинок</span><span></span><span>сусідні</span><span></span></div>
{ryady}</div>
<p class="vkhid-urivok__z">{podii}</p>
<p class="prymitka">Ті самі числа, що на відкритій сторінці будинку{f", дані станом на {e(versiia)}" if versiia else ""}. Скарга — звернення людей,
не перевірений факт. У довідці — ще місяці, статуси й події поруч з посиланням на кожне рішення.
<a href="{b["url"]}">Відкрити сторінку цього будинку</a> · {zrazok}.</p></div>'''


def urivok_sp(sp: list | None) -> str:
    """Юристу — уривок зі справжньої сторінки статті (якщо зведення «Судової практики» є у збірці)."""
    import storinky_sp as SP
    st = next((s for s in sp or () if s.kodeks == 'КУпАП' and s.nomer == '130'), None) or (sp[0] if sp else None)
    if not st:
        return ('<div class="kartka vkhid-urivok"><p class="mikro">Що буде в довідці</p><ul class="spysok-tekst">'
                '<li>скільки справ за вашою статтею у вашому суді, за роками</li><li>чим закінчуються: частки результатів і покарань</li>'
                '<li>скільки минає від події до рішення — де дані точні</li></ul></div>')
    p = st.pidsumok()
    period = f'{SP.ROKY_VIDKRYTI[0]}–{SP.ROKY_VIDKRYTI[-1]}'
    ryadky = []
    if p['n'] >= SP.MIN_N:
        ryadky = [f'<li>{e(k)} — {SP.vids(v / p["n"])}</li>' for k, v in sorted(p['kat'].items(), key=lambda x: -x[1])[:3]]
    return f'''<div class="kartka vkhid-urivok">
<p class="mikro">Уривок зі справжніх даних · {e(st.st)}</p>
<p class="vkhid-urivok__z"><b>{SP.sprav(p["n"])}</b> у районних судах Києва за {period}. Чим закінчились:</p>
<ul class="spysok-tekst">{"".join(ryadky) or "<li>справ замало, щоб рахувати частки</li>"}</ul>
<p class="prymitka">{e(SP.ZASTEREZHENNIA)} <a href="{st.slug}">Уся сторінка статті</a>.</p></div>'''


# ---------------------------------------------------------------- сторінка

def poshuk_adresy() -> str:
    return f'''<form class="poshuk vkhid-poshuk" role="search" action="/vulytsi/"><label class="prykhovano" for="poshuk-vulytsi">Вулиця і номер будинку</label>
<input id="poshuk-vulytsi" type="search" autocomplete="off" enterkeyhint="search" placeholder="{PRYKLAD_PROSHUKU}">
<ul class="poshuk__spysok" id="poshuk-spysok" hidden></ul></form>'''


def poshuk_statti(ye: set | None = None) -> str:
    """Юристу замість пошуку адреси — найчастіші статті (лише ті, чиї сторінки є у збірці) й «Інша стаття»."""
    statti = [(k, n, t) for k, n, t in POPULIARNI_STATTI if ye and f'{k}-{n}' in ye]
    return ('<nav class="vkhid-statti" aria-label="Статті">' + ''.join(
        f'<a class="knopka" href="/sudova-praktyka/{k}/{n}/">ст.{NBSP}{n} — {e(t)}</a>' for k, n, t in statti)
        + f'<a class="knopka" href="/sudova-praktyka/{"#poshuk" if statti else ""}">{"Інша стаття" if statti else "Усі статті"}</a></nav>')


def kartky_tovariv(slug: str, period_podii: str) -> str:
    v = VKHODY[slug]
    vyhid = []
    for i, kl in enumerate(v['tovary']):
        punkty = v['punkty'].get(kl)
        punkty = ([e(x) for x in T.pidpyska_daie()] if punkty is None else
                  [e(x.format(podii=M.podii_zvitu(period_podii))) for x in punkty])
        vyhid.append(f'<div class="kartka tovar{" tovar--holovnyi" if i == 0 else ""}"><h3>{e(T.TOVARY[kl])}</h3>'
                     f'<p class="tovar__tsina">{T.tsina(kl)}</p><ul>{"".join(f"<li>{p}</li>" for p in punkty)}</ul>'
                     f'{knopka(slug, kl, i == 0)}</div>')
    return '<div class="tovary">' + ''.join(vyhid) + '</div>'


def pershyi_ekran(slug: str, ur: str, variant: str = 'a', statti: set | None = None) -> str:
    """Перший екран: потреба → пошук → ціна з кнопкою; уривок — поруч (b), під пошуком (a) або після трьох питань (c)."""
    v = VKHODY[slug]
    pidpys = v['pidpys'].format(**tsiny_slovamy())
    poshuk = poshuk_statti(statti) if slug == 'yurysta' else poshuk_adresy()
    hol = v['tovary'][0]
    tsina = (f'<p class="vkhid-tsina">{knopka(slug, hol, True)}<span class="prymitka">'
             f'{M.prymitka_oplaty("Кнопка відкриє сторінку, де можна залишити пошту.")}'
             f'{"Сторінка будинку — безкоштовно." if slug != "yurysta" else "Сторінка статті — безкоштовно."}</span></p>')
    holova = (f'<span class="mitka">{e(v["mitka"])}</span><h1>{e(v["h1"])}</h1><p class="vkhid-pidpys">{e(pidpys)}</p>')
    if variant == 'b':
        return (f'<section class="vkhid-ekran vkhid-ekran--b"><div class="vkhid-ekran__liva">{holova}{poshuk}{tsina}</div>'
                f'<div class="vkhid-ekran__prava">{ur}</div></section>')
    if variant == 'c':
        pytannia = ''.join(f'<li><b>{e(p)}</b><span>{e(vid)}</span></li>' for p, vid in (
            ('Чи гріють і чи є вода?', 'теми звернень 1551 по місяцях — опалення, вода, світло'),
            ('Чи працює ліфт і чи прибирають двір?', 'скарги мешканців цього будинку й сусідніх поруч'),
            ('Що було на цій адресі?', 'події з рішень судів з адресою будинку й на вулиці')))
        return (f'<section class="vkhid-ekran vkhid-ekran--c">{holova}<ol class="vkhid-pytannia">{pytannia}</ol>'
                f'{poshuk}{tsina}</section><section class="rozdil">{ur}</section>')
    return f'<section class="vkhid-ekran vkhid-ekran--a">{holova}{poshuk}{tsina}</section><section class="rozdil">{ur}</section>'


def storinka_vkhodu(slug: str, adresa_saitu: str, ur: str, period_podii: str = '', variant: str | None = None,
                    statti: set | None = None) -> str:
    v = VKHODY[slug]
    if variant is None:
        variant = VARIANT_ORENDARIA if slug == 'orendaria' else 'b'
    ts = tsiny_slovamy()
    zast = ('Довідка — не оцінка будинку й не порада, де жити. Скарги 1551 — звернення людей, не перевірені факти; події — '
            'те, що дійшло до суду.' if slug != 'yurysta' else 'Без імен суддів і людей. Статистика минулих рішень, а не юридична допомога.')
    tilo = (f'<div hidden data-vkhid="{e(dzherelo(slug))}"></div>' + pershyi_ekran(slug, ur, variant, statti)
            + f'<section class="rozdil"><h2>Що можна замовити</h2>{kartky_tovariv(slug, period_podii)}'
              f'<p class="prymitka">{zast} {M.prymitka_oplaty("Кнопка відкриє сторінку, де можна залишити пошту.")}</p></section>')
    if slug != 'yurysta':
        tilo += ('<section class="rozdil"><h2>Звідки дані</h2><p class="rozdil__pidpys">Скарги 1551 — відкриті дані міста (КМДА). '
                 'Події — з рішень судів у Єдиному державному реєстрі судових рішень: лише те, що дійшло до суду, а не всі події. '
                 'Колір і числа показують кількість, а не оцінку будинку. <a href="/pro-dani/">Як ми працюємо з даними</a>.</p></section>')
    skrypty = ('/sait/sp.js',) if slug == 'yurysta' else ('/sait/poshuk-spilne.js', '/sait/poshuk.js')
    return Z.storinka(shlyakh=f'/dlia/{slug}/', title=v['title'], opys=v['opys'].format(**ts), tilo=tilo,
                      adresa_saitu=adresa_saitu, aktyvne='', skrypty=skrypty, indeksuvaty=False,
                      dodatkovo_head='<link rel="stylesheet" href="/sait/vkhid.css">\n')


def zibraty(vykhid: Path, adresa_saitu: str, bud=None, versiia: str = '', period_podii: str = '',
            sudova_praktyka: Path | None = None) -> list:
    """Пише 6 сторінок-входів; повертає їхні адреси (для звіту збирача — не для sitemap: вони noindex)."""
    import storinky_sp as SP
    sp = None
    if sudova_praktyka:
        d = SP.prochytaty(sudova_praktyka)
        stroky = set(d.get('stroky') or ())
        sp = [SP.Stattia(s, stroky) for s in d['statti']]
    b = pryklad_budynku(bud)
    ur = urivok(b, bud, versiia)
    adresy = []
    for slug in VKHODY:
        Z.zapysaty(vykhid / 'dlia' / slug / 'index.html',
                   storinka_vkhodu(slug, adresa_saitu, urivok_sp(sp) if slug == 'yurysta' else ur, period_podii,
                                   statti={f'{SP.SLUG[s.kodeks]}-{s.nomer}' for s in sp} if sp else None))
        adresy.append(f'/dlia/{slug}/')
    return adresy
