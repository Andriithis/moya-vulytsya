# -*- coding: utf-8 -*-
"""Облік клієнтів «Для бізнесу» з командного рядка — для партнера (ZAVDANNYA-157; `site/worker/prodazh/biznes.js`).

Ходить у сервер продажу з ключем партнера (той самий секрет ADMIN_KLIUCH, що й для вивантаження форм). Ключ — у змінній
середовища MV_ADMIN_KLIUCH, адреса сайту — MV_ADRESA_SAITU; у файли їх не писати.

  python site/prodazh/biznes_klienty.py zapyty                                  # запити зі сторінки /biznes/ (CSV у теку)
  python site/prodazh/biznes_klienty.py novyi "ТОВ «Назва»" ofis@firma.ua --tarif rik --do 2027-11-30 --dohovir Л-1/2026
  python site/prodazh/biznes_klienty.py posylannia k1 --dniv 7 [--maks 20]     # посилання — показується один раз
  python site/prodazh/biznes_klienty.py prodovzhyty k1 --do 2028-11-30 [--tarif rik] [--uvimknuty]
  python site/prodazh/biznes_klienty.py vymknuty k1 --prychyna "договір розірвано"   # [--lyshe-posylannia]
  python site/prodazh/biznes_klienty.py spysok                                  # клієнти, строки, скільки завантажень

Лише стандартна бібліотека Python.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def zapyt(adresa: str, kliuch: str, shliakh: str, tilo: dict | None = None) -> tuple[int, bytes]:
    r = urllib.request.Request(f'{adresa.rstrip("/")}/api/admin/biznes/{shliakh}', method='POST' if tilo is not None else 'GET',
                               data=json.dumps(tilo).encode('utf-8') if tilo is not None else None,
                               headers={'authorization': f'Bearer {kliuch}', 'content-type': 'application/json',
                                        'user-agent': 'moya-vulytsya-biznes'})
    try:
        with urllib.request.urlopen(r, timeout=30) as v:
            return v.status, v.read()
    except urllib.error.HTTPError as err:
        return err.code, err.read()


def main(argv=None, env=os.environ) -> int:
    ap = argparse.ArgumentParser(description='Облік клієнтів «Для бізнесу» (ZAVDANNYA-157)')
    pp = ap.add_subparsers(dest='dia', required=True)
    pp.add_parser('spysok', help='клієнти')
    z = pp.add_parser('zapyty', help='запити зі сторінки /biznes/ — CSV')
    z.add_argument('--fail', type=Path, default=Path('biznes-zapyty.csv'))
    n = pp.add_parser('novyi', help='новий клієнт після підписання договору')
    n.add_argument('nazva'); n.add_argument('kontakt')
    n.add_argument('--tarif', choices=('misiats', 'rik'), required=True)
    n.add_argument('--do', dest='diie_do', required=True, help='останній день договору, РРРР-ММ-ДД')
    n.add_argument('--dohovir', default='', help='номер договору')
    p = pp.add_parser('posylannia', help='особисте посилання на копію на N днів')
    p.add_argument('klient'); p.add_argument('--dniv', type=int, default=7); p.add_argument('--maks', type=int, default=20)
    pr = pp.add_parser('prodovzhyty', help='продовжити договір')
    pr.add_argument('klient'); pr.add_argument('--do', dest='diie_do', required=True)
    pr.add_argument('--tarif', choices=('misiats', 'rik')); pr.add_argument('--dohovir')
    pr.add_argument('--uvimknuty', action='store_true', help='увімкнути вимкненого клієнта')
    v = pp.add_parser('vymknuty', help='вимкнути клієнта (або лише його посилання)')
    v.add_argument('klient'); v.add_argument('--prychyna', default='')
    v.add_argument('--lyshe-posylannia', action='store_true', help='вимкнути лише посилання (напр. переслали чужим), клієнт діє')
    a = ap.parse_args(argv)

    adresa, kliuch = env.get('MV_ADRESA_SAITU', '').strip(), env.get('MV_ADMIN_KLIUCH', '').strip()
    if not adresa or not kliuch:
        print('Потрібні змінні MV_ADRESA_SAITU (https://<сайт>) і MV_ADMIN_KLIUCH (секрет ADMIN_KLIUCH сервера)', file=sys.stderr)
        return 2
    if a.dia == 'spysok':
        k, b = zapyt(adresa, kliuch, 'klienty')
    elif a.dia == 'zapyty':
        k, b = zapyt(adresa, kliuch, 'zapyty.csv')
        if k == 200:
            a.fail.write_bytes(b)
            n = b.count(b'\n') - 1
            print(f'Записано {a.fail} ({n} запитів). Файл — з контактами людей: не пересилати.')
            return 0
    elif a.dia == 'novyi':
        k, b = zapyt(adresa, kliuch, 'klient', {'nazva': a.nazva, 'kontakt': a.kontakt, 'tarif': a.tarif, 'diie_do': a.diie_do,
                                                'dohovir': a.dohovir})
    elif a.dia == 'posylannia':
        k, b = zapyt(adresa, kliuch, 'posylannia', {'klient': a.klient, 'dniv': a.dniv, 'maks': a.maks})
    elif a.dia == 'prodovzhyty':
        t = {'diie_do': a.diie_do, 'uvimknuty': a.uvimknuty}
        if a.tarif: t['tarif'] = a.tarif
        if a.dohovir: t['dohovir'] = a.dohovir
        k, b = zapyt(adresa, kliuch, f'klient/{a.klient}', t)
    else:
        k, b = zapyt(adresa, kliuch, 'vymknuty', {'klient': a.klient, 'prychyna': a.prychyna, 'lyshe_posylannia': a.lyshe_posylannia})
    try:
        print(json.dumps(json.loads(b), ensure_ascii=False, indent=2))
    except ValueError:
        print(b.decode('utf-8', 'replace')[:500])
    if k == 201 and a.dia == 'posylannia':
        print('Посилання показано один раз: надішліть його контакту клієнта з договору. Загубили — видайте нове.')
        try:      # ZAVDANNYA-172 (ZVIT-169): строк — датою, а не секундами з 1970 року
            import datetime
            do_ = json.loads(b).get('do_')
            if do_:
                print(f'Діє до: {datetime.datetime.fromtimestamp(do_, datetime.timezone.utc):%d.%m.%Y} включно (за Гринвічем)')
        except (ValueError, TypeError, AttributeError):
            pass
    return 0 if k < 400 else 1


if __name__ == '__main__':
    sys.exit(main())
