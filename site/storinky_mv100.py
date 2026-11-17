"""Сторінки будинків, районів, вітрини, оплата-заглушка, «Видалити або виправити», «Як ми працюємо з даними»
(ZAVDANNYA-85; MV-99, MV-100).

Збирач сайту (`zibraty_sait.py --budynky <budynky.json>`) викликає звідси `zibraty_vse`. Дані будинків — зведення
з приватного `dani-edrsr` (`src/budynky_sait.py`): **лише числа** — скарги 1551 по групах за 12 місяців, медіана сусідів,
події з рішень за роками й групами. Описів, посилань на рішення, імен тут немає й бути не може.

Правила:
  * події з рішень — лише числом (MV-100), за останні 3 роки (MV-32); старші — «у підписці» без чисел;
  * скарги 1551 — звернення людей, не перевірені факти; порівняння з сусідами — два числа поруч, без оцінки;
  * колір — кількість (шкала даних), не страх; жодних рейтингів;
  * ціни — одна таблиця `site/tsiny.py` (MV-100, MV-102); «Для бізнесу» — ціна за домовленістю і форма запиту.
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import dani as D
import tsiny as T
import zibraty_sait as Z

e, chyslo, vidminok, NBSP = Z.e, Z.chyslo, Z.vidminok, Z.NBSP

# Ціни — одна таблиця для всього сайту (site/tsiny.py; MV-100, MV-102).
TSINY, TOVARY = T.TSINY, T.TOVARY
MIN_DANYKH_DLYA_POSHUKU = 3      # будинок з 1–2 записами — сторінка є, але не в пошуку Google (як вулиці)
MISIATSI = ('січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень',
            'жовтень', 'листопад', 'грудень')
MISIATSI_RODOVYI = ('січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня',
                    'жовтня', 'листопада', 'грудня')
HRUPY_PODII = D.HR.NAZVA            # назви груп — brend/hrupy.json (MV-116)


def tsina(kl: str) -> str:
    return T.tsina(kl)


def misiats(ym: str) -> str:
    r, m = ym.split('-')
    return f'{MISIATSI[int(m) - 1]} {r}'


def period_1551(ms: list) -> str:
    return f'{misiats(ms[0])} — {misiats(ms[-1])}' if ms else ''


def slug_nomera(n: str) -> str:
    """«17-А» → «17-a», «12/4» → «12-4», «37 к6» → «37-k6»."""
    return D.translit(re.sub(r'[/\s]+', '-', n)) or 'bud'


def z_velykoi(t: str) -> str:
    return t[:1].upper() + t[1:]


def shyryna(n: float, maks: float) -> int:
    """Ширина смуги — класом з кроком 5 % (без атрибутів style: CSP)."""
    if n <= 0 or maks <= 0:
        return 0
    return max(1, min(20, round(n / maks * 20)))


def skarhy_slovo(n: int) -> str:
    return f'{chyslo(n)} {vidminok(n, ("звернення", "звернення", "звернень"))}'


def kryhty_html(punkty: list) -> str:
    chastyny = []
    for i, (url, nazva) in enumerate(punkty):
        if i:
            chastyny.append('<span aria-hidden="true">›</span>')
        chastyny.append(f'<a href="{url}">{e(nazva)}</a>' if url else f'<span>{e(nazva)}</span>')
    return f'<nav class="kryhty" aria-label="Де ви">{"".join(chastyny)}</nav>'


def kryhty_ld(punkty: list, adresa_saitu: str) -> dict:
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'name': n, **({'item': adresa_saitu + u} if u else {})}
        for i, (u, n) in enumerate(punkty)]}


def ld_skrypt(*obiekty) -> str:
    return ''.join(f'<script type="application/ld+json">'
                   f'{json.dumps(o, ensure_ascii=False, sort_keys=True).replace("</", "<" + chr(92) + "/")}</script>\n'
                   for o in obiekty)


def knopky_dovidky(budynok: str = '', dzherelo: str = '') -> str:
    q = f'&amp;budynok={e(budynok)}' if budynok else ''
    d = f'&amp;dzherelo={e(dzherelo)}' if dzherelo else ''
    return (f'<div class="tsiny">'
            f'<a class="knopka knopka--holovna" href="/oplata/?tovar=dovidka{q}{d}">Довідка — {tsina("dovidka")}</a>'
            f'<a class="knopka" href="/oplata/?tovar=try{q}{d}">3 довідки — {tsina("try")}</a>'
            f'<a class="knopka" href="/oplata/?tovar=zvit{q}{d}">Повний звіт — {tsina("zvit")}</a>'
            f'</div>')


# ---------------------------------------------------------------- дані будинків

class Budynky:
    """Зведення з dani-edrsr + прив'язка до сторінок вулиць і районів сайту."""

    def __init__(self, shlyakh: Path, dn: D.Dani, vulytsi: list):
        z = json.loads(Path(shlyakh).read_text(encoding='utf-8'))
        self.misiatsi = z.get('skarhy_misiatsi', [])
        self.r_susidy = z.get('r_susidy_m', 300)
        self.versiia = z.get('versiia', '')
        # вулиця з довідника (OSM) → сторінка вулиці сайту: той самий ключ, що в dani.py
        za_kliuchem = {}
        for v in vulytsi:
            za_kliuchem.setdefault((v.typ, D.kliuch(v.korotka)), v)
        self.spysok = []
        zainiati = set()
        for b in z['budynky']:
            r = D.rozibraty_vulytsiu(b['vulytsia'])
            v = za_kliuchem.get((r[0], D.kliuch(r[1]))) if r else None
            if v:
                slug_v, nazva_v = v.slug, v.nazva
            else:
                nazva_v = D.povna_nazva(*r) if r else b['vulytsia']
                slova = nazva_v.split(' ')
                if 'вулиця' in slova and len(slova) > 1:
                    slova.remove('вулиця')
                slug_v = D.translit(' '.join(slova)) or 'vulytsia'
            slug = f'{slug_v}/{slug_nomera(b["nomer"])}'
            baza, i = slug, 2
            while slug in zainiati:
                slug = f'{baza}-{i}'
                i += 1
            zainiati.add(slug)
            skarhy = dict(sorted(b.get('skarhy', {}).items(), key=lambda x: (-x[1], x[0])))
            podii = {int(r_): g for r_, g in b.get('podii', {}).items()}
            vidkryti = {r_: podii.get(r_, {}) for r_ in D.VIDKRYTI_ROKY}
            self.spysok.append({
                'slug': slug, 'url': f'/budynok/{slug}/', 'nomer': b['nomer'], 'vulytsia': nazva_v,
                'vulytsia_slug': slug_v if v else None, 'rayon': b.get('rayon'),
                'adresa': f'{nazva_v}, {b["nomer"]}', 'lat': b['lat'], 'lon': b['lon'],
                'skarhy': skarhy, 'skarh': sum(skarhy.values()), 'susidy': b.get('susidy'), 'susidiv': b.get('susidiv', 0),
                'vidkryti': vidkryti, 'podii_vidkr': sum(sum(g.values()) for g in vidkryti.values()),
                'stari': any(r_ < D.VIDKRYTI_ROKY[0] for r_ in podii),
            })
        self.spysok.sort(key=lambda x: x['slug'])
        self.za_vulytseyu = defaultdict(list)
        for b in self.spysok:
            if b['vulytsia_slug']:
                self.za_vulytseyu[b['vulytsia_slug']].append(b)
        for s in self.za_vulytseyu.values():
            s.sort(key=lambda b: kliuch_nomera(b['nomer']))
        self.za_rayonom = defaultdict(list)
        for b in self.spysok:
            if b['rayon']:
                self.za_rayonom[b['rayon']].append(b)

    @staticmethod
    def indeksuvaty(b: dict) -> bool:
        return b['skarh'] + b['podii_vidkr'] >= MIN_DANYKH_DLYA_POSHUKU


