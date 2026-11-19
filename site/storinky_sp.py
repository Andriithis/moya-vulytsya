"""«Судова практика» — розділ сайту (ZAVDANNYA-111; MV-121, MV-122; дослідження — `docs/SUDOVA-PRAKTYKA.md`).

Збирач сайту (`zibraty_sait.py --sudova-praktyka <sudova-praktyka.json>`) викликає звідси `zibraty`. Дані — зведення з
приватного `dani-edrsr` (`src/sudova_praktyka.py sait`): **лише числа** — справи за статтею × судом × роком × частиною ×
результатом × поєднанням покарань, і строк «від події до рішення» днями. Справ, текстів, імен немає й бути не може.

Сторінки:
  /sudova-praktyka/                       розділ: статті КУпАП і КК, ціни
  /sudova-praktyka/<kupap|kk>/<номер>/    безкоштовно (MV-122, п. 1): частки результатів і покарань по всьому Києву за
                                          останні 3 роки, поєднання покарань, строк (де точний), роки, питання-відповіді;
                                          по кожному суду й фільтри — за замком: «довідка 199» і «юристу 490/міс» (оплата —
                                          заглушка /oplata/, як на інших вітринах)
Правила:
  * без імен суддів (S-Д.5 dani-edrsr) і без порівняння судів «хто м'якший»: таблиця судів — лише в платному;
  * показуємо лише поля з точністю ≥ 95 % (MV-67): строк — лише для статей зі списку `stroky` у даних;
  * частка на менш ніж MIN_N справах — «замало справ»; сторінка з < 100 справ — noindex;
  * жодних прогнозів і порад (AGENTS.md, розд. 4): «у N % справ суд призначив…», а не «вам призначать».
"""
from __future__ import annotations

import json
import statistics
from collections import Counter
from pathlib import Path

import tsiny as T
import zibraty_sait as Z
from storinky_mv100 import kryhty_html, kryhty_ld, ld_skrypt

e, chyslo, NBSP = Z.e, Z.chyslo, Z.NBSP

SLUG = {'КУпАП': 'kupap', 'КК': 'kk'}
NAZVA_KODEKSU = {'КУпАП': 'Адміністративні правопорушення (КУпАП)', 'КК': 'Кримінальні справи (КК)'}
ROKY_VIDKRYTI = ('2024', '2025', '2026')      # безкоштовно — останні 3 роки (як MV-32 для карти)
MIN_N = 20                                     # менше справ — частку не показуємо
MIN_INDEKS = 100                               # менше справ за 3 роки — сторінка не для пошуку Google
SKHOZHI = {'130': ['124', '126', '122-4'], '124': ['122-4', '130', '286'], '122-4': ['124', '130'], '126': ['130', '124'],
           '173-2': ['173'], '173': ['173-2'], '185': ['186', '190'], '186': ['185', '190'], '190': ['185', '186'],
           '286': ['124', '130'], '309': ['185']}
# додаткові покарання з поєднань (dani-edrsr: sudova_praktyka.DOD_KOROTKO)
DODATKOVI = ('позбавлення права керування', 'позбавлення права обіймати посади', 'конфіскація майна',
             'конфіскація чи вилучення транспорту')


def vids(x: float) -> str:
    if 0.995 <= x < 1:
        return f'>99{NBSP}%'           # не писати «100 %», коли є винятки
    return f'{x * 100:.0f}{NBSP}%' if x >= 0.01 or x == 0 else f'<1{NBSP}%'


def sprav(n: int) -> str:
    return f'{chyslo(n)} {Z.vidminok(n, ("справа", "справи", "справ"))}'


def strok_slovamy(d: int | None) -> str:
    if d is None:
        return '—'
    if d < 60:
        return f'{d}{NBSP}{Z.vidminok(d, ("день", "дні", "днів"))}'
    return f'{d / 30.44:.1f}'.replace('.', ',') + f'{NBSP}міс.'


def mediana(dni: Counter) -> int | None:
    n = sum(dni.values())
    if not n:
        return None
    vse = []
    for d, k in sorted(dni.items()):
        vse += [d] * k
    return round(statistics.median(vse))


