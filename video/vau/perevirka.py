"""Перевірка сценарію рушія «Вау» перед записом (ZAVDANNYA-127). Правила — AGENTS.md розд. 4–8, MV-25, MV-60, KOMPAS.

Повертає список зауважень; порожній — сценарій можна рендерити. Перевіряє все, що побачить або почує людина:
текст у кадрі, мітки на карті, макети, голос.
"""
from __future__ import annotations

import re

ZABORONENI = re.compile(
    r'небезпеч|безпечн|рейтинг|страшн|страх|найгірш|топ[- ]?\d|прогноз|будьте уважн|обережн|кримінальн\w* район|'
    r'уникайте|не ходіть|куди не ходити|чорн\w* спис', re.I)
SLIDY = re.compile(r'ОСОБА_|НОМЕР_|ІНФОРМАЦІЯ_|\bкв\.\s*\d|квартир\w*\s*№?\s*\d', re.I)
NOMER_BUDYNKU = re.compile(r'(?:вул\.|просп\.|бульв\.|пров\.|пл\.|шосе|узвіз|провулок|вулиця|проспект)\s*[^,\n*]{2,40},\s*(?:буд\.?\s*)?\d', re.I)
CHUTLYVI = re.compile(r'насильств|статев|згвалт|сексуал|розбещ|неповнолітн|дитин|дітей|малолітн|вбивств', re.I)
RAMKA = (29.9, 49.95, 31.2, 50.85)   # Київ із запасом; переліт від України позначається meta['za_mezhamy']


def teksty(S: dict) -> list[str]:
    out = []
    for it in S.get('tekst', []):
        for k in ('tekst', 'zag', 'knopka', 'pidpys', 'dz', 'pered', 'pislia'):
            if it.get(k):
                out.append(str(it[k]))
        for r in it.get('riady', []):
            out.append(str(r.get('tekst', '')))
    for m in S.get('mitky', []):
        out.append(str(m.get('tekst', '')))
    for u in S.get('ui', []):
        for k in ('tekst', 'zag', 'pid', 'knopka', 'pidkazka'):
            if u.get(k):
                out.append(str(u[k]))
        for c in u.get('chysla', []):
            out.append(str(c[1]))
        for s in u.get('sektsii', []):
            out.append(str(s.get('zag', '')))
        for d in u.get('dopysy', []):
            out.append(' '.join(map(str, d)))
    for h in (S.get('zvuk') or {}).get('holos', []):
        out.append(str(h.get('tekst', '')))
    if S.get('dzherelo'):
        out.append(S['dzherelo'])
    return out


def pereviryty(S: dict, meta: dict | None = None) -> list[str]:
    meta = meta or {}
    z = []
    dozvoleni_nomery = meta.get('publichni', [])
    for t in teksty(S):
        if ZABORONENI.search(t):
            z.append(f'заборонене слово: «{ZABORONENI.search(t).group()}» у «{t[:60]}»')
        if SLIDY.search(t):
            z.append(f'слід знеособлення в «{t[:60]}»')
        if CHUTLYVI.search(t):
            z.append(f'чутлива тема в «{t[:60]}»')
        m = NOMER_BUDYNKU.search(t)
        if m and not any(p in t for p in dozvoleni_nomery):
            z.append(f'номер будинку (MV-25): «{m.group()}»')
    if (S.get('zvuk') or {}).get('holos') and not S.get('holos_poznaka'):
        z.append('голос без позначки «голос згенеровано» (MV-150)')
    tryv = S.get('tryvalist', 0)
    if not 5 <= tryv <= 65:
        z.append(f'довжина {tryv} с поза 5–65 с')
    if not S.get('kamera'):
        z.append('немає камери')
    if not meta.get('za_mezhamy'):
        for k in S.get('kamera', []):
            if not (RAMKA[0] <= k['c'][0] <= RAMKA[2] and RAMKA[1] <= k['c'][1] <= RAMKA[3]):
                z.append(f'камера поза Києвом: {k["c"]}')
    for sh in S.get('tochky', []):
        d = sh['dani']
        for x, y in zip(d['x'], d['y']):
            if not (RAMKA[0] <= x / 1e5 <= RAMKA[2] and RAMKA[1] <= y / 1e5 <= RAMKA[3]):
                z.append('точка поза Києвом')
                break
    if not meta.get('kintsivka') and not meta.get('obryv'):
        z.append('немає кінцівки з посиланням на місце (KOMPAS, розд. 0)')
    if not meta.get('kudy'):
        z.append('не вказано, куди веде ролик (meta kudy)')
    for k in ('nazva', 'hachok', 'meta'):
        if not meta.get(k):
            z.append(f'немає meta {k}')
    return z
