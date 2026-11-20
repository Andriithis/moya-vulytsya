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
import zaholovky as ZH
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


# Гасла (MV-52, MV-106) і меседжі ліній (MV-107, docs/KOMPAS.md, розд. 3) — одне місце для всього сайту.
HASLO_BRENDU = 'Що відбувається під боком'
HASLO_BUDYNKU = 'Що болить вашому будинку'
OPYS_BUDYNKU = 'Скарги мешканців і події з рішень судів — по кожному будинку'
MESEDZH = {
    'miy-budynok': 'Перш ніж орендувати чи купити — подивіться, що болить будинку й вулиці довкола.',
    'osbb': 'Що болить вашому будинку — щомісяця, у порівнянні із сусідами.',
    'sudova-praktyka': 'Як суди Києва вирішують справи за вашою статтею.',
    'biznes': 'Події й скарги по кожній адресі Києва — для ваших продуктів.',
}


def haslo_budynku() -> str:
    """Гасло лінії «Мій будинок» з описом дрібно (MV-106): на сторінках будинків і вітрині «Мій будинок»."""
    return f'<p class="haslo-linii"><b>{HASLO_BUDYNKU}</b><span>{OPYS_BUDYNKU}</span></p>'


def tsina(kl: str) -> str:
    return T.tsina(kl)


def prymitka_oplaty(yak: str) -> str:
    """ZAVDANNYA-150, п. 2: «Оплата ще не працює» — лише в режимі «скоро» (`--oplata skoro`, MV_OPLATA). Коли продаж увімкнено,
    рядка немає (порожньо)."""
    return f'Оплата ще не працює. {yak} ' if T.OPLATA['rezhym'] == 'skoro' else ''


def misiats(ym: str) -> str:
    r, m = ym.split('-')
    return f'{MISIATSI[int(m) - 1]} {r}'


def period_1551(ms: list) -> str:
    return f'{misiats(ms[0])} — {misiats(ms[-1])}' if ms else ''


# Б-2 (ZAVDANNYA-110): квартира, офіс, приміщення, поверх — не частина номера будинку; те саме правило, що
# dani-edrsr/src/budynky_sait.py (KVARTYRA) — тут на випадок старого зведення.
KVARTYRA = re.compile(r'\s*,?\s*(?:оф(?:іс)?|кв(?:артира)?|прим(?:іщення)?|кімн(?:ата)?|\d*\s*поверх|секція)\b\.?.*$'
                      r'|\s*,?\s*(?:оф(?:іс)?|кв|прим)\.?\s*№?\s*\d.*$', re.I)


def bez_kvartyry(n: str) -> str:
    """«43 кв32» → «43», «15/5 оф73» → «15/5»."""
    t = KVARTYRA.sub('', n or '').strip(' ,')
    return t or n


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
    # ZAVDANNYA-154: Google вимагає адресу в кожного пункту, крім останнього; проміжний пункт без сторінки (вулиця без
    # своєї сторінки) у розмітку не йде — на сторінці його видно, як і раніше.
    punkty = [p for i, p in enumerate(punkty) if p[0] or i == len(punkty) - 1]
    return {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
        {'@type': 'ListItem', 'position': i + 1, 'name': n, **({'item': adresa_saitu + u} if u else {})}
        for i, (u, n) in enumerate(punkty)]}


def ld_skrypt(*obiekty) -> str:
    return ''.join(f'<script type="application/ld+json">'
                   f'{json.dumps(o, ensure_ascii=False, sort_keys=True).replace("</", "<" + chr(92) + "/")}</script>\n'
                   for o in obiekty)


