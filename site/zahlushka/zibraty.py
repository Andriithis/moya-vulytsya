"""Збирання заглушки «Моя вулиця» в окрему теку, готову до розміщення.

Що робить:
  * копіює сторінки, стилі, скрипти й шрифти з site/zahlushka/ у вихідну теку
    (за замовчуванням _site/zahlushka/, вона в .gitignore);
  * створює config.js зі змінних середовища
        MV_SUPABASE_URL                — адреса сховища (https://<проєкт>.supabase.co)
        MV_SUPABASE_PUBLICHNYI_KLYUCH  — публічний ключ (anon / publishable)
    ключ ніколи не пишеться у файли репозиторію, лише у зібрану теку;
  * підставляє значення замість місць у квадратних дужках ([ВЛАСНИК] тощо)
    з файлу --zapovnennya (JSON: {"ВЛАСНИК": "...", ...});
  * звужує дозвіл на з'єднання (Content-Security-Policy) до однієї адреси сховища.

Режим --dlya-publikatsiyi падає, якщо:
  * не задано адресу або ключ сховища, або адреса не https://<проєкт>.supabase.co;
  * ключ схожий на секретний (service_role, sb_secret_) — такий ключ у сторінці
    дав би будь-кому право читати й видаляти заявки;
  * у будь-якій сторінці лишилося незаповнене місце в квадратних дужках
    (ім'я власника внизу, [КОНТАКТ], [СЕРВІС І КРАЇНА ЗБЕРІГАННЯ] у політиці…).

Приклад (перегляд у себе, без сховища):
    python site/zahlushka/zibraty.py
Приклад (для публікації):
    MV_SUPABASE_URL=... MV_SUPABASE_PUBLICHNYI_KLYUCH=... \\
    python site/zahlushka/zibraty.py --dlya-publikatsiyi --zapovnennya zapovnennya.json
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import re
import shutil
import sys
from pathlib import Path

DZHERELO = Path(__file__).resolve().parent
KORIN = DZHERELO.parents[1]
FAILY = ['index.html', 'polityka.html', 'zrazok.html', 'styli.css', 'zrazok.css',
         'nadsylannya.js', 'storinka.js',
         # ZAVDANNYA-06: оферта, звернення, встановлення на телефон
         'oferta.html', 'zvernennya.html', 'zvernennya.js', 'vstanovlennya.js',
         'manifest.webmanifest', 'sw.js']
STORINKY = ['index.html', 'polityka.html', 'zrazok.html', 'oferta.html', 'zvernennya.html']
# Ціни з MV-11 — ОДНЕ місце для оферти: у тексті оферти стоять {{tsina.analiz}} і {{tsina.pidpyska}}.
# Змінили ціну рішенням MV — змінити тут і на головній (перевірка test_zahlushka звіряє все з RISHENNYA.md).
TSINY = {'analiz': 690, 'pidpyska': 299}
ZMINNA = re.compile(r'\{\{[^{}]*\}\}')
# Робочий файл кешу: маркери, які підставляє збирання.
SW_VERSIYA = "/*VERSIYA*/'rozrobka'"
SW_FAILY = "/*FAILY*/['./', 'index.html']"
MISTSE = re.compile(r"\[[А-ЯІЇЄҐ][А-ЯІЇЄҐ ,'’-]*\]")
ADRESA_SUPABASE = re.compile(r'^https://[a-z0-9]{10,40}\.supabase\.co$')
CSP_ZAHLUSHKA = 'connect-src \'self\' https://*.supabase.co'


class PomylkaZbyrannya(Exception):
    pass


def rol_klyucha(klyuch: str) -> str | None:
    """Повертає роль зі старого ключа-JWT (anon / service_role) або None."""
    chastyny = klyuch.split('.')
    if len(chastyny) != 3:
        return None
    try:
        dani = chastyny[1] + '=' * (-len(chastyny[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(dani)).get('role')
    except (ValueError, json.JSONDecodeError):
        return None


def klyuch_sekretnyi(klyuch: str) -> bool:
    return klyuch.startswith('sb_secret_') or rol_klyucha(klyuch) == 'service_role'


def zibraty(vykhid: Path, adresa: str, klyuch: str, zapovnennya: dict[str, str],
            dlya_publikatsiyi: bool) -> list[str]:
    """Збирає сайт. Повертає список незаповнених місць (порожній — усе заповнено)."""
    adresa = adresa.strip().rstrip('/')
    klyuch = klyuch.strip()
    if klyuch and klyuch_sekretnyi(klyuch):
        raise PomylkaZbyrannya('Це секретний ключ (service_role / sb_secret_). '
                               'У сторінку можна класти лише публічний ключ.')
    if dlya_publikatsiyi:
        if not adresa or not klyuch:
            raise PomylkaZbyrannya('Не задано MV_SUPABASE_URL або MV_SUPABASE_PUBLICHNYI_KLYUCH.')
        if not ADRESA_SUPABASE.match(adresa):
            raise PomylkaZbyrannya(f'Адреса сховища має бути https://<проєкт>.supabase.co, а не {adresa!r}.')

    if vykhid.exists():
        shutil.rmtree(vykhid)
    (vykhid / 'shryfty').mkdir(parents=True)
    for nazva in FAILY:
        shutil.copy2(DZHERELO / nazva, vykhid / nazva)
    for shryft in sorted((DZHERELO / 'shryfty').iterdir()):
        shutil.copy2(shryft, vykhid / 'shryfty' / shryft.name)
    (vykhid / 'ikony').mkdir()
    for ikona in sorted((DZHERELO / 'ikony').glob('*.png')):
        shutil.copy2(ikona, vykhid / 'ikony' / ikona.name)

    nezapovneni: list[str] = []
    for nazva in STORINKY:
        shlyakh = vykhid / nazva
        tekst = shlyakh.read_text(encoding='utf-8')
        for mistse, znachennya in zapovnennya.items():
            znachennya = str(znachennya).strip()
            if znachennya:
                tekst = tekst.replace(f'[{mistse}]', html.escape(znachennya))
        for nazva_tsiny, tsina in TSINY.items():
            tekst = tekst.replace('{{tsina.' + nazva_tsiny + '}}', str(tsina))
        zalyshky = sorted(set(ZMINNA.findall(tekst)))
        if zalyshky:
            raise PomylkaZbyrannya(f'{nazva}: невідомі змінні {zalyshky}')
        if adresa and CSP_ZAHLUSHKA in tekst:
            tekst = tekst.replace(CSP_ZAHLUSHKA, f"connect-src 'self' {adresa}")
        shlyakh.write_text(tekst, encoding='utf-8')
        for m in sorted(set(MISTSE.findall(tekst))):
            nezapovneni.append(f'{nazva}: {m}')

    if adresa and klyuch:
        config = ('// Створено zibraty.py під час збирання. У git не потрапляє.\n'
                  'window.MV_CONFIG = ' + json.dumps(
                      {'adresaSkhovyshcha': adresa, 'publichnyiKlyuch': klyuch},
                      ensure_ascii=False, indent=2) + ';\n')
        (vykhid / 'config.js').write_text(config, encoding='utf-8')
    else:
        shutil.copy2(DZHERELO / 'config.example.js', vykhid / 'config.js')

    zibraty_sw(vykhid)

    if dlya_publikatsiyi and nezapovneni:
        raise PomylkaZbyrannya('Незаповнені місця — публікувати не можна:\n  ' + '\n  '.join(nezapovneni))
    return nezapovneni


def zibraty_sw(vykhid: Path) -> None:
    """Підставляє в sw.js перелік файлів для кешу і версію — відбиток усіх файлів."""
    sw = vykhid / 'sw.js'
    tekst = sw.read_text(encoding='utf-8')
    if SW_VERSIYA not in tekst or SW_FAILY not in tekst:
        raise PomylkaZbyrannya('sw.js: не знайдено місць для версії і переліку файлів.')
    faily = sorted(str(p.relative_to(vykhid)).replace(os.sep, '/') for p in vykhid.rglob('*')
                   if p.is_file() and p.name != 'sw.js')
    vidbytok = hashlib.sha256()
    for f in faily:
        vidbytok.update(f.encode() + b'\0' + (vykhid / f).read_bytes())
    tekst = tekst.replace(SW_VERSIYA, json.dumps(vidbytok.hexdigest()[:12]))
    tekst = tekst.replace(SW_FAILY, json.dumps(['./'] + faily, ensure_ascii=False))
    sw.write_text(tekst, encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description='Зібрати заглушку «Моя вулиця».')
    p.add_argument('--vykhid', type=Path, default=KORIN / '_site' / 'zahlushka')
    p.add_argument('--zapovnennya', type=Path, help='JSON зі значеннями для місць у квадратних дужках')
    p.add_argument('--dlya-publikatsiyi', action='store_true', help='сувора перевірка перед публікацією')
    a = p.parse_args(argv)
    zapovnennya = {}
    if a.zapovnennya:
        zapovnennya = json.loads(a.zapovnennya.read_text(encoding='utf-8'))
    try:
        nezapovneni = zibraty(a.vykhid, os.environ.get('MV_SUPABASE_URL', ''),
                              os.environ.get('MV_SUPABASE_PUBLICHNYI_KLYUCH', ''),
                              zapovnennya, a.dlya_publikatsiyi)
    except PomylkaZbyrannya as e:
        print('ЗБИРАННЯ ЗУПИНЕНО:', e, file=sys.stderr)
        return 1
    print(f'Зібрано в {a.vykhid}')
    if nezapovneni:
        print('Увага, ще не заповнено (для перегляду можна, для публікації — ні):')
        for n in nezapovneni:
            print('  ', n)
    return 0


if __name__ == '__main__':
    sys.exit(main())
