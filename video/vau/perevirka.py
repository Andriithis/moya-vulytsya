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
                 'komentar', 'kolony', 'shtamp', 'taimer', 'kalendar'}
ZASTARILI = {'fin'}         # нерухома кінцева картка 3–5 с (С1) — заборонено
# ZAVDANNYA-175: позначка — за тим, чий голос (video/vau/holos_servis.py, poznaka())
POZNAKY_HOLOSU = ('Голос змінено програмою', 'Голос згенеровано')
LICH_PODII = re.compile(r'\bподі[яйї]', re.I)


def novynky(S: dict) -> list[float]:
    """Моменти, коли в кадрі з'являється щось нове: текст, макет, мітка, удар, хвиля, розпад соти, нова хвиля точок,
    переліт камери (дуга або зміна зуму >= 0,8 чи розвороту >= 35°)."""
    t = [x['t0'] for x in S.get('tekst', [])] + [x['t0'] for x in S.get('ui', [])] + [x['t0'] for x in S.get('mitky', [])]
    t += [x['t'] for x in S.get('spalakh', [])] + [x['t'] for x in S.get('kiltsia', [])]
    t += [x['t0'] for x in S.get('lini', [])]
    t += [k[0] for u in S.get('ui', []) if u.get('typ') == 'sota' for k in u.get('kroky', [])]   # «Сота» стрибає (MV-148)
    for sh in S.get('soty', []):
        t += [r['t'] for r in sh.get('rozpad', [])]
    hvyli = [sh['dani']['t'] for sh in S.get('tochky', [])]
    hvyli += [[f['properties']['t'] for f in sh['dani'].get('features', [])] for sh in S.get('adresy', [])]   # адреси (138)
    for tt in hvyli:
        tt = sorted(tt)
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
    # С7 «лише темна» скасовано (MV-158, MV-161): світла тема — повноправна (В4)
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
    if (S.get('zvuk') or {}).get('holos'):
        if not S.get('holos_poznaka'):
            z.append('голос без позначки (MV-150, MV-171)')
        elif S['holos_poznaka'] not in POZNAKY_HOLOSU:
            z.append(f"позначка голосу «{S['holos_poznaka']}» — лише {' або '.join(POZNAKY_HOLOSU)} (MV-171)")
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
    if (meta.get('pravyla') or 0) >= 129:   # ролики ZAVDANNYA-129 і новіші (старі чернетки 127 — як були)
        z += mezhi_129(S, meta)
        if not meta.get('dovhyi'):
            z += montazh(S, meta)
    if (meta.get('pravyla') or 0) >= 138:
        z += pravyla_138(S, meta)
    if (meta.get('pravyla') or 0) >= 129:
        z += pravda(S, meta) + kudy(meta)
        if not meta.get('dovhyi'):
            z += rukh_na_starti(S)
    return z


# ------------------------------------------------------------------ ZAVDANNYA-138: вигляди, адреси, чергування (В2)

SHARY = {'soty', 'adresy', 'tochky', 'zvit', 'zapys', 'ne_karta'}     # «шар» ролика — вісь В2
RIVNI = ('misto', 'rayon', 'vulytsia', 'mistse')


def pravyla_138(S: dict, meta: dict) -> list[str]:
    """Стиль сот — лише явний вибір сценарію (жодного типового); шар ролика названо; адреси — лише число, без підписів."""
    z = []
    for sh in S.get('soty', []):
        if not sh.get('styl_sot'):
            z.append('В2/В9: стиль сот не вибрано (styl_sot) — типового немає')
    if meta.get('shar') not in SHARY:
        z.append(f"В2: шар ролика ({meta.get('shar')}) — один з {', '.join(sorted(SHARY))}")
    for sh in S.get('adresy', []):
        for f in sh['dani'].get('features', []):
            zaivi = set(f.get('properties', {})) - {'n', 't'}
            if zaivi:
                z.append(f'MV-25: у шарі адрес лише число подій — зайве: {", ".join(sorted(zaivi))}')
                break
    if S.get('druha') and not S['druha'].get('s'):
        z.append('поділений екран без другої сцени')
    return z


