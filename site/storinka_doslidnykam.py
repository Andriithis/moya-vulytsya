# -*- coding: utf-8 -*-
"""Сторінка «Дані для дослідників» — /doslidnykam/ (ZAVDANNYA-158; набір — `dani-edrsr/src/vidkrytyi_nabir.py`, MV-142).

Поки в `site/doslidnykam.json` немає DOI — режим «готуємо»: що буде в наборі, ліцензія, як цитувати, пошта на запуск.
З DOI — посилання на сховище (Zenodo) і розмітка `Dataset` для Google Dataset Search.
На сторінці лише опис набору: жодних чисел, адрес чи описів подій.
"""
from __future__ import annotations

import json
from pathlib import Path

import storinky_mv100 as M
import zibraty_sait as Z

NALASHTUVANNIA = Path(__file__).resolve().parent / 'doslidnykam.json'
SHLIAKH = '/doslidnykam/'
NAZVA_NABORU = 'Події з рішень судів і скарги 1551 за районами й місяцями — Київ'
AVTOR = 'Моя вулиця'
LITSENZII = {'CC BY 4.0': 'https://creativecommons.org/licenses/by/4.0/deed.uk'}
OPYS_LD = ('Лише числа: події з рішень судів першої інстанції (Єдиний державний реєстр судових рішень) і звернення на '
           'гарячу лінію 1551 за районами Києва, місяцями й сімома групами подій або темами звернень. Без адрес, координат, '
           'описів і номерів справ; числа від 1 до 4 приховано. Лише те, що дійшло до суду; не оцінка районів.')


def nalashtuvannia(shliakh: Path = NALASHTUVANNIA) -> dict:
    n = json.loads(shliakh.read_text(encoding='utf-8'))
    return {k: (n.get(k) or '').strip() for k in ('doi', 'versiia', 'period', 'litsenziia')}


def tsytata(n: dict) -> str:
    versiia = f' (версія {n["versiia"]})' if n['versiia'] else ''
    doi = f' https://doi.org/{n["doi"]}' if n['doi'] else ' Посилання (DOI) — після викладення.'
    return f'{AVTOR}. {NAZVA_NABORU}{versiia} [набір даних].{doi}'


def dataset_ld(n: dict, adresa_saitu: str) -> dict:
    """schema.org Dataset — лише коли набір уже викладено (є DOI): без файлу Google показує порожню картку"""
    lic = LITSENZII.get(n['litsenziia'] or 'CC BY 4.0', '')
    d = {'@context': 'https://schema.org', '@type': 'Dataset', 'name': NAZVA_NABORU, 'description': OPYS_LD,
         'url': adresa_saitu + SHLIAKH, 'identifier': f'https://doi.org/{n["doi"]}', 'sameAs': f'https://doi.org/{n["doi"]}',
         'license': lic, 'isAccessibleForFree': True, 'inLanguage': 'uk',
         'creator': {'@type': 'Organization', 'name': AVTOR, 'url': adresa_saitu + '/'},
         'keywords': ['судові рішення', 'ЄДРСР', '1551', 'Київ', 'райони', 'court decisions', 'Ukraine', 'open data'],
         'spatialCoverage': {'@type': 'Place', 'name': 'Київ, Україна'},
         'isBasedOn': ['https://data.gov.ua/'],
         'distribution': [{'@type': 'DataDownload', 'encodingFormat': 'text/csv', 'contentUrl': f'https://doi.org/{n["doi"]}'}]}
    if n['versiia']:
        d['version'] = n['versiia']
    return d