def kliuch_nomera(n: str) -> tuple:
    m = re.match(r'(\d+)(.*)', n)
    return (int(m.group(1)), m.group(2)) if m else (10 ** 6, n)


# ---------------------------------------------------------------- сторінка будинку

def abzats_budynku(b: dict, period: str, r_m: int) -> str:
    """Абзац людською мовою — лише з чисел, без вигадок і оцінок (ROLYKY-I-SOTSMEREZHI, розд. 5, п. 4)."""
    rechennia = []
    if b['skarh']:
        top = list(b['skarhy'].items())[:2]
        t = f'За {period} до гарячої лінії 1551 щодо будинку {e(b["adresa"])} надійшло {skarhy_slovo(b["skarh"])}'
        t += '. Найчастіше — ' + ' і '.join(f'{e(h)} ({chyslo(n)})' for h, n in top) + '.'
        if b['susidy']:
            h0, n0 = top[0]
            s0 = b['susidy'].get(h0, 0)
            t += (f' Сусідній будинок у радіусі {r_m}{NBSP}м зазвичай має на тему «{e(h0)}» — {chyslo_m(s0)}.')
        rechennia.append(t)
    else:
        rechennia.append(f'За {period} звернень до 1551 з адресою цього будинку в даних немає.')
    roky = f'{D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]}'
    if b['podii_vidkr']:
        hr = Counter()
        for g in b['vidkryti'].values():
            hr.update(g)
        rechennia.append(f'У даних судів за {roky} з адресою будинку — {Z.podii_slovo(b["podii_vidkr"])}: '
                         + ', '.join(f'{D.HR.SLOVO[k]} — {chyslo(n)}'
                                     for k, n in sorted(hr.items(), key=lambda x: (-x[1], x[0]))) + '.')
    else:
        rechennia.append(f'Подій з рішень судів за {roky} з адресою цього будинку в даних немає.')
    return ' '.join(rechennia)


def chyslo_m(x: float) -> str:
    return chyslo(int(x)) if x == int(x) else f'{x:.1f}'.replace('.', ',')


