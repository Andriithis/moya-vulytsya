"""Заглушка роликів і карток для пробного режиму, поки генератора роликів (ZAVDANNYA-94) немає.

    python avtopostynh/zahlushka.py <тека>       # manifest.json + файли-замінники

Кладе по одному «ролику» на кожну групу компасу (MV-111) і дві картки. Файли — замінники (картинка-сота й
порожній відеофайл з підписом «заглушка»), щоб пройти весь шлях: розклад → перевірка → черга → «публікація» в теку →
сторінка-перегляд → «прибрати». Тексти — приклади за правилами, без справжніх подій; на справжні дані їх не виносити.
"""
from __future__ import annotations

import json
import struct
import sys
import zlib
from pathlib import Path

POZYTSII = [
    ('shcho_bolyt', '/vulytsia/khreshchatyk/', 'вулиця Хрещатик', 'Що болить Хрещатику за жовтень',
     'Скарги мешканців до 1551 за жовтень і події з рішень судів числом. Скарга — звернення, не перевірений факт.'),
    ('istorii', '/vulytsia/volodymyrska/', 'Володимирська вулиця', 'Одна вулиця — одна історія',
     'Історія з рішення суду, переказана простими словами. Рішення № 120000002 — лише те, що дійшло до суду.'),
    ('hry', '/vulytsia/prospekt-peremohy/', 'проспект Перемоги', 'Вгадай, де це було',
     'Три вулиці — одна правильна. Відповідь — на сторінці вулиці.'),
    ('shcho_buvaie', '/rayon/shevchenkivskyi/', 'Шевченківський район', 'Що буває за керування напідпитку',
     'Як вирішують суди Києва: частки рішень і строки. Без імен і без порад.'),
    ('zghory', '/rayon/pecherskyi/', 'Печерський район', 'Таймлапс: соти наростають',
     'Скільки подій з рішень судів у даних, рік за роком. Колір — кількість даних, а не оцінка місця.'),
    ('yak_pratsiuie', '/rayon/podilskyi/', 'Подільський район', 'Звідки ці дані',
     'Рішення судів з відкритого реєстру й скарги до 1551 — як ми перетворюємо їх на події й числа.'),
    ('istorii_z_danykh', '/rayon/obolonskyi/', 'Оболонський район', 'Що найчастіше крадуть у магазинах',
     'Історія з даних: що найчастіше фігурує в рішеннях про дрібні крадіжки. Візуал для медіа — на сторінці.'),
    ('istorii', '/vulytsia/sadova/', 'Садова вулиця', 'Що було на Садовій',
     'Ще одна історія з вулиці. Рішення № 120000003 — лише те, що дійшло до суду.'),
    ('hry', '/vulytsia/khreshchatyk/', 'вулиця Хрещатик', 'Яка з двох вулиць?',
     'Дві вулиці, одне число. Відповідь — на сторінці вулиці.'),
]


def png(shyryna=270, vysota=480) -> bytes:
    """Простий PNG кольору індиго — замінник картки."""
    ryad = b'\x00' + bytes((0x44, 0x47, 0xA6)) * shyryna
    dani = zlib.compress(ryad * vysota)

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', shyryna, vysota, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', dani) + chunk(b'IEND', b''))


def zrobyty(teka: Path) -> list[dict]:
    teka = Path(teka)
    (teka / 'rolyky').mkdir(parents=True, exist_ok=True)
    (teka / 'kartky').mkdir(parents=True, exist_ok=True)
    manifest = []
    for i, (hrupa, shliakh, nazva, zaholovok, pidpys) in enumerate(POZYTSII):
        f = f'rolyky/zahlushka-{i:02d}-{hrupa}.mp4'
        (teka / f).write_bytes(b'zahlushka: tut bude rolyk ZAVDANNYA-94')
        p = {'nazva': f'zahlushka-{i:02d}-{hrupa}', 'typ': 'rolyk', 'hrupa': hrupa, 'fail': f, 'zaholovok': zaholovok,
             'pidpys': f'[ЗАГЛУШКА] {pidpys}', 'mistse': {'shliakh': shliakh, 'nazva': nazva}, 'perepysano': True}
        if 'Рішення №' in pidpys:
            p['podii'] = [f'zahlushka-{i}']
        manifest.append(p)
    for i, (shliakh, nazva) in enumerate([('/vulytsia/khreshchatyk/', 'вулиця Хрещатик'),
                                          ('/vulytsia/prospekt-peremohy/', 'проспект Перемоги')]):
        f = f'kartky/zahlushka-tsyfry-{i}.png'
        (teka / f).write_bytes(png())
        manifest.append({'nazva': f'zahlushka-tsyfry-{i}', 'typ': 'kartka', 'hrupa': 'tsyfry', 'fail': f,
                         'pidpys': f'[ЗАГЛУШКА] Вулиця в цифрах: {nazva}. Число — скільки записів у даних, а не оцінка вулиці.',
                         'mistse': {'shliakh': shliakh, 'nazva': nazva}, 'perepysano': True})
    (teka / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    print(f'позицій: {len(zrobyty(Path(sys.argv[1])))}')