class Stattia:
    """Одна стаття: рядки зведення [суд, рік, частина, категорія, поєднання, справ, {днів: справ}]."""

    def __init__(self, s: dict, stroky: set):
        self.kodeks, self.nomer, self.nazva = s['kodeks'], s['nomer'], s['nazva']
        self.kat, self.pokarano = s['kat'], set(s['pokarano'])
        self.ryadky = s['ryadky']
        self.kliuch = f'ст.{self.nomer} {self.kodeks}'
        self.stroky = self.kliuch in stroky
        self.slug = f'/sudova-praktyka/{SLUG[self.kodeks]}/{self.nomer}/'
        self.st = f'ст.{NBSP}{self.nomer} {self.kodeks}'

    def pidsumok(self, roky=ROKY_VIDKRYTI) -> dict:
        kat, pr, dni, n, poroku = Counter(), Counter(), Counter(), 0, Counter()
        for sud, rik, ch, k, p, k_n, d in self.ryadky:
            poroku[rik] += k_n
            if roky and rik not in roky:
                continue
            n += k_n
            kat[k] += k_n
            if p:
                pr[p] += k_n
            for dd, kk in d.items():
                dni[int(dd)] += kk
        # кожен вид покарання — основним чи разом з основним (MV-122): «штраф і позбавлення права керування» — в обох
        vydy = Counter()
        for k, v in kat.items():
            if k in self.pokarano:
                vydy[k] += v
        for p, v in pr.items():
            for d in DODATKOVI:
                if f' і {d}' in p:
                    vydy[d] += v
        pokarano = sum(v for k, v in kat.items() if k in self.pokarano)
        return dict(n=n, kat=kat, poiednannia=pr, vydy=vydy, pokarano=pokarano,
                    dni=mediana(dni) if self.stroky else None, dni_n=sum(dni.values()), poroku=poroku)

    @property
    def sudy(self) -> list:
        return sorted({r[0] for r in self.ryadky}, key=Z.kliuch_abetky)

    @property
    def chastyny(self) -> list:
        return sorted({r[2] for r in self.ryadky if r[2]}, key=lambda x: int(x) if x.isdigit() else 99)


# ---------------------------------------------------------------- блоки

def smuhy(ryady: list) -> str:
    """[(назва, справ, частка)] — смугами (ширина — data-shyr, ставить sp.js; CSP без style)."""
    out = []
    for nazva, v, x in ryady:
        out.append(f'<div class="sp-ryad"><span class="sp-ryad__nazva">{e(nazva)}</span>'
                   f'<span class="sp-smuha"><i data-shyr="{max(0.5, round(x * 100, 1))}"></i></span>'
                   f'<b>{vids(x)}</b><small>{chyslo(v)}</small></div>')
    return '<div class="sp-smuhy">' + ''.join(out) + '</div>'


def roky_html(st: Stattia, poroku: Counter, roky_vid: str) -> str:
    roky = sorted(r for r in poroku if r >= roky_vid)
    if not roky:
        return ''
    maks = max(poroku[r] for r in roky) or 1
    stovp = ''.join(f'<div class="rik"><span class="rik__chyslo">{chyslo(poroku[r])}</span>'
                    f'<span class="rik__stovpchyk" data-vys="{max(2, round(poroku[r] / maks * 140))}"></span><span>{r}</span></div>'
                    for r in roky)
    return (f'<div class="kartka"><div class="roky roky--usi sp-roky" aria-hidden="true">{stovp}</div>'
            f'<table class="prykhovano"><caption>Справи за {e(st.st)} за роками</caption><tbody>'
            + ''.join(f'<tr><th scope="row">{r}</th><td>{poroku[r]}</td></tr>' for r in roky) + '</tbody></table></div>')


def knopky_kupity(st: Stattia) -> str:
    d = f'sp-{SLUG[st.kodeks]}-{st.nomer}'
    return ('<div class="diyi">'
            + T.knopka_oplaty(f'/oplata/?tovar=spdovidka&amp;dzherelo={d}', f'Довідка по моєму суду — {T.tsina("spdovidka")}', True)
            + T.knopka_oplaty(f'/oplata/?tovar=spyurist&amp;dzherelo={d}', f'Юристу: усі суди й фільтри — {T.tsina("spyurist")}')
            + '</div>')