def storinka_budynku(b: dict, bud: Budynky, adresa_saitu: str, susidni: list) -> str:
    period = period_1551(bud.misiatsi)
    roky_t = f'{D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]}'
    kryhty = [('/', 'Головна')]
    if b['rayon']:
        kryhty.append((f'/rayon/{Z.slug_rayonu(b["rayon"])}/', f'{b["rayon"]} район'))
    if b['vulytsia_slug']:
        kryhty.append((f'/vulytsia/{b["vulytsia_slug"]}/', b['vulytsia']))
    else:
        kryhty.append(('', b['vulytsia']))
    kryhty.append(('', f'буд. {b["nomer"]}'))
    ch = [kryhty_html(kryhty)]
    rayon_t = f'{b["rayon"]} район' if b['rayon'] else 'Київ'
    ch.append(f'''<section class="zaholovok">
<span class="mitka">{e(rayon_t)} · будинок</span>
<h1>{e(b["adresa"])}</h1>
<p>{abzats_budynku(b, period, bud.r_susidy)}</p>
{Z.onovleno(bud.versiia)}</section>''')
    ch.append('<section class="chysla" aria-label="Коротко">'
              f'<div class="kartka chyslo-blok"><b class="chyslo">{chyslo(b["skarh"])}</b><span>звернень до 1551 за 12 місяців</span></div>'
              f'<div class="kartka chyslo-blok"><b class="chyslo">{chyslo(b["podii_vidkr"])}</b><span>подій з рішень судів за {roky_t}</span></div>'
              '</section>')

    # Скарги 1551
    if b['skarh']:
        sus = b['susidy'] or {}
        maks = max(list(b['skarhy'].values()) + list(sus.values()) + [1])
        ryady = []
        for h, n in b['skarhy'].items():
            s = sus.get(h)
            ryady.append(
                f'<div class="por__ryad"><span class="por__nazva">{e(z_velykoi(h))}</span>'
                f'<span class="por__smuha"><i class="sh-{shyryna(n, maks)} por--tut"></i></span><b>{chyslo(n)}</b>'
                + (f'<span class="por__smuha"><i class="sh-{shyryna(s, maks)} por--sus"></i></span><b class="por__sus">{chyslo_m(s)}</b>'
                   if s is not None else '<span class="por__smuha"></span><b class="por__sus">—</b>')
                + '</div>')
        pidpys_sus = (f'Сусідні — медіана: скільки звернень цієї теми зазвичай має один будинок у радіусі {bud.r_susidy}{NBSP}м '
                      f'(порівнювали з {chyslo(b["susidiv"])} будинками).' if sus else
                      'Сусідніх будинків зі зверненнями замало для порівняння.')
        ch.append(f'''<section class="rozdil"><h2>Скарги 1551 за 12 місяців</h2>
<p class="rozdil__pidpys">{e(z_velykoi(period))}. Це звернення людей до гарячої лінії міста, а не перевірені факти. Масові відключення
світла чи тепла торкаються багатьох будинків одразу. {pidpys_sus}</p>
<div class="kartka por"><div class="por__shapka" aria-hidden="true"><span>Тема</span><span>цей будинок</span><span></span><span>сусідні</span><span></span></div>
{"".join(ryady)}
<table class="prykhovano"><caption>Звернення 1551 за темами</caption><thead><tr><th>Тема</th><th>Цей будинок</th><th>Сусідні (медіана)</th></tr></thead><tbody>
{"".join(f'<tr><th scope="row">{e(h)}</th><td>{n}</td><td>{chyslo_m(sus[h]) if h in sus else "—"}</td></tr>' for h, n in b['skarhy'].items())}
</tbody></table></div>
<p class="prymitka">Текстів звернень, дат і статусів тут немає — вони в довідці про будинок.</p></section>''')

    # Події з рішень — лише числом
    hrupy = [k for k, _ in D.HRUPY if any(g.get(k) for g in b['vidkryti'].values())]
    if hrupy:
        shapka = ''.join(f'<th scope="col">{r}</th>' for r in D.VIDKRYTI_ROKY)
        ryady = ''.join(f'<tr><th scope="row">{e(HRUPY_PODII[k])}</th>'
                        + ''.join(f'<td>{chyslo(b["vidkryti"][r][k]) if b["vidkryti"][r].get(k) else "—"}</td>' for r in D.VIDKRYTI_ROKY) + '</tr>'
                        for k in hrupy)
        stari = (f'<p class="rozdil__pidpys">Події за {Z.PERIOD_ZAMKNENYI} з адресою будинку теж є — у підписці.</p>'
                 if b['stari'] else '')
        ch.append(f'''<section class="rozdil"><h2>Події з рішень судів — лише числом</h2>
<p class="rozdil__pidpys">Подія — випадок, який описано в рішенні суду, з адресою цього будинку. Це не всі події: лише те, що дійшло
до суду. {D.VIDKRYTI_ROKY[-1]} — неповний рік.</p>
<div class="kartka"><table class="tabl"><thead><tr><th scope="col">Група</th>{shapka}</tr></thead><tbody>{ryady}</tbody></table></div>
{stari}<p class="prymitka">Описів подій і посилань на рішення тут немає — вони в довідці й звіті.</p></section>''')
    elif b['stari']:
        ch.append(f'<section class="rozdil"><h2>Події з рішень судів</h2><p class="rozdil__pidpys">За {roky_t} подій з адресою '
                  f'цього будинку немає; за {Z.PERIOD_ZAMKNENYI} — є, у підписці.</p></section>')

    ch.append(f'''<section class="rozdil"><h2>Довідка про будинок</h2>
<p class="rozdil__pidpys">У довідці: теми звернень 1551 по місяцях і статуси простими словами, порівняння з сусідніми будинками,
події біля будинку й на вулиці коротко — прочитати за 2–3 хвилини. Повний звіт «перед купівлею» — ще й 10 років подій, карта району
й порівняння зі схожими місцями.</p>
{knopky_dovidky(b['url'], 'budynok')}
<p class="prymitka">Оплата ще не працює — кнопка відкриє сторінку, де можна залишити пошту. <a href="/miy-budynok/">Що входить і підписка</a>.</p></section>''')

    if susidni:
        ch.append('<section class="rozdil"><h2>Інші будинки вулиці</h2><ul class="spysok-vulyts spysok-bud">' + ''.join(
            f'<li><a href="{x["url"]}">{e(x["nomer"])}</a></li>' for x in susidni) + '</ul></section>')
    posylannia = []
    if b['vulytsia_slug']:
        posylannia.append(f'<a class="knopka" href="/vulytsia/{b["vulytsia_slug"]}/">{e(b["vulytsia"])} — уся вулиця</a>')
    if b['rayon']:
        posylannia.append(f'<a class="knopka" href="/rayon/{Z.slug_rayonu(b["rayon"])}/">{e(b["rayon"])} район</a>')
    if posylannia:
        ch.append(f'<section class="rozdil"><h2>Поруч</h2><div class="diyi">{"".join(posylannia)}</div></section>')
    ch.append(f'<p class="prymitka">Скарги 1551 — відкриті дані міста (КМДА, data.gov.ua, CC BY), {e(period)}. Події — з рішень судів '
              f'у Єдиному державному реєстрі судових рішень, станом на {e(bud.versiia)}. Колір смуг показує кількість, а не оцінку будинку. '
              f'<a href="/pro-dani/">Як ми працюємо з даними</a> · <a href="/vydalyty/">Видалити або виправити подію</a>.</p>')

    place = {'@context': 'https://schema.org', '@type': 'Place', 'name': f'{b["adresa"]}, Київ',
             'url': f'{adresa_saitu}{b["url"]}',
             'address': {'@type': 'PostalAddress', 'streetAddress': b['adresa'], 'addressLocality': 'Київ', 'addressCountry': 'UA'},
             'geo': {'@type': 'GeoCoordinates', 'latitude': round(b['lat'], 5), 'longitude': round(b['lon'], 5)}}
    if b['rayon']:
        place['containedInPlace'] = {'@type': 'Place', 'name': f'{b["rayon"]} район, Київ'}
    title = f'{b["adresa"]}, Київ: скарги 1551 і події з рішень судів | Моя вулиця'
    opys = (f'{b["adresa"]} ({rayon_t}): {skarhy_slovo(b["skarh"])} до 1551 за 12 місяців'
            + (f' (найчастіше — {next(iter(b["skarhy"]))})' if b['skarh'] else '')
            + f', {Z.podii_slovo(b["podii_vidkr"])} з рішень судів за {roky_t}. Порівняння з сусідніми будинками.')
    return Z.storinka(shlyakh=b['url'], title=title, opys=opys, tilo='\n'.join(ch), adresa_saitu=adresa_saitu,
                      aktyvne='miy-budynok/', dodatkovo_head=ld_skrypt(place, kryhty_ld(kryhty, adresa_saitu)),
                      indeksuvaty=Budynky.indeksuvaty(b), kartynka=(f'{b["url"]}kartynka.png', alt_budynku(b)))


