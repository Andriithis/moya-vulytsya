"""Колода гри «Вгадай, де це було» для збирання сайту (ZAVDANNYA-07).

Що робить:
  * читає файл колоди (формат — site/hra/koloda.schema.json);
  * відкидає події заборонених категорій MV-12 / MV-4 (статеві злочини, щодо дітей,
    домашнє насильство) — навіть якщо вони трапилися у файлі;
  * відкидає неповні події й події з координатами поза Києвом;
  * для публікації — не пропускає демо-колоду і події без посилання на рішення.

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
# Посилання на рішення — лише офіційний реєстр (doc_url з архівів data.gov.ua, MV-7).
POSYLANNYA = re.compile(r'^https://reyestr\.court\.gov\.ua/Review/[0-9]{5,12}$')


class PomylkaKolody(Exception):
    pass


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


def prochytaty(shlyakh: Path) -> dict:
    try:
        return json.loads(Path(shlyakh).read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as e:
        raise PomylkaKolody(f'Не вдалося прочитати колоду {shlyakh}: {e}') from e
