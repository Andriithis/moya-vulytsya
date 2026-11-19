"""Ціни «Моєї вулиці» — ОДНА таблиця для всього сайту: сторінок будинків і вітрин (`storinky_mv100.py`), заглушки й
оферти (`zahlushka/zibraty.py`). Змінили ціну рішенням MV — змінити лише тут; тести звіряють, що на зібраному сайті
немає інших сум (`tests/test_sait.py`, `tests/test_zahlushka.py`).

MV-100 (17.11.2026): довідка 199, 3 довідки 449, повний звіт 299 (MV-136), підписка 399/міс (1 довідка включена), додаткова 99.
MV-102 (17.11.2026): рієлтор 799/міс (5 довідок), ОСББ 1 490/рік, «Для бізнесу» — ціна за домовленістю (None).
MV-122 (17.11.2026): «Судова практика» — довідка людині 199, підписка юристу 490/міс. В оферті їх ще немає (NE_V_OFERTI):
текст оферти для цих товарів — окремим рішенням Андрія (юриста не буде, MV-152; чернетка — `docs/SUDOVA-PRAKTYKA-PRODUKT.md`).
ZAVDANNYA-135: обидва товари вже продаються сервером (NA_PRODAZH), але лишаються «скоро», доки вони в NE_V_OFERTI:
увімкнути продаж = дописати оферту й прибрати їх звідти (одна зміна тут; сайт і сервер беруть це з однієї таблиці).
"""
from __future__ import annotations

import re

NBSP = ' '

TSINY = {
    'dovidka': 199,            # довідка про будинок, разово
    'try': 449,                # пакет «3 довідки»
    'zvit': 299,               # повний звіт «перед купівлею» (звіт адреси)
    'pidpyska': 399,           # на місяць, 1 довідка включена
    'dodatkova': 99,           # додаткова довідка в підписці
    'rieltor': 799,            # підписка рієлтора: 5 довідок на місяць
    'osbb': 1490,              # річна оплата за будинок
    'biznes': None,            # ціна за домовленістю, запит через форму (відповідає партнер)
    'spdovidka': 199,          # «Судова практика»: довідка по своєму суду й статті, разово (MV-122)
    'spyurist': 490,           # «Судова практика»: підписка юристу, на місяць (MV-122)
}
TOVARY = {
    'dovidka': 'Довідка про будинок', 'try': '3 довідки', 'zvit': 'Повний звіт «перед купівлею»',
    'pidpyska': 'Підписка', 'dodatkova': 'Додаткова довідка в підписці', 'rieltor': 'Підписка для рієлтора',
    'osbb': 'Будинок для ОСББ', 'biznes': 'Дані для бізнесу',
    'spdovidka': 'Довідка «Як закінчуються такі справи в моєму суді»', 'spyurist': 'Підписка юристу «Практика»',
}
# Товари, яких ще немає в оферті заглушки (тексти оферти — окремим рішенням, MV-152). Вони — «скоро», навіть коли оплату
# ввімкнено (prodaietsia()).
NE_V_OFERTI = set()  # MV-164: обидва товари «Судової практики» — в оферті
# За який строк ціна (порожньо — разово).
STROK = {'pidpyska': ' на місяць', 'rieltor': ' на місяць', 'osbb': ' на рік', 'spyurist': ' на місяць'}
ZA_DOMOVLENISTIU = 'ціна за домовленістю'


def suma(n: int) -> str:
    """1490 → «1 490» (нерозривний пробіл між тисячами)."""
    return f'{n:,}'.replace(',', NBSP)


def tsina(kl: str, strok: bool = True) -> str:
    """«199 грн», «399 грн на місяць», «ціна за домовленістю»."""
    t = TSINY[kl]
    if t is None:
        return ZA_DOMOVLENISTIU
    return f'{suma(t)}{NBSP}грн' + (STROK.get(kl, '') if strok else '')


# ---------------------------------------------------------------- кнопки оплати (ZAVDANNYA-132)
# Один перемикач на весь сайт: 'skoro' — оплату не підключено, на кожній кнопці оплати другий рядок «Скоро — залиште
# пошту» (кнопка веде на /oplata/, де сервер записує пошту, товар і будинок); 'tak' — звичайні кнопки, /oplata/ — справжня
# оплата. Ставить збирач (`zibraty_sait.py --oplata`, у скрипті викладки — змінна MV_OPLATA). Ціни й адреси кнопок — ті самі.
REZHYMY_OPLATY = ('skoro', 'tak')
OPLATA = {'rezhym': 'skoro'}
NAPYS_SKORO = 'Скоро — залиште пошту'