def chysla_budynku(b: dict) -> list:
    roky_t = f'{D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]}'
    return [(chyslo(b['skarh']), f'{vidminok(b["skarh"], ("звернення", "звернення", "звернень"))} до 1551 за 12 місяців'),
            (chyslo(b['podii_vidkr']), f'{vidminok(b["podii_vidkr"], ("подія", "події", "подій"))} з рішень судів за {roky_t}')]


def alt_budynku(b: dict) -> str:
    return f'{b["adresa"]}: ' + ', '.join(f'{a} {p}' for a, p in chysla_budynku(b))


def kartynka_budynku(b: dict, kolory: dict) -> bytes:
    import kartynky as K
    return K.kartynka(f'{b["rayon"]} район · будинок' if b['rayon'] else 'Київ · будинок', b['adresa'], chysla_budynku(b), kolory)


# ---------------------------------------------------------------- сторінка району

def storinka_rayonu(dn: D.Dani, rayon: str, vulytsi: list, bud: Budynky | None, podii_hrupy: Counter,
                    adresa_saitu: str) -> str:
    slug = Z.slug_rayonu(rayon)
    roky_t = Z.PERIOD_VIDKRYTYI
    vsogo = sum(podii_hrupy.values())
    budynky = bud.za_rayonom.get(rayon, []) if bud else []
    skarhy = Counter()
    for b in budynky:
        skarhy.update(b['skarhy'])
    kryhty = [('/', 'Головна'), ('/rayony/', 'Райони'), ('', f'{rayon} район')]
    ch = [kryhty_html(kryhty)]
    rech = [f'У {e(rayon)} районі за {roky_t} у даних судів — {Z.podii_slovo(vsogo)} з точною адресою'
            + (': ' + ', '.join(f'{D.HR.SLOVO[k]} — {chyslo(n)}'
                                for k, n in podii_hrupy.most_common(3)) if vsogo else '') + '.']
    if skarhy:
        top = skarhy.most_common(3)
        rech.append(f'До гарячої лінії 1551 за {period_1551(bud.misiatsi)} з адресами будинків району — '
                    f'{skarhy_slovo(sum(skarhy.values()))}; найчастіше — ' + ', '.join(f'{e(h)} ({chyslo(n)})' for h, n in top) + '.')
    rech.append(f'{chyslo(len(vulytsi))} {vidminok(len(vulytsi), ("вулиця", "вулиці", "вулиць"))} району має свою сторінку'
                + (f', будинків — {chyslo(len(budynky))}' if budynky else '') + '.')
    ch.append(f'<section class="zaholovok"><span class="mitka">Київ · район</span><h1>{e(rayon)} район</h1><p>{" ".join(rech)}</p></section>')
    if vsogo:
        maks = max(podii_hrupy.values())
        ch.append('<section class="rozdil"><h2>Події з рішень судів за групами</h2>'
                  f'<p class="rozdil__pidpys">{roky_t}; лише події з точною адресою в районі. Це кількість у даних, а не оцінка району.</p>'
                  '<div class="kartka por">' + ''.join(
                      f'<div class="por__ryad por__ryad--1"><span class="por__nazva">{e(HRUPY_PODII[k])}</span>'
                      f'<span class="por__smuha"><i class="sh-{shyryna(n, maks)} por--tut"></i></span><b>{chyslo(n)}</b></div>'
                      for k, n in podii_hrupy.most_common()) + '</div></section>')
    if skarhy:
        maks = max(skarhy.values())
        ch.append('<section class="rozdil"><h2>Скарги 1551 за темами</h2>'
                  f'<p class="rozdil__pidpys">{e(z_velykoi(period_1551(bud.misiatsi)))}; звернення людей, не перевірені факти.</p>'
                  '<div class="kartka por">' + ''.join(
                      f'<div class="por__ryad por__ryad--1"><span class="por__nazva">{e(z_velykoi(h))}</span>'
                      f'<span class="por__smuha"><i class="sh-{shyryna(n, maks)} por--tut"></i></span><b>{chyslo(n)}</b></div>'
                      for h, n in skarhy.most_common(10)) + '</div></section>')
    vs = sorted(vulytsi, key=lambda v: (Z.kliuch_abetky(v.korotka), v.slug))
    ch.append(f'<section class="rozdil"><h2>Вулиці району</h2><p class="rozdil__pidpys">За абеткою; поруч — подій за {roky_t}. '
              f'<a href="/vulytsi/{slug}/">Покажчик вулиць району</a>.</p>{Z.spysok_vulyts(vs)}</section>')
    ch.append(f'<section class="rozdil"><h2>Мій будинок</h2><p class="rozdil__pidpys">Знайдіть свою вулицю — на її сторінці є '
              f'будинки зі своєю сторінкою.</p>{knopky_dovidky("", "rayon")}</section>')
    title = f'{rayon} район, Київ: події з судових рішень і скарги 1551 | Моя вулиця'
    opys = (f'{rayon} район Києва: {Z.podii_slovo(vsogo)} з судових рішень за {roky_t}, скарги 1551 за темами, '
            f'{chyslo(len(vulytsi))} вулиць зі своєю сторінкою.')
    place = {'@context': 'https://schema.org', '@type': 'Place', 'name': f'{rayon} район, Київ',
             'url': f'{adresa_saitu}/rayon/{slug}/', 'containedInPlace': {'@type': 'City', 'name': 'Київ'}}
    return Z.storinka(shlyakh=f'/rayon/{slug}/', title=title, opys=opys, tilo='\n'.join(ch), adresa_saitu=adresa_saitu,
                      aktyvne='vulytsi/', dodatkovo_head=ld_skrypt(place, kryhty_ld(kryhty, adresa_saitu)))