def storinka(adresa_saitu: str, n: dict | None = None) -> str:
    n = n or nalashtuvannia()
    gotovyi = bool(n['doi'])
    kryhty = [('/', 'Головна'), ('', 'Дані для дослідників')]
    e = Z.e
    lic = n['litsenziia'] or 'CC BY 4.0'
    lic_url = LITSENZII.get(lic, '')
    if gotovyi:
        mitka = 'Відкриті дані'
        stan = (f'<p>Версія {e(n["versiia"])}{", події за " + e(n["period"]) if n["period"] else ""}. Нова версія — з оновленням '
                f'даних; посилання нижче завжди веде на найновішу.</p>')
        diyi = (f'<a class="knopka knopka--holovna" href="https://doi.org/{e(n["doi"])}" rel="noopener">Завантажити набір</a>'
                f'<a class="knopka" href="/pro-dani/">Як ми працюємо з даними</a>')
    else:
        mitka = 'Готуємо'
        stan = ('<p>Першу версію викладемо після оновлення даних по всьому Києву. Залиште пошту — напишемо один раз, коли набір '
                'можна буде завантажити.</p>')
        diyi = ('<a class="knopka knopka--holovna" href="/zahlushka/?dzherelo=doslidnykam#peredzamovlennya">Повідомити, коли '
                'буде</a><a class="knopka" href="/pro-dani/">Як ми працюємо з даними</a>')
    tilo = f'''{M.kryhty_html(kryhty)}
<section class="zaholovok"><span class="mitka">{mitka}</span><h1>Дані для дослідників</h1>
<p>Відкритий набір чисел про події з рішень судів і звернення до 1551 за районами Києва й місяцями — безкоштовно, для
курсових, дипломних, наукових робіт і журналістики. Потрібне лише посилання на джерело.</p>
{stan}<div class="diyi">{diyi}</div></section>
<section class="rozdil"><h2>Що в наборі</h2><div class="kartka"><ul class="spysok-tekst">
<li><b>Події з рішень судів</b> — скільки подій у кожному районі за кожен місяць, окремо за сімома групами: ДТП, порушення
водіїв, крадіжки й шкода майну, насильство й грабежі, наркотики, хуліганство й порядок, алкоголь, тютюн і торгівля. Місяць —
коли сталася подія, а не коли ухвалено рішення.</li>
<li><b>Звернення до 1551</b> — скільки звернень у кожному районі за кожен місяць, за темами.</li>
<li>Таблиці у форматі CSV (UTF-8), опис полів і коротка методика, файл для цитування, контрольні суми файлів.</li>
<li>Кожна версія має постійне посилання (DOI) — на нього можна посилатися в роботі.</li></ul></div></section>
<section class="rozdil"><h2>Чого в наборі немає</h2><div class="kartka"><ul class="spysok-tekst">
<li>Адрес, точок на карті, назв вулиць, описів подій, номерів справ, статей, судів і суддів.</li>
<li>Статевих злочинів і справ щодо дітей — щоб у малих числах не вказати на потерпілих.</li>
<li>Числа від 1 до 4 приховано, підсумків немає — щоб не можна було вказати на конкретну справу чи звернення.</li></ul></div></section>
<section class="rozdil"><h2>Як читати ці числа</h2><div class="kartka"><ul class="spysok-tekst">
<li>Це лише те, що дійшло до суду й було оприлюднене, а не всі правопорушення. Число залежить і від роботи поліції та судів.</li>
<li>Звернення до 1551 — те, про що написали мешканці, а не перевірений факт.</li>
<li>Набір не оцінює райони й нічого не каже про причини. Порівнюючи райони, враховуйте населення й площу.</li>
<li>Рішення за останні місяці ще надходять до реєстру: у нових версіях числа останнього року зростатимуть.</li></ul></div></section>
<section class="rozdil"><h2>Ліцензія і як цитувати</h2><div class="kartka">
<p>Ліцензія <a href="{e(lic_url)}" rel="license noopener">{e(lic)}</a>: можна використовувати, змінювати й поширювати, зокрема в
комерційних цілях, з посиланням на джерело.</p>
<p><b>Як цитувати:</b> {e(tsytata(n))}</p>
<p class="prymitka">Джерела: Єдиний державний реєстр судових рішень (Державна судова адміністрація України); відкриті дані
гарячої лінії 1551 (КМДА); межі районів © учасники OpenStreetMap.</p></div></section>
<section class="rozdil"><h2>Потрібно детальніше?</h2><p class="rozdil__pidpys">Вибірки за статтями, вулицями чи будинками
для дослідження — за запитом і договором: <a href="/biznes/">Для бізнесу</a>. Помилка в даних —
<a href="/vydalyty/">Видалити або виправити подію</a>.</p></section>'''
    ld = [M.kryhty_ld(kryhty, adresa_saitu)] + ([dataset_ld(n, adresa_saitu)] if gotovyi else [])
    return Z.storinka(shlyakh=SHLIAKH, title='Дані для дослідників: події з рішень судів і 1551 за районами Києва | Моя вулиця',
                      opys='Відкритий набір чисел для досліджень: події з рішень судів і звернення до 1551 за районами Києва й '
                           'місяцями. CC BY 4.0, без адрес і описів.',
                      tilo=tilo, adresa_saitu=adresa_saitu, dodatkovo_head=M.ld_skrypt(*ld))


def zibraty(vykhid: Path, adresa_saitu: str, n: dict | None = None) -> list:
    Z.zapysaty(vykhid / 'doslidnykam' / 'index.html', storinka(adresa_saitu, n))
    return [SHLIAKH]
