"""Заголовки й описи сторінок для пошуку Google (ZAVDANNYA-154).

Одне місце для шаблонів: сторінки будинку, вулиці й району. Шаблон підлаштовується під довжину: Google показує
заголовок до ≈ 60–70 знаків і опис до ≈ 160 (решту обрізає трьома крапками), тому для довгих адрес — коротший хвіст.

Як шукають люди (запити, під які пишемо, — `docs/GOOGLE-154.md`, розд. 3):
  «вул. Хрещатик 22», «Хрещатик 22 Київ», «що за будинок Хрещатик 22», «вул. … 12 відгуки», «Оболонський район який».
У заголовку — адреса так, як її пишуть («вул. Хрещатик, 22»), місто й що на сторінці. Не пишемо «відгуки» (звернення до
1551 — не відгуки про будинок) і жодної оцінки безпечності (AGENTS.md, розд. 4): ні «безпечний», ні «небезпечний», ні балів.

Варіант шаблонів — `VARIANT` ('a' — порада; 'b', 'c' — для вибору центральним чатом, `docs/GOOGLE-154.md`, розд. 4).
"""
from __future__ import annotations

import re

VARIANT = 'a'
MAKS_TITLE = 65         # з запасом до 70: Google міряє пікселями, кирилиця ширша
MAKS_OPYS = 160

# Як тип вулиці пишуть у запитах і на табличках: «вул. Хрещатик», «просп. Перемоги».
SKOROCHENNIA = {'вулиця': 'вул.', 'проспект': 'просп.', 'бульвар': 'бульв.', 'провулок': 'пров.', 'площа': 'пл.',
                'набережна': 'наб.'}
TYPY_PISLYA = ('вулиця', 'проспект', 'бульвар', 'провулок', 'площа', 'набережна')


def korotka_nazva(nazva: str) -> str:
    """«вулиця Хрещатик» → «вул. Хрещатик»; «Йорданська вулиця» → «вул. Йорданська»; «Харківське шосе» — як є."""
    slova = nazva.split(' ')
    if len(slova) > 1 and slova[0] in SKOROCHENNIA:
        return ' '.join([SKOROCHENNIA[slova[0]]] + slova[1:])
    if len(slova) > 1 and slova[-1] in TYPY_PISLYA:
        return ' '.join([SKOROCHENNIA[slova[-1]]] + slova[:-1])
    return nazva


def korotka_adresa(vulytsia: str, nomer: str) -> str:
    return f'{korotka_nazva(vulytsia)}, {nomer}'


def pershyi_shcho_vlize(varianty, maks: int) -> str:
    for v in varianty:
        if len(v) <= maks:
            return v
    return varianty[-1]


def skorotyty(t: str, maks: int = MAKS_OPYS) -> str:
    if len(t) <= maks:
        return t
    return t[:maks - 1].rsplit(' ', 1)[0].rstrip(',;:—–-(') + '…'


# ---------------------------------------------------------------- будинок

def title_budynku(vulytsia: str, nomer: str, variant: str | None = None) -> str:
    a = korotka_adresa(vulytsia, nomer)
    v = variant or VARIANT
    if v == 'b':
        rjad = [f'Що за будинок {a}, Київ: скарги мешканців і суди', f'Що за будинок {a}, Київ', f'{a}, Київ']
    elif v == 'c':
        rjad = [f'{a}, Київ — скарги 1551 і рішення судів по будинку', f'{a}, Київ — скарги 1551 і суди', f'{a}, Київ']
    else:
        rjad = [f'{a}, Київ — скарги мешканців і події з рішень судів', f'{a}, Київ — скарги мешканців і суди',
                f'{a}, Київ — скарги і суди', f'{a}, Київ']
    return pershyi_shcho_vlize(rjad, MAKS_TITLE)


def opys_budynku(vulytsia: str, nomer: str, rayon_t: str, skarh: str, top: str | None, podii: str, roky_t: str,
                 variant: str | None = None) -> str:
    """skarh, podii — уже з числом і відмінком («12 звернень», «3 події»). Довгий — без хвоста, а не обрізаний посеред."""
    a = korotka_adresa(vulytsia, nomer)
    rayon_k = rayon_t.replace(' район', ' р-н')
    pro_skarhy = f'{skarh} мешканців до 1551 за рік' + (f', найчастіше — {top}' if top else '')
    v = variant or VARIANT
    pochatok = f'{a} ({rayon_k})' if v == 'b' else f'Що відомо про будинок {a} ({rayon_k})'
    rjad = [f'{pochatok}: {pro_skarhy}; {podii} з рішень судів за {roky_t}. Порівняння з сусідніми будинками.',
            f'{pochatok}: {pro_skarhy}; {podii} з рішень судів за {roky_t}.',
            f'{pochatok}: {skarh} мешканців до 1551 за рік; {podii} з рішень судів за {roky_t}.']
    return skorotyty(pershyi_shcho_vlize(rjad, MAKS_OPYS))


# ---------------------------------------------------------------- вулиця

def title_vulytsi(nazva: str, rayon: str | None, podii: str, roky_t: str, variant: str | None = None) -> str:
    k = korotka_nazva(nazva)
    v = variant or VARIANT
    if v == 'b':
        rjad = [f'{k}, Київ: {podii} з рішень судів за {roky_t}', f'{k}, Київ: {podii} з рішень судів', f'{k}, Київ']
    elif v == 'c':
        rjad = [f'{k}, Київ — що відбувається на вулиці: {podii}', f'{k}, Київ — що відбувається на вулиці', f'{k}, Київ']
    else:
        rjad = ([f'{k}, Київ ({rayon} р-н) — події з рішень судів і будинки'] if rayon else []) + [
            f'{k}, Київ — події з рішень судів і будинки', f'{k}, Київ — події з рішень судів', f'{k}, Київ']
    return pershyi_shcho_vlize(rjad, MAKS_TITLE)


def opys_vulytsi(nazva: str, rayon_t: str, podii: str, roky_t: str, budynkiv: str | None, vydy: str | None) -> str:
    pochatok = f'{korotka_nazva(nazva)} ({rayon_t}) — що відбувається на вулиці: {podii} з рішень судів за {roky_t}'
    khvist = f'; {budynkiv} зі своєю сторінкою' if budynkiv else ''
    rjad = ([f'{pochatok}, найбільше вирізняється: {vydy}{khvist}. Роки, дні й години.'] if vydy else []) + [
        f'{pochatok}{khvist}. Роки, дні й години.', f'{pochatok}{khvist}.']
    return skorotyty(pershyi_shcho_vlize(rjad, MAKS_OPYS))


# ---------------------------------------------------------------- район

def title_rayonu(rayon: str) -> str:
    return pershyi_shcho_vlize([f'{rayon} район Києва — події з рішень судів і скарги мешканців',
                                f'{rayon} район Києва — події з судів і скарги', f'{rayon} район Києва'], MAKS_TITLE)


def opys_rayonu(rayon: str, podii: str, roky_t: str, vulyts: str, budynkiv: str | None) -> str:
    t = (f'{rayon} район Києва в цифрах, без оцінок: {podii} з рішень судів за {roky_t}, скарги мешканців до 1551 за темами, '
         f'{vulyts}' + (f' і {budynkiv}' if budynkiv else '') + ' зі своєю сторінкою.')
    return skorotyty(t)


ZABORONENO = re.compile(r'безпечн|рейтинг|страшн|відгук', re.I)
