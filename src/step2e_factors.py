# -*- coding: utf-8 -*-
"""Крок 2e. Шар чинників середовища для карти.

Витягає з osm_risks_raw.json координати тих об'єктів, які модель ризику
(крок 4) рахує як ознаки, і складає компактний data/factors.json.
Сам osm_risks_raw.json на карту не годиться — він важить десятки мегабайт.

Дерева, трава й лавки свідомо не входять: їх на порядок більше за решту,
а ваги в моделі мізерні — карта стала б важкою без користі для аналізу.

Групування — за криміналістичною роллю об'єкта, а не за абеткою:
  0) притягують правопорушення — місця, куди люди йдуть по те, що створює привід;
  1) збирають людей — генератори потоку, самі по собі не «погані»;
  2) стан середовища — ознаки занедбаності або, навпаки, догляду.
Свідомо НЕ підписуємо «підвищує/знижує ризик»: напрямок впливу видно з ваги
в engine_report.json, і він буває несподіваним (напр., дитячі майданчики за
даними моделі ризик наркотиків підвищують).
"""
import os, sys, json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
RAW  = os.path.join(DATA, 'osm_risks_raw.json')
OUT  = os.path.join(DATA, 'factors.json')

# ключ у RAW | назва для людей | база ознаки в моделі (як у step4_engine.NAMES) | група
CATS = [
    ('bar_on',   'Бари, клуби',                 'бари',           0),
    ('bar_off',  'Алкоголь на винос',           'алкоголь_винос', 0),
    ('shop24',   'Магазини біля дому, фастфуд', 'магазини',       0),
    ('food',     'Кафе, ресторани',             'кафе',           0),
    ('finance',  'Ломбарди, обмінники',         'ломбарди',       0),
    ('gambling', 'Гральні заклади',             'гральні',        0),
    ('fuel',     'АЗС',                         'АЗС',            0),
    ('school',   'Школи, садки',                'школи',          1),
    ('univer',   'ВНЗ',                         'ВНЗ',            1),
    ('health',   'Лікарні, аптеки',             'лікарні',        1),
    ('market',   'Ринки, ТЦ',                   'ринки',          1),
    ('metro',    'Метро, вокзали',              'метро',          1),
    ('busstop',  'Зупинки транспорту',          'зупинки',        1),
    ('play',     'Дитячі майданчики',           'майданчики',     1),
    ('abandon',  'Покинуті будівлі',            'покинуті',       2),
    ('parking',  'Відкриті паркінги',           'паркінги',       2),
    ('cctv',     'Камери спостереження',        'камери',         2),
]
GROUPS = ['Притягують правопорушення', 'Збирають людей', 'Стан середовища']

def main():
    if not os.path.exists(RAW):
        print('немає data/osm_risks_raw.json — спершу крок 2b')
        sys.exit(1)
    raw = json.load(open(RAW, encoding='utf-8'))
    out, total = [], 0
    for key, name, base, grp in CATS:
        pts = []
        for el in raw.get(key, []):
            la = el.get('lat') or (el.get('center') or {}).get('lat')
            lo = el.get('lon') or (el.get('center') or {}).get('lon')
            if la and lo:
                pts.append([round(la, 5), round(lo, 5)])
        out.append({'k': key, 'n': name, 'b': base, 'g': grp, 'pts': pts})
        total += len(pts)
        print(f'   {name:30} {len(pts):6,}')
    json.dump({'groups': GROUPS, 'cats': out},
              open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print(f"\n=== ГОТОВО === {total:,} об'єктів -> data/factors.json "
          f'({os.path.getsize(OUT)/1048576:.1f} МБ)')

if __name__ == '__main__':
    main()
