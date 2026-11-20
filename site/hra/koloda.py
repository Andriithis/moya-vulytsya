"""Колода гри «Вгадай, де це було» для збирання сайту (ZAVDANNYA-07).

Що робить:
  * читає файл колоди (формат — site/hra/koloda.schema.json);
  * відкидає події заборонених категорій MV-12 / MV-4 (статеві злочини, щодо дітей,
    домашнє насильство) — навіть якщо вони трапилися у файлі;
  * відкидає неповні події й події з координатами поза Києвом;
  * прибирає з описів «ОСОБА_N» (→ «особа») і дати; не вдалося — подію не бере (ZAVDANNYA-110, Б-4);
  * ZAVDANNYA-176 (ZVIT-168, №3): у гру — лише події, де в короткому описі є ознака місця (метро, магазин, зупинка,
    парк, міст…: `MISTSE`), інакше гра не має розв'язку; короткий опис — цілими реченнями (обрізаний «…» — до
    останнього цілого речення, немає — подію не беремо); події з потерпілими — поза грою, як межа «Літопису» (MV-165:
    опис показати не можна, а без опису вгадувати нічого); з повного опису — номери протоколів і хвіст «чим вчинив
    правопорушення, передбачене ст. …»; «пішохода особа» → «пішохода» (роль уже каже, хто це);
  * для публікації — не пропускає демо-колоду, події без посилання на рішення в реєстрі й описи з «ОСОБА_» чи датою.

Ті самі правила відсіву повторює сама гра (hra-yadro.js), тож заборонена подія
не з'явиться на екрані навіть з «сирого» файлу.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

DZHERELO = Path(__file__).resolve().parent
DEMO = DZHERELO / 'koloda-demo.json'

ZABORONENI_KATEHORII = frozenset({'statevi_zlochyny', 'shchodo_ditei', 'domashnie_nasylstvo'})
POLYA = ('id', 'vyd', 'kategoriia', 'rik', 'opys_korotkyi', 'opys_povnyi', 'adresa', 'lat', 'lon')
MEZHI = {'pivden': 50.21, 'pivnich': 50.60, 'zakhid': 30.23, 'skhid': 30.83}
ID_SPRAVZHNII = re.compile(r'^[0-9]{5,12}-[0-9]{1,3}$')
# Посилання на рішення — лише офіційний реєстр (doc_url з архівів data.gov.ua, MV-7): файл рішення
# od.reyestr…/files/<NN>/<32 знаки>.rtf (так у випуску й колоді з Release, ZAVDANNYA-110, Б-4) або сторінка Review/<номер>.
POSYLANNYA = re.compile(r'^https://(reyestr\.court\.gov\.ua/Review/[0-9]{5,12}'
                        r'|od\.reyestr\.court\.gov\.ua/files/[0-9]{1,3}/[0-9a-f]{32}\.rtf)$')
# Знеособлення реєстру й дати в описах (Б-4): «ОСОБА_1» → «особа», дата — геть; що лишилося — подію не беремо.
OSOBA = re.compile(r'ОСОБА_\d+')
DATA = re.compile(r'\b\d{1,2}\s?\.\s?\d{1,2}\s?\.\s?(?:\d{4}|\d{2})(?!\d)(?:\s*(?:року|р\.))?')
SLIDY = re.compile(r'[А-ЯІЇЄҐ]{3,}_\d|ОСОБА|\b\d{1,2}\s?\.\s?\d{1,2}\s?\.\s?\d{2,4}\b')
TEKSTY = ('opys_korotkyi', 'opys_povnyi')
# Ознака місця в описі (ZAVDANNYA-176): без неї гравець «тицяє в центр».
MISTSE = re.compile(r"метро|станці|вокзал|магазин|супермаркет|гіпермаркет|\bТЦ\b|\bТРЦ\b|торгов|ринк|ринок|аптек|парк|сквер|площ|"
                    r"зупинк|кафе|ресторан|\bбар\w*|кіоск|\bМАФ|пляж|набережн|мост|міст[уі]?\b|перехрест|тролейбус|автобус|трамва|"
                    r"фунікулер|\bАЗС\b|заправ|лікарн|школ|університет|стадіон|озер|острів|гідропарк|\bліс\w*|підземн|переход|тунел|"
                    r"естакад|розв.язк|автостоянк|парковк|стоянц|базар|аеропорт|причал|храм|церкв|собор|кладовищ|цвинтар", re.I)
# Види з потерпілими — як site/ihry/litopys/litopys.py, Z_POTERPILYMY (тест звіряє).
Z_POTERPILYMY = frozenset({'tilesni', 'hrabizh_rozbii', 'vbyvstvo', 'strilba', 'pohroza', 'dtp_poterpili',
                           'zhorstokist_do_tvaryn', 'nedopomoha', 'samoupravstvo'})
NE_PODIIA_NA_POCHATKU = re.compile(r'^(?:Відносно|Суду\s+надійшов|До\s+суду|Відповідно\s+до|Згідно|Із\s+протокол|З\s+протокол)', re.I)
KINETS_RECHENNIA = re.compile(r'[.!?](?=\s+[А-ЯІЇЄҐA-Z«"])')
PROTOKOL = re.compile(r'\s*,?\s*(?:(?:серії|серія)\s*:?\s*[A-ZА-ЯІЇЄҐ]{1,4}\s*\d*\s*(?:№\s*)?\d*(?![\wа-яіїєґ])|№\s*[A-ZА-ЯІЇЄҐ]{0,4}\s*\d{4,})')
KHVIST_KVAL = re.compile(r'[,;]?\s*(?:чим\s+|тим\s+самим\s+|і\s+|та\s+)?(?:вчинив|вчинил[аи]|скоїв|скоїл[аи]|вчинено)\s+'
                         r'(?:адміністративне\s+)?(?:право)?порушення\s*,?\s*(?:що\s+)?передбачен\w+\s+(?:ч\.\s*\d+\s*)?ст\.?\s*[\d-]+[^.]*', re.I)
ROL_OSOBA = re.compile(r'\b(водій|водія|водієві|пасажир\w*|пішохід|пішохода|пішоходу|потерпіл\w+|продав\w+|покуп\w+|охоронц?\w*|'
                       r'працівник\w*|власник\w*)\s+особ[аиуіою]\b', re.I)


def tsili_rechennia(t: str) -> str:
    '''Короткий опис, обрізаний посеред речення («…»), — до останнього цілого речення; немає — ''.'''
    t = (t or '').strip()
    if t.endswith('…'):
        kintsi = [m.end() for m in KINETS_RECHENNIA.finditer(t)]
        return t[:kintsi[-1]] if kintsi and kintsi[-1] >= 60 else ''
    return t if t[-1:] in '.!?»"' else ''


def dlia_vgadai(p: dict) -> dict | None:
    '''Подія для «Вгадай» (ZAVDANNYA-176) або None: з ознакою місця, цілими реченнями, без потерпілих.'''
    if p.get('kategoriia') in Z_POTERPILYMY:
        return None
    k = tsili_rechennia(p['opys_korotkyi'])
    if not k or not MISTSE.search(k) or NE_PODIIA_NA_POCHATKU.search(k):
        return None
    povnyi = KHVIST_KVAL.sub('', PROTOKOL.sub('', p['opys_povnyi'])).strip(' ,;')
    if povnyi[-1:] not in ('.', '!', '?', '»', '"'):          # повний опис теж лише цілими реченнями
        kintsi = [m.end() for m in KINETS_RECHENNIA.finditer(povnyi)]
        povnyi = povnyi[:kintsi[-1]] if kintsi and kintsi[-1] >= len(k) else k
    return dict(p, opys_korotkyi=k, opys_povnyi=povnyi)


class PomylkaKolody(Exception):
    pass


def ochystyty(t: str) -> str:
    """«ОСОБА_1 12.03.2025 року, керуючи…» → «Особа, керуючи…»: без міток реєстру й дат."""
    t = OSOBA.sub('особа', t or '')
    t = re.sub(r'АДРЕСА_\d+', '(адресу приховано судом)', t)
    t = re.sub(r'\s*(ІНФОРМАЦІЯ|НОМЕР|ПІБ|ДАТА)_\d+', '', t)
    t = DATA.sub('', t)
    t = ROL_OSOBA.sub(lambda m: m.group(1), t)
    t = re.sub(r'\s+([,.;:])', r'\1', t)
    t = re.sub(r',\s*,', ',', t)
    t = re.sub(r'\s{2,}', ' ', t).strip(' ,')
    t = re.sub(r'(^|[.!?]\s+)([а-яіїєґ])', lambda m: m.group(1) + m.group(2).upper(), t)
    return t


def zaboronena(podiya: dict) -> bool:
    return str(podiya.get('kategoriia') or '').strip().lower() in ZABORONENI_KATEHORII


def prydatna(podiya: dict) -> bool:
    if not isinstance(podiya, dict):
        return False
    if any(podiya.get(p) in (None, '') for p in POLYA):
        return False
    try:
        lat, lon = float(podiya['lat']), float(podiya['lon'])
    except (TypeError, ValueError):
        return False
    if not (MEZHI['pivden'] <= lat <= MEZHI['pivnich'] and MEZHI['zakhid'] <= lon <= MEZHI['skhid']):
        return False
    return not zaboronena(podiya)


def pidhotuvaty(fail: dict) -> dict:
    """Повертає колоду лише з придатними подіями, без повторів id, упорядковану за id."""
    if not isinstance(fail, dict) or not isinstance(fail.get('podii'), list):
        raise PomylkaKolody('У файлі колоди немає списку podii.')
    bachyly: set[str] = set()
    podii = []
    for p in fail['podii']:
        if not prydatna(p) or p['id'] in bachyly:
            continue
        p = dict(p, **{k: ochystyty(p[k]) for k in TEKSTY})
        if any(SLIDY.search(p[k]) for k in TEKSTY) or not prydatna(p):
            continue
        p = dlia_vgadai(p)
        if p is None:
            continue
        bachyly.add(p['id'])
        podii.append(p)
    podii.sort(key=lambda p: p['id'])
    demo = bool(fail.get('demo')) or any(p.get('demo') is True for p in podii)
    return dict(fail, demo=demo, podii=podii)


def dlya_publikatsiyi(koloda: dict) -> None:
    """Падає, якщо колоду не можна публікувати."""
    if koloda.get('demo'):
        raise PomylkaKolody('Це демо-колода — публікувати не можна. Потрібна справжня колода з конвеєра dani-edrsr.')
    if len(koloda['podii']) < 10:
        raise PomylkaKolody(f'У колоді лише {len(koloda["podii"])} придатних подій — для раунду потрібно щонайменше 10.')
    for p in koloda['podii']:
        if not ID_SPRAVZHNII.match(str(p['id'])):
            raise PomylkaKolody(f'{p["id"]}: id має бути «номер рішення-номер епізоду».')
        if not str(p.get('rishennya_nomer') or '').strip():
            raise PomylkaKolody(f'{p["id"]}: немає номера рішення.')
        if not POSYLANNYA.match(str(p.get('rishennya_url') or '')):
            raise PomylkaKolody(f'{p["id"]}: немає посилання на рішення в реєстрі.')
        if any(SLIDY.search(str(p.get(k) or '')) for k in TEKSTY):
            raise PomylkaKolody(f'{p["id"]}: в описі лишилися «ОСОБА_» чи дата.')


def prochytaty(shlyakh: Path) -> dict:
    try:
        return json.loads(Path(shlyakh).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        raise PomylkaKolody(f'Не вдалося прочитати колоду {shlyakh}: {e}') from e
