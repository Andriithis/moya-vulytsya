"""Яку адресу показувати в безкоштовних роликах і постах (MV-60, уточнює MV-25).

Одне правило для `video/` і `brend/` — щоб не правити файли вручну:
- номер будинку — лише для подій у публічних місцях (ТЦ, магазин, вокзал, парковка, перехрестя,
  вулиця біля закладу); тип місця пишемо в полі `typ_mistsia` події;
- житловий будинок, невідомий тип місця або чутлива справа — лише вулиця
  (AGENTS.md розд. 4: жодних «небезпечних будинків»).
Якщо `typ_mistsia` не задано — вважаємо, що місце не публічне (безпечніше сховати номер).
"""
from __future__ import annotations

import re

# Тип місця → підпис (для README і повідомлень перевірки).
PUBLICHNI = {
    'tts': 'торговий центр',
    'mahazyn': 'магазин',
    'vokzal': 'вокзал',
    'parkovka': 'парковка',
    'perekhrestia': 'перехрестя',
    'zaklad': 'вулиця біля закладу',
}
# Інші відомі типи — номер не показуємо.
NEPUBLICHNI = {'zhytlo': 'житловий будинок', 'vulytsia': 'вулиця', 'nevidomo': 'невідомо'}

CHUTLYVI = ['насильств', 'статев', 'згвалт', 'сексуал', 'розбещ', 'неповнолітн', 'дитин', 'дітей', 'малолітн']

# «вул. П. Орлика, 10», «вул. Цитадельна, 6/8», «вул. Х, буд. 28-А», «вул. Х, 3, корп. 2»
NOMER = re.compile(r',\s*(?:буд(?:инок)?\.?\s*)?\d+[\w/\-–]*(?:\s*,.*)?$', re.I)


def bez_nomera(adresa: str) -> str:
    """Адреса без номера будинку: «вул. П. Орлика, 10» → «вул. П. Орлика»."""
    return NOMER.sub('', (adresa or '').strip()).strip()


def maie_nomer(adresa: str) -> bool:
    return bool(adresa) and bez_nomera(adresa) != adresa.strip()


def chutlyva(*teksty: str) -> bool:
    t = ' '.join(x or '' for x in teksty).lower()
    return any(z in t for z in CHUTLYVI)


def mozhna_nomer(typ_mistsia: str | None, chutlyva_sprava: bool = False) -> bool:
    return typ_mistsia in PUBLICHNI and not chutlyva_sprava


def adresa_dlia_pokazu(adresa: str, typ_mistsia: str | None = None, chutlyva_sprava: bool = False) -> str:
    """Те, що бачить людина: повна адреса — лише для публічного місця й не чутливої справи."""
    if mozhna_nomer(typ_mistsia, chutlyva_sprava):
        return (adresa or '').strip()
    return bez_nomera(adresa)


def nevidomyi_typ(typ_mistsia: str | None) -> bool:
    return typ_mistsia is not None and typ_mistsia not in PUBLICHNI and typ_mistsia not in NEPUBLICHNI