def zamok_sudiv(st: Stattia) -> str:
    """Платна частина за замком: назви судів (вони — і ключові слова), фільтри без даних, кнопки. Чисел по судах тут
    немає — їх не можна дістати з коду сторінки."""
    stovptsi = ['Справ', 'Покарано', 'Закрито'] + (['Строк'] if st.stroky else [])
    shapka = '<th scope="col">Суд</th>' + ''.join(f'<th scope="col">{k}</th>' for k in stovptsi)
    ryady = ''.join(f'<tr><th scope="row">{e(s)}</th>' + ''.join(
        f'<td class="sp-zamk">{Z.ZAMOK_SVG}</td>' for _ in stovptsi) + '</tr>' for s in st.sudy)
    ch = ', '.join(f'ч.{NBSP}{c}' for c in st.chastyny[:6]) or '—'
    filtry = ''.join(f'<label>{n}<select disabled><option>{v}</option></select></label>'
                     for n, v in (('З року', 'усі'), ('До року', 'усі'), ('Частина статті', 'усі частини'), ('Суд', 'усі суди')))
    return f'''<section class="rozdil" id="po-sudakh"><h2>По кожному суду Києва</h2>
<p class="rozdil__pidpys">Таблиця по {len(st.sudy)} районних судах, частини статті ({ch}), кожен рік і фільтри — у платній частині.
Імен суддів немає. Суди між собою не оцінюємо: різні суди отримують різні справи.</p>
<div class="sp-filtry sp-filtry--zamk" aria-label="Фільтри платної частини">{filtry}</div>
<div class="sp-tablytsia-ramka"><table class="sp-tablytsia sp-tablytsia--zamk"><thead><tr>{shapka}</tr></thead><tbody>{ryady}</tbody></table></div>
{knopky_kupity(st)}
<p class="prymitka">Довідка — разово: ваш суд і частина статті, частки результатів і покарань за 3 роки, строк. Підписка юристу —
усі статті й суди Києва, частини, роки, фільтри, вивантаження таблиць. Оплата ще не працює: кнопка відкриє сторінку, де можна
залишити пошту.</p></section>'''


def faq_statti(st: Stattia, p: dict, period: str, korotko: str) -> list:
    faq = [(f'Чим найчастіше закінчуються справи за {st.st} у Києві?', korotko)]
    pr = p['vydy'].get('позбавлення права керування', 0)
    if pr and p['n'] >= MIN_N:
        z_shtrafom = sum(v for k, v in p['poiednannia'].items() if k.startswith('штраф і позбавлення права керування'))
        faq.append((f'Чи позбавляють права керування за {st.st}?',
                    f'У {vids(pr / p["n"])} справ за {period} суд призначив позбавлення права керування'
                    + (f', з них разом зі штрафом — {sprav(z_shtrafom)}.' if z_shtrafom else '.')))
    if p['dni'] is not None:
        faq.append((f'Скільки часу минає від події до рішення суду за {st.st}?',
                    f'Половина справ за {period} вирішена протягом {strok_slovamy(p["dni"])} від дня події ('
                    f'{sprav(p["dni_n"])} з датою події в тексті). Дати надходження справи до суду в рішеннях майже немає, тож строк '
                    'розгляду в самому суді ми не рахуємо.'))
    faq += [('Чи можна за цими цифрами передбачити рішення в моїй справі?',
             'Ні. Це частки минулих рішень у реєстрі. Кожна справа залежить від доказів і обставин; ми не прогнозуємо й не радимо.'),
            ('Звідки дані?', 'Рішення районних судів Києва з Єдиного державного реєстру судових рішень. Статтю, результат і '
             'покарання читає програма; точність перевірено на вибірці рішень.')]
    return faq


