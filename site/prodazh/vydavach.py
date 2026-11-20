# -*- coding: utf-8 -*-
"""Видавач довідок (ZAVDANNYA-99): бере оплачені довідки з черги сервера продажу, запускає генератор
`dani-edrsr/src/zvit/zibraty.py` (--dovidka, --osbb або --povnyi) і віддає готовий файл серверу; сервер кладе його в сховище
й надсилає покупцю посилання на пошту.

Працює там, де лежать дані генератора (випуск events-<дата>.db, скарги 1551, знімок OSM): сервер партнера або ПК.
Сервер продажу (Cloudflare Workers) Python і гігабайти даних не запускає — тому видавач окремо (docs/PRODAZH-SERVER.md).

  VYDACHA_KLIUCH=… ZVIT_DB=… ZVIT_SKARGY=… ZVIT_OSM=… \\
  python site/prodazh/vydavach.py --server https://<сайт> --dani-edrsr ../dani-edrsr [--raz] [--pauza 20] [--shi]
  python site/prodazh/vydavach.py --server https://<сайт> --do-porozhnoi --maks-khvylyn 40 …   # запуск GitHub Actions
                                                       (шаблон site/prodazh/github/vydavach.yml, ZAVDANNYA-133)

Ключ видавача — лише змінна середовища VYDACHA_KLIUCH (той самий, що секрет Workers). Видавач не бачить пошти покупців,
сум і платежів — лише номер довідки, адресу будинку й режим («Судова практика» — статтю, суд і частину, ZAVDANNYA-135).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

KORIN = Path(__file__).resolve().parents[2]


def zapyt(server: str, kliuch: str, metod: str, shliakh: str, tilo: bytes | None = None, typ: str | None = None):
    h = {'authorization': f'Bearer {kliuch}', 'user-agent': 'moya-vulytsya-vydavach'}
    if typ:
        h['content-type'] = typ
    r = urllib.request.Request(server.rstrip('/') + shliakh, data=tilo, method=metod, headers=h)
    with urllib.request.urlopen(r, timeout=120) as v:
        return v.status, v.read()


def zibraty(generator: Path, d: dict, teka: Path, shi: bool) -> tuple[Path | None, Path | None]:
    """Один запуск генератора. Повертає (файл довідки або None — генератор упав чи не знайшов будинок; «картку для
    мешканців» або None). Картка (ZAVDANNYA-178, MV-183; генератор --kartka) — поруч із довідкою, звітом, ОСББ: лише числа,
    без описів справ; не вийшла — довідка йде без неї.
    Режим sp («Судова практика», ZAVDANNYA-135) — інший генератор (dani-edrsr/src/sp_dovidka.py, поруч зі zvit/) з
    параметрами {stattia, sud, chastyna}; дані — змінна SP_DANI (dovidka.json з Release dani-edrsr). ШІ там немає."""
    vyhid = teka / f'{d["id"]}.html'
    kartka = None
    if d['rezhym'] == 'sp':
        sp = generator.parent.parent / 'sp_dovidka.py'
        komanda = [sys.executable, str(sp), '--parametry', json.dumps(d.get('parametry') or {}, ensure_ascii=False),
                   '--vyhid', str(vyhid), '--nomer', d['id']]
    else:
        # osbb — щомісячна довідка ОСББ (ZAVDANNYA-143; dani-edrsr S-Зв.5): довідка + зверху останній місяць скарг 1551
        prapor = {'dovidka': ['--dovidka'], 'osbb': ['--osbb'], 'povnyi': ['--povnyi']}.get(d['rezhym'], ['--povnyi'])
        # два режими (довідка + картка) — генератор пише <id>-<режим>.html
        osnovnyi = 'povnyi' if prapor == ['--povnyi'] else 'dovidka'
        vyhid, kartka = teka / f'{d["id"]}-{osnovnyi}.html', teka / f'{d["id"]}-kartka.html'
        komanda = [sys.executable, str(generator), d['adresa'], *prapor, '--kartka', '--vyhid', str(teka / f'{d["id"]}-<режим>.html'), '--chysto']
    if shi and d['rezhym'] != 'sp':
        komanda.append('--shi')
    p = subprocess.run(komanda, capture_output=True, text=True, timeout=30 * 60)
    if p.returncode != 0 or not vyhid.exists():
        print(f'  генератор: код {p.returncode}; {(p.stderr or p.stdout).strip()[-400:]}', flush=True)
        return None, None
    return vyhid, (kartka if kartka is not None and kartka.exists() else None)


def odyn_obkhid(server: str, kliuch: str, generator: Path, shi: bool, n: int = 1) -> int:
    """Узяти до n довідок, зібрати, віддати. Повертає, скільки взято."""
    _, tilo = zapyt(server, kliuch, 'GET', f'/api/vnutr/cherha?n={n}')
    dovidky = json.loads(tilo)['dovidky']
    with tempfile.TemporaryDirectory(prefix='vydavach-') as t:
        for d in dovidky:
            pochatok = time.time()
            print(f'{d["id"]}: {d["rezhym"]} — {d["adresa"]}', flush=True)
            f, kartka = zibraty(generator, d, Path(t), shi)
            if f is None:
                zapyt(server, kliuch, 'POST', f'/api/vnutr/pomylka/{d["id"]}')
                print('  не вдалося — сервер поверне в чергу (до 3 спроб)', flush=True)
                continue
            if kartka is not None:
                # картка — до довідки: лист «готово» вже несе посилання на неї. Не прийняв сервер — довідка йде без картки
                try:
                    zapyt(server, kliuch, 'PUT', f'/api/vnutr/kartka/{d["id"]}', kartka.read_bytes(), 'text/html; charset=utf-8')
                except urllib.error.HTTPError as e:
                    print(f'  картку сервер не взяв ({e.code}) — довідка без неї', flush=True)
            status, _ = zapyt(server, kliuch, 'PUT', f'/api/vnutr/dovidka/{d["id"]}', f.read_bytes(), 'text/html; charset=utf-8')
            print(f'  готово за {time.time() - pochatok:.0f} с, сервер: {status}', flush=True)
    return len(dovidky)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description='Видавач довідок сервера продажу (ZAVDANNYA-99)')
    ap.add_argument('--server', required=True, help='адреса сайту, напр. https://moya-vulytsya.ua')
    ap.add_argument('--dani-edrsr', type=Path, default=KORIN.parent / 'dani-edrsr', help='тека dani-edrsr (генератор)')
    ap.add_argument('--generator', type=Path, help='шлях до zibraty.py (за замовчуванням — <dani-edrsr>/src/zvit/zibraty.py)')
    ap.add_argument('--raz', action='store_true', help='один обхід черги і вихід (для перевірки або планувальника)')
    ap.add_argument('--pauza', type=int, default=20, help='секунд між перевірками порожньої черги')
    ap.add_argument('--shi', action='store_true', help='перекази ШІ в довідці (генератор --shi; змінна ZVIT_SHI_KOMANDA)')
    ap.add_argument('--do-porozhnoi', action='store_true',
                    help='брати, доки черга не спорожніє, і вийти (GitHub Actions: один запуск забирає всю чергу)')
    ap.add_argument('--maks-khvylyn', type=float, default=40, help='з --do-porozhnoi: не брати нових після стількох хвилин')
    a = ap.parse_args(argv)
    kliuch = os.environ.get('VYDACHA_KLIUCH')
    if not kliuch:
        ap.error('немає змінної VYDACHA_KLIUCH (ключ видавача — той самий, що секрет Workers)')
    generator = a.generator or a.dani_edrsr / 'src' / 'zvit' / 'zibraty.py'
    if not generator.exists():
        ap.error(f'немає генератора: {generator}')
    pochatok, vsogo, zbii = time.time(), 0, 0
    while True:
        try:
            vziato = odyn_obkhid(a.server, kliuch, generator, a.shi)
            zbii = 0
        except OSError as err:   # мережа, сервер недоступний — спробувати згодом
            print(f'сервер не відповів: {err}', flush=True)
            vziato, zbii = 0, zbii + 1
        vsogo += vziato
        if a.raz:
            return 0
        if a.do_porozhnoi:
            # Черга порожня (або сервер тричі поспіль не відповів, або вийшов час) — вихід; недороблене підхопить
            # наступний запуск: сервер штовхає GitHub після кожної оплати, а розклад Workers — кожні 10 хв.
            if (not vziato and zbii == 0) or zbii >= 3 or time.time() - pochatok > a.maks_khvylyn * 60:
                print(f'видано за запуск: {vsogo}', flush=True)
                return 0 if zbii < 3 else 1
            if not vziato:
                time.sleep(min(a.pauza, 10))
            continue
        if not vziato:
            time.sleep(a.pauza)


if __name__ == '__main__':
    sys.exit(main())