def zum_u_chasi(S: dict, t: float) -> float:
    K = sorted(S.get('kamera', []), key=lambda k: k['t'])
    if not K:
        return 10.0
    if t <= K[0]['t']:
        return K[0]['z']
    for a, b in zip(K, K[1:]):
        if t <= b['t']:
            k = (t - a['t']) / max(1e-6, b['t'] - a['t'])
            return a['z'] + (b['z'] - a['z']) * k
    return K[-1]['z']


def osi(S: dict, meta: dict) -> dict:
    """Три осі В2: тема, шар, рівень наближення (за зумом камери, медіана кожні 0,5 с; «не карта» — свій рівень)."""
    shar = meta.get('shar', '?')
    tema = meta.get('tema_os') or S.get('tema', 'temna')
    if shar in ('ne_karta', 'zvit'):
        riven = 'ne_karta'
    else:
        T = float(S.get('tryvalist', 0))
        zz = sorted(zum_u_chasi(S, i * 0.5) for i in range(int(T * 2) + 1))
        m = zz[len(zz) // 2]
        riven = RIVNI[0] if m < 11.2 else RIVNI[1] if m < 13.5 else RIVNI[2] if m < 15.5 else RIVNI[3]
    return {'tema': tema, 'shar': shar, 'riven': meta.get('riven') or riven}


def pereviryty_pachku(rolyky: list[tuple[dict, dict]]) -> list[str]:
    """В2 (Андрій: «всі відео однотипні»): два ролики поспіль різняться щонайменше за двома осями з трьох."""
    z = []
    vsi = {(m.get('pidsumky') or {}).get('vsi') for _, m in rolyky} - {None}
    if len(vsi) > 1:      # критик ZVIT-170: 71 420 / 71 417 / 71 428 у сусідніх роликах
        z.append(f'одне «усього подій» на пачку — зараз різні: {", ".join(str(x) for x in sorted(vsi))} (зібрати з одного випуску)')
    oo = [(m.get('id', S.get('id')), osi(S, m)) for S, m in rolyky]
    for (ia, a), (ib, b) in zip(oo, oo[1:]):
        rizni = [k for k in ('tema', 'shar', 'riven') if a[k] != b[k]]
        if len(rizni) < 2:
            z.append(f'В2: {ia} → {ib} різні лише за {len(rizni)} осями ({", ".join(rizni) or "жодною"}): '
                     f'{a} / {b}')
    return z


# ------------------------------------------------------------------ ZAVDANNYA-175 (критик ZVIT-170, топ-10 №2, №3, №5)
# Гачок — правда, яку перевіряє програма: число в гачку — з бази (meta['fakty'], рахує сценарій у момент збирання) або
# з опису самої події (meta['fabula'], ролик з однією подією); «одне й те саме» — лише коли вид один; «в судах» — не
# підміна «у наших даних»; відсоток — лише з базою >= VIDSOTOK_BAZA подій (AGENTS.md розд. 6: сигнал без бази не існує).

VULYTSIA = re.compile(r'вул\.|просп\.|бульв\.|пров\.|пл\.|узвіз|шосе|вулиця|проспект|набережна', re.I)
HACHOK_STYLI = {'hook', 'velykyi', 'pytannia', 'slovo', 'split', 'komentar', 'shtamp'}
HACHOK_DO = 1.5               # гачок — те, що в кадрі до 1,5 с
VIDSOTOK_BAZA = 50
DZHERELO_MAKS = 50            # рядок джерела 34 px в один рядок (stsena.css)
ODNE_I_TE_SAME = re.compile(r'одне й те саме|одне і те саме|те саме\b|однаков\w*|той самий|та сама', re.I)
V_SUDAKH = re.compile(r'\b(?:в|у) судах\b|\bсуди Києва\b|\bсудів Києва\b', re.I)
NAI = re.compile(r'найчаст|найбільш|найменш|найрідш|найпоширен', re.I)
CHYSLO = re.compile(r'\d+(?:[,.:]\d+)?')
VIDSOTOK = re.compile(r'(\d+(?:[,.]\d+)?)\s?%|(\d+(?:[,.]\d+)?)\s+відсот', re.I)
NE_DANI = re.compile(r'^(?:19|20)\d\d$|^1551$')          # рік і номер служби 1551 — не твердження про дані


def _norm(t: str) -> str:
    """«71 428» → «71428», «00 год. 46 хв.» → «00:46», зірочки розмітки геть."""
    t = str(t).replace('*', '')
    t = re.sub(r'(?<=\d)[    ](?=\d{3}\b)', '', t)
    t = re.sub(r'\b(\d{1,2})\s*год\.?\s*(\d{2})\s*хв\.?', lambda m: f'{int(m.group(1)):02d}:{m.group(2)}', t)
    return t


def _chysla(t: str) -> list[str]:
    t = _norm(t)
    t = re.sub(r'\d+(?:[,.]\d+)?\s*(?:с|сек\w*|секунд\w*)\b', ' ', t)     # «за 9 секунд», «за 3 с» — тривалість ролика
    return [x for x in CHYSLO.findall(t) if not NE_DANI.match(x)]


def _rivni(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return abs(float(a.replace(',', '.').replace(':', '.')) - float(b.replace(',', '.').replace(':', '.'))) < 1e-9
    except ValueError:
        return False


def hachok(S: dict) -> list[str]:
    """Тексти, які глядач бачить або чує в перші HACHOK_DO с."""
    out = []
    for it in S.get('tekst', []):
        if it['t0'] <= 1e-6 and it.get('styl') in HACHOK_STYLI:      # С2: гачок стоїть повністю з кадру 0
            out += [str(it.get(k)) for k in ('tekst', 'pid', 'zag') if it.get(k)]
            out += [str(r.get('zag', '')) + ' ' + str(r.get('tekst', '')) for r in it.get('riady', [])]
    out += [str(h.get('tekst', '')) for h in (S.get('zvuk') or {}).get('holos', []) if h.get('t', 0) <= HACHOK_DO]
    return out


def pravda(S: dict, meta: dict) -> list[str]:
    z = []
    fakty = meta.get('fakty') or {}
    dozv = [_norm(str(v)) for v in fakty.values() if not isinstance(v, (dict, list))]
    dozv += [str(x) for x in meta.get('chysla_ne_z_bazy', [])]        # «за 2 мільйони» — приклад, не дані; пояснити в сценарії
    fabula = _norm(meta.get('fabula') or '')
    opys = [meta['hachok']] if meta.get('hachok') else []      # опис гачка в каталозі: слова перевіряємо, числа — ні («з кадру 0»)
    for t in hachok(S) + opys:
        for x in ([] if t in opys else _chysla(t)):
            if not any(_rivni(x, d) for d in dozv) and not (fabula and re.search(r'(?<![\d,.])' + re.escape(x) + r'(?![\d])', fabula)):
                z.append(f'гачок: число {x} у «{_norm(t)[:50]}» не підтверджене базою (meta fakty) чи описом події (meta fabula)')
        if ODNE_I_TE_SAME.search(t) and fakty.get('vydiv') != 1:
            z.append(f'гачок: «{ODNE_I_TE_SAME.search(t).group()}» — лише коли вид один (meta fakty vydiv = 1, зараз {fakty.get("vydiv")})')
        if V_SUDAKH.search(t) and (NAI.search(t) or _chysla(t)):
            z.append(f'гачок: «{V_SUDAKH.search(t).group()}» — ми рахуємо події в наших даних, не всі справи судів; '
                     f'писати «у наших даних»')
    # підпис на карті: число одразу після назви вулиці («вул. Вишгородська · 45») читається як номер будинку (MV-25)
    for m in S.get('mitky', []):
        n = m.get('n')
        dvoinyk = isinstance(n, str) and re.match(r'\s*[·,:\-–—]?\s*\d', n)
        dvoinyk = dvoinyk or re.search(r'(?:вул\.|просп\.|бульв\.|пров\.|пл\.|узвіз|шосе|вулиця)[^\d]{2,40}[·:–—-]\s*\d+\s*$', str(m.get('tekst', '')))
        if VULYTSIA.search(str(m.get('tekst', ''))) and dvoinyk:
            z.append(f"підпис «{m.get('tekst')}{n if isinstance(n, str) else ''}» — число після назви вулиці схоже на номер будинку: "
                     f"n числом (сцена пише «N подій» окремим рядком)")
    if len(str(S.get('dzherelo') or '')) > DZHERELO_MAKS:
        z.append(f"рядок джерела задовгий ({len(S['dzherelo'])} > {DZHERELO_MAKS} знаків) — не влазить в один рядок над гачком")
    # ролик-відповідь — лише на справжній коментар (критик ZVIT-170, n6; реєстр ROLYKY-TYPY): посилання на нього в meta
    if any(it.get('styl') == 'komentar' for it in S.get('tekst', [])) and not meta.get('komentar_dzherelo'):
        z.append('відповідь на коментар — лише на справжній: meta komentar_dzherelo (посилання на коментар; MV_KOMENTAR)')
    # одне «усього подій» (топ-10 №6): лічильник з підсумком несе pidsumok і показує саме число з meta['pidsumky']
    pids = meta.get('pidsumky') or {}
    for it in S.get('tekst', []):
        if it.get('styl') not in ('lich', 'slovo', 'velykyi'):
            continue
        k = it.get('pidsumok')
        kin = kinets_lich(it)
        if k:
            if k not in pids:
                z.append(f'підсумок «{k}» без числа з одного джерела (Rolyk.pidsumok)')
            elif kin is not None and kin != pids[k]:
                z.append(f'підсумок «{k}»: у кадрі {kin}, у джерелі {pids[k]}')
        elif it.get('styl') == 'lich' and NA_KARTI_MISTA.search(str(it.get('pidpys', ''))):
            z.append(f"лічильник «{it.get('pidpys')}» — усього подій: лише з одного джерела (pidsumok='vsi')")
    # відсоток — лише з базою: кожне «N %» має запис meta['vidsotky'] = [{'v': N, 'k': k, 'n': n}] з n >= VIDSOTOK_BAZA
    vs = meta.get('vidsotky') or []
    vsi = list(teksty(S))
    for it in S.get('tekst', []):
        for r in it.get('riady', []):
            if '%' in str(r.get('pislia', '')) and r.get('n') is not None:
                vsi.append(f"{r['n']} %")
        if '%' in str(it.get('pislia', '')) and it.get('do') is not None:
            vsi.append(f"{it['do']} %")
    for t in vsi:
        for m in VIDSOTOK.finditer(_norm(t)):
            v = float((m.group(1) or m.group(2)).replace(',', '.'))
            ok = [x for x in vs if abs(float(x['v']) - v) < 1e-9 and x['n'] >= VIDSOTOK_BAZA and abs(x['k'] / x['n'] * 100 - v) < 1]
            if not ok:
                z.append(f'відсоток {m.group().strip()} без бази >= {VIDSOTOK_BAZA} подій (meta vidsotky) — писати «k з n»')
    return z


# Компас (docs/KOMPAS.md, розд. 0): заклик веде на сторінку того самого місця. Карта загалом — лише для ролика про все місто.
KUDY_MISTSE = re.compile(r'^/(?:vulytsia|rayon|budynok|mistse)/[^/?#]+/')
KUDY_PRODUKT = re.compile(r'^/(?:miy-budynok|osbb|sudova-praktyka|biznes|dlia|pidpyska|oplata)/')
KUDY_HRA = re.compile(r'^/(?:karta/\?ihry|hra/|ihry/)')
KUDY_KARTA_MISTSE = re.compile(r'^/karta/#\d+(?:\.\d+)?/\d+\.\d+/\d+\.\d+')     # карта, відкрита на цьому місці


NA_KARTI_MISTA = re.compile(r'на карті(?: Києва)?\s*$|усього подій|подій у Києві', re.I)


def kinets_lich(it: dict):
    """Число, на якому лічильник зупиняється (останній ключ або do)."""
    if it.get('kluchi'):
        return it['kluchi'][-1][1]
    return it.get('do')


def kudy(meta: dict) -> list[str]:
    k = meta.get('kudy') or ''
    if meta.get('obryv') and k == '/':
        return []                       # вступ продуктового ролика: заклик — у записі сторінки
    if KUDY_MISTSE.match(k) or KUDY_PRODUKT.match(k) or KUDY_HRA.match(k) or KUDY_KARTA_MISTSE.match(k):
        return []
    if k.split('?')[0].split('#')[0] == '/karta/' and (meta.get('pro_misto') or meta.get('riven') == 'misto'):
        return []                       # ролик про все місто → карта міста
    return [f'заклик «{k}» — не конкретне місце (KOMPAS розд. 0): сторінка вулиці, району, місця, будинку, продукту, '
            f'гри або /karta/#зум/широта/довгота; карта загалом — лише для ролика про все місто (meta pro_misto)']


def storinka_isnuie(kudy_: str, sait: Path | str) -> bool:
    """Чи є сторінка заклику в зібраному сайті (site/zibraty_sait.py): /vulytsia/x/ → <сайт>/vulytsia/x/index.html."""
    from pathlib import Path as _P
    shliakh = kudy_.split('#')[0].split('?')[0].strip('/')
    f = _P(sait) / shliakh / 'index.html' if shliakh else _P(sait) / 'index.html'
    return f.is_file()


def posylannia(meta: dict, sait) -> list[str]:
    """Перевірка під час збирання ролика: заклик веде на сторінку, яка існує (критик ZVIT-170: n7 → 404)."""
    if not sait:
        return ['не перевірено посилання: немає зібраного сайту (--sait або MV_SAIT) — ролик без перевірки заклику не збираємо']
    k = meta.get('kudy') or ''
    if meta.get('obryv') and k == '/':
        return []
    if not storinka_isnuie(k, sait):
        return [f'заклик «{k}»: такої сторінки в зібраному сайті {sait} немає (404)']
    return []


# Топ-10 №4 (критик ZVIT-170): у 22 з 29 роликів перші 1,5–2 с — нерухомий текст над нерухомою картою; у TikTok гортають
# далі приблизно за секунду. Правило: до START_RUKH с щось рухається — камера помітно (зум, поворот, нахил, зсув), точки
# з'являються, лічильник біжить, лінія малюється, сота розпадається, вигляд 139 анімується або запис сайту вже діє.
START_RUKH = 1.5
RUKH_Z, RUKH_KUT, RUKH_ZSUV = 0.12, 5.0, 0.001     # зум, градуси повороту чи нахилу, градуси широти/довготи (≈ 100 м)
RUKH_STYLI = {'lich', 'godynnyk', 'taimer', 'vidlik', 'kalendar', 'kolony', 'stovpchyky', 'split'}


def kamera_u_chasi(S: dict, t: float) -> dict:
    K = sorted(S.get('kamera', []), key=lambda k: k['t'])
    if not K:
        return {}
    if t <= K[0]['t']:
        return K[0]
    for a, b in zip(K, K[1:]):
        if t <= b['t']:
            k = (t - a['t']) / max(1e-6, b['t'] - a['t'])
            return {x: (a.get(x, 0) + (b.get(x, 0) - a.get(x, 0)) * k) for x in ('z', 'p', 'b')} | {
                'c': [a['c'][i] + (b['c'][i] - a['c'][i]) * k for i in (0, 1)]}
    return K[-1]


def rukh_na_starti(S: dict) -> list[str]:
    T = START_RUKH
    a, b = kamera_u_chasi(S, 0.0), kamera_u_chasi(S, T)
    if a and b and (abs(b['z'] - a['z']) >= RUKH_Z or abs(b.get('b', 0) - a.get('b', 0)) >= RUKH_KUT
                    or abs(b.get('p', 0) - a.get('p', 0)) >= RUKH_KUT
                    or max(abs(b['c'][0] - a['c'][0]), abs(b['c'][1] - a['c'][1])) >= RUKH_ZSUV):
        return []
    for sh in S.get('tochky', []):
        if any(0 < t <= T for t in sh['dani'].get('t', [])):
            return []
    for sh in S.get('adresy', []):
        if any(0 < f['properties'].get('t', -1) <= T for f in sh['dani'].get('features', [])):
            return []
    for sh in S.get('soty', []):
        if any(r['t'] <= T for r in sh.get('rozpad', [])):
            return []
    if any(it.get('styl') in RUKH_STYLI and it['t0'] <= T for it in S.get('tekst', [])):
        return []
    if any(l['t0'] <= T for l in S.get('lini', [])) or any(k['t'] <= T for k in S.get('kiltsia', [])):
        return []
    if S.get('styl') or S.get('zapys_rukh'):
        return []
    return [f'рух у перші {T} с: камера майже стоїть і нічого не з\'являється — кадр 0…{T} с нерухомий (критик ZVIT-170, №4)']