def storinka_statti(st: Stattia, vsi: dict, dani: dict, adresa_saitu: str) -> str:
    p = st.pidsumok()
    period = f'{ROKY_VIDKRYTI[0]}–{ROKY_VIDKRYTI[-1]}'
    malo = p['n'] < MIN_N
    holovne = sorted(p['kat'].items(), key=lambda x: -x[1])[:2]
    korotko = f'У районних судах Києва за {period} у наших даних {sprav(p["n"])} за {st.st} у першій інстанції.'
    if not malo and holovne:
        korotko += f' Найчастіше — {holovne[0][0]} ({vids(holovne[0][1] / p["n"])})'
        top_pr = p['poiednannia'].most_common(1)
        if top_pr and top_pr[0][1] / p['n'] >= .1:
            korotko += f'; {top_pr[0][0]} — у {vids(top_pr[0][1] / p["n"])} справ.'
        elif len(holovne) > 1:
            korotko += f', далі — {holovne[1][0]} ({vids(holovne[1][1] / p["n"])}).'
        else:
            korotko += '.'
    kryhty = [('/', 'Головна'), ('/sudova-praktyka/', 'Судова практика'), ('', f'Стаття {st.nomer} {st.kodeks}')]
    ch = [kryhty_html(kryhty), f'''<section class="zaholovok">
<span class="mitka">Судова практика · Київ · {period}</span>
<h1>Стаття {e(st.nomer)} {e(st.kodeks)} — як вирішують справи суди Києва</h1>
<p>{e(st.nazva)}. {e(korotko)}</p>
</section>''']
    chysla = [(chyslo(p['n']), f'справ за {period}')]
    if not malo:
        chysla.append((vids(p['pokarano'] / p['n']), 'закінчились стягненням' if st.kodeks == 'КУпАП'
                       else 'закінчились обвинувальним вироком'))
    if p['dni'] is not None and p['dni_n'] >= MIN_N:
        chysla.append((strok_slovamy(p['dni']), 'за стільки від події вирішено половину справ'))
    chysla.append((str(len(st.sudy)), 'районних судів Києва'))
    ch.append('<section class="chysla" aria-label="Коротко">' + ''.join(
        f'<div class="kartka chyslo-blok"><b class="chyslo">{a}</b><span>{b}</span></div>' for a, b in chysla) + '</section>')
    if malo:
        ch.append(f'<section class="rozdil"><p class="prymitka">Справ замало (менше {MIN_N}), щоб рахувати частки.</p></section>')
    else:
        ch.append(f'''<section class="rozdil"><h2>Чим закінчуються справи</h2>
<p class="rozdil__pidpys">Кінцеве рішення суду першої інстанції в кожній справі за {period}, усі суди Києва разом. Частка — від усіх
справ з рішенням по суті. Апеляцію не враховано.{" Кримінальні справи, закриті ухвалою (примирення, давність), сюди ще не входять — частки рахуються серед вироків." if st.kodeks == "КК" else ""}</p>
{smuhy([(k, p['kat'][k], p['kat'][k] / p['n']) for k in st.kat if p['kat'].get(k)])}</section>''')
        vydy = [(k, v, v / p['n']) for k, v in sorted(p['vydy'].items(), key=lambda x: -x[1])]
        pr = [(k, v, v / p['n']) for k, v in p['poiednannia'].most_common(6) if v >= MIN_N]
        ch.append(f'''<section class="rozdil"><h2>Які покарання призначають — і разом з чим</h2>
<p class="rozdil__pidpys">Кожен вид — у скількох справах його призначено, основним чи разом з основним: справа, де суд призначив
штраф і позбавлення права керування, рахується в обох рядках.{" Для «з випробуванням» додаткове покарання відбувається, звільняють лише від основного." if st.kodeks == "КК" else ""}</p>
{smuhy(vydy)}
{('<h3 class="sp-pidzaholovok">Поєднання покарань</h3>' + smuhy(pr)) if pr else '<p class="prymitka">Поєднань покарань у цих справах майже немає: суд призначає одне покарання.</p>'}
</section>''')
    if p['dni'] is not None and p['dni_n'] >= MIN_N:
        ch.append(f'''<section class="rozdil"><h2>Скільки часу минає</h2>
<p class="rozdil__pidpys">Від дня події, описаної в рішенні, до рішення суду першої інстанції: половина справ — до
{strok_slovamy(p["dni"])}, решта — довше ({period}, {sprav(p["dni_n"])} з датою події). Дати надходження справи до суду в текстах майже
немає, тож це не строк розгляду в самому суді.</p></section>''')
    ch.append(f'''<section class="rozdil"><h2>Справи за роками</h2>
<p class="rozdil__pidpys">Скільки справ за {e(st.st)} дійшло до рішення в наших даних. Тексти рішень ще докачуються: старші роки
неповні, тож порівнювати роки між собою поки не можна.</p>
{roky_html(st, p['poroku'], dani.get('roky_vid', '2016'))}</section>''')
    ch.append(zamok_sudiv(st))
    ch.append(f'''<section class="rozdil"><h2>Як ми рахуємо</h2>
<ul class="sp-spysok">
<li>Джерело — рішення районних судів Києва з Єдиного державного реєстру судових рішень. Це лише те, що дійшло до суду
й оприлюднене в реєстрі.</li>
<li>Одна справа — один рядок: останнє рішення суду першої інстанції по суті (вирок чи постанова). Справа за кількома статтями
рахується на сторінці кожної статті, за якою суд вирішував; покарання в такій справі одне на всю справу (остаточне), тож
воно може включати й покарання за іншу статтю (наприклад, позбавлення права керування, коли поруч ст.{NBSP}130).</li>
<li>Статтю, результат і покарання читає програма з тексту рішення; точність перевірено на вибірці рішень (показуємо лише те,
що проходить 95{NBSP}%).{"" if st.stroky else " Строк від події до рішення для цієї статті не показуємо: дату події в таких рішеннях програма читає недостатньо точно (часто кілька епізодів чи період)."}</li>
<li>Це статистика минулих рішень, а не прогноз вашої справи й не юридична порада. Імен суддів ми не показуємо.</li>
</ul></section>''')
    faq = faq_statti(st, p, period, korotko)
    ch.append('<section class="rozdil"><h2>Питання й відповіді</h2>' + ''.join(
        f'<div class="kartka sp-faq"><h3>{e(q)}</h3><p>{e(a)}</p></div>' for q, a in faq) + '</section>')
    skhozhi = [vsi[n] for n in SKHOZHI.get(st.nomer, []) if n in vsi]
    if skhozhi:
        ch.append('<section class="rozdil"><h2>Схожі статті</h2><ul class="spysok-vulyts">' + ''.join(
            f'<li><a href="{s.slug}">Ст.{NBSP}{e(s.nomer)} {e(s.kodeks)} — {e(s.nazva)}</a></li>' for s in skhozhi) + '</ul></section>')
    ch.append(f'<p class="prymitka">Дані на {e(dani.get("versiia", ""))}. Тексти рішень ще докачуються.</p>')

    adresa = adresa_saitu + st.slug
    ld = [{'@context': 'https://schema.org', '@type': 'Dataset', 'name': f'Стаття {st.nomer} {st.kodeks}: рішення судів Києва',
           'description': korotko, 'spatialCoverage': {'@type': 'Place', 'name': 'Київ'},
           'temporalCoverage': f'{ROKY_VIDKRYTI[0]}/{ROKY_VIDKRYTI[-1]}', 'url': adresa,
           'variableMeasured': ['кількість справ', 'частка результатів', 'частка видів покарання']
           + (['строк від події до рішення'] if p['dni'] is not None else []),
           'isBasedOn': 'Єдиний державний реєстр судових рішень', 'creator': {'@type': 'Organization', 'name': 'Моя вулиця'}},
          {'@context': 'https://schema.org', '@type': 'FAQPage', 'mainEntity': [
              {'@type': 'Question', 'name': q, 'acceptedAnswer': {'@type': 'Answer', 'text': a}} for q, a in faq]},
          kryhty_ld(kryhty, adresa_saitu)]
    title = f'Стаття {st.nomer} {st.kodeks} у судах Києва: чим закінчуються справи — {period} | Моя вулиця'
    return Z.storinka(shlyakh=st.slug, title=title, opys=korotko, tilo='\n'.join(ch), adresa_saitu=adresa_saitu,
                      aktyvne='sudova-praktyka/', dodatkovo_head=ld_skrypt(*ld) + '<link rel="stylesheet" href="/sait/sp.css">\n',
                      indeksuvaty=p['n'] >= MIN_INDEKS, skrypty=('/sait/sp.js',))


