"""Перевірка правил кожної одиниці перед чергою й ще раз перед публікацією (ZAVDANNYA-107, п. 1).

Одиниця — один допис, вікторина, картка або ролик для однієї мережі й одного каналу (поля й формат — `docs/AVTOPOSTYNH.md`, розд. 8).
Що не пройшло — у чергу як «відхилено» з причинами (видно на сторінці-перегляді), у мережу не йде.

Правила (джерело — у дужках):
- номер житлового будинку в тексті — ні; лише для публічного місця й не чутливої справи (MV-25, MV-60,
  `brend/adresa_pokazu.py`);
- імена, ініціали, «ОСОБА_», номери справ — ні (KOMPAS, розд. 6; AGENTS, розд. 4);
- «небезпечн-», «безпечн-», рейтинги, «найгірший», «куди не ходити», страшилки — ні (AGENTS, розд. 4; KOMPAS, розд. 3а);
- чутливі справи (насильство, статеві, щодо дітей) — ні, як у грі й районних дописах (MV-69, MV-102, ZAVDANNYA-97);
- емодзі — ні (KOMPAS, розд. 6);
- рівно одне посилання на сайт — на сторінку того самого місця (будинок, вулиця, район, точка на карті) з
  `?dzherelo=<мережа>` (MV-5, KOMPAS, розд. 0 і 5);
- одиниця з подіями — з номером рішення й «лише те, що дійшло до суду» (MV-60);
- чернетка, яку ШІ ще не переписав (MV-21, MV-25), — ні;
- межі довжини кожної мережі; файл ролика чи картки — є;
- подія чи місце, які Андрій уже прибирав, і подія, що виходила за останні 90 днів, — ні (ZAVDANNYA-107, п. 3).
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'brend'))
from adresa_pokazu import PUBLICHNI, chutlyva  # noqa: E402

MEREZHI = ('telegram', 'youtube', 'facebook', 'instagram', 'tiktok')

ZABORONENI = re.compile(
    r'небезпеч|безпечн|рейтинг|найгірш|найкримінальн|кримінальн\w* район|страшн|куди не ходи|топ[- ]?\d', re.I)
SLIDY = re.compile(r'ОСОБА_?\d*|НОМЕР_|ІНФОРМАЦІЯ_|\bкв\.\s*\d|\bквартир', re.I)
VELYKA = "А-ЯІЇЄҐ"
MALA = "а-яіїєґ'’ʼ"
# «Іваненко І. І.», «І.І. Іваненко», «гр. Іваненко», «суддя Іваненко»
IMIA = re.compile(
    rf"\b[{VELYKA}][{MALA}]+(?:-[{VELYKA}][{MALA}]+)?\s+[{VELYKA}]\.\s?[{VELYKA}]\.|"
    rf"\b[{VELYKA}]\.\s?[{VELYKA}]\.\s?[{VELYKA}][{MALA}]{{2,}}|"
    rf"\b(?:гр\.|громадян\w*|судд[яіею]\w*|обвинувачен\w*|потерпіл\w*)\s+[{VELYKA}][{MALA}]{{2,}}")
NOMER_SPRAVY = re.compile(r'\b\d{1,4}/\d{2,7}/\d{2}\b|справ[аиі]\s*№', re.I)
CHUTLYVI = re.compile(r'насильств|статев|зґвалт|згвалт|сексуал|розбещ|неповнолітн|малолітн|дитин|дітей|педофіл', re.I)
CHUTLYVI_KATEGORII = {'domashnie_nasylstvo', 'nasylstvo_domashnie', 'nasylstvo', 'statevi', 'statevi_zlochyny', 'dity',
                      'shchodo_ditei'}
# Номер будинку в тексті: «буд. 5», «будинку 12», «вул. Х, 42», «Хрещатик, 22», «кв. 3».
NOMER_BUDYNKU = re.compile(
    rf"буд\w*\.?\s*№?\s*\d|"
    rf"\b(?:вул|вулиц\w*|просп|проспект\w*|бульв|бульвар\w*|пров|провул\w*|пл|площ\w*|узвіз\w*|шосе|наб)\.?\s+[^,;\n]{{1,50}},\s*\d|"
    rf"\b[{VELYKA}][{MALA}]+,\s*\d{{1,3}}(?![\d.,:])(?:-?[А-ЯA-Z](?![{MALA}]))?(?:/\d{{1,3}})?"
    rf"(?!\s*(?:грн|р\.|%)|\s+(?!корп|під'?їзд|буд)[{MALA}]{{2,}})",
    re.I)
EMODZI = re.compile('[\U0001F000-\U0001FAFF☀-➿⬀-⯿️]')
LYSHE_SUD = 'лише те, що дійшло до суду'
# Сторінка конкретного місця на сайті (site/zibraty_sait.py, site/storinky_mv100.py).
MISTSE_URL = re.compile(r'^/(?:budynok/[^?#]+/|vulytsia/[^/?#]+/|rayon/[^/?#]+/|karta/)$')
URL = re.compile(r'https?://[^\s<>"\')]+')

# Межі мереж (символів). Telegram: текст 4096, підпис до файлу 1024, вікторина 300/100/200 (Bot API).
# YouTube: назва 100, опис 5000. Instagram і TikTok: підпис 2200. Facebook: з запасом 5000.
MEZHI = {
    'telegram': {'tekst': 4096, 'pidpys': 1024, 'pytannia': 300, 'varianty': 100, 'poiasnennia': 200},
    'youtube': {'nazva': 100, 'tekst': 5000},
    'facebook': {'tekst': 5000},
    'instagram': {'tekst': 2200},
    'tiktok': {'tekst': 2200},
}
MAKS_FAIL_MB = {'telegram': 50, 'youtube': 2048, 'facebook': 1024, 'instagram': 300, 'tiktok': 1024}
DNIV_BEZ_POVTORU = 90


def mitka(merezha: str, kanal_slug: str = '') -> str:
    """Значення `?dzherelo=`: назва мережі, для районного каналу — ще й район (`telegram-pecherskyi`)."""
    return f'{merezha}-{kanal_slug}' if kanal_slug else merezha


def z_mitkoiu(url: str, dzherelo: str) -> str:
    """Посилання з тією самою адресою й лише однією міткою `?dzherelo=`."""
    s = urlsplit(url)
    return f'{s.scheme}://{s.netloc}{s.path}?dzherelo={dzherelo}' + (f'#{s.fragment}' if s.fragment else '')


def khesh_tekstu(t: str) -> str:
    return hashlib.sha1(re.sub(r'\W+', ' ', (t or '').lower()).strip().encode('utf-8')).hexdigest()[:16]


def teksty(o: dict) -> list[str]:
    """Усе, що побачить людина в мережі."""
    r = [o.get('nazva', ''), o.get('tekst', ''), o.get('pytannia', ''), o.get('poiasnennia', '')]
    r += list(o.get('varianty') or [])
    r += [k.get('tekst', '') for k in o.get('knopky') or []]
    return [x for x in r if x]


def posylannia_na_sait(o: dict, adresa_saitu: str) -> list[str]:
    hostyty = urlsplit(adresa_saitu).netloc
    vsi = [k['url'] for k in o.get('knopky') or [] if k.get('url')]
    if o.get('posylannia'):
        vsi.append(o['posylannia'])
    for t in teksty(o):
        vsi += URL.findall(t)
    return sorted({u.rstrip('.,;:') for u in vsi if urlsplit(u).netloc == hostyty})


def pereviryty(o: dict, adresa_saitu: str, teka_media: Path | None = None, zaboroneno: dict | None = None,
               nedavni_podii: set | None = None) -> list[str]:
    """Список порушень; порожній — можна публікувати."""
    zh = []
    merezha = o.get('merezha')
    if merezha not in MEREZHI:
        return [f'невідома мережа {merezha!r}']
    vse = '\n'.join(teksty(o))
    mistse = o.get('mistse') or {}
    chutlyva_sprava = chutlyva(vse) or o.get('kategoriia') in CHUTLYVI_KATEGORII
    if ZABORONENI.search(vse):
        zh.append(f'заборонене слово: «{ZABORONENI.search(vse).group(0)}»')
    if SLIDY.search(vse) or IMIA.search(vse):
        zh.append('схоже на ім\'я чи знеособлений слід із рішення')
    if NOMER_SPRAVY.search(vse):
        zh.append('номер справи')
    if CHUTLYVI.search(vse) or o.get('kategoriia') in CHUTLYVI_KATEGORII:
        zh.append('чутлива справа (MV-69, MV-102)')
    if NOMER_BUDYNKU.search(vse) and not (mistse.get('typ_mistsia') in PUBLICHNI and not chutlyva_sprava):
        zh.append(f'номер будинку в тексті: «{NOMER_BUDYNKU.search(vse).group(0)}» (MV-25, MV-60)')
    if EMODZI.search(vse):
        zh.append('емодзі')
    # посилання
    posyl = posylannia_na_sait(o, adresa_saitu)
    if len(posyl) != 1:
        zh.append(f'посилань на сайт {len(posyl)}, треба рівно одне — на сторінку місця')
    for u in posyl:
        s = urlsplit(u)
        q = parse_qs(s.query)
        if not MISTSE_URL.match(s.path):
            zh.append(f'посилання не на сторінку місця: {s.path}')
        elif mistse.get('shliakh') and s.path != mistse['shliakh']:
            zh.append(f'посилання на інше місце: {s.path}, а одиниця про {mistse["shliakh"]}')
        dz = q.get('dzherelo', [''])
        if len(dz) != 1 or not (dz[0] == merezha or dz[0].startswith(merezha + '-')):
            zh.append(f'мітка dzherelo={",".join(dz)} не відповідає мережі {merezha}')
        if set(q) - {'dzherelo'}:
            zh.append('зайві параметри в посиланні')
    if not mistse.get('shliakh'):
        zh.append('не вказано місце')
    # події
    if o.get('podii'):
        if LYSHE_SUD not in vse:
            zh.append(f'немає «{LYSHE_SUD}» (MV-60)')
        if not re.search(r'[Рр]ішення\s*№\s*\d{6,}', vse):
            zh.append('немає номера рішення (MV-60)')
    if o.get('chernetka') and not o.get('perepysano'):
        zh.append('чернетка: опис ще не переписав ШІ (MV-21, MV-25)')
    # довжина
    mezhi = MEZHI.get(merezha, {})
    pole_tekstu = 'pidpys' if merezha == 'telegram' and o.get('fail') else 'tekst'
    if len(o.get('tekst', '')) > mezhi.get(pole_tekstu, 10 ** 6):
        zh.append(f'текст довший за {mezhi[pole_tekstu]} знаків')
    for pole in ('nazva', 'pytannia', 'poiasnennia'):
        if pole in mezhi and len(o.get(pole, '')) > mezhi[pole]:
            zh.append(f'{pole} довше за {mezhi[pole]} знаків')
    if 'varianty' in mezhi and any(len(v) > mezhi['varianty'] for v in o.get('varianty') or []):
        zh.append(f'варіант вікторини довший за {mezhi["varianty"]} знаків')
    if o.get('typ') == 'vikteryna':
        if merezha != 'telegram':
            zh.append('вікторина — лише Telegram')
        if not 2 <= len(o.get('varianty') or []) <= 10 or not 0 <= o.get('pravylna', -1) < len(o.get('varianty') or []):
            zh.append('вікторина: 2–10 варіантів і правильний серед них')
    if merezha == 'youtube' and not o.get('nazva'):
        zh.append('немає назви ролика')
    # файл
    if o.get('typ') in ('rolyk', 'kartka'):
        if not o.get('fail'):
            zh.append('немає файлу')
        elif teka_media is not None:
            f = (teka_media / o['fail'])
            if not f.is_file():
                zh.append(f'файлу немає: {o["fail"]}')
            elif f.stat().st_size > MAKS_FAIL_MB[merezha] * 1024 * 1024:
                zh.append(f'файл більший за {MAKS_FAIL_MB[merezha]} МБ')
    if merezha in ('youtube', 'tiktok') and o.get('typ') != 'rolyk':
        zh.append(f'{merezha} — лише ролики')
    if merezha == 'instagram' and o.get('typ') not in ('rolyk', 'kartka'):
        zh.append('instagram — лише ролик або картка')
    # прибране раніше й повтори
    z = zaboroneno or {}
    for p in o.get('podii') or []:
        if p in z.get('podiia', {}):
            zh.append(f'подію {p} прибирали: {z["podiia"][p]}')
        if nedavni_podii and p in nedavni_podii:
            zh.append(f'подія {p} вже виходила за останні {DNIV_BEZ_POVTORU} днів')
    if o.get('pozytsiia') and o['pozytsiia'] in z.get('pozytsiia', {}):
        zh.append(f'цей ролик чи картку прибирали: {z["pozytsiia"][o["pozytsiia"]]}')
    if mistse.get('shliakh') in z.get('mistse', {}):
        zh.append(f'про це місце більше не пишемо: {z["mistse"][mistse["shliakh"]]}')
    if khesh_tekstu(o.get('tekst', '')) in z.get('tekst', {}):
        zh.append(f'такий самий текст прибирали: {z["tekst"][khesh_tekstu(o.get("tekst", ""))]}')
    return zh
