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

# ZAVDANNYA-129 (MV-151, зауваження критика ZVIT-128): правила монтажу — один раз для всіх роликів
BANER_MAKS = 1.0            # С1: кінцівка ≤ 1 с поверх руху
PAUZA_MAKS = 2.0            # С4: щось нове в кадрі щонайпізніше кожні 2 с
KARTKA_MAKS = 130           # С4: переказ — одне речення (знаків)
ZAKHYST = re.compile(r'не оцінка|не кращ|не гірш', re.I)   # С8: захисні фрази — коротко (≤ 1,5 с) або в підписі публікації
ZAKHYST_MAKS = 1.5
ZUM_ZHYTLO = 15.3           # MV-151: житло — камера не ближче рівня вулиці (3D-план будинку = номер, MV-25)
NOMER_RISHENNIA = re.compile(r'рішенн\w*\s+(?:суду\s+)?№', re.I)
KOMPONUVANNIA = {'hook', 'velykyi', 'pytannia', 'lich', 'kartka', 'stovpchyky', 'variant', 'vidlik', 'godynnyk', 'slovo', 'split',
                 'komentar', 'kolony', 'shtamp', 'taimer'}
ZASTARILI = {'fin'}         # нерухома кінцева картка 3–5 с (С1) — заборонено
LICH_PODII = re.compile(r'\bподі[яйї]', re.I)


def novynky(S: dict) -> list[float]:
    """Моменти, коли в кадрі з'являється щось нове: текст, макет, мітка, удар, хвиля, розпад соти, нова хвиля точок,
    переліт камери (дуга або зміна зуму >= 0,8 чи розвороту >= 35°)."""
    t = [x['t0'] for x in S.get('tekst', [])] + [x['t0'] for x in S.get('ui', [])] + [x['t0'] for x in S.get('mitky', [])]
    t += [x['t'] for x in S.get('spalakh', [])] + [x['t'] for x in S.get('kiltsia', [])]
    t += [x['t0'] for x in S.get('lini', [])]
    for sh in S.get('soty', []):
        t += [r['t'] for r in sh.get('rozpad', [])]
    for sh in S.get('tochky', []):
        tt = sorted(sh['dani']['t'])
        if tt:
            t.append(tt[0])
            x = tt[0]          # довга хвиля точок теж «нове»: позначка кожні 1,5 с, поки точки ще з'являються
            while x < tt[-1]:
                x += 1.5
                t.append(min(x, tt[-1]))
    K = sorted(S.get('kamera', []), key=lambda k: k['t'])
    for a, b in zip(K, K[1:]):
        if b.get('luk') or abs(b['z'] - a['z']) >= 0.8 or abs(b.get('b', 0) - a.get('b', 0)) >= 35:
            t.append(a['t'] + 0.15)
    for it in S.get('tekst', []):          # відлік 3-2-1 і годинник — нове число щосекунди
        if it.get('styl') in ('vidlik', 'godynnyk', 'taimer'):
            x = it['t0']
            while x < it['t1']:
                x += 1.0
                t.append(x)
    t += S.get('novynky', [])
    return sorted(t)