def storinka_rayoniv(rayony: list, adresa_saitu: str) -> str:
    kryhty = [('/', 'Головна'), ('', 'Райони')]
    tilo = (kryhty_html(kryhty) + '<section class="zaholovok"><h1>Райони Києва</h1><p>Десять районів: події з судових рішень, '
            'скарги 1551 і всі вулиці кожного району.</p></section><nav class="rayony" aria-label="Райони">'
            + ''.join(f'<a href="/rayon/{Z.slug_rayonu(r)}/">{e(r)}</a>' for r in rayony) + '</nav>')
    return Z.storinka(shlyakh='/rayony/', title='Райони Києва — події з судових рішень і скарги 1551 | Моя вулиця',
                      opys='Райони Києва: події з судових рішень, скарги 1551 і вулиці кожного району.', tilo=tilo,
                      adresa_saitu=adresa_saitu, aktyvne='vulytsi/', dodatkovo_head=ld_skrypt(kryhty_ld(kryhty, adresa_saitu)))


# ---------------------------------------------------------------- вітрини

def vitryna(shlyakh: str, nazva: str, mitka: str, vstup: str, tilo: str, title: str, opys: str, adresa_saitu: str,
            aktyvne: str = '', kartynka: tuple | None = None) -> str:
    kryhty = [('/', 'Головна'), ('', nazva)]
    t = (kryhty_html(kryhty) + f'<section class="zaholovok"><span class="mitka">{e(mitka)}</span><h1>{e(nazva)}</h1>'
         f'<p>{vstup}</p></section>' + tilo)
    return Z.storinka(shlyakh=shlyakh, title=title, opys=opys, tilo=t, adresa_saitu=adresa_saitu, aktyvne=aktyvne or shlyakh[1:],
                      dodatkovo_head=ld_skrypt(kryhty_ld(kryhty, adresa_saitu)), kartynka=kartynka)


def kartka_tovaru(kl: str, pidpys: str, punkty: list, holovna: bool = False, dzherelo: str = '') -> str:
    li = ''.join(f'<li>{p}</li>' for p in punkty)
    d = f'&amp;dzherelo={dzherelo}' if dzherelo else ''
    if TSINY[kl] is None:
        # Ціна за домовленістю (MV-102): форма запиту — передзамовлення заглушки з вибором «Для компанії»; відповідає партнер.
        href, napys = f'/zahlushka/?shcho=kompaniya{d}#peredzamovlennya', 'Надіслати запит'
    else:
        href, napys = f'/oplata/?tovar={kl}{d}', 'Замовити'
    return (f'<div class="kartka tovar{" tovar--holovnyi" if holovna else ""}"><h3>{e(TOVARY[kl])}</h3>'
            f'<p class="tovar__tsina{"" if TSINY[kl] is not None else " tovar__tsina--nema"}">{tsina(kl)}</p><p class="tovar__pidpys">{pidpys}</p><ul>{li}</ul>'
            f'<a class="knopka{" knopka--holovna" if holovna else ""}" href="{href}">{napys}</a></div>')


def vitryna_miy_budynok(adresa_saitu: str, prykl: list, kartynka: tuple | None = None) -> str:
    tovary = ''.join([
        kartka_tovaru('dovidka', 'Разово, для одного будинку', [
            'скарги 1551 за 12 місяців: теми, місяці, статуси простими словами',
            'порівняння з сусідніми будинками', 'події з рішень судів біля будинку й на вулиці — коротко',
            'прочитати за 2–3 хвилини'], True, dzherelo='miy-budynok'),
        kartka_tovaru('try', 'Три будинки — порівняти перед орендою чи купівлею', [
            'три довідки на вибір', 'дешевше, ніж три окремо'], dzherelo='miy-budynok'),
        kartka_tovaru('zvit', 'Перед купівлею житла', [
            'усе з довідки', 'події за 10 років з описами людською мовою', 'карта району й порівняння зі схожими місцями'],
            dzherelo='miy-budynok'),
        kartka_tovaru('pidpyska', 'Щомісяця', [
            '1 довідка на місяць включено', f'додаткові довідки — по {tsina("dodatkova")}',
            'карта з адресами й подіями, сповіщення про нове біля дому'], dzherelo='miy-budynok'),
        kartka_tovaru('rieltor', 'Для рієлтора', ['5 довідок на місяць', 'для показів і клієнтів'], dzherelo='miy-budynok'),
    ])
    pryklady = ''.join(f'<li><a href="{b["url"]}">{e(b["adresa"])}</a></li>' for b in prykl)
    tilo = f'''<section class="rozdil"><h2>Знайдіть свій будинок</h2>
<p class="rozdil__pidpys">Відкрийте свою вулицю — на її сторінці є список будинків. Сторінка будинку безкоштовна: скарги 1551 і події з рішень
судів числом.</p>
<form class="poshuk" role="search" action="/vulytsi/"><label class="prykhovano" for="poshuk-vulytsi">Назва вулиці</label>
<input id="poshuk-vulytsi" type="search" autocomplete="off" placeholder="Назва вулиці, наприклад: Хрещатик">
<ul class="poshuk__spysok" id="poshuk-spysok" hidden></ul></form>
{f'<p class="prymitka">Наприклад:</p><ul class="spysok-vulyts">{pryklady}</ul>' if pryklady else ''}</section>
<section class="rozdil"><h2>Що можна замовити</h2><div class="tovary">{tovary}</div>
<p class="prymitka">Довідка — не оцінка будинку й не порада, де жити. Скарги 1551 — звернення людей, не перевірені факти; події — те,
що дійшло до суду. Оплата ще не працює: кнопка відкриє сторінку, де можна залишити пошту.</p></section>'''
    return Z.storinka(
        shlyakh='/miy-budynok/', title='Мій будинок — довідка про будинок у Києві за 199 грн | Моя вулиця',
        opys='Довідка про будинок: скарги 1551, порівняння з сусідами, події з рішень судів. 199 грн разово, 3 довідки — 449, повний звіт — 599.',
        tilo=kryhty_html([('/', 'Головна'), ('', 'Мій будинок')])
        + '<section class="zaholovok"><span class="mitka">Для мешканців, орендарів і покупців</span><h1>Мій будинок</h1>'
          '<p>Що відомо про будинок: на що скаржаться мешканці в 1551 і які події з рішень судів були з цією адресою. '
          'Перед орендою, купівлею чи просто для себе.</p></section>' + tilo,
        adresa_saitu=adresa_saitu, aktyvne='miy-budynok/', skrypty=('/sait/poshuk.js',), kartynka=kartynka,
        dodatkovo_head=ld_skrypt(kryhty_ld([('/', 'Головна'), ('', 'Мій будинок')], adresa_saitu)))


