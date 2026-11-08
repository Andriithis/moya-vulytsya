"""Перевірка сценарію ролика перед рендером (ZAVDANNYA-11).

Запуск: python video/perevirka.py video/stsenarii/*.json [--koloda шлях/koloda-2026-11-08.json]
Рендер (video/rendery.py) викликає цю перевірку сам і не рендерить сценарій із зауваженнями.

Що перевіряємо (AGENTS.md розд. 4–5, MV-4, MV-12, MV-24, ZAVDANNYA-11 п. 4–5):
- текст точки до 140 знаків; у тексті немає «небезпечно», «безпечно», «рейтинг», «страшно»;
- немає слідів імен і номерів із рішень (ОСОБА_, НОМЕР_, «кв.»), немає категорій MV-4;
- точка — у межах Києва; є посилання на рішення (для подій);
- загальна тривалість 20–35 с; «Тур» — 4–5 подій; «Вгадай» — пауза 3 с; «Цифри» — 3 факти.
З --koloda: подія є в колоді, координати збігаються, категорія не з MV-4.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
MEZHA = KORIN / 'site' / 'hra' / 'mezha-kyieva.geojson'

ZABORONENI = re.compile(r'небезпеч|безпечн|рейтинг|страшн|кримінальн\w* район', re.I)
SLIDY = re.compile(r'ОСОБА_|НОМЕР_|ІНФОРМАЦІЯ_|\bкв\.\s*\d|\bквартир', re.I)
MV4_SLOVA = re.compile(r'насильств|статев|зґвалт|розбещ|неповнолітн|малолітн|дитин|педофіл', re.I)
MV4_KATEGORII = {'domashnie_nasylstvo', 'statevi', 'dity', 'shchodo_ditei', 'nasylstvo'}
SHABLONY = {'tur', 'vhadai', 'tsyfry'}
MAKS_TEKST = 140


def _poligony():
    g = json.loads(MEZHA.read_text(encoding='utf-8'))['geometry']
    return g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]


def u_kyievi(lon, lat, _p=[]):
    if not _p:
        _p.extend(_poligony())
    for poly in _p:
        kilce, vseredyni = poly[0], False
        j = len(kilce) - 1
        for i in range(len(kilce)):
            xi, yi = kilce[i]
            xj, yj = kilce[j]
            if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                vseredyni = not vseredyni
            j = i
        if vseredyni:
            return True
    return False


def _teksty(S):
    """Усі рядки, які потрапляють на екран."""
    for blok in ('vstup', 'kinets'):
        for k in ('mitka', 'tekst', 'pidtekst'):
            if S.get(blok, {}).get(k):
                yield f'{blok}.{k}', S[blok][k]
    for i, p in enumerate(S.get('tochky', [])):
        for k in ('tekst', 'adresa', 'vyd', 'koly', 'chyslo'):
            if p.get(k):
                yield f'tochky[{i}].{k}', p[k]
    if S.get('tsentr', {}).get('adresa'):
        yield 'tsentr.adresa', S['tsentr']['adresa']


def tryvalist(S):
    t = S['vstup']['tryvalist'] + S['kinets']['tryvalist']
    for p in S['tochky']:
        t += p['tryvalist'] + p.get('pytannya', 0) + p.get('pauza', 0)
    return t


def pereviryty(S, imia='', koloda=None):
    z = []

    def zauv(s):
        z.append(f'{imia}: {s}')

    if S.get('shablon') not in SHABLONY:
        zauv(f'невідомий шаблон {S.get("shablon")!r}')
        return z
    for d, t in _teksty(S):
        if ZABORONENI.search(t):
            zauv(f'{d}: заборонене слово — {t!r}')
        if SLIDY.search(t):
            zauv(f'{d}: схоже на ім\'я чи номер із рішення — {t!r}')
        if MV4_SLOVA.search(t):
            zauv(f'{d}: категорія MV-4 — {t!r}')
    tochky = S.get('tochky', [])
    for i, p in enumerate(tochky):
        if len(p.get('tekst', '')) > MAKS_TEKST:
            zauv(f'tochky[{i}].tekst: {len(p["tekst"])} знаків, можна до {MAKS_TEKST}')
        if not p.get('tryvalist') or p['tryvalist'] < 2:
            zauv(f'tochky[{i}]: тривалість не задана або менша за 2 с')
        if S['shablon'] != 'tsyfry':
            if not (isinstance(p.get('lat'), (int, float)) and isinstance(p.get('lon'), (int, float))):
                zauv(f'tochky[{i}]: немає координат')
            elif not u_kyievi(p['lon'], p['lat']):
                zauv(f'tochky[{i}]: точка поза межею Києва')
            if not str(p.get('rishennya_url', '')).startswith('https://'):
                zauv(f'tochky[{i}]: немає посилання на рішення')
            if not p.get('adresa'):
                zauv(f'tochky[{i}]: немає адреси')
    t = tryvalist(S)
    if not 20 <= t <= 35:
        zauv(f'тривалість {t:.1f} с, треба 20–35 с')
    if S['shablon'] == 'tur' and not 4 <= len(tochky) <= 5:
        zauv(f'«Тур району» — 4–5 подій, а є {len(tochky)}')
    if S['shablon'] == 'vhadai':
        for i, p in enumerate(tochky):
            if p.get('pauza') != 3:
                zauv(f'tochky[{i}]: пауза «ваш варіант?» має бути 3 с')
            if not p.get('pytannya'):
                zauv(f'tochky[{i}]: немає тривалості питання')
    if S['shablon'] == 'tsyfry':
        c = S.get('tsentr') or {}
        if len(tochky) != 3:
            zauv(f'«Вулиця в цифрах» — 3 факти, а є {len(tochky)}')
        if not (c.get('adresa') and c.get('lat') and u_kyievi(c.get('lon', 0), c.get('lat', 0))):
            zauv('tsentr: немає адреси або точки в Києві')
        for i, p in enumerate(tochky):
            if not p.get('chyslo'):
                zauv(f'tochky[{i}]: немає числа')
    if koloda is not None and S['shablon'] != 'tsyfry':
        for i, p in enumerate(tochky):
            e = koloda.get(p.get('id'))
            if not e:
                zauv(f'tochky[{i}]: події {p.get("id")} немає в колоді')
                continue
            if (round(e['lat'], 6), round(e['lon'], 6)) != (round(p['lat'], 6), round(p['lon'], 6)):
                zauv(f'tochky[{i}]: координати не збігаються з колодою')
            if e.get('kategoriia') in MV4_KATEGORII:
                zauv(f'tochky[{i}]: категорія MV-4 {e["kategoriia"]}')
            if e.get('rishennya_url') != p.get('rishennya_url'):
                zauv(f'tochky[{i}]: посилання на рішення не збігається з колодою')
    return z


def main(argv):
    koloda = None
    if '--koloda' in argv:
        i = argv.index('--koloda')
        koloda = {e['id']: e for e in json.loads(Path(argv[i + 1]).read_text(encoding='utf-8'))['podii']}
        argv = argv[:i] + argv[i + 2:]
    if not argv:
        sys.exit(__doc__)
    vse = []
    for f in argv:
        S = json.loads(Path(f).read_text(encoding='utf-8'))
        z = pereviryty(S, Path(f).name, koloda)
        print(f'{Path(f).name}: {tryvalist(S):.1f} с, ' + ('гаразд' if not z else f'{len(z)} зауважень'))
        vse += z
    for s in vse:
        print('  ' + s)
    return 1 if vse else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