def montazh(S: dict, meta: dict) -> list[str]:
    """С1–С8, С10: перевірки монтажу (не для довгих роликів YouTube — meta['dovhyi'])."""
    z = []
    T = float(S.get('tryvalist', 0))
    tekst = S.get('tekst', [])
    for it in tekst:
        if it.get('styl') in ZASTARILI:
            z.append('С1: нерухома кінцева картка (styl fin) — лише банер <= 1 с поверх руху')
        if it.get('styl') == 'baner' and min(it['t1'], T) - it['t0'] > BANER_MAKS + 1e-6:
            z.append(f"С1: кінцівка {min(it['t1'], T) - it['t0']:.1f} с > {BANER_MAKS} с")
        if it.get('styl') == 'kartka':
            if it.get('drukarka') is True:
                z.append('С4: переказ друкується по букві — показати цілим')
            if len(it.get('tekst', '')) > KARTKA_MAKS:
                z.append(f"С4: переказ задовгий ({len(it['tekst'])} знаків > {KARTKA_MAKS}) — одне речення")
        if ZAKHYST.search(str(it.get('tekst', ''))) and not meta.get('yak_tse_pratsiuie') and it['t1'] - it['t0'] > ZAKHYST_MAKS + 1e-6:
            z.append(f"С8: захисна фраза {it['t1'] - it['t0']:.1f} с — коротко (<= {ZAKHYST_MAKS} с) або в підпис публікації")
        if it.get('styl') == 'lich' and LICH_PODII.search(str(it.get('pidpys', ''))) and not it.get('formy'):
            z.append('С10: підпис лічильника не узгоджується з числом, поки той біжить — formy')
    pershi = [it for it in tekst if it['t0'] <= 1e-6 and it.get('styl') in ('hook', 'velykyi', 'pytannia', 'slovo', 'split', 'komentar', 'shtamp', 'lich')]
    if not pershi:
        z.append('С2: у кадрі 0 немає повного гачка (текст має стояти з 0 с)')
    tt = sorted([0.0] + [x for x in novynky(S) if 0 <= x <= T] + [max(0.0, T - 0.5)])
    for a, b in zip(tt, tt[1:]):
        if b - a > PAUZA_MAKS + 1e-6:
            z.append(f'С4: {a:.1f}–{b:.1f} с нічого нового ({b - a:.1f} с > {PAUZA_MAKS} с)')
            break
    styli = {it.get('styl') for it in tekst} & KOMPONUVANNIA
    styli |= {'ui-' + u['typ'] for u in S.get('ui', []) if u.get('typ') not in ('zavisa', 'sota')}
    if T >= 9 and len(styli) < 3:
        z.append(f'С6: лише {len(styli)} компонування ({", ".join(sorted(styli))}) — потрібно >= 3')
    if S.get('tema') == 'svitla' and not meta.get('ne_tiktok'):
        z.append('С7: світла тема в ролику для TikTok')
    if meta.get('petlia'):
        K = sorted(S.get('kamera', []), key=lambda k: k['t'])
        a, b = K[0], K[-1]
        if abs(a['z'] - b['z']) > 0.05 or abs(a['c'][0] - b['c'][0]) > 1e-4 or abs(a['c'][1] - b['c'][1]) > 1e-4 or b['t'] < T - 1e-6:
            z.append('С1: петля — остання позиція камери має збігатися з першою')
    return z


def mezhi_129(S: dict, meta: dict) -> list[str]:
    """MV-151: житло — не ближче рівня вулиці; номер рішення — лише в ролику з однією подією."""
    z = []
    if not meta.get('publichni'):
        for k in S.get('kamera', []):
            if k['z'] > ZUM_ZHYTLO + 1e-6:
                z.append(f"MV-151: камера z {k['z']} ближче рівня вулиці (житло) на {k['t']} с")
                break
    nomery = [t for t in teksty(S) if NOMER_RISHENNIA.search(t)]
    if nomery and not meta.get('odna_podiia'):
        z.append('MV-151: номер рішення — лише в ролику з однією подією (тут — підсумковий)')
    if meta.get('odna_podiia') and not nomery:
        z.append('MV-151: ролик з однією подією — потрібен номер рішення')
    return z


def teksty(S: dict) -> list[str]:
    out = []
    for it in S.get('tekst', []):
        for k in ('tekst', 'zag', 'knopka', 'pidpys', 'dz', 'pered', 'pislia', 'khto'):
            if it.get(k):
                out.append(str(it[k]))
        for r in it.get('riady', []):
            out.append(str(r.get('tekst', '')))
            out.append(str(r.get('zag', '')))
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
    out += [str(x) for x in S.get('pidpys_publikatsii', [])]
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
    if meta.get('pravyla') == 129:          # ролики ZAVDANNYA-129 і новіші (старі чернетки 127 — як були)
        z += mezhi_129(S, meta)
        if not meta.get('dovhyi'):
            z += montazh(S, meta)
    return z