def vitryna_osbb(adresa_saitu: str, kartynka: tuple | None = None) -> str:
    tilo = f'''<section class="rozdil"><h2>Що отримує правління</h2><div class="tovary">
{kartka_tovaru('osbb', 'Річна оплата за будинок', [
        'щомісяця — довідка про ваш будинок: усі звернення 1551 з темами, статусами й строками',
        'порівняння з сусідніми будинками', 'рахунок для юридичної особи'], True, dzherelo='osbb')}
<div class="kartka tovar"><h3>Навіщо</h3><ul><li>бачити, що турбує мешканців, ще до зборів</li>
<li>мати числа для розмови з управителем і районною адміністрацією</li><li>звітувати мешканцям</li></ul></div>
</div></section>
<section class="rozdil"><h2>Безкоштовно вже зараз</h2><p class="rozdil__pidpys">Сторінка будинку з темами звернень 1551 за 12 місяців —
знайдіть свою вулицю в <a href="/vulytsi/">покажчику</a>.</p></section>'''
    return vitryna('/osbb/', 'Для ОСББ', 'Для правлінь ОСББ і управителів',
                   'Щомісячна довідка про ваш будинок: звернення мешканців до 1551 і порівняння з сусідніми будинками.',
                   tilo, 'Для ОСББ — щомісячна довідка про будинок, скарги 1551 | Моя вулиця',
                   'Для правлінь ОСББ: щомісячна довідка про будинок — звернення 1551, статуси, порівняння з сусідами. Річна оплата.',
                   adresa_saitu, kartynka=kartynka)


def vitryna_sudova(adresa_saitu: str, kartynka: tuple | None = None) -> str:
    tilo = '''<section class="rozdil"><h2>Що тут буде</h2><div class="kartka"><ul class="spysok-tekst">
<li>Статті кодексів і суди Києва: скільки справ, чим закінчуються, скільки тривають, як змінюється за роками.</li>
<li>Безкоштовно — короткі цифри по статті; повні таблиці по судах і фільтри — платно.</li>
<li>Без імен людей. Лише те, що ми розбираємо точно.</li></ul></div>
<p class="prymitka">Розділ готуємо: спершу перевіряємо, наскільки точно розбираємо статтю, суд і результат справи. Показуємо лише те,
що проходить перевірку.</p></section>
<section class="rozdil"><h2>Повідомити про запуск</h2><div class="diyi">
<a class="knopka knopka--holovna" href="/oplata/?tovar=sudova&amp;dzherelo=sudova-praktyka">Залишити пошту</a></div></section>'''
    return vitryna('/sudova-praktyka/', 'Судова практика', 'Скоро',
                   'Що вирішують суди Києва за статтями: кількість справ, результати й строки — з тієї самої бази рішень, що й карта.',
                   tilo, 'Судова практика: суди Києва за статтями — скоро | Моя вулиця',
                   'Судова практика за статтями й судами Києва: скільки справ, результати, строки. Розділ готуємо — залиште пошту.',
                   adresa_saitu, kartynka=kartynka)


def vitryna_biznes(adresa_saitu: str, kartynka: tuple | None = None) -> str:
    tilo = f'''<section class="rozdil"><h2>Набори й доступ</h2><div class="tovary">
{kartka_tovaru('biznes', 'Користування базою на рік за договором — не продаж', [
        'події з рішень судів з адресами й точками на карті (Київ, 10 років)', 'скарги 1551 по будинках',
        'вивантаження файлом або доступ для програм', 'оновлення щомісяця'], True, dzherelo='biznes')}
<div class="kartka tovar"><h3>Для кого</h3><ul><li>забудовники й агенції нерухомості</li><li>страхові й банки</li>
<li>дослідники й медіа</li></ul></div></div>
<p class="prymitka">Умови — в <a href="/zahlushka/oferta.html">оферті</a> і договорі. Вивантаження бази — лише компаніям за договором.
Платежі й договори оформлює партнер проєкту.</p></section>'''
    return vitryna('/biznes/', 'Для бізнесу', 'Для компаній',
                   'База подій із судових рішень і скарг 1551 — у користування на рік за договором. Ціна — за домовленістю: залиште запит, відповість партнер проєкту.',
                   tilo, 'Дані для бізнесу: події з судових рішень і скарги 1551 Києва | Моя вулиця',
                   'Дані для компаній: події з судових рішень з адресами, скарги 1551 по будинках. Користування на рік за договором.',
                   adresa_saitu, kartynka=kartynka)


def storinka_oplaty(adresa_saitu: str) -> str:
    tovary = ''.join(f'<li><b>{e(TOVARY[k])}</b> — {tsina(k)}</li>' for k in TOVARY)
    tilo = f'''{kryhty_html([('/', 'Головна'), ('', 'Оплата')])}
<section class="zaholovok"><span class="mitka">Скоро</span><h1>Оплата скоро</h1>
<p>Ми ще не приймаємо оплату. Залиште пошту — напишемо один раз, коли довідку можна буде замовити.</p></section>
<section class="rozdil"><div class="diyi">
<a class="knopka knopka--holovna" href="/zahlushka/?dzherelo=oplata#peredzamovlennya">Залишити пошту</a>
<a class="knopka" href="/miy-budynok/">Що входить у довідку</a></div>
<p class="prymitka">Пошту залишаєте у формі передзамовлення; її зберігають за <a href="/zahlushka/polityka.html">політикою конфіденційності</a>
і пишуть лише про запуск.</p></section>
<section class="rozdil"><h2>Ціни</h2><div class="kartka"><ul class="spysok-tekst">{tovary}</ul></div></section>'''
    return Z.storinka(shlyakh='/oplata/', title='Оплата скоро | Моя вулиця', opys='Оплата ще не працює — залиште пошту.',
                      tilo=tilo, adresa_saitu=adresa_saitu, indeksuvaty=False)


