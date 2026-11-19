# -*- coding: utf-8 -*-
"""Щомісячний лист «Нове біля дому» підписникам — «Стежу» (ZAVDANNYA-150, п. 4; MV-14, ZAVDANNYA-119).

Як видавач довідок (`vydavach.py`): бере чергу в сервера продажу, складає листи там, де лежать дані, і віддає їх серверу,
а сервер підставляє пошту й надсилає. Ключ — той самий VYDACHA_KLIUCH (секрет Workers); пошти скрипт не бачить — лише
непрозорий номер підписника й адреси «Стежу».

Раз на місяць, після оновлення даних (новий випуск і скарги 1551):
  1. dani-edrsr: python src/nove_tyzhnia.py <events-нова.db> <тека 1551> nove-<дата>.json --do <дата> --dniv 30 \\
                   --poperednii <events-стара.db> [--perekazy perekazy-<дата>.json]
  2. продукт:    python bot/indeks.py <events-нова.db> <budynky.json> indeks.json     (точки будинків, як на сайті)
  3. VYDACHA_KLIUCH=… python site/prodazh/lyst_stezhu.py --server https://<сайт> --strichka nove-<дата>.json \\
                   --indeks indeks.json --period 2026-11 [--proba teka/]

`--proba` — нічого не надсилати: листи (тема й текст) пишуться в теку, черга сервера не змінюється.
Повторний запуск за той самий місяць нікому не шле вдруге (сервер відповідає 409).
Лист — лише підписка 399 і рієлтор, лише адреси «Стежу», радіус 300 м (`lyst/lyst.py`); перед надсиланням — перевірка слів
(`vady_tekstu`: без «небезпечно», рейтингів, прогнозів, порад, службових слів, «ОСОБА»).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
from pathlib import Path

KORIN = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(KORIN / 'lyst'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import lyst as L  # noqa: E402
from vydavach import zapyt  # noqa: E402


def posylannia(sait: str) -> dict:
    k = f'{sait.rstrip("/")}/kabinet/#stezhu'
    return {'stezhu': k, 'vidpyska': k, 'vidpyska_napys': 'Не надсилати цей лист — кнопка в кабінеті, розділ «Стежу»'}


def lysty(strichka: dict, pidpysnyky: list, indeks: dict, sait: str) -> tuple[list[dict], dict]:
    """pidpysnyky — з черги сервера [{id, adresy: [{budynok, adresa}]}]. Повертає ([{id, tema, tekst}], звіт)."""
    tochky = {b['u']: b for b in indeks.get('budynky', [])}
    pos = posylannia(sait)
    vyhid, zvit = [], {'pidpysnykiv': len(pidpysnyky), 'lystiv': 0, 'tykhykh': 0, 'bez_tochky': 0, 'zatrymano': 0, 'bez_adres': 0}
    for x in pidpysnyky:
        adresy = []
        for a in x.get('adresy', []):
            b = tochky.get(a['budynok'])
            if b is None:
                zvit['bez_tochky'] += 1           # будинок зник з даних — пропускаємо адресу, а не весь лист
                continue
            adresy.append(L.Adresa(a['adresa'], b['la'], b['lo']))
        if not adresy:
            zvit['bez_adres'] += 1
            continue
        l = L.zibraty(strichka, L.Pidpysnyk(x['id'], 'pidpyska', adresy, tykhyi_lyst=True))
        if l is None:
            continue
        tekst = L.tekst(l, pos)
        if L.vady_tekstu(tekst) or L.vady_tekstu(L.tema(l)):
            zvit['zatrymano'] += 1
            continue
        zvit['lystiv'] += 1
        zvit['tykhykh'] += l.tykhyi
        vyhid.append({'id': x['id'], 'tema': L.tema(l), 'tekst': tekst})
    return vyhid, zvit


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Щомісячний лист «Стежу» підписникам (черга сервера продажу).')
    ap.add_argument('--server', required=True, help='адреса сайту з сервером продажу')
    ap.add_argument('--strichka', type=Path, required=True, help='nove-<дата>.json за місяць (dani-edrsr/src/nove_tyzhnia.py --dniv 30)')
    ap.add_argument('--indeks', type=Path, required=True, help='indeks.json (bot/indeks.py): точки будинків')
    ap.add_argument('--period', required=True, help='місяць листа РРРР-ММ (один лист на місяць кожному)')
    ap.add_argument('--proba', type=Path, help='не надсилати: записати листи в цю теку')
    a = ap.parse_args(argv)
    kliuch = os.environ.get('VYDACHA_KLIUCH', '')
    if not kliuch:
        print('Потрібна змінна VYDACHA_KLIUCH (той самий ключ, що секрет Workers).', file=sys.stderr)
        return 2
    strichka = json.loads(a.strichka.read_text(encoding='utf-8'))
    indeks = json.loads(a.indeks.read_text(encoding='utf-8'))
    _, tilo = zapyt(a.server, kliuch, 'GET', f'/api/vnutr/stezhu?period={urllib.parse.quote(a.period)}')
    vyhid, zvit = lysty(strichka, json.loads(tilo)['pidpysnyky'], indeks, a.server)
    nadislano = povtor = 0
    for l in vyhid:
        if a.proba:
            a.proba.mkdir(parents=True, exist_ok=True)
            (a.proba / f'{l["id"]}.txt').write_text(f'{l["tema"]}\n\n{l["tekst"]}', encoding='utf-8')
            continue
        tilo_ = json.dumps({'period': a.period, 'tema': l['tema'], 'tekst': l['tekst']}, ensure_ascii=False).encode('utf-8')
        try:
            zapyt(a.server, kliuch, 'POST', f'/api/vnutr/lyst-stezhu/{l["id"]}', tilo_, 'application/json')
            nadislano += 1
        except Exception as err:  # noqa: BLE001 — 409 (уже надіслано) і 404 (підписка скінчилась) — не помилка розсилки
            if getattr(err, 'code', None) in (404, 409):
                povtor += 1
            else:
                raise
    print({**zvit, 'nadislano': nadislano, 'propushcheno_servera': povtor, 'proba': bool(a.proba)})
    return 0


if __name__ == '__main__':
    sys.exit(main())