def storinka_rozdilu(statti: list, dani: dict, adresa_saitu: str) -> str:
    period = f'{ROKY_VIDKRYTI[0]}–{ROKY_VIDKRYTI[-1]}'
    kryhty = [('/', 'Головна'), ('', 'Судова практика')]
    ch = [kryhty_html(kryhty), '''<section class="zaholovok">
<span class="mitka">Для людини зі справою й для юристів</span>
<h1>Судова практика — як суди Києва вирішують справи за статтями</h1>
<p>Для кожної статті: скільки справ, чим закінчуються, які покарання призначають і разом з чим, скільки часу минає від події до
рішення. По кожному суду й частині статті — у платній частині. Без імен суддів і без прогнозів.</p>
</section>''']
    for kodeks in ('КУпАП', 'КК'):
        ryady = []
        for st in statti:
            if st.kodeks != kodeks:
                continue
            p = st.pidsumok()
            ryady.append(f'<li><a href="{st.slug}">Ст.{NBSP}{e(st.nomer)} — {e(st.nazva)}</a><small>{sprav(p["n"])}</small></li>')
        ch.append(f'<section class="rozdil"><h2>{NAZVA_KODEKSU[kodeks]}</h2><ul class="spysok-vulyts">{"".join(ryady)}</ul></section>')
    ch.append(f'''<section class="rozdil"><h2>Що можна замовити</h2><div class="tovary">
<div class="kartka tovar tovar--holovnyi"><h3>{e(T.TOVARY["spdovidka"])}</h3><p class="tovar__tsina">{T.tsina("spdovidka")}</p>
<p class="tovar__pidpys">Разово, для людини зі справою</p><ul><li>ваш суд і частина статті</li><li>частки результатів і покарань за 3 роки</li>
<li>строк від події до рішення</li><li>простими словами, без прогнозу й порад</li></ul>
{T.knopka_oplaty('/oplata/?tovar=spdovidka&amp;dzherelo=sudova-praktyka', 'Замовити', True)}</div>
<div class="kartka tovar"><h3>{e(T.TOVARY["spyurist"])}</h3><p class="tovar__tsina">{T.tsina("spyurist")}</p>
<p class="tovar__pidpys">Для юристів і адвокатів</p><ul><li>усі статті й суди Києва</li><li>частини статті, кожен рік, фільтри</li>
<li>вивантаження таблиць</li></ul>
{T.knopka_oplaty('/oplata/?tovar=spyurist&amp;dzherelo=sudova-praktyka', 'Замовити')}</div></div>
<p class="prymitka">Числа — справи за {period} у наших даних (тексти ще докачуються). Це статистика минулих рішень, а не юридична
порада. Оплата ще не працює: кнопка відкриє сторінку, де можна залишити пошту.</p></section>''')
    return Z.storinka(shlyakh='/sudova-praktyka/', title='Судова практика Києва за статтями: чим закінчуються справи | Моя вулиця',
                      opys='Як суди Києва вирішують справи за статтями КУпАП і КК: частки результатів і покарань, строки, роки. Без імен суддів.',
                      tilo='\n'.join(ch), adresa_saitu=adresa_saitu, aktyvne='sudova-praktyka/',
                      dodatkovo_head=ld_skrypt(kryhty_ld(kryhty, adresa_saitu)) + '<link rel="stylesheet" href="/sait/sp.css">\n',
                      skrypty=('/sait/sp.js',))


def prochytaty(shliakh: Path) -> dict:
    dani = json.loads(Path(shliakh).read_text(encoding='utf-8'))
    for s in dani['statti']:
        for r in s['ryadky']:
            if len(r) != 7:
                raise SystemExit(f'{shliakh}: рядок {r[:3]} не з 7 полів — не та версія зведення dani-edrsr')
    return dani


def zibraty(shliakh: Path, vykhid: Path, adresa_saitu: str) -> list:
    """Пише розділ і сторінки статей; повертає адреси для sitemap (лише ті, що для пошуку)."""
    dani = prochytaty(shliakh)
    stroky = set(dani.get('stroky') or ())
    statti = [Stattia(s, stroky) for s in dani['statti']]
    vsi = {s.nomer: s for s in statti}
    adresy = ['/sudova-praktyka/']
    Z.zapysaty(vykhid / 'sudova-praktyka' / 'index.html', storinka_rozdilu(statti, dani, adresa_saitu))
    for st in statti:
        Z.zapysaty(vykhid / st.slug.strip('/') / 'index.html', storinka_statti(st, vsi, dani, adresa_saitu))
        if st.pidsumok()['n'] >= MIN_INDEKS:
            adresy.append(st.slug)
    return adresy