def storinka_vydalyty(adresa_saitu: str) -> str:
    kryhty = [('/', 'Головна'), ('', 'Видалити або виправити подію')]
    tilo = f'''{kryhty_html(kryhty)}
<section class="zaholovok"><h1>Видалити або виправити подію</h1>
<p>Якщо подія стосується вас і показана неправильно або ви хочете, щоб її прибрали, — напишіть нам. Відповідаємо й виправляємо
<b>протягом 10 робочих днів</b>.</p></section>
<section class="rozdil"><h2>Як це працює</h2><div class="kartka"><ol class="spysok-tekst">
<li>Заповніть <a href="/zahlushka/zvernennya.html">форму звернення</a>: адреса або вулиця, що саме не так, як з вами зв’язатися.</li>
<li>Ми перевіряємо подію за рішенням суду, з якого її взято.</li>
<li>Протягом 10 робочих днів — виправляємо, прибираємо або пояснюємо, чому лишаємо, і пишемо вам.</li>
<li>Прибрана подія зникає з карти, довідок і звітів після найближчого оновлення даних і більше не повертається.</li>
</ol></div></section>
<section class="rozdil"><h2>Що ми можемо виправити</h2><div class="kartka"><ul class="spysok-tekst">
<li>Неправильна адреса чи місце події.</li><li>Опис, який каже більше, ніж рішення суду.</li>
<li>Подія, яку суд не підтвердив (виправдання, скасування рішення).</li>
<li>Подія, що дозволяє впізнати вас, хоча суд приховав ці дані.</li></ul></div>
<p class="prymitka">Скарги 1551 — відкриті дані міста; ми показуємо лише теми й кількість, без текстів. Помилку в них виправляє гаряча лінія 1551.</p></section>'''
    return Z.storinka(shlyakh='/vydalyty/', title='Видалити або виправити подію — 10 робочих днів | Моя вулиця',
                      opys='Як прибрати або виправити подію на сайті «Моя вулиця»: форма звернення, відповідь за 10 робочих днів.',
                      tilo=tilo, adresa_saitu=adresa_saitu, dodatkovo_head=ld_skrypt(kryhty_ld(kryhty, adresa_saitu)))


def storinka_pro_dani(adresa_saitu: str, versiia: str, period: str) -> str:
    kryhty = [('/', 'Головна'), ('', 'Як ми працюємо з даними')]
    tilo = f'''{kryhty_html(kryhty)}
<section class="zaholovok"><h1>Як ми працюємо з даними</h1>
<p>Звідки числа на сайті, що вони означають і чого не означають.</p></section>
<section class="rozdil"><h2>Звідки дані</h2><div class="kartka"><ul class="spysok-tekst">
<li><b>Події</b> — з рішень судів у Єдиному державному реєстрі судових рішень (річні архіви на data.gov.ua). Подія — випадок, описаний
у рішенні, з місцем, де він стався. Кілька рішень в одній справі — одна подія. Дані станом на {e(versiia)}.</li>
<li><b>Скарги 1551</b> — відкриті дані гарячої лінії міста (КМДА, data.gov.ua, ліцензія CC BY){f", {e(period)}" if period else ""}.
Персональних даних у наборі немає; ми показуємо лише теми й кількість.</li>
<li><b>Адреси й карта</b> — OpenStreetMap (ODbL), підкладка — OpenFreeMap.</li></ul></div></section>
<section class="rozdil"><h2>Що ці числа означають</h2><div class="kartka"><ul class="spysok-tekst">
<li>Це лише те, що дійшло до суду або до 1551, а не всі події.</li>
<li>Колір і числа показують кількість у даних, а не те, наскільки місце «погане». Ми не ставимо місцям оцінок, не прогнозуємо й не
стверджуємо причин.</li>
<li>Скарга 1551 — звернення людини, а не перевірений факт.</li>
<li>Подію, яку суд не підтвердив (виправдання, скасування), ми не показуємо.</li></ul></div></section>
<section class="rozdil"><h2>Що ми не показуємо відкрито</h2><div class="kartka"><ul class="spysok-tekst">
<li>Імен, номерів квартир і даних, які суд приховав, немає ніде.</li>
<li>На безкоштовних сторінках немає описів подій і посилань на рішення — лише числа.</li>
<li>Безкоштовно — останні 3 роки; старші — у підписці.</li>
<li>Домашнє насильство рахуємо нарівні з іншими подіями. Статеві злочини й справи щодо дітей на сторінках будинків, вулиць
і районів не рахуємо — лише в загальному числі великих сот на карті.</li></ul></div></section>
<section class="rozdil"><h2>Якщо щось не так</h2><p class="rozdil__pidpys"><a href="/vydalyty/">Видалити або виправити подію</a> — відповідаємо
за 10 робочих днів. <a href="/zahlushka/polityka.html">Політика конфіденційності</a>.</p></section>'''
    return Z.storinka(shlyakh='/pro-dani/', title='Як ми працюємо з даними — суди, 1551, OpenStreetMap | Моя вулиця',
                      opys='Звідки дані «Моєї вулиці»: рішення судів з ЄДРСР, скарги 1551, OpenStreetMap. Що означають числа і чого ми не показуємо.',
                      tilo=tilo, adresa_saitu=adresa_saitu, dodatkovo_head=ld_skrypt(kryhty_ld(kryhty, adresa_saitu)))


# ---------------------------------------------------------------- усе разом

def podii_rayoniv(dn: D.Dani) -> dict:
    """Район → групи → подій за останні 3 роки (лише з точкою; домашнє насильство — нарівні, статеві й щодо дітей — ні, MV-102)."""
    out = defaultdict(Counter)
    if dn.rayony is None:
        return out
    kesh = {}
    for p in dn.podii:
        if p.lat is None or p.chutlyva or not D.vidkryta(p):
            continue
        k = (round(p.lat, 3), round(p.lon, 3))
        if k not in kesh:
            kesh[k] = dn.rayony.rayon(p.lat, p.lon)
        r = kesh[k]
        hr = D.HR.hrupa(p.vyd, p.stattia)
        if r and hr:
            out[r][hr] += 1
    return out


