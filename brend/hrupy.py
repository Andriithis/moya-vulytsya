# -*- coding: utf-8 -*-
"""Групи подій для показу — читач копії одного словника (MV-116, ZAVDANNYA-108).

Правда — `dani-edrsr/src/hrupy.py`; тут лише її копія `brend/hrupy.json` (оновлюється там командою
`python src/hrupy.py --json ../moya-vulytsya/brend/hrupy.json`, збіг перевіряє check_build `dani-edrsr`).
Звідси беруть назви, порядок, кольори й склад груп сайт і сторінки будинків (`site/`), довідка й звіт (`dani-edrsr/src/zvit/`),
ролики (`video/`). Інших назв груп у коді продукту немає (tests/test_hrupy.py).

Група — лише показ: вид події (`event.vyd`) і сталий номер події не змінюються.
"""
import json
from pathlib import Path

SLOVNYK = json.loads((Path(__file__).resolve().parent / 'hrupy.json').read_text(encoding='utf-8'))
HRUPY = [(h['kliuch'], h['nazva']) for h in SLOVNYK['hrupy']]          # у порядку легенди
KLIUCHI = [k for k, _ in HRUPY]
NAZVA = dict(HRUPY)
SLOVO = {h['kliuch']: h['slovo'] for h in SLOVNYK['hrupy']}               # у реченні: «крадіжки й шкода майну»
KOLIR = {t: [h[t] for h in SLOVNYK['hrupy']] for t in ('svitla', 'temna')}
_VYD = SLOVNYK['vyd']
_ZA_STATTEIU = {(v, s): k for v, s, k in SLOVNYK['za_statteiu']}
_PERSHI = {k: tuple(v) for k, v in SLOVNYK['pershi'].items()}


def stattia(st):
    """'ст.130 КУпАП · керування…' -> 'ст.130 КУпАП'"""
    return (st or '').split(' · ')[0].strip()


def hrupa(vyd, st=''):
    """ключ групи події (вид + стаття); None — поза групами"""
    return _ZA_STATTEIU.get((vyd, stattia(st))) or _VYD.get(vyd)


def nazva(vyd, st=''):
    k = hrupa(vyd, st)
    return NAZVA[k] if k else ''


def pershyi(k, st):
    """0 — пункт іде першим у своїй групі (нетверезі за кермом у «Порушеннях водіїв»), 1 — решта"""
    return 0 if stattia(st) in _PERSHI.get(k, ()) else 1
