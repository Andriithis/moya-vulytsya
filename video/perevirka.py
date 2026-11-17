"""Перевірка сценарію ролика перед рендером (ZAVDANNYA-11).

Запуск: python video/perevirka.py video/stsenarii/*.json [--koloda шлях/koloda-2026-11-08.json]
Рендер (video/rendery.py) викликає цю перевірку сам і не рендерить сценарій із зауваженнями.

Що перевіряємо (AGENTS.md розд. 4–5, MV-4, MV-12, MV-24, ZAVDANNYA-11 п. 4–5):
- текст точки до 140 знаків; у тексті немає «небезпечно», «безпечно», «рейтинг», «страшно»;
- немає слідів імен і номерів із рішень (ОСОБА_, НОМЕР_, «кв.»), немає категорій MV-4;
- точка — у межах Києва; є посилання на рішення (для подій);
- загальна тривалість 20–35 с; «Тур» — 4–5 подій; «Вгадай» — пауза 3 с; «Цифри» — 3 факти.
- MV-60: номер будинку на екрані — лише для публічного місця (поле typ_mistsia, правило —
  brend/adresa_pokazu.py); кожна подія — з номером рішення; рендер показує лише підготовлений
  сценарій (pidhotuvaty), тож номер прибирається кодом, а не вручну.
З --koloda: подія є в колоді, координати й номер рішення збігаються, категорія не з MV-4.

Шаблони ZAVDANNYA-94 (генератор video/heneruvaty.py, сім груп MV-111):
- кожен ролик закінчується посиланням на сторінку цього місця (kinets.posylannia, MV-106) — не на головну;
- «Одна історія» (istoriia): 2–3 картки — лише переказ ШІ, що пройшов перевірку програмою (perekaz_perevirka: без
  цифр, дат, імен, марок авто, мови суду й уривків рішення; MV-21, MV-25); одна точка в Києві з номером рішення;
- «Що болить вулиці» (shcho_bolyt): 2–4 факти числом, вулиця без номера будинку;
- «Таймлапс» (taimlaps): у сотах — лише числа (класи), без адрес; підпис років — з даних;
- «Переліт» (perelit): зупинки в межах України, остання — у Києві;
- «Картки» (kartky): 2–5 карток з числами;
- тривалість нових шаблонів — 20–40 с; текст для голосу (holos) — ті самі заборони, що й на екрані.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'brend'))
from adresa_pokazu import PUBLICHNI, adresa_dlia_pokazu, chutlyva, nevidomyi_typ  # noqa: E402

MEZHA = KORIN / 'site' / 'hra' / 'mezha-kyieva.geojson'

ZABORONENI = re.compile(r'небезпеч|безпечн|рейтинг|страшн|кримінальн\w* район', re.I)
SLIDY = re.compile(r'ОСОБА_|НОМЕР_|ІНФОРМАЦІЯ_|\bкв\.\s*\d|\bквартир', re.I)
MV4_SLOVA = re.compile(r'насильств|статев|зґвалт|розбещ|неповнолітн|малолітн|дитин|педофіл', re.I)
MV4_KATEGORII = {'domashnie_nasylstvo', 'statevi', 'dity', 'shchodo_ditei', 'nasylstvo'}
SHABLONY = {'tur', 'vhadai', 'tsyfry', 'istoriia', 'shcho_bolyt', 'kartky', 'perelit', 'taimlaps'}
NOVI = {'istoriia', 'shcho_bolyt', 'kartky', 'perelit', 'taimlaps'}
# Сторінки, на які може вести ролик (MV-106, KOMPAS розд. 0: на конкретне місце чи вітрину лінії, не на головну).
SHLIAKHY = ('/vulytsia/', '/rayon/', '/rayony/', '/budynok/', '/miy-budynok/', '/osbb/', '/sudova-praktyka/', '/biznes/',
            '/karta/', '/zahlushka/hra/', '/pro-dani/', '/dlia-media/')
UKRAINA = (22.0, 44.3, 40.3, 52.5)   # lon0, lat0, lon1, lat1
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


def nomer_rishennya(p):
    """Номер рішення в ЄДРСР: поле rishennya_nomer або перша частина id події («128041647-1»)."""
    n = str(p.get('rishennya_nomer') or str(p.get('id', '')).split('-')[0])
    return n if n.isdigit() else ''


def pidhotuvaty(S):
    """Сценарій, як його побачить людина (MV-60): адреса — за правилом номера будинку,
    у кожної події — номер рішення. Лише такий сценарій віддає сцені рендер."""
    S = json.loads(json.dumps(S))
    for p in S.get('tochky', []):
        if p.get('adresa'):
            p['adresa'] = adresa_dlia_pokazu(p['adresa'], p.get('typ_mistsia'), chutlyva(p.get('vyd'), p.get('tekst')))
        if S.get('shablon') != 'tsyfry':
            p['rishennya_nomer'] = nomer_rishennya(p)
    c = S.get('tsentr')
    if c and c.get('adresa'):
        c['adresa'] = adresa_dlia_pokazu(c['adresa'], c.get('typ_mistsia'))
    S['pidhotovano'] = True
    return S


def _teksty(S):
    """Усі рядки, які потрапляють на екран або в голос."""
    for blok in ('vstup', 'kinets', 'vershyny'):
        for k in ('mitka', 'tekst', 'pidtekst', 'pidpys', 'holos'):
            if (S.get(blok) or {}).get(k):
                yield f'{blok}.{k}', S[blok][k]
    for i, p in enumerate(S.get('tochky', []) + S.get('periody', [])):
        for k in ('tekst', 'adresa', 'vyd', 'koly', 'chyslo', 'mitka', 'pidpys', 'pidtekst', 'holos', 'holos_pytannya', 'holos_vidpovid'):
            if p.get(k):
                yield f'tochky[{i}].{k}', str(p[k])
        for j, t in enumerate(p.get('karty', [])):
            yield f'tochky[{i}].karty[{j}]', t
        for j, t in enumerate(p.get('holos') if isinstance(p.get('holos'), list) else []):
            yield f'tochky[{i}].holos[{j}]', t
    if S.get('tsentr', {}).get('adresa'):
        yield 'tsentr.adresa', S['tsentr']['adresa']


def tryvalist(S):
    t = S['vstup']['tryvalist'] + S['kinets']['tryvalist'] + (S.get('vershyny') or {}).get('tryvalist', 0)
    for p in S.get('tochky', []) + S.get('periody', []):
        t += (sum(p['tryvalosti']) if p.get('tryvalosti') else p['tryvalist']) + p.get('pytannya', 0) + p.get('pauza', 0)
    return t


def _perekaz():
    """Перевірка переказу ШІ — та сама, що для історій вулиць на сайті (копія dani-edrsr/src/perekaz_perevirka.py)."""
    sys.path.insert(0, str(KORIN / 'site' / 'sait'))
    import perekazy
    return perekazy.vady


def pereviryty_novyi(S, zauv):
    sh, tochky = S['shablon'], S.get('tochky', [])
    pos = str((S.get('kinets') or {}).get('posylannia', ''))
    if not pos.startswith('https://'):
        zauv('kinets.posylannia: ролик має закінчуватися посиланням на сторінку цього місця (MV-106)')
    elif not any(sh_ in pos for sh_ in SHLIAKHY):
        zauv(f'kinets.posylannia: {pos} — не сторінка місця чи вітрина лінії (не на головну)')
    if sh == 'istoriia':
        if len(tochky) != 1:
            zauv('«Одна історія» — одна точка')
        for i, p in enumerate(tochky):
            karty = p.get('karty') or []
            if not 2 <= len(karty) <= 3:
                zauv(f'tochky[{i}]: 2–3 картки переказу, а є {len(karty)}')
            if p.get('dzherelo_tekstu') != 'perekaz_shi':
                zauv(f'tochky[{i}]: текст історії — лише переказ ШІ (dzherelo_tekstu = perekaz_shi, MV-21)')
            vady = _perekaz()(' '.join(karty))
            vady = [v for v in vady if v != 'довжина' or len(' '.join(karty)) < 40]
            if vady:
                zauv(f'tochky[{i}]: переказ не пройшов перевірку — {", ".join(vady)}')
            for j, k in enumerate(karty):
                if len(k) > MAKS_TEKST:
                    zauv(f'tochky[{i}].karty[{j}]: {len(k)} знаків, можна до {MAKS_TEKST}')
    if sh == 'shcho_bolyt':
        c = S.get('tsentr') or {}
        if not 2 <= len(tochky) <= 4:
            zauv(f'«Що болить вулиці» — 2–4 факти, а є {len(tochky)}')
        if not (c.get('nazva') and u_kyievi(c.get('lon', 0), c.get('lat', 0))):
            zauv('tsentr: немає назви вулиці або точки в Києві')
        if re.search(r',\s*\d', c.get('nazva', '')):
            zauv('tsentr.nazva: номер будинку в безкоштовному ролику (MV-25)')
        for i, p in enumerate(tochky):
            if not p.get('chyslo'):
                zauv(f'tochky[{i}]: немає числа')
    if sh == 'kartky' and not 2 <= len(tochky) <= 5:
        zauv(f'«Картки» — 2–5 карток, а є {len(tochky)}')
    if sh == 'perelit':
        for i, p in enumerate(tochky):
            if not (UKRAINA[0] <= p.get('lon', 0) <= UKRAINA[2] and UKRAINA[1] <= p.get('lat', 0) <= UKRAINA[3]):
                zauv(f'tochky[{i}]: зупинка поза Україною')
        if tochky and not u_kyievi(tochky[-1].get('lon', 0), tochky[-1].get('lat', 0)):
            zauv('остання зупинка перельоту — не в Києві')
    if sh == 'taimlaps':
        per, fc = S.get('periody') or [], S.get('soty') or {}
        if len(per) < 2:
            zauv('таймлапс — щонайменше 2 періоди')
        if not S.get('vershyny'):
            zauv('таймлапс — наприкінці 3D-вершини (vershyny)')
        for f in fc.get('features', []):
            if set(f.get('properties', {})) - {'k', 'v', 'q', 'h'}:
                zauv('у сотах таймлапсу — лише класи й висота, без адрес і описів (MV-3)')
                break
            if len(f['properties'].get('k', [])) != len(per):
                zauv('у соті класів не стільки, скільки періодів')
                break


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
    for i, p in enumerate(tochky + [S.get('tsentr') or {}]):
        if nevidomyi_typ(p.get('typ_mistsia')):
            zauv(f'typ_mistsia «{p["typ_mistsia"]}» невідомий; публічні: {", ".join(PUBLICHNI)}')
    for i, p in enumerate(tochky):
        if len(str(p.get('tekst', ''))) > MAKS_TEKST:
            zauv(f'tochky[{i}].tekst: {len(p["tekst"])} знаків, можна до {MAKS_TEKST}')
        if (not p.get('tryvalist') or p['tryvalist'] < 2) and not p.get('tryvalosti'):
            zauv(f'tochky[{i}]: тривалість не задана або менша за 2 с')
        if S['shablon'] in ('tur', 'vhadai', 'istoriia'):
            if not (isinstance(p.get('lat'), (int, float)) and isinstance(p.get('lon'), (int, float))):
                zauv(f'tochky[{i}]: немає координат')
            elif not u_kyievi(p['lon'], p['lat']):
                zauv(f'tochky[{i}]: точка поза межею Києва')
            if not str(p.get('rishennya_url', '')).startswith('https://'):
                zauv(f'tochky[{i}]: немає посилання на рішення')
            if not p.get('adresa'):
                zauv(f'tochky[{i}]: немає адреси')
            if not nomer_rishennya(p):
                zauv(f'tochky[{i}]: немає номера рішення (rishennya_nomer)')
    t = tryvalist(S)
    mezha = 40 if S['shablon'] in NOVI else 35
    if not 20 <= t <= mezha:
        zauv(f'тривалість {t:.1f} с, треба 20–{mezha} с')
    if S['shablon'] in NOVI:
        pereviryty_novyi(S, zauv)
        return z
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
            if e.get('rishennya_nomer') and str(e['rishennya_nomer']) != nomer_rishennya(p):
                zauv(f'tochky[{i}]: номер рішення не збігається з колодою')
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
