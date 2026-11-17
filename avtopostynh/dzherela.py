"""Звідки береться пачка тижня (ZAVDANNYA-107, п. 1).

1. **Районні канали Telegram** — генератор дописів `bot/kanaly.py` (ZAVDANNYA-97) на покажчику `bot/indeks.py`
   з нового випуску. Поки 97 не злито, генератор береться з його гілки (`--bot-teka`), а без нього — заглушка
   (`zahlushka.py`), щоб пробний режим працював.
2. **Ролики й картки** — тека з `manifest.json`, яку пишуть генератор роликів (ZAVDANNYA-94) і `brend/zrobyty.py`.
   Домовленість про формат (одна позиція — один готовий файл):

       {"nazva": "shcho-bolyt-khreshchatyk", "typ": "rolyk" | "kartka", "hrupa": "shcho_bolyt" (rozklad.HRUPY),
        "fail": "rolyky/shcho-bolyt-khreshchatyk.mp4", "zaholovok": "назва для YouTube",
        "pidpys": "текст під роликом, без посилання — його додає сервіс",
        "mistse": {"shliakh": "/vulytsia/khreshchatyk/", "nazva": "вулиця Хрещатик", "typ_mistsia": null, "rayon": "…"},
        "podii": ["128041647-1"], "stsenarii": "stsenarii/….json" (необов'язково — тоді ще й video/perevirka.py),
        "perepysano": true}

   Сервіс сам дописує посилання на сторінку місця з `?dzherelo=<мережа>` і розкладає позиції по днях.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from pravyla import mitka, z_mitkoiu
from rozklad import HRUPY, chas_telegram, nazva_tyzhnia, sloty_kartok, sloty_rolykiv

KORIN = Path(__file__).resolve().parents[1]


def id_odynytsi(*chastyny) -> str:
    return hashlib.sha1('|'.join(map(str, chastyny)).encode('utf-8')).hexdigest()[:16]


# ==================================================================== Telegram
def zavantazhyty_kanaly(bot_teka: Path | None):
    """Модуль `kanaly` з `bot/` (після злиття 97) або з указаної теки (гілка 97). Немає — None."""
    for teka in [bot_teka, KORIN / 'bot']:
        if teka and (Path(teka) / 'kanaly.py').is_file():
            for t in (str(teka), str(KORIN / 'brend'), str(KORIN / 'video'), str(KORIN / 'site')):
                if t not in sys.path:
                    sys.path.insert(0, t)
            spec = importlib.util.spec_from_file_location('kanaly', Path(teka) / 'kanaly.py')
            m = importlib.util.module_from_spec(spec)
            sys.modules['kanaly'] = m
            spec.loader.exec_module(m)
            return m
    return None


def z_dopysu_kanalu(d: dict, slug_rayonu: str, nomer_kanalu: int, tyzhden: str) -> dict:
    """Допис `bot/kanaly.py` → одиниця черги."""
    dz = mitka('telegram', slug_rayonu)
    knopky = [{'tekst': k['tekst'], 'url': z_mitkoiu(k['url'], dz)} for ryad in d.get('knopky', []) for k in ryad]
    shliakh = urlsplit(knopky[0]['url']).path if knopky else ''
    den = date.fromisoformat(d['data'])
    o = {'tyzhden': tyzhden, 'merezha': 'telegram', 'kanal': d['rayon'], 'kanal_slug': slug_rayonu,
         'typ': 'vikteryna' if d['typ'] == 'vhadai' else 'dopys', 'hrupa': d['typ'],
         'chas': chas_telegram(den, nomer_kanalu), 'tekst': d.get('tekst', ''), 'knopky': knopky,
         'mistse': {'shliakh': shliakh, 'rayon': d['rayon']}, 'podii': [d['podiia']] if d.get('podiia') else [],
         'chernetka': bool(d.get('chernetka')), 'perepysano': bool(d.get('perepysano')), 'dzherelo': 'bot/kanaly.py'}
    if d['typ'] == 'vhadai':
        o.update(pytannia=d['pytannia'], varianty=d['varianty'], pravylna=d['pravylna'], poiasnennia=d['poiasnennia'])
    o['id'] = id_odynytsi(tyzhden, 'telegram', d['rayon'], d['data'], d['typ'], d.get('podiia') or d.get('vulytsia'))
    return o


def telegram_tyzhnia(indeks: dict, pn: date, vzhe: set, bot_teka: Path | None = None, adresa_saitu: str | None = None
                     ) -> tuple[list[dict], str]:
    K = zavantazhyty_kanaly(bot_teka)
    if K is None:
        return [], 'генератора дописів bot/kanaly.py немає (ZAVDANNYA-97 не злито) — дописів Telegram не буде'
    h = K.Henerator(indeks, adresa_saitu) if adresa_saitu else K.Henerator(indeks)
    dopysy = h.pachka(pn, 7, vzhe)
    slugy = {r['n']: r['s'] for r in indeks['rayony']}
    poriadok = {r: i for i, r in enumerate(sorted(slugy))}
    tyzhden = nazva_tyzhnia(pn)
    return [z_dopysu_kanalu(d, slugy[d['rayon']], poriadok[d['rayon']], tyzhden) for d in dopysy], ''


# ==================================================================== ролики й картки
def pidpys_dlia(poz: dict, merezha: str, adresa_saitu: str) -> tuple[str, str]:
    url = z_mitkoiu(adresa_saitu.rstrip('/') + poz['mistse']['shliakh'], mitka(merezha))
    tekst = poz.get('pidpys', '').strip()
    return f'{tekst}\n\n{poz["mistse"].get("nazva", "Це місце")} — на сайті: {url}', url


def z_pozytsii(poz: dict, merezha: str, chas_: str, tyzhden: str, adresa_saitu: str, hrupa: str = '') -> dict:
    tekst, url = pidpys_dlia(poz, merezha, adresa_saitu)
    o = {'tyzhden': tyzhden, 'merezha': merezha, 'kanal': '', 'typ': poz['typ'], 'hrupa': hrupa or poz.get('hrupa', ''),
         'chas': chas_, 'tekst': tekst, 'posylannia': url, 'fail': poz['fail'], 'mistse': poz['mistse'],
         'podii': poz.get('podii') or [], 'perepysano': bool(poz.get('perepysano', True)),
         'chernetka': bool(poz.get('chernetka')), 'pozytsiia': poz['nazva'], 'stsenarii': poz.get('stsenarii', ''),
         'dzherelo': 'manifest'}
    if merezha == 'youtube':
        o['nazva'] = poz.get('zaholovok') or poz['mistse'].get('nazva', '')
    o['id'] = id_odynytsi(tyzhden, merezha, chas_, poz['nazva'])
    return o


def media_tyzhnia(manifest: list[dict], pn: date, vykorystani: set, adresa_saitu: str) -> tuple[list[dict], list[str]]:
    """Розкласти ролики й картки по слотах тижня. vykorystani — назви позицій, що вже стояли в черзі."""
    tyzhden = nazva_tyzhnia(pn)
    vilni = [p for p in manifest if p['nazva'] not in vykorystani]
    odynytsi, propusky = [], []
    for s in sloty_rolykiv(pn):
        poz = next((p for p in vilni if p['typ'] == 'rolyk' and p.get('hrupa') == s['hrupa']), None)
        if not poz:
            propusky.append(f'{s["den"].isoformat()}: немає ролика групи {HRUPY[s["hrupa"]]}')
            continue
        vilni.remove(poz)
        odynytsi += [z_pozytsii(poz, m, s['chas'], tyzhden, adresa_saitu, s['hrupa']) for m in s['merezhi']]
    for s in sloty_kartok(pn):
        poz = next((p for p in vilni if p['typ'] == 'kartka'), None)
        if not poz:
            propusky.append(f'{s["den"].isoformat()}: немає картки')
            continue
        vilni.remove(poz)
        odynytsi += [z_pozytsii(poz, m, s['chas'], tyzhden, adresa_saitu) for m in s['merezhi']]
    return odynytsi, propusky


def chytaty_manifest(teka: Path | None) -> list[dict]:
    if not teka or not (Path(teka) / 'manifest.json').is_file():
        return []
    return json.loads((Path(teka) / 'manifest.json').read_text(encoding='utf-8'))


def dni(pn: date) -> list[date]:
    return [pn + timedelta(days=i) for i in range(7)]
