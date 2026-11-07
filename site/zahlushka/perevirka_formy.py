"""Перевірка форми заглушки двічі на добу (ZAVDANNYA-02, п. 10; MV-8).

Що робить, по черзі (будь-який збій — код виходу 1, тобто червоний запуск):
  1. Додає тестову заявку і тестову подію тим самим шляхом, що й сторінка:
     REST-адреса сховища + ПУБЛІЧНИЙ ключ, канал «perevirka».
  2. Перевіряє, що публічним ключем ці рядки НЕ можна прочитати
     (якщо можна — витік: будь-хто прочитав би контакти).
  3. Читає їх СЕКРЕТНИМ ключем і перевіряє, що вони є.
  4. Видаляє всі рядки з каналом «perevirka» секретним ключем і перевіряє,
     що нічого не лишилося.

Звідки бере адресу і ключі (лише зі змінних середовища, ніколи з файлів):
  MV_ADRESA_SAITU                — якщо задано, адреса й публічний ключ беруться
                                   з опублікованого {сайт}/config.js, тобто
                                   точно ті самі, що в сторінці;
  MV_SUPABASE_URL                — інакше адреса сховища;
  MV_SUPABASE_PUBLICHNYI_KLYUCH  — інакше публічний ключ;
  MV_SUPABASE_SEKRETNYI_KLYUCH   — ключ service_role / sb_secret_ (секрет GitHub).

Лише стандартна бібліотека Python — нічого не треба встановлювати.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KANAL = 'perevirka'
CHAS_ODIKUVANNYA = 20


class Zbii(Exception):
    pass


def zaholovky(klyuch: str, prefer: str | None = None) -> dict[str, str]:
    z = {'apikey': klyuch, 'Content-Type': 'application/json', 'Accept': 'application/json'}
    if klyuch.startswith('eyJ'):
        z['Authorization'] = 'Bearer ' + klyuch
    if prefer:
        z['Prefer'] = prefer
    return z


def zapyt(metod: str, adresa: str, klyuch: str, tilo=None, prefer: str | None = None):
    dani = None if tilo is None else json.dumps(tilo).encode('utf-8')
    z = urllib.request.Request(adresa, data=dani, method=metod, headers=zaholovky(klyuch, prefer))
    try:
        with urllib.request.urlopen(z, timeout=CHAS_ODIKUVANNYA) as v:
            vmist = v.read().decode('utf-8')
            return v.status, (json.loads(vmist) if vmist.strip() else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')[:300]
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise Zbii(f'{metod} {adresa}: немає зв\'язку зі сховищем ({e})') from e


def z_saitu(sait: str) -> tuple[str, str]:
    """Читає адресу сховища і публічний ключ з опублікованого config.js."""
    adresa = sait.rstrip('/') + '/config.js'
    try:
        with urllib.request.urlopen(adresa, timeout=CHAS_ODIKUVANNYA) as v:
            tekst = v.read().decode('utf-8')
    except (urllib.error.URLError, OSError) as e:
        raise Zbii(f'Не вдалося прочитати {adresa}: {e}') from e
    m = re.search(r'window\.MV_CONFIG\s*=\s*(\{.*?\})\s*;', tekst, re.S)
    if not m:
        raise Zbii(f'У {adresa} немає window.MV_CONFIG')
    c = json.loads(m.group(1))
    return c['adresaSkhovyshcha'], c['publichnyiKlyuch']


def perevirka(url: str, publichnyi: str, sekretnyi: str, vyvid=print) -> None:
    rest = url.rstrip('/') + '/rest/v1/'
    filtr = '?kanal=eq.' + KANAL
    zayavka = {'shcho': 'povidomyty', 'misto': 'Перевірка', 'adresa': None,
               'kontakt': 'perevirka-formy', 'zghoda': True, 'kanal': KANAL}
    podiya = {'nazva': 'pryishly', 'kanal': KANAL}

    # 1. Додати публічним ключем — як сторінка.
    for tablytsya, ryadok in (('zayavka', zayavka), ('podiya', podiya)):
        kod, vidp = zapyt('POST', rest + tablytsya, publichnyi, ryadok, 'return=minimal')
        if kod not in (200, 201, 204):
            raise Zbii(f'Сторінка не змогла б додати рядок у {tablytsya}: {kod} {vidp}')
        vyvid(f'додано тестовий рядок у {tablytsya}')

    # 2. Публічний ключ не повинен читати.
    for tablytsya in ('zayavka', 'podiya'):
        kod, vidp = zapyt('GET', rest + tablytsya + filtr + '&select=id', publichnyi)
        if kod == 200 and vidp:
            raise Zbii(f'ВИТІК: публічним ключем видно рядки {tablytsya}. Негайно перевірте доступ у сховищі.')
        vyvid(f'публічним ключем {tablytsya} не читається ({kod})')

    # 3. Секретним ключем рядки видно.
    for tablytsya in ('zayavka', 'podiya'):
        kod, vidp = zapyt('GET', rest + tablytsya + filtr + '&select=id', sekretnyi)
        if kod != 200 or not vidp:
            raise Zbii(f'Тестового рядка в {tablytsya} немає: {kod} {vidp}')
        vyvid(f'тестовий рядок у {tablytsya} знайдено ({len(vidp)})')

    # 4. Видалити і переконатися, що нічого не лишилось.
    for tablytsya in ('zayavka', 'podiya'):
        kod, vidp = zapyt('DELETE', rest + tablytsya + filtr, sekretnyi, prefer='return=representation')
        if kod not in (200, 204):
            raise Zbii(f'Не вдалося видалити тестові рядки з {tablytsya}: {kod} {vidp}')
        kod, vidp = zapyt('GET', rest + tablytsya + filtr + '&select=id', sekretnyi)
        if kod != 200 or vidp:
            raise Zbii(f'Після видалення в {tablytsya} лишилися тестові рядки: {kod} {vidp}')
        vyvid(f'тестові рядки з {tablytsya} видалено')


def main() -> int:
    pochatok = time.monotonic()
    try:
        sait = os.environ.get('MV_ADRESA_SAITU', '').strip()
        if sait:
            url, publichnyi = z_saitu(sait)
        else:
            url = os.environ.get('MV_SUPABASE_URL', '').strip()
            publichnyi = os.environ.get('MV_SUPABASE_PUBLICHNYI_KLYUCH', '').strip()
        sekretnyi = os.environ.get('MV_SUPABASE_SEKRETNYI_KLYUCH', '').strip()
        if not url or not publichnyi or not sekretnyi:
            raise Zbii('Не задано адресу сховища, публічний або секретний ключ.')
        perevirka(url, publichnyi, sekretnyi)
    except Zbii as e:
        print('ПЕРЕВІРКА ФОРМИ НЕ ПРОЙШЛА:', e, file=sys.stderr)
        return 1
    print(f'Форма працює. Час перевірки: {time.monotonic() - pochatok:.1f} с')
    return 0


if __name__ == '__main__':
    sys.exit(main())
