# -*- coding: utf-8 -*-
"""Перекази ШІ для «Однієї історії з вулиці» (ZAVDANNYA-110, Б-1; MV-25, MV-110).

На відкритих сторінках сирої фабули немає: блок історії показує лише переказ ШІ, який пройшов перевірку програмою.
Переказу немає або він не пройшов — блоку немає. Перекази готує крок `dani-edrsr/src/perekazy_istorii.py`
(`claude -p` з підписки Андрія на ПК) і віддає файлом `perekazy-<дата>.json`; збирач сайту читає його ключем
`--perekazy` і перевіряє кожен переказ ще раз — тими самими правилами (копія — `dani-edrsr/src/perekaz_perevirka.py`).

  vady(tekst, fabula=None) -> [вада, …]   порожній список — переказ можна показати
  prochytaty(shlyakh) -> {event_id: переказ}
"""
from __future__ import annotations

import json
import re
from pathlib import Path

MIN_DOVZHYNA, MAKS_DOVZHYNA = 40, 320
SPILNYKH_SLIV = 6        # стільки слів підряд, як у рішенні, — це вже уривок рішення, а не переказ

# Будь-яка цифра: дата, година, сума, номер будинку, авто, справи, статті — у переказі для відкритої сторінки їх немає.
TSYFRA = re.compile(r'\d')
DATA_SLOVAMY = re.compile(r'\b(січн|лютого|берез|квітн|травн|червн|липн|серпн|вересн|жовтн|листопад|грудн)\w*', re.I)
CHAS = re.compile(r'\b(год\.|годин[іиуа]?\b|хв\.|хвилин)', re.I)   # частина доби («вночі») — можна
SUMA = re.compile(r'\b(грн|гривень|гривні|гривня|коп\.|копійок|долар\w*|євро|USD|EUR|UAH)\b|[$€₴]', re.I)
# Марки й моделі авто (латиницею й кирилицею), номерні знаки.
MARKY = re.compile(
    r'\b(toyota|тойот\w*|bmw|бмв|mercedes\w*|мерседес\w*|audi|ауді|volkswagen|фольксваген\w*|vw|skoda|октаві\w*|фабі[аяюї]\w*|суперб|кодіак|daewoo|деу|'
    r'lanos|ланос\w*|sens|сенс|ваз|lada|лада|жигул\w*|заз|таврі\w*|renault|рено|hyundai|хюндай|хьюндай|kia|кіа|nissan|ніссан\w*|'
    r'mazda|мазд\w*|honda|хонд\w*|ford|форд\w*|opel|опель\w*|chevrolet|шевроле|mitsubishi|мітсубіші|lexus|лексус\w*|'
    r'peugeot|пежо|citroen|сітроен\w*|fiat|фіат\w*|volvo|вольво|subaru|субару|tesla|тесл\w*|geely|джилі|chery|чері|'
    r'porsche|порше|land\s?rover|range\s?rover|infiniti|інфініті|suzuki|сузукі|jeep|джип\w*|dodge|додж|seat|сеат|'
    r'jaguar|ягуар|byd|ravon|равон|daf|iveco|івеко|scania|скані\w*|газель|уаз|камаз|богдан)\b', re.I)
NOMERNYI_ZNAK = re.compile(r'д\.?\s?н\.?\s?з|номерн\w* знак', re.I)
# Сліди імен, знеособлення реєстру, квартири, суд і процес.
SLIDY = re.compile(r'_|\bкв\.|квартир\w*\s+№|\bгр\.\s*[А-ЯІЇЄҐ]', re.I)
IMENA = re.compile(r'[А-ЯІЇЄҐ][а-яіїєґ\']+\s+[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.')
SLIDY_REGISTR = re.compile(r'ОСОБА|АДРЕСА|ІНФОРМАЦІЯ|ПІБ')
SUD = re.compile(r'суддя|судді\b|головуюч|постанов|ухвал|вирок|обвинувачен|підозрюван|протокол|клопотан|прокурор|'
                 r'\bст\.|\bстатт[іяю]\b|кодекс|КУпАП|\bКК\b', re.I)
ZABORONENI = re.compile(r'небезпечн|безпечн|рейтинг|страшн', re.I)
NEPOVNOLITNI = re.compile(r'неповнолітн|малолітн|дит(ин|я)', re.I)


def slova(t: str) -> list[str]:
    return re.findall(r"[a-zа-яіїєґ']+", (t or '').lower().replace('’', "'").replace('ʼ', "'"))


def spilnyi_uryvok(tekst: str, fabula: str | None, n: int = SPILNYKH_SLIV) -> bool:
    """Чи є в переказі n слів підряд, як у рішенні (дослівний уривок)."""
    if not fabula:
        return False
    f = slova(fabula)
    nabir = {tuple(f[i:i + n]) for i in range(len(f) - n + 1)}
    s = slova(tekst)
    return any(tuple(s[i:i + n]) in nabir for i in range(len(s) - n + 1))


def vady(tekst: str | None, fabula: str | None = None) -> list[str]:
    """Чому переказ не можна показати на відкритій сторінці. Порожній список — можна."""
    t = (tekst or '').strip()
    if not t:
        return ['порожньо']
    zh = []
    if not MIN_DOVZHYNA <= len(t) <= MAKS_DOVZHYNA:
        zh.append('довжина')
    if TSYFRA.search(t):
        zh.append('цифри (дата, година, сума чи номер)')
    if DATA_SLOVAMY.search(t):
        zh.append('дата')
    if CHAS.search(t):
        zh.append('година')
    if SUMA.search(t):
        zh.append('сума')
    if MARKY.search(t) or NOMERNYI_ZNAK.search(t):
        zh.append('марка чи номер авто')
    if SLIDY.search(t) or SLIDY_REGISTR.search(t) or IMENA.search(t):
        zh.append('сліди імен чи квартир')
    if SUD.search(t):
        zh.append('мова суду')
    if ZABORONENI.search(t):
        zh.append('заборонене слово')
    if NEPOVNOLITNI.search(t):
        zh.append('діти')
    if spilnyi_uryvok(t, fabula):
        zh.append('уривок рішення')
    return zh


def prochytaty(shlyakh: Path | None) -> dict[str, str]:
    """Файл кроку `dani-edrsr/src/perekazy_istorii.py`: {"perekazy": {event_id: {"perekaz": …}}} → {event_id: переказ}."""
    if not shlyakh:
        return {}
    d = json.loads(Path(shlyakh).read_text(encoding='utf-8'))
    vykhid = {}
    for eid, x in (d.get('perekazy') or {}).items():
        t = x.get('perekaz') if isinstance(x, dict) else x
        if isinstance(t, str) and t.strip():
            vykhid[str(eid)] = t.strip()
    return vykhid