def chysla_vitryn(dn: D.Dani, bud: Budynky | None, vulyts: int) -> dict:
    """Числа для картинок вітрин (ZAVDANNYA-88, п. 3): лише відкриті роки (MV-32), без чутливих (MV-102)."""
    podii = sum(1 for p in dn.podii if p.lat is not None and not p.chutlyva and D.vidkryta(p))
    roky_t = f'{D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]}'
    p_t = (chyslo(podii), f'{vidminok(podii, ("подія", "події", "подій"))} з рішень судів за {roky_t} з точною адресою')
    budynkiv = len(bud.spysok) if bud else 0
    zi_skarhamy = sum(1 for b in bud.spysok if b['skarh']) if bud else 0
    skarh = sum(b['skarh'] for b in bud.spysok) if bud else 0
    b_t = (chyslo(budynkiv), f'{vidminok(budynkiv, ("будинок", "будинки", "будинків"))} Києва зі своєю сторінкою')
    s_t = (chyslo(skarh), f'{vidminok(skarh, ("звернення", "звернення", "звернень"))} до 1551 за 12 місяців')
    zs_t = (chyslo(zi_skarhamy), f'{vidminok(zi_skarhamy, ("будинок", "будинки", "будинків"))} зі зверненнями до 1551')
    v_t = (chyslo(vulyts), f'{vidminok(vulyts, ("вулиця", "вулиці", "вулиць"))} зі своєю сторінкою')
    return {
        'miy-budynok': ('Для мешканців, орендарів і покупців', 'Мій будинок', [b_t, s_t] if bud else [v_t]),
        'osbb': ('Для правлінь ОСББ', 'Для ОСББ', [zs_t, s_t] if bud else [v_t]),
        'sudova-praktyka': ('Скоро', 'Судова практика', [p_t]),
        'biznes': ('Для компаній', 'Для бізнесу', [p_t, s_t] if bud else [p_t, v_t]),
    }


def zibraty_vse(dn: D.Dani, rayony: list, za_rayonom: dict, bud: Budynky | None,
                vykhid: Path, adresa_saitu: str, pachky=None, vulyts: int = 0) -> list:
    """Пише сторінки будинків, районів, вітрин і довідкові; повертає адреси для sitemap.
    `pachky` (site/khostynh.py, варіант workers) — сторінки й картинки будинків ідуть у пачки, а не окремими файлами."""
    adresy = []
    kolory = Z.kolory_tem()['svitla']

    def budynok(b, vikno):
        html_ = storinka_budynku(b, bud, adresa_saitu, vikno)
        png = kartynka_budynku(b, kolory)
        if pachky is not None:
            pachky.dodaty(b['slug'], html_, png)
        else:
            Z.zapysaty(vykhid / 'budynok' / b['slug'] / 'index.html', html_)
            Z.zapysaty_bajty(vykhid / 'budynok' / b['slug'] / 'kartynka.png', png)
    if bud:
        for v_slug, spysok in bud.za_vulytseyu.items():
            for i, b in enumerate(spysok):
                budynok(b, spysok[max(0, i - 6):i] + spysok[i + 1:i + 7])
        for b in bud.spysok:
            if not b['vulytsia_slug']:
                budynok(b, [])
        adresy += [b['url'] for b in bud.spysok if Budynky.indeksuvaty(b)]
    pr = podii_rayoniv(dn)
    for r in rayony:
        Z.zapysaty(vykhid / 'rayon' / Z.slug_rayonu(r) / 'index.html',
                   storinka_rayonu(dn, r, za_rayonom[r], bud, pr.get(r, Counter()), adresa_saitu))
        adresy.append(f'/rayon/{Z.slug_rayonu(r)}/')
    Z.zapysaty(vykhid / 'rayony' / 'index.html', storinka_rayoniv(rayony, adresa_saitu))
    adresy.append('/rayony/')
    prykl = []
    if bud:
        # Приклади — будинки з «середньою» кількістю даних з різних районів: не добірка тих, де найбільше
        kandydaty = sorted((b for b in bud.spysok if b['vulytsia_slug'] and Budynky.indeksuvaty(b) and b['skarh'] and b['podii_vidkr']),
                           key=lambda b: (b['skarh'] + b['podii_vidkr'], b['slug']))
        kandydaty = kandydaty[len(kandydaty) // 2:] + kandydaty[:len(kandydaty) // 2]
        bachyly = set()
        for b in kandydaty:
            if b['rayon'] not in bachyly:
                bachyly.add(b['rayon'])
                prykl.append(b)
            if len(prykl) == 3:
                break
        prykl.sort(key=lambda b: b['slug'])
    import kartynky as K
    kv = {}
    for shl, (mitka, nazva, chysla) in chysla_vitryn(dn, bud, vulyts).items():
        Z.zapysaty_bajty(vykhid / shl / 'kartynka.png', K.kartynka(mitka, nazva, chysla, kolory))
        kv[shl] = (f'/{shl}/kartynka.png', f'{nazva}: ' + ', '.join(f'{a} {p}' for a, p in chysla))
    for shl, html_ in (('miy-budynok', vitryna_miy_budynok(adresa_saitu, prykl, kv['miy-budynok'])),
                       ('osbb', vitryna_osbb(adresa_saitu, kv['osbb'])),
                       ('sudova-praktyka', vitryna_sudova(adresa_saitu, kv['sudova-praktyka'])),
                       ('biznes', vitryna_biznes(adresa_saitu, kv['biznes'])),
                       ('vydalyty', storinka_vydalyty(adresa_saitu)),
                       ('pro-dani', storinka_pro_dani(adresa_saitu, dn.versiia, period_1551(bud.misiatsi) if bud else ''))):
        Z.zapysaty(vykhid / shl / 'index.html', html_)
        adresy.append(f'/{shl}/')
    Z.zapysaty(vykhid / 'oplata' / 'index.html', storinka_oplaty(adresa_saitu))
    return adresy