def knopky_dovidky(budynok: str = '', dzherelo: str = '', adresa: str = '', odna: bool = False) -> str:
    """Кнопки покупки. odna (ZAVDANNYA-177, ZVIT-165, п. 7): на сторінці будинку — одна головна кнопка «Довідка», а «3 довідки»
    й повний звіт — посиланнями під нею (три рівні кнопки на сторінці одного будинку плутали)."""
    from urllib.parse import quote
    q = (f'&amp;budynok={e(budynok)}' if budynok else '') + (f'&amp;adresa={quote(adresa)}' if adresa else '')
    d = f'&amp;dzherelo={e(dzherelo)}' if dzherelo else ''
    if odna:
        return (f'<div class="tsiny tsiny--odna">'
                + T.knopka_oplaty(f'/oplata/?tovar=dovidka{q}{d}', f'Довідка про цей будинок — {tsina("dovidka")}', True)
                + f'<p class="tsiny__inshi">Або: <a href="/oplata/?tovar=zvit{q}{d}">повний звіт перед купівлею — {tsina("zvit")}</a> · '
                f'<a href="/oplata/?tovar=try{q}{d}">3 довідки для трьох адрес — {tsina("try")}</a></p></div>')
    return (f'<div class="tsiny">'
            + T.knopka_oplaty(f'/oplata/?tovar=dovidka{q}{d}', f'Довідка — {tsina("dovidka")}', True)
            + T.knopka_oplaty(f'/oplata/?tovar=try{q}{d}', f'3 довідки — {tsina("try")}')
            + T.knopka_oplaty(f'/oplata/?tovar=zvit{q}{d}', f'Повний звіт — {tsina("zvit")}') +
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
            b = dict(b, nomer=bez_kvartyry(b['nomer']))
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


BUDYNKIV_PORUCH = 6
R_PORUCH_M = 400


def budynky_poruch(spysok: list, n: int = BUDYNKIV_PORUCH, r_m: float = R_PORUCH_M) -> dict:
    """ZAVDANNYA-154: для кожного будинку — до n найближчих будинків інших вулиць у радіусі r_m (slug → [будинки]).
    Посилання «Будинки поруч»: людина бачить сусідній квартал, Google — шлях до кожного будинку, і до тих, у чиєї вулиці
    немає своєї сторінки."""
    import math
    krok = 0.005                       # ≈ 550 м по широті — клітинка сітки
    sitka = defaultdict(list)
    for b in spysok:
        sitka[(int(b['lat'] // krok), int(b['lon'] // krok))].append(b)
    kx = math.cos(math.radians(50.45))
    rez = {}
    for b in spysok:
        i, j = int(b['lat'] // krok), int(b['lon'] // krok)
        kandydaty = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for x in sitka.get((i + di, j + dj), ()):
                    if x is b or (x['vulytsia'] == b['vulytsia']):
                        continue
                    d = math.hypot(x['lat'] - b['lat'], (x['lon'] - b['lon']) * kx) * 111_200
                    if d <= r_m:
                        kandydaty.append((round(d), x['slug'], x))
        kandydaty.sort(key=lambda t: (t[0], t[1]))
        rez[b['slug']] = [x for _, _, x in kandydaty[:n]]
    return rez


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
            t += ' ' + rechennia_susidiv(h0, b['susidy'].get(h0, 0), r_m)
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


def rechennia_susidiv(tema: str, s0: float, r_m: int) -> str:
    """ZVIT-165, п. 7: «Сусідній будинок … зазвичай має на тему «…» — 0» звучало незграбно й наче будинок «вирізняється».
    Число — те саме (медіана сусідніх), сказане людською мовою; оцінки немає."""
    if not s0:
        return f'У більшості сусідніх будинків у радіусі {r_m}{NBSP}м звернень на тему «{e(tema)}» не було.'
    return (f'У сусідніх будинках у радіусі {r_m}{NBSP}м на цю тему зазвичай {chyslo_m(s0)} '
            f'{vidminok(int(s0), ("звернення", "звернення", "звернень")) if s0 == int(s0) else "звернення"} на будинок.')


def urivok_dovidky(b: dict, r_m: int) -> str:
    """ZAVDANNYA-150, п. 13: біля кнопок купівлі — що саме буде в довідці ЦЬОГО будинку, з його ж відкритих чисел
    (без нових фактів: опис, місяці й статуси — лише в довідці)."""
    punkty = []
    if b['skarh']:
        h0, n0 = next(iter(b['skarhy'].items()))
        s0 = (b['susidy'] or {}).get(h0)
        por = ((f' — тут {chyslo(n0)}, у більшості сусідніх у радіусі {r_m}{NBSP}м — жодного' if not s0 else
                f' — тут {chyslo(n0)}, у сусідніх у радіусі {r_m}{NBSP}м зазвичай {chyslo_m(s0)}') if s0 is not None else '')
        punkty.append(f'{skarhy_slovo(b["skarh"])} до 1551 — по місяцях і статусах: що вирішили, що ні; найчастіше «{e(h0)}»{por}')
    else:
        punkty.append('скарги 1551 будинку й двору за 12 місяців — їх тут немає, і це теж відповідь')
    punkty.append(f'події з рішень судів біля будинку й на вулиці — коротко, з посиланням на кожне рішення'
                  + (f' (з адресою самого будинку — {chyslo(b["podii_vidkr"])} за {D.VIDKRYTI_ROKY[0]}–{D.VIDKRYTI_ROKY[-1]})'
                     if b['podii_vidkr'] else ''))
    punkty.append('три висновки зверху — прочитати за 2–3 хвилини; можна зберегти файлом PDF')
    return ('<div class="kartka urivok"><p><b>Що буде в довідці про цей будинок</b></p><ul class="spysok-tekst">'
            + ''.join(f'<li>{x}</li>' for x in punkty)
            + '</ul><p class="prymitka"><a href="/zahlushka/zrazok.html">Подивитися зразок</a></p></div>')


def chyslo_m(x: float) -> str:
    return chyslo(int(x)) if x == int(x) else f'{x:.1f}'.replace('.', ',')


def podii_zvitu(period: str) -> str:
    """що про події в повному звіті — чесно за періодом, що є в даних (ZAVDANNYA-109; той самий період, що в звіті).
    ZAVDANNYA-150, п. 9: «людською мовою» — лише переказ ШІ, а він увімкнений не завжди (MV-159), тому — «стислий опис з рішення»."""
    return (f'події за {period} зі стислим описом з рішення' if period else 'події з рішень судів зі стислим описом з рішення')


def storinka_budynku(b: dict, bud: Budynky, adresa_saitu: str, susidni: list, period_podii: str = '',
                    poruch: list | None = None) -> str:
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
        pidpys_sus = (f'Сусідні — скільки звернень цієї теми зазвичай має один будинок у радіусі {bud.r_susidy}{NBSP}м: '
                      f'половина з {chyslo(b["susidiv"])} сусідніх будинків має менше, половина — більше.' if sus else
                      'Сусідніх будинків зі зверненнями замало для порівняння.')
        if sus and not any(sus.get(h) for h in b['skarhy']):      # ZVIT-165, п. 7: «0» у всіх темах
            pidpys_sus += (f' У більшості з {chyslo(b["susidiv"])} сусідніх будинків звернень на ці теми не було — тому в '
                           'стовпчику «сусідні» нулі.')
        ch.append(f'''<section class="rozdil"><h2>Скарги 1551 за 12 місяців</h2>
<p class="rozdil__pidpys">{e(z_velykoi(period))}. Це звернення людей до гарячої лінії міста, а не перевірені факти. Масові відключення
світла чи тепла торкаються багатьох будинків одразу. {pidpys_sus}</p>
<div class="kartka por"><div class="por__shapka" aria-hidden="true"><span>Тема</span><span>цей будинок</span><span></span><span>сусідні</span><span></span></div>
{"".join(ryady)}
<table class="prykhovano"><caption>Звернення 1551 за темами</caption><thead><tr><th>Тема</th><th>Цей будинок</th><th>Сусідні (зазвичай)</th></tr></thead><tbody>
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

    # ZVIT-165, п. 7: без другого опису тієї самої довідки; одна головна кнопка. Гасло лінії над блоком лишається (MV-106).
    ch.append(f'''<section class="rozdil">{haslo_budynku()}<h2>Довідка про будинок</h2>
{urivok_dovidky(b, bud.r_susidy)}
{knopky_dovidky(b['url'], 'budynok', b['adresa'], odna=True)}
<p class="rozdil__pidpys">Повний звіт «перед купівлею» — ще й {podii_zvitu(period_podii)}, рік за роком, що повторюється на вулиці
й поруч, порівняння зі схожими будинками й карта будинку та вулиці.</p>
<p class="prymitka">{prymitka_oplaty('Кнопка відкриє сторінку, де можна залишити пошту.')}<a href="/miy-budynok/">Що входить і підписка</a>.</p></section>''')

    if susidni:
        ch.append('<section class="rozdil"><h2>Інші будинки вулиці</h2><ul class="spysok-vulyts spysok-bud">' + ''.join(
            f'<li><a href="{x["url"]}">{e(x["nomer"])}</a></li>' for x in susidni) + '</ul></section>')
    if poruch:      # ZAVDANNYA-154: сусідні будинки інших вулиць — лише адреса й посилання, без чисел і оцінок
        ch.append(f'<section class="rozdil"><h2>Будинки поруч</h2><p class="rozdil__pidpys">Найближчі будинки інших вулиць '
                  f'у радіусі {R_PORUCH_M}{NBSP}м, що мають свою сторінку.</p><ul class="spysok-tekst">' + ''.join(
                      f'<li><a href="{x["url"]}">{e(x["adresa"])}</a></li>' for x in poruch) + '</ul></section>')
    posylannia = []
    # ZVIT-165, п. 6: «де це» — будинок на карті Києва (та сама безкоштовна карта сотами, без адрес подій)
    posylannia.append(f'<a class="knopka" href="/karta/#16.5/{b["lat"]:.5f}/{b["lon"]:.5f}/0/0">Показати місце на карті</a>')
    if b['vulytsia_slug']:
        posylannia.append(f'<a class="knopka" href="/vulytsia/{b["vulytsia_slug"]}/">{e(b["vulytsia"])} — уся вулиця</a>')
    if b['rayon']:
        posylannia.append(f'<a class="knopka" href="/rayon/{Z.slug_rayonu(b["rayon"])}/">{e(b["rayon"])} район</a>')
    if posylannia:
        ch.append(f'<section class="rozdil"><h2>Де це й що поруч</h2><div class="diyi">{"".join(posylannia)}</div></section>')
    ch.append(f'<p class="prymitka">Скарги 1551 — відкриті дані міста (КМДА, data.gov.ua, CC BY), {e(period)}. Події — з рішень судів '
              f'у Єдиному державному реєстрі судових рішень, станом на {e(Z.data_slovamy(bud.versiia))}. Колір смуг показує кількість, а не оцінку будинку. '
              f'<a href="/pro-dani/">Як ми працюємо з даними</a> · <a href="/vydalyty/">Видалити або виправити подію</a>.</p>')

    place = {'@context': 'https://schema.org', '@type': 'Place', 'name': f'{b["adresa"]}, Київ',
             'url': f'{adresa_saitu}{b["url"]}',
             'address': {'@type': 'PostalAddress', 'streetAddress': b['adresa'], 'addressLocality': 'Київ', 'addressCountry': 'UA'},
             'geo': {'@type': 'GeoCoordinates', 'latitude': round(b['lat'], 5), 'longitude': round(b['lon'], 5)}}
    if b['rayon']:
        place['containedInPlace'] = {'@type': 'Place', 'name': f'{b["rayon"]} район, Київ'}
    if re.match(r'^\d{4}-\d{2}-\d{2}$', bud.versiia or ''):
        place['dateModified'] = bud.versiia           # Д-2 (ZAVDANNYA-110), як на сторінці вулиці (MV-101)
    # ZAVDANNYA-154: шаблони під запити людей — site/zaholovky.py
    title = ZH.title_budynku(b['vulytsia'], b['nomer'])
    opys = ZH.opys_budynku(b['vulytsia'], b['nomer'], rayon_t, skarhy_slovo(b['skarh']),
                           next(iter(b['skarhy'])) if b['skarh'] else None, Z.podii_slovo(b['podii_vidkr']), roky_t)
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
                    adresa_saitu: str, kolory: dict | None = None, vykhid: Path | None = None, mistsia: list | None = None) -> str:
    slug = Z.slug_rayonu(rayon)
    roky_t = Z.PERIOD_VIDKRYTYI
    vsogo = sum(podii_hrupy.values())
    budynky = bud.za_rayonom.get(rayon, []) if bud else []
    skarhy = Counter()
    for b in budynky:
        skarhy.update(b['skarhy'])
    kryhty = [('/', 'Головна'), ('/rayony/', 'Райони'), ('', f'{rayon} район')]
    ch = [kryhty_html(kryhty)]
    rech = [f'{e(Z.u_rayoni(rayon))} за {roky_t} у даних судів — {Z.podii_slovo(vsogo)} з точною адресою'
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
    vs = sorted((v for v in vulytsi if v.nedavni), key=lambda v: (Z.kliuch_abetky(v.korotka), v.slug))   # Д-6: без «0»
    ch.append(f'<section class="rozdil"><h2>Вулиці району</h2><p class="rozdil__pidpys">За абеткою; поруч — подій за {roky_t}. '
              f'<a href="/vulytsi/{slug}/">Покажчик вулиць району</a>.</p>{Z.spysok_vulyts(vs)}</section>')
    bez_vulytsi = sorted((b for b in budynky if not b['vulytsia_slug']), key=lambda b: (b['vulytsia'], kliuch_nomera(b['nomer'])))
    if bez_vulytsi:     # ZAVDANNYA-154: інакше на ці будинки не веде жодна сторінка (сироти для Google)
        ch.append('<section class="rozdil"><h2>Будинки на вулицях без окремої сторінки</h2>'
                  '<p class="rozdil__pidpys">Ці вулиці не мають своєї сторінки, а будинки на них — мають: '
                  'скарги 1551 чи події з рішень судів з адресою будинку.</p><ul class="spysok-tekst">' + ''.join(
                      f'<li><a href="{b["url"]}">{e(b["adresa"])}</a></li>' for b in bez_vulytsi) + '</ul></section>')
    if mistsia:     # ZAVDANNYA-124: публічні місця району — посилання на їхні сторінки
        import storinky_mistsia as SM
        ch.append(SM.blok_mists(mistsia, 'Публічні місця району'))
    ch.append(f'<section class="rozdil"><h2>Мій будинок</h2><p class="rozdil__pidpys">Знайдіть свою вулицю — на її сторінці є '
              f'будинки зі своєю сторінкою.</p>{knopky_dovidky("", "rayon")}</section>')
    title = ZH.title_rayonu(rayon)
    opys = ZH.opys_rayonu(rayon, Z.podii_slovo(vsogo), roky_t,
                          f'{chyslo(len(vulytsi))} {vidminok(len(vulytsi), ("вулиця", "вулиці", "вулиць"))}',
                          f'{chyslo(len(budynky))} {vidminok(len(budynky), ("будинок", "будинки", "будинків"))}' if budynky else None)
    place = {'@context': 'https://schema.org', '@type': 'Place', 'name': f'{rayon} район, Київ',
             'url': f'{adresa_saitu}/rayon/{slug}/', 'containedInPlace': {'@type': 'City', 'name': 'Київ'}}
    kartynka = None
    if kolory is not None and vykhid is not None:      # Д-2 (ZAVDANNYA-110): картинка для поширення — лише числа
        import kartynky as K
        chysla = [(chyslo(vsogo), f'{vidminok(vsogo, ("подія", "події", "подій"))} з рішень судів за {roky_t}')]
        if skarhy:
            n = sum(skarhy.values())
            chysla.append((chyslo(n), f'{vidminok(n, ("звернення", "звернення", "звернень"))} до 1551 за 12 місяців'))
        Z.zapysaty_bajty(vykhid / 'rayon' / slug / 'kartynka.png', K.kartynka('Київ · район', f'{rayon} район', chysla, kolory))
        kartynka = (f'/rayon/{slug}/kartynka.png', f'{rayon} район: ' + ', '.join(f'{a} {p}' for a, p in chysla))
    return Z.storinka(shlyakh=f'/rayon/{slug}/', title=title, opys=opys, tilo='\n'.join(ch), adresa_saitu=adresa_saitu,
                      aktyvne='rayony/', dodatkovo_head=ld_skrypt(place, kryhty_ld(kryhty, adresa_saitu)), kartynka=kartynka)


def storinka_rayoniv(rayony: list, adresa_saitu: str, bez_rayonu: list | None = None) -> str:
    kryhty = [('/', 'Головна'), ('', 'Райони')]
    tilo = (kryhty_html(kryhty) + '<section class="zaholovok"><h1>Райони Києва</h1><p>Десять районів: події з судових рішень, '
            'скарги 1551 і всі вулиці кожного району.</p></section><nav class="rayony" aria-label="Райони">'
            + ''.join(f'<a href="/rayon/{Z.slug_rayonu(r)}/">{e(r)}</a>' for r in rayony) + '</nav>')
    if bez_rayonu:      # ZAVDANNYA-154: будинки без вулиці й району зі сторінкою — інакше на них не веде жодне посилання
        tilo += ('<section class="rozdil"><h2>Будинки поза районами</h2><p class="rozdil__pidpys">Будинки, район і вулицю яких '
                 'у даних не визначено.</p><ul class="spysok-tekst">' + ''.join(
                     f'<li><a href="{b["url"]}">{e(b["adresa"])}</a></li>' for b in bez_rayonu) + '</ul></section>')
    return Z.storinka(shlyakh='/rayony/', title='Райони Києва — події з судових рішень і скарги 1551 | Моя вулиця',
                      opys='Райони Києва: події з судових рішень, скарги 1551 і вулиці кожного району.', tilo=tilo,
                      adresa_saitu=adresa_saitu, aktyvne='rayony/', dodatkovo_head=ld_skrypt(kryhty_ld(kryhty, adresa_saitu)))


# ---------------------------------------------------------------- вітрини

def vitryna(shlyakh: str, nazva: str, mitka: str, vstup: str, tilo: str, title: str, opys: str, adresa_saitu: str,
            aktyvne: str = '', kartynka: tuple | None = None, skrypty: tuple = (), css: tuple = ()) -> str:
    kryhty = [('/', 'Головна'), ('', nazva)]
    t = (kryhty_html(kryhty) + f'<section class="zaholovok"><span class="mitka">{e(mitka)}</span><h1>{e(nazva)}</h1>'
         f'<p>{vstup}</p></section>' + tilo)
    return Z.storinka(shlyakh=shlyakh, title=title, opys=opys, tilo=t, adresa_saitu=adresa_saitu, aktyvne=aktyvne or shlyakh[1:],
                      dodatkovo_head=ld_skrypt(kryhty_ld(kryhty, adresa_saitu)) + ''.join(f'<link rel="stylesheet" href="{c}">\n' for c in css),
                      kartynka=kartynka, skrypty=skrypty)


def kartka_tovaru(kl: str, pidpys: str, punkty: list, holovna: bool = False, dzherelo: str = '') -> str:
    li = ''.join(f'<li>{p}</li>' for p in punkty)
    d = f'&amp;dzherelo={dzherelo}' if dzherelo else ''
    if TSINY[kl] is None:
        # Ціна за домовленістю (MV-102): форма запиту — передзамовлення заглушки з вибором «Для компанії»; відповідає партнер.
        knopka = (f'<a class="knopka{" knopka--holovna" if holovna else ""}" '
                  f'href="/zahlushka/?shcho=kompaniya{d}#peredzamovlennya">Надіслати запит</a>')
    else:
        knopka = T.knopka_oplaty(f'/oplata/?tovar={kl}{d}', 'Замовити', holovna)
    return (f'<div class="kartka tovar{" tovar--holovnyi" if holovna else ""}"><h3>{e(TOVARY[kl])}</h3>'
            f'<p class="tovar__tsina{"" if TSINY[kl] is not None else " tovar__tsina--nema"}">{tsina(kl)}</p><p class="tovar__pidpys">{pidpys}</p><ul>{li}</ul>'
            f'{knopka}</div>')


def vitryna_miy_budynok(adresa_saitu: str, prykl: list, kartynka: tuple | None = None, period_podii: str = '') -> str:
    tovary = ''.join([
        kartka_tovaru('dovidka', 'Разово, для одного будинку', [
            'скарги 1551 за 12 місяців: теми, місяці, статуси простими словами',
            'порівняння з сусідніми будинками', 'події з рішень судів біля будинку й на вулиці — коротко',
            'прочитати за 2–3 хвилини'], True, dzherelo='miy-budynok'),
        kartka_tovaru('try', 'Три будинки — порівняти перед орендою чи купівлею', [
            'три довідки на вибір', 'дешевше, ніж три окремо'], dzherelo='miy-budynok'),
        kartka_tovaru('zvit', 'Перед купівлею житла', [
            'усе з довідки', podii_zvitu(period_podii), 'рік за роком і що повторюється на вулиці',
            'порівняння зі схожими будинками, карта будинку й вулиці'],
            dzherelo='miy-budynok'),
        kartka_tovaru('pidpyska', 'Щомісяця', [e(x) for x in T.pidpyska_daie()], dzherelo='miy-budynok'),
        kartka_tovaru('rieltor', 'Для рієлтора', ['5 довідок на місяць', 'для показів і клієнтів'], dzherelo='miy-budynok'),
    ])
    pryklady = ''.join(f'<li><a href="{b["url"]}">{e(b["adresa"])}</a></li>' for b in prykl)
    tilo = f'''<section class="rozdil"><h2>Знайдіть свій будинок</h2>
<p class="rozdil__pidpys">Введіть вулицю й номер будинку або відкрийте свою вулицю — на її сторінці є список будинків. Сторінка будинку
безкоштовна: скарги 1551 і події з рішень судів числом.</p>
<form class="poshuk" role="search" action="/vulytsi/"><label class="prykhovano" for="poshuk-vulytsi">Вулиця і номер будинку</label>
<input id="poshuk-vulytsi" type="search" autocomplete="off" placeholder="Вулиця і будинок, наприклад: Хрещатик 22">
<ul class="poshuk__spysok" id="poshuk-spysok" hidden></ul></form>
{f'<p class="prymitka">Наприклад, вулиці:</p><ul class="spysok-vulyts">{pryklady}</ul>' if pryklady else ''}</section>
<section class="rozdil"><h2>Що можна замовити</h2><div class="tovary">{tovary}</div>
<p class="prymitka">Довідка — не оцінка будинку й не порада, де жити. Скарги 1551 — звернення людей, не перевірені факти; події — те,
що дійшло до суду. {prymitka_oplaty('Кнопка відкриє сторінку, де можна залишити пошту.')}</p></section>'''
    return Z.storinka(
        shlyakh='/miy-budynok/', title='Що болить вашому будинку — довідка про будинок у Києві за 199 грн | Моя вулиця',
        opys=(f'Довідка про будинок: скарги 1551, порівняння з сусідами, події з рішень судів. {T.TSINY["dovidka"]} грн разово, '
              f'3 довідки — {T.TSINY["try"]}, повний звіт — {T.TSINY["zvit"]}.'),
        tilo=kryhty_html([('/', 'Головна'), ('', 'Мій будинок')])
        + '<section class="zaholovok"><span class="mitka">Мій будинок · для мешканців, орендарів і покупців</span>'
          f'<h1>{HASLO_BUDYNKU}</h1><p class="zaholovok__opys">{OPYS_BUDYNKU}.</p>'
          f'<p>{MESEDZH["miy-budynok"]} На що скаржаться мешканці в 1551 і які події з рішень судів були з цією адресою.</p></section>' + tilo,
        adresa_saitu=adresa_saitu, aktyvne='miy-budynok/', skrypty=('/sait/poshuk-spilne.js', '/sait/poshuk.js'), kartynka=kartynka,
        dodatkovo_head=ld_skrypt(kryhty_ld([('/', 'Головна'), ('', 'Мій будинок')], adresa_saitu)))


def vitryna_osbb(adresa_saitu: str, kartynka: tuple | None = None) -> str:
    tilo = f'''<section class="rozdil"><h2>Що отримує правління</h2><div class="tovary">
{kartka_tovaru('osbb', 'Річна оплата за будинок', [
        'щомісяця — довідка про ваш будинок: звернення 1551 за місяць і за рік, теми й статуси',
        'порівняння з сусідніми будинками',
        'оплата карткою; рахунок для юридичної особи — на запит, виставляє партнер проєкту'], True, dzherelo='osbb')}
<div class="kartka tovar"><h3>Навіщо</h3><ul><li>бачити, що турбує мешканців, ще до зборів</li>
<li>мати числа для розмови з управителем і районною адміністрацією</li><li>звітувати мешканцям</li></ul></div>
</div></section>
<section class="rozdil"><h2>Безкоштовно вже зараз</h2><p class="rozdil__pidpys">Сторінка будинку з темами звернень 1551 за 12 місяців —
знайдіть свою вулицю в <a href="/vulytsi/">покажчику</a>.</p></section>'''
    return vitryna('/osbb/', 'Для ОСББ', 'Для правлінь ОСББ і управителів',
                   MESEDZH['osbb'] + ' Щомісячна довідка: звернення мешканців до 1551 і порівняння з сусідніми будинками.',
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
                   MESEDZH['sudova-praktyka'] + ' Кількість справ, результати й строки — з тієї самої бази рішень, що й карта.',
                   tilo, 'Судова практика: суди Києва за статтями — скоро | Моя вулиця',
                   'Судова практика за статтями й судами Києва: скільки справ, результати, строки. Розділ готуємо — залиште пошту.',
                   adresa_saitu, kartynka=kartynka)


# «Для бізнесу» (ZAVDANNYA-157; MV-3, MV-92, MV-102): що в копії бази — ті самі поля, що в dani-edrsr/src/kopiia_biznesu.py
# (POLIA), людськими словами; у прикладі рядка — лише формат, без жодної справжньої чи вигаданої події.
POLIA_BIZNES = [
    ('data, hodyna', 'дата й година події (немає дати події — дата рішення з позначкою)'),
    ('hrupa, vyd, stattia', 'група події, як на карті, вид і стаття кодексу'),
    ('opys', 'опис події з рішення суду, без імен суддів, поліцейських і захисників'),
    ('adresa, tochnist', 'будинок, перехрестя чи назване місце'),
    ('shyrota, dovhota, sota', 'координати точки; без точного місця — клітинка ≈ 500 м'),
    ('sud, data_rishennia, nomer_spravy', 'суд, дата рішення, номер справи'),
    ('posylannia', 'посилання на рішення в державному реєстрі — оригінал біля кожної події'),
    ('chutlyva, domashnie', 'позначки: домашнє насильство, статеві злочини, справи щодо дітей — як оприлюднив суд'),
    ('problemy', 'окрема таблиця: місця, де однотипні події повторюються, і які події туди входять'),
    ('skarhy_1551', 'окрема таблиця: звернення до 1551 по будинках — числом за темами, без тексту заявника'),
]
PRYKLAD_BIZNES = [('data', '2025-03-14'), ('hodyna', '22'), ('hrupa', HRUPY_PODII['vod']), ('stattia', 'ст.130 КУпАП'),
                  ('opys', '‹опис події з рішення›'), ('adresa', '‹вулиця, номер будинку›'), ('tochnist', 'будинок'),
                  ('shyrota', '50.4…'), ('dovhota', '30.5…'), ('sud', '‹районний суд міста Києва›'),
                  ('posylannia', 'https://reyestr.court.gov.ua/…')]
META_BIZNES = [('nerukhomist', 'нерухомість (забудова, агенція, оцінка)'), ('strakhuvannia', 'страхування чи банк'),
               ('doslidzhennia', 'дослідження чи медіа'), ('mista', 'громада, міська служба'), ('inshe', 'інше')]


def vitryna_biznes(adresa_saitu: str, kartynka: tuple | None = None, period_podii: str = '', chysla: list | None = None) -> str:
    kyiv = f'Київ{", " + period_podii if period_podii else ""}'
    ch = ''.join(f'<div class="kartka chyslo-blok"><b class="chyslo-velyke">{e(n)}</b><span>{e(t)}</span></div>' for n, t in (chysla or []))
    polia = ''.join(f'<tr><th scope="row"><code>{e(k)}</code></th><td>{e(v)}</td></tr>' for k, v in POLIA_BIZNES)
    pryklad = ''.join(f'<tr><th scope="row"><code>{e(k)}</code></th><td>{e(v)}</td></tr>' for k, v in PRYKLAD_BIZNES)
    meta = ''.join(f'<option value="{k}">{e(v)}</option>' for k, v in META_BIZNES)
    tilo = f'''{f'<section class="rozdil"><div class="chysla">{ch}</div></section>' if ch else ''}
<section class="rozdil"><h2>Що в базі</h2><div class="kartka"><ul class="spysok-tekst">
<li>Події з рішень судів з адресою й точкою на карті ({e(kyiv)}): що сталося, коли, де, за якою статтею — і посилання на оригінал рішення.</li>
<li>Місця, де однотипні події повторюються, — окремою таблицею.</li>
<li>Звернення до 1551 по будинках — числом за темами.</li>
<li>Оновлення щомісяця: нова копія з усіма змінами, події, видалені за зверненнями людей, з неї прибрано.</li>
</ul></div>
<p class="prymitka">Подія — окремий випадок, установлений судом. Концентрація подій — статистика, а не оцінка місця й не прогноз.
Дані показують лише те, що дійшло до суду.</p></section>
<section class="rozdil"><h2>Поля</h2><div class="tablytsia-obhortka"><table class="biznes-tablytsia"><thead><tr><th scope="col">Поле</th>
<th scope="col">Що в ньому</th></tr></thead><tbody>{polia}</tbody></table></div>
<p class="prymitka">Повний опис полів — у файлі з описом, що йде з кожною копією.</p></section>
<section class="rozdil"><h2>Як виглядає рядок</h2><div class="tablytsia-obhortka"><table class="biznes-tablytsia biznes-tablytsia--pryklad">
<caption>Лише формат: у кутових дужках — що стоїть у справжньому рядку</caption><tbody>{pryklad}</tbody></table></div></section>
<section class="rozdil"><h2>Як ви отримуєте базу</h2><ol class="spysok-tekst">
<li>Залишаєте запит нижче — партнер проєкту відповідає протягом 2 робочих днів.</li>
<li>Підписуєте договір користування на місяць або рік; {tsina('biznes')} — залежить від строку й території.</li>
<li>Щомісяця отримуєте особисте посилання на свіжу копію: база SQLite і таблиці CSV (відкриваються в Excel і Google Таблицях).
Посилання діє кілька днів, потім — нове з новою копією.</li>
<li>Доступ для програм за адресою — пізніше, за запитом.</li></ol></section>
<section class="rozdil"><h2>Умови користування</h2><div class="kartka"><ul class="spysok-tekst">
<li>Користування, а не продаж: база лише для вашої компанії, без перепродажу й передачі іншим.</li>
<li>Без спроб упізнати людей і відновити те, що суд приховав.</li>
<li>Видалення за зверненням людей діє і для вас: такі події зникають з наступної копії, попередню треба замінити.</li>
<li>Посилання на оригінал рішення лишається біля кожної події, коли ви показуєте дані своїм клієнтам.</li>
</ul></div><p class="prymitka">Повністю — у договорі користування. Загальні правила сайту — в <a href="/zahlushka/oferta.html">оферті</a>.
Договори й рахунки оформлює партнер проєкту.</p></section>
<section class="rozdil"><h2>Для кого</h2><div class="kartka"><ul class="spysok-tekst"><li>забудовники, агенції й оцінювачі нерухомості</li>
<li>страхові компанії й банки</li><li>дослідники, медіа, громади</li></ul></div></section>
<section class="rozdil" id="zapyt"><h2>Запит на доступ</h2>
<form class="biznes-forma" id="biznes-forma" novalidate>
<label>Компанія<input name="kompaniia" required maxlength="160" autocomplete="organization"></label>
<label>Контакт — пошта чи телефон<input name="kontakt" required maxlength="160" autocomplete="email"></label>
<label>Для чого<select name="meta" required><option value="">Оберіть</option>{meta}</select></label>
<label>Яка територія<input name="terytoriia" maxlength="200" placeholder="Київ, район, кілька вулиць"></label>
<fieldset><legend>На який строк</legend>
<label class="vybir-riadok"><input type="radio" name="strok" value="misiats"> місяць</label>
<label class="vybir-riadok"><input type="radio" name="strok" value="rik"> рік</label>
<label class="vybir-riadok"><input type="radio" name="strok" value="ne_znaiu" checked> ще не знаю</label></fieldset>
<label>Що ще важливо<textarea name="komentar" maxlength="2000" rows="4"></textarea></label>
<label class="vybir-riadok"><input type="checkbox" name="zghoda" required> Погоджуюся з <a href="/zahlushka/polityka.html">політикою конфіденційності</a></label>
<button class="knopka knopka--holovna" type="submit">Надіслати запит</button>
<p class="biznes-forma__stan" role="status" aria-live="polite"></p>
</form>
<p class="prymitka">Самі ми нікому не пишемо — лише відповідаємо на запити. Не виходить надіслати — <a href="/zahlushka/?shcho=kompaniya&amp;dzherelo=biznes#peredzamovlennya">запасна форма</a>.</p></section>'''
    return vitryna('/biznes/', 'Для бізнесу', 'Для компаній',
                   MESEDZH['biznes'] + ' База подій із судових рішень і скарг 1551 — у користування на місяць або рік за договором. '
                   'Свіжа копія щомісяця за особистим посиланням. Ціна — за домовленістю.',
                   tilo, 'Дані для бізнесу: події з судових рішень і скарги 1551 Києва | Моя вулиця',
                   'Дані для компаній: події з судових рішень з адресами, скарги 1551 по будинках. Користування на місяць або рік за договором.',
                   adresa_saitu, kartynka=kartynka, skrypty=('/sait/biznes.js',), css=('/sait/biznes.css',))


def storinka_oplaty(adresa_saitu: str) -> str:
    tovary = ''.join(f'<li><b>{e(TOVARY[k])}</b> — {tsina(k)}</li>' for k in TOVARY)
    # Т-3 (ZAVDANNYA-110): що й для якого будинку обрали — читає sait/oplata.js і передає у форму передзамовлення.
    nazvy = {k: f'{TOVARY[k]} — {tsina(k)}' for k in TOVARY}
    tilo = f'''{kryhty_html([('/', 'Головна'), ('', 'Оплата')])}
<section class="zaholovok"><span class="mitka">Скоро</span><h1>Оплата скоро</h1>
<p>Ми ще не приймаємо оплату. Залиште пошту — напишемо один раз, коли довідку можна буде замовити.</p>
<p class="kartka vybir" id="vybir" data-tovary="{e(json.dumps(nazvy, ensure_ascii=False))}" hidden></p></section>
<section class="rozdil"><div class="diyi">
<a class="knopka knopka--holovna" id="oplata-poshta" href="/zahlushka/?dzherelo=oplata#peredzamovlennya">Залишити пошту</a>
<a class="knopka" href="/miy-budynok/">Що входить у довідку</a></div>
<p class="prymitka">Пошту залишаєте у формі передзамовлення; її зберігають за <a href="/zahlushka/polityka.html">політикою конфіденційності</a>
і пишуть лише про запуск. Обраний товар і будинок збережемо разом із поштою.</p></section>
<section class="rozdil"><h2>Ціни</h2><div class="kartka"><ul class="spysok-tekst">{tovary}</ul></div></section>'''
    return Z.storinka(shlyakh='/oplata/', title='Оплата скоро | Моя вулиця', opys='Оплата ще не працює — залиште пошту.',
                      tilo=tilo, adresa_saitu=adresa_saitu, indeksuvaty=False, skrypty=('/sait/oplata.js',))


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
<li>Прибрана подія зникає з карти, довідок і звітів у той самий строк і більше не повертається. Уже надіслані довідки — знімок
на свою дату, їх ми не змінюємо.</li>
</ol></div></section>
<section class="rozdil"><h2>Що ми можемо виправити</h2><div class="kartka"><ul class="spysok-tekst">
<li>Неправильна адреса чи місце події.</li><li>Опис, який каже більше, ніж рішення суду.</li>
<li>Подія, яку суд не підтвердив (виправдання, скасування рішення).</li>
<li>Подія, що дозволяє впізнати вас, хоча суд приховав ці дані.</li>
<li>Подія, що сталася понад 10 років тому: номер будинку прибираємо за першим проханням, без пояснень.</li></ul></div>
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
у рішенні, з місцем, де він стався. Кілька рішень в одній справі — одна подія. Дані станом на {e(Z.data_slovamy(versiia))}.</li>
<li><b>Скарги 1551</b> — відкриті дані гарячої лінії міста (КМДА, data.gov.ua, ліцензія CC BY){f", {e(period)}" if period else ""}.
Персональних даних у наборі немає; ми показуємо лише теми й кількість.</li>
<li><b>Адреси й карта</b> — OpenStreetMap (ODbL), підкладка — OpenFreeMap.</li></ul></div></section>
<section class="rozdil"><h2>Що ці числа означають</h2><div class="kartka"><ul class="spysok-tekst">
<li>Це лише те, що дійшло до суду або до 1551, а не всі події.</li>
<li>Колір і числа показують кількість у даних, а не те, наскільки місце «погане». Ми не ставимо місцям оцінок, не прогнозуємо й не
стверджуємо причин.</li>
<li>Скарга 1551 — звернення людини, а не перевірений факт.</li>
<li>Подію, яку суд не підтвердив (виправдання, скасування), ми не показуємо.</li></ul></div></section>
<section class="rozdil" id="zakonna-syla"><h2>Рішення, що ще не набрали законної сили</h2><div class="kartka">
<p>Частина подій узята з рішень, які ще не набрали законної сили: не минув строк на оскарження або подано апеляцію. Доки
рішення не набрало законної сили, людина вважається невинуватою, а вищий суд може рішення змінити чи скасувати. Біля
кожної події ми цього окремо не позначаємо — пояснення одне для всього сайту. Якщо рішення скасують або людину виправдають,
подію приберемо з найближчим оновленням даних; побачили таке раніше — <a href="/vydalyty/">напишіть нам</a>.</p></div></section>
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
                vykhid: Path, adresa_saitu: str, pachky=None, vulyts: int = 0, mistsia_rayonu: dict | None = None) -> list:
    """Пише сторінки будинків, районів, вітрин і довідкові; повертає адреси для sitemap.
    `pachky` (site/khostynh.py, варіант workers) — сторінки й картинки будинків ідуть у пачки, а не окремими файлами."""
    adresy = []
    kolory = Z.kolory_tem()['svitla']

    poruch = budynky_poruch(bud.spysok) if bud else {}

    def budynok(b, vikno):
        html_ = storinka_budynku(b, bud, adresa_saitu, vikno, D.period_podii(dn), poruch.get(b['slug']))
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
                   storinka_rayonu(dn, r, za_rayonom[r], bud, pr.get(r, Counter()), adresa_saitu, kolory, vykhid,
                                   (mistsia_rayonu or {}).get(r)))
        adresy.append(f'/rayon/{Z.slug_rayonu(r)}/')
    bez_rayonu = sorted((b for b in bud.spysok if not b['vulytsia_slug'] and b['rayon'] not in rayony),
                        key=lambda b: (b['vulytsia'], kliuch_nomera(b['nomer']))) if bud else []
    Z.zapysaty(vykhid / 'rayony' / 'index.html', storinka_rayoniv(rayony, adresa_saitu, bez_rayonu))
    adresy.append('/rayony/')
    prykl = []
    if bud:
        # Т-7 (ZAVDANNYA-110, MV-25): приклади — вулиці зі сторінками будинків, без номерів житлових будинків; «середні» за
        # кількістю будинків, з різних районів (не добірка тих, де найбільше).
        vulytsi_b = sorted(((len(sp), sl) for sl, sp in bud.za_vulytseyu.items() if sl in dn.vulytsi and len(sp) >= 2))
        vulytsi_b = vulytsi_b[len(vulytsi_b) // 2:] + vulytsi_b[:len(vulytsi_b) // 2]
        bachyly = set()
        for _n, sl in vulytsi_b:
            v = dn.vulytsi[sl]
            r = v.rayony.most_common(1)[0][0] if v.rayony else ''
            if r not in bachyly:
                bachyly.add(r)
                prykl.append({'url': f'/vulytsia/{sl}/', 'adresa': v.nazva})
            if len(prykl) == 3:
                break
        prykl.sort(key=lambda b: b['url'])
    import kartynky as K
    kv = {}
    cv = chysla_vitryn(dn, bud, vulyts)
    for shl, (mitka, nazva, chysla) in cv.items():
        Z.zapysaty_bajty(vykhid / shl / 'kartynka.png', K.kartynka(mitka, nazva, chysla, kolory))
        kv[shl] = (f'/{shl}/kartynka.png', f'{nazva}: ' + ', '.join(f'{a} {p}' for a, p in chysla))
    for shl, html_ in (('miy-budynok', vitryna_miy_budynok(adresa_saitu, prykl, kv['miy-budynok'], D.period_podii(dn))),
                       ('osbb', vitryna_osbb(adresa_saitu, kv['osbb'])),
                       ('sudova-praktyka', vitryna_sudova(adresa_saitu, kv['sudova-praktyka'])),
                       ('biznes', vitryna_biznes(adresa_saitu, kv['biznes'], D.period_podii(dn), cv['biznes'][2])),
                       ('vydalyty', storinka_vydalyty(adresa_saitu)),
                       ('pro-dani', storinka_pro_dani(adresa_saitu, dn.versiia, period_1551(bud.misiatsi) if bud else ''))):
        Z.zapysaty(vykhid / shl / 'index.html', html_)
        adresy.append(f'/{shl}/')
    Z.zapysaty(vykhid / 'oplata' / 'index.html', storinka_oplaty(adresa_saitu))
    return adresy
