"""Ціни «Моєї вулиці» — ОДНА таблиця для всього сайту: сторінок будинків і вітрин (`storinky_mv100.py`), заглушки й
оферти (`zahlushka/zibraty.py`). Змінили ціну рішенням MV — змінити лише тут; тести звіряють, що на зібраному сайті
немає інших сум (`tests/test_sait.py`, `tests/test_zahlushka.py`).

MV-100 (17.11.2026): довідка 199, 3 довідки 449, повний звіт 599, підписка 399/міс (1 довідка включена), додаткова 99.
MV-102 (17.11.2026): рієлтор 799/міс (5 довідок), ОСББ 1 490/рік, «Для бізнесу» — ціна за домовленістю (None).
"""
from __future__ import annotations

NBSP = ' '

TSINY = {
    'dovidka': 199,            # довідка про будинок, разово
    'try': 449,                # пакет «3 довідки»
    'zvit': 599,               # повний звіт «перед купівлею» (звіт адреси)
    'pidpyska': 399,           # на місяць, 1 довідка включена
    'dodatkova': 99,           # додаткова довідка в підписці
    'rieltor': 799,            # підписка рієлтора: 5 довідок на місяць
    'osbb': 1490,              # річна оплата за будинок
    'biznes': None,            # ціна за домовленістю, запит через форму (відповідає партнер)
}
TOVARY = {
    'dovidka': 'Довідка про будинок', 'try': '3 довідки', 'zvit': 'Повний звіт «перед купівлею»',
    'pidpyska': 'Підписка', 'dodatkova': 'Додаткова довідка в підписці', 'rieltor': 'Підписка для рієлтора',
    'osbb': 'Будинок для ОСББ', 'biznes': 'Дані для бізнесу',
}
# За який строк ціна (порожньо — разово).
STROK = {'pidpyska': ' на місяць', 'rieltor': ' на місяць', 'osbb': ' на рік'}
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


def dozvoleni_sumy() -> set[int]:
    """Усі суми, які можуть бути на сайті (0 — безкоштовна карта)."""
    return {0} | {v for v in TSINY.values() if v is not None}


# ---------------------------------------------------------------- для сервера продажу (ZAVDANNYA-99)
# Скільки довідок дає покупка або підписка за один період (MV-100, MV-102). ОСББ — довідки лише на свій будинок.
DOVIDOK = {'dovidka': 1, 'try': 3, 'zvit': 1, 'pidpyska': 1, 'rieltor': 5, 'osbb': 1}
# Період підписки: скільки місяців між списаннями (ОСББ — рік, MV-102).
PERIOD_MISIATSIV = {'pidpyska': 1, 'rieltor': 1, 'osbb': 12}
# Який звіт генерувати (dani-edrsr/src/zvit/zibraty.py): повний — лише «Повний звіт», решта — довідка.
REZHYM = {'zvit': 'povnyi'}
# Що можна купити через сервер (бізнес — за домовленістю, додаткова — лише з кабінету підписника).
NA_PRODAZH = ('dovidka', 'try', 'zvit', 'pidpyska', 'rieltor', 'osbb')


MODUL_JS = '// Зібрано з site/tsiny.py (python site/tsiny.py). Не редагувати руками.\nexport default '


def dlia_servera() -> dict:
    """Таблиця цін для сервера продажу (`site/worker/prodazh/tsiny.js`; той самий вміст звіряє тест)."""
    return {
        'pro': 'Зібрано з site/tsiny.py (python site/tsiny.py). Не редагувати руками.',
        'tsiny': TSINY, 'nazvy': TOVARY, 'dovidok': DOVIDOK, 'period_misiatsiv': PERIOD_MISIATSIV,
        'rezhym': REZHYM, 'na_prodazh': list(NA_PRODAZH),
    }


if __name__ == '__main__':
    import json
    from pathlib import Path
    f = Path(__file__).resolve().parent / 'worker' / 'prodazh' / 'tsiny.js'
    f.write_text(MODUL_JS + json.dumps(dlia_servera(), ensure_ascii=False, indent=1) + ';\n', encoding='utf-8')
    print(f)
