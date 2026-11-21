# -*- coding: utf-8 -*-
"""Випуск із Release dani-edrsr — у робочий файл для видавача довідок і листа «Стежу» (ZAVDANNYA-195).

  gh release download <тег> -R Andriithis/dani-edrsr --pattern '<шаблон>' --dir <тека>     (див. vydavach.yml)
  python site/prodazh/vypusk_z_release.py <тека> <вихід.db> [--povnyi]

З 21.11.2026 у Release лише стиснуті файли (`events-<дата>.db.xz` ≈ 340 МБ і вузький `vuzkyi-events-<дата>.db.xz` ≈ 92 МБ,
ZVIT-191). Видавач і лист беруть **вузький** (MV-159: генератору досить вузького; усі поля, які він читає, у ньому є);
`--povnyi` — повний. Немає потрібного — береться той, що є: стиснутий чи ні (старі випуски — `events-<дата>.db`).
Розпаковується потоком (lzma зі стандартної бібліотеки, без `xz` у системі) у `<вихід>.chast`, потім перейменовується:
обірване розпакування не лишає «готового» файла. Нічого не публікує.
"""
from __future__ import annotations

import argparse
import lzma
import os
import shutil
import sqlite3
import sys
from pathlib import Path

VUZKYI = ('vuzkyi-events-*.db.xz', 'vuzkyi-events-*.db', 'events-*.db.xz', 'events-*.db')
POVNYI = ('events-*.db.xz', 'events-*.db', 'vuzkyi-events-*.db.xz', 'vuzkyi-events-*.db')


class Zupynka(Exception):
    pass


def vybraty(teka: Path, povnyi: bool = False) -> Path:
    """Файл випуску в теці: за порядком шаблонів, серед однакових — найновіший за назвою (дата в назві)."""
    for shablon in (POVNYI if povnyi else VUZKYI):
        z = sorted(p for p in teka.glob(shablon) if p.is_file())
        if z:
            return z[-1]
    raise Zupynka(f'У {teka} немає файла випуску ({", ".join(VUZKYI)})')


def rozpakuvaty(dzherelo: Path, vykhid: Path) -> Path:
    chast = vykhid.with_name(vykhid.name + '.chast')
    if dzherelo.suffix == '.xz':
        with lzma.open(dzherelo, 'rb') as f, open(chast, 'wb') as g:
            shutil.copyfileobj(f, g, 1 << 20)
    else:
        shutil.copyfile(dzherelo, chast)
    try:                                    # битий чи не той файл — зупинка тут, а не в генераторі
        con = sqlite3.connect(f'file:{chast}?mode=ro', uri=True)
        versiia = con.execute('SELECT versiia FROM release').fetchone()
        con.close()
    except sqlite3.DatabaseError as e:
        chast.unlink(missing_ok=True)
        raise Zupynka(f'{dzherelo.name}: не база випуску ({e})') from e
    if not versiia:
        chast.unlink(missing_ok=True)
        raise Zupynka(f'{dzherelo.name}: у таблиці release немає версії')
    os.replace(chast, vykhid)
    return vykhid


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('teka', type=Path, help='тека, куди gh release download склав файли')
    ap.add_argument('vykhid', type=Path, help='робочий файл бази, напр. _dani/vypusk.db')
    ap.add_argument('--povnyi', action='store_true', help='повний випуск замість вузького')
    a = ap.parse_args(argv)
    try:
        f = vybraty(a.teka, a.povnyi)
        rozpakuvaty(f, a.vykhid)
    except Zupynka as e:
        print(f'Зупинка: {e}', file=sys.stderr)
        return 1
    print(f'{f.name} -> {a.vykhid} ({a.vykhid.stat().st_size / 1e6:.0f} МБ)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