def knopka_oplaty(href: str, napys: str, holovna: bool = False) -> str:
    """<a> кнопки оплати; href і napys — уже екрановані. Товар, якого ще немає в продажу (NA_PRODAZH; «Судова практика»),
    лишається «скоро» й після ввімкнення оплати — сервер на нього показує «залиште пошту»."""
    klas = 'knopka' + (' knopka--holovna' if holovna else '')
    tovar = re.search(r'[?&;]tovar=([a-z]+)', href)
    if OPLATA['rezhym'] == 'skoro' or (tovar and tovar.group(1) not in prodaietsia()):
        return (f'<a class="{klas} knopka--skoro" href="{href}"><span>{napys}</span>'
                f'<small class="knopka__skoro">{NAPYS_SKORO}</small></a>')
    return f'<a class="{klas}" href="{href}">{napys}</a>'


def dozvoleni_sumy() -> set[int]:
    """Усі суми, які можуть бути на сайті (0 — безкоштовна карта)."""
    return {0} | {v for v in TSINY.values() if v is not None}


# ---------------------------------------------------------------- для сервера продажу (ZAVDANNYA-99)
# Скільки довідок дає покупка або підписка за один період (MV-100, MV-102). ОСББ — довідки лише на свій будинок.
# «Судова практика» (ZAVDANNYA-135, пропозиція): довідка людині — 1; підписка юристу — 3 довідки «стаття × суд» на місяць
# (для клієнтів), довідок про будинки не дає.
DOVIDOK = {'dovidka': 1, 'try': 3, 'zvit': 1, 'pidpyska': 1, 'rieltor': 5, 'osbb': 1, 'spdovidka': 1, 'spyurist': 3}
# Період підписки: скільки місяців між списаннями (ОСББ — рік, MV-102).
PERIOD_MISIATSIV = {'pidpyska': 1, 'rieltor': 1, 'osbb': 12, 'spyurist': 1}
# Який звіт генерувати: повний — лише «Повний звіт» (dani-edrsr/src/zvit/zibraty.py), «Судова практика» — sp
# (dani-edrsr/src/sp_dovidka.py), решта — довідка про будинок.
REZHYM = {'zvit': 'povnyi', 'spdovidka': 'sp', 'spyurist': 'sp'}
# Що можна купити через сервер (бізнес — за домовленістю, додаткова — лише з кабінету підписника).
NA_PRODAZH = ('dovidka', 'try', 'zvit', 'pidpyska', 'rieltor', 'osbb', 'spdovidka', 'spyurist')
# Товари «Судової практики»: без будинку; довідки — лише «стаття × суд», не про будинок.
SUDOVA = ('spdovidka', 'spyurist')


def prodaietsia() -> tuple:
    """Що продається зараз: у продажу й уже в оферті."""
    return tuple(t for t in NA_PRODAZH if t not in NE_V_OFERTI)


MODUL_JS = '// Зібрано з site/tsiny.py (python site/tsiny.py). Не редагувати руками.\nexport default '


def dlia_servera() -> dict:
    """Таблиця цін для сервера продажу (`site/worker/prodazh/tsiny.js`; той самий вміст звіряє тест)."""
    return {
        'pro': 'Зібрано з site/tsiny.py (python site/tsiny.py). Не редагувати руками.',
        'tsiny': TSINY, 'nazvy': TOVARY, 'dovidok': DOVIDOK, 'period_misiatsiv': PERIOD_MISIATSIV,
        'rezhym': REZHYM, 'na_prodazh': list(NA_PRODAZH), 'prodaietsia': list(prodaietsia()), 'sudova': list(SUDOVA),
    }


if __name__ == '__main__':
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent / 'worker' / 'prodazh' / 'tsiny.js'
    f.write_text(MODUL_JS + json.dumps(dlia_servera(), ensure_ascii=False, indent=1) + ';\n', encoding='utf-8')
    print(f)
