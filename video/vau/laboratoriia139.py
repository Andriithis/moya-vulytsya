"""Візуальна лабораторія роликів (ZAVDANNYA-139): широкий набір виглядів для тесту в TikTok (MV-158, MV-161).

    python video/vau/laboratoriia139.py <events.db>                  # → video/vyhid/kesh/stsenarii/139-*.json + 139-katalog.json
    python video/vau/laboratoriia139.py <events.db> --lyshe neon,teplo

Кожен вигляд — кліп 5 с з рухом камери (темна або своя тема) і, де є сенс, ще світлий варіант для кадру. Вигляди, яких
рушій ще не мав, — у `vyhliady139.js` (поле сценарію `styl`), нові теми — там само (поле `tema`); наявні стилі сот
(`styl_sot`: sait, plytka) беруться з рушія як є. Числа — з випуску в момент збирання.

Межі (AGENTS.md розд. 4, MV-25, MV-60, MV-151): жодних підписів з номером житлового будинку — місця на карті лише
точкою й числом; камера біля житла не ближче рівня вулиці (z 15,3); колір — вид події або кількість даних, без червоного;
дані — dani.py (без насильства, чутливих і «поза Києвом»). Це зразки вигляду, не готові ролики: кінцівки-банера немає,
решта перевірок `perevirka.py` (з правилами 129) — та сама, крім скасованого «лише темна» (MV-158).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

TUT = Path(__file__).resolve().parent
sys.path.insert(0, str(TUT))
import dani as D  # noqa: E402
import perevirka  # noqa: E402
from stsenarii import KYIV, PROFIL, Rolyk, VYHID, fp  # noqa: E402

TRYV = 5.0
VOKZAL = (30.48848, 50.44001)        # Центральний вокзал — публічне місце (MV-60), без номера в кадрі
PODIL = (30.5150, 50.4590)           # центр і Поділ — щільні адреси для шарів адрес


# ------------------------------------------------------------------ дані

def soty_lab(P, riven=8, c=KYIV, **kw):
    """Соти як на сайті (D.soty) + поля для виглядів: h — висота за числом (логарифм, 0…1), d — відстань від центру (0…1)."""
    g = D.soty(P, riven, **kw)
    if not g['features']:
        return g
    nmax = max(f['properties']['n'] for f in g['features'])
    dm = max(D.vidstan_m(c[1], c[0], f['properties']['cy'], f['properties']['cx']) for f in g['features']) or 1
    for f in g['features']:
        pr = f['properties']
        pr['h'] = round(math.log1p(pr['n']) / math.log1p(nmax), 3)
        pr['d'] = round(D.vidstan_m(c[1], c[0], pr['cy'], pr['cx']) / dm, 3)
    return g


def mistsia(P, c, radius_m, t0=0.2, t1=2.6, maks=None, seed=7, poriadok='vypadkovo', min_m=0):
    """Місця (адреси) довкола c: координата, кількість подій, переважний вид, момент появи. Без адреси й номера."""
    hrupy = list(D.HRUPY)
    d = defaultdict(list)
    for p in P:
        if D.vidstan_m(c[1], c[0], p.lat, p.lon) <= radius_m:
            d[(round(p.lat, 5), round(p.lon, 5))].append(p)
    elem = sorted(d.items(), key=lambda kv: -len(kv[1]))
    if min_m:
        vz = []
        for kv in elem:
            if all(D.vidstan_m(kv[0][0], kv[0][1], a[0][0], a[0][1]) >= min_m for a in vz):
                vz.append(kv)
        elem = vz
    if maks:
        elem = elem[:maks]
    rng = random.Random(seed)
    out = {'x': [], 'y': [], 'n': [], 'g': [], 't': []}
    nn = len(elem)
    for i, ((lat, lon), pp) in enumerate(elem):
        vyd = Counter(p.vyd for p in pp).most_common(1)[0][0]
        out['x'].append(round(lon * 1e5))
        out['y'].append(round(lat * 1e5))
        out['n'].append(len(pp))
        out['g'].append(hrupy.index(vyd) if vyd in hrupy else 0)
        if poriadok == 'vid_tsentru':
            k = D.vidstan_m(c[1], c[0], lat, lon) / radius_m
        elif poriadok == 'vid_bilshykh':
            k = i / max(1, nn - 1)
        else:
            k = rng.random()
        out['t'].append(round(t0 + (t1 - t0) * k, 3))
    return out


def chastky_100(P):
    c = Counter(p.vyd for p in P if p.vyd in D.HRUPY)
    vsogo = sum(c.values())
    syri = {k: 100 * v / vsogo for k, v in c.items()}
    tsili = {k: int(v) for k, v in syri.items()}
    for k in sorted(syri, key=lambda k: -(syri[k] - tsili[k]))[:100 - sum(tsili.values())]:
        tsili[k] += 1
    return [{'tekst': D.HRUPY[k][0], 'n': n, 'kolir': D.HRUPY[k][1]} for k, n in sorted(tsili.items(), key=lambda kv: -kv[1]) if n]


# ------------------------------------------------------------------ збирач кліпу

class Lab:
    def __init__(self, P, V):
        self.P, self.V = P, V
        self.katalog = []
        self._soty = None

    @property
    def soty9(self):
        if getattr(self, '_soty9', None) is None:
            self._soty9 = soty_lab(self.P, 9, c=(30.515, 50.455), min_chastka=0.2, min_n=2)
        return self._soty9

    @property
    def soty(self):
        if self._soty is None:
            self._soty = soty_lab(self.P, 8, min_chastka=0.2, min_n=3)
        return self._soty

    def rolyk(self, kod, tema, nazva):
        R = Rolyk(f'139-{kod}-{tema}', TRYV, tema=tema, nazva=nazva, hachok='зразок вигляду', meta='лабораторія вигляду 139',
                  kudy='/karta/', obryv=True, pravyla=129)
        R.S['zatemnennia'] = 0.85
        return R

    def zberehty(self, R, kod, hrupa, nazva, shcho, dlia, kadr_t=3.6, svitla=None):
        S = R.S
        S['kamera'].sort(key=lambda k: k['t'])
        zauv = zauvazhennia(S, R.meta)
        if zauv:
            raise SystemExit(f"{S['id']}: " + '; '.join(zauv))
        VYHID.mkdir(parents=True, exist_ok=True)
        (VYHID / f"{S['id']}.json").write_text(json.dumps(S, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        zapys = {'kod': kod, 'id': S['id'], 'tema': S['tema'], 'hrupa': hrupa, 'nazva': nazva, 'shcho': shcho, 'dlia': dlia,
                 'kadr_t': kadr_t, 'kadr_svitla': None}
        if svitla is not None:
            svitla.S['kamera'].sort(key=lambda k: k['t'])
            zs = zauvazhennia(svitla.S, svitla.meta)
            if zs:
                raise SystemExit(f"{svitla.S['id']}: " + '; '.join(zs))
            (VYHID / f"{svitla.S['id']}.json").write_text(json.dumps(svitla.S, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
            zapys['kadr_svitla'] = svitla.S['id']
        self.katalog.append(zapys)
        print(f"{S['id']}: {nazva}" + (f" (+ {svitla.S['id']})" if svitla else ''))


NE_KARTA = {'infografika', 'hodynnyk', 'kalendar', 'kartka_zvit'}


def zauvazhennia(S, meta):
    """perevirka.py з правилами 129, крім С7 «лише темна» (скасовано MV-158); у «не карті» гачок — заголовок панелі
    з кадру 0, тож С2 рахується виконаним; плюс тексти всередині вигляду."""
    ne_karta = any(st.get('typ') in NE_KARTA for st in S.get('styl', []))
    z = [x for x in perevirka.pereviryty(S, meta) if not x.startswith('С7') and not (ne_karta and x.startswith('С2'))]
    return z + perevirty_styl(S, meta)


def perevirty_styl(S, meta):
    """Тексти всередині вигляду (панелі «не карта», підписи) — ті самі заборони, що й решта кадру."""
    z = []
    ryadky = []

    def zibraty(x):
        if isinstance(x, str):
            ryadky.append(x)
        elif isinstance(x, dict):
            for k, v in x.items():
                if k not in ('typ', 'kolir'):
                    zibraty(v)
        elif isinstance(x, list):
            for v in x:
                zibraty(v)
    zibraty(S.get('styl', []))
    for t in ryadky:
        for nazva, rx in (('заборонене слово', perevirka.ZABORONENI), ('слід знеособлення', perevirka.SLIDY),
                          ('чутлива тема', perevirka.CHUTLYVI), ('номер будинку (MV-25)', perevirka.NOMER_BUDYNKU)):
            if rx.search(t):
                z.append(f'{nazva} у вигляді: «{t[:60]}»')
    return z


def orbita(R, c, z0, z1, p0, p1, b0, b1, t1=TRYV, e='io'):
    R.kam(0, c, z0, p0, b0).kam(t1, c, z1, p1, b1, e=e)


def hachok(R, tekst, y='verkh'):
    R.tekst(0, TRYV + 1, 'hook', tekst, y=y)


# ------------------------------------------------------------------ вигляди

def soty_misto(L: Lab, kod, tema, styl=None, styl_sot=None, nazva='', hook=None, kam=None, **kw):
    R = L.rolyk(kod, tema, nazva)
    c = (30.53, 50.445)
    if kam:
        kam(R)
    else:
        R.kam(0, c, 10.55, 25, 0).kam(TRYV, c, 11.15, 55, -32, e='io')
    if styl_sot or kw.get('vershyny'):
        R.soty(L.P, 8, vysota=kw.get('vysota', ((0, 1),)), prozorist=((0, 1),), min_chastka=0.2, min_n=3,
               **({'styl_sot': styl_sot} if styl_sot else {}), maks_vysota=kw.get('maks_vysota', 2400))
    if styl:
        st = dict(styl)
        if st.get('dani') in ('soty', 'soty9'):
            st['dani'] = getattr(L, st['dani'])
        R.S['styl'] = [st]
    hachok(R, hook or f'{D.chyslo(len(L.P))} подій\n*з рішень судів*')
    R.S['novynky'] = [1.5, 3.0, 4.5]
    return R


def adresy(L: Lab, kod, tema, styl, nazva, hook, c=PODIL, z=(14.1, 14.7), p=(40, 58), b=(-10, -40), radius=1700, maks=None, poriadok='vypadkovo', **kw):
    R = L.rolyk(kod, tema, nazva)
    R.kam(0, c, z[0], p[0], b[0]).kam(TRYV, c, z[1], p[1], b[1], e='io')
    st = dict(styl)
    st['mistsia'] = mistsia(L.P, c, radius, maks=maks, poriadok=poriadok, **kw)
    R.S['styl'] = [st]
    R.S['novynky'] = [1.5, 3.0, 4.5]
    hachok(R, hook)
    return R, st


def zbuduvaty(L: Lab, lyshe=None):
    P = L.P
    n_vsi = len(P)

    def treba(kod):
        return not lyshe or kod in lyshe

    # ---------------- соти
    if treba('sait'):
        R = soty_misto(L, 'sait', 'temna', styl_sot='sait', nazva='Соти над дорогами', vysota=((0, 0.3), (TRYV, 1)))
        S2 = soty_misto(L, 'sait', 'svitla', styl_sot='sait', nazva='Соти над дорогами', vysota=((0, 0.3), (TRYV, 1)))
        L.zberehty(R, 'sait', 'Соти', 'Над дорогами (як на сайті)', 'Напівпрозорі соти лежать над дорогами: вулиці видно крізь '
                   'заливку, найбільші соти — м\'ятні стовпчики. Те саме, що людина побачить на сайті.',
                   'Місто за N секунд, Сота пояснює, будь-який ролик, що веде на карту', svitla=S2)
    if treba('plytka'):
        R = soty_misto(L, 'plytka', 'temna', styl_sot='plytka', nazva='Плитка', vysota=((0, 0.3), (TRYV, 1)))
        S2 = soty_misto(L, 'plytka', 'svitla', styl_sot='plytka', nazva='Плитка', vysota=((0, 0.3), (TRYV, 1)))
        L.zberehty(R, 'plytka', 'Соти', '«Плитка»', 'Суцільна мозаїка зі швами кольору тла; дороги й назви вулиць під сотами '
                   'сховані. Найчистіший кадр, читається з телефона здалеку.', 'Вгадай район за плиткою, Місто за N секунд, '
                   'обкладинки', svitla=S2)
    if treba('sklo_kraia'):
        st = {'typ': 'sklo_kraia', 'dani': 'soty', 'rozkyd': 1.4}

        def kam_(R):
            R.kam(0, (30.505, 50.452), 11.9, 35, 0).kam(TRYV, (30.515, 50.456), 12.5, 55, -30, e='io')
        R = soty_misto(L, 'sklo_kraia', 'temna', st, nazva='Скло з підсвіткою країв', kam=kam_)
        S2 = soty_misto(L, 'sklo_kraia', 'svitla', st, nazva='Скло з підсвіткою країв', kam=kam_)
        L.zberehty(R, 'sklo_kraia', 'Соти', 'Скло з підсвіткою країв', 'Прозорі соти, межа світиться м\'яким ореолом, найбільші '
                   'соти — м\'ятний край. З\'являються хвилею від центру.', 'Сота пояснює, Тур району, спокійні ролики з голосом',
                   svitla=S2)
    if treba('neon'):
        R = soty_misto(L, 'neon', 'temna', {'typ': 'neon', 'dani': 'soty', 'rozkyd': 1.8}, nazva='Контурні неонові')
        L.zberehty(R, 'neon', 'Соти', 'Контурні неонові', 'Лише світні контури сот кольором шкали, заливки майже немає; соти '
                   '«вмикаються» від центру. Лише темна — на світлому неон не світиться.', 'Місто за N секунд, Нічне місто, '
                   'гачки на перші 2 секунди')
    if treba('dykhannia'):
        st = {'typ': 'dykhannia', 'dani': 'soty', 'period': 1.5}
        R = soty_misto(L, 'dykhannia', 'temna', st, nazva='Дихаючі соти')
        S2 = soty_misto(L, 'dykhannia', 'svitla', st, nazva='Дихаючі соти')
        L.zberehty(R, 'dykhannia', 'Соти', '«Дихаючі» соти', 'Соти пульсують: що більше подій, то глибший «вдих»; хвиля йде від '
                   'центру. Підкладка під текст і голос, зациклюється.', 'Петлі, фон під голос, Сота пояснює', svitla=S2)
    for kod, nazva, shcho, dlia, st, kam in (
        ('stovpy_vsi', '3D-стовпчики: усі соти', 'Кожна сота — стовпчик, висота — за кількістю подій (логарифм, щоб центр не '
         'затуляв усе). Камера облітає місто під нахилом.', 'Місто за N секунд, «вау»-відкриття, обкладинки',
         {'typ': 'stovpy', 'dani': 'soty', 'maks_vysota': 2600}, None),
        ('stovpy_vershyny', '3D-стовпчики: лише вершини', 'Пласкі соти й стовпчики тільки там, де подій найбільше (верхні '
         '12 %, як на сайті). Найменше шуму.', 'Сота розпадається, Міф чи факт, ролики-відповіді', None, None),
        ('stovpy_skliani', 'Напівпрозорі стовпчики над вулицями', 'Стовпчики, крізь які видно вулиці й назви; контур сот на '
         'землі. Ближче до району — читається, де саме.', 'Тур району, Вулиця тижня, Сота пояснює',
         {'typ': 'stovpy', 'dani': 'soty9', 'skliani': True, 'maks_vysota': 1300, 'z_ref': 12.5}, 'blyzko'),
        ('stovpy_rist', 'Стовпчики, що ростуть', 'Стовпчики виростають хвилею від центру міста за 3 секунди — рух сам '
         'тримає погляд.', 'Перші 3 секунди будь-якого «вау», Місто за N секунд',
         {'typ': 'stovpy', 'dani': 'soty', 'rist': True, 'rozkyd': 2.4, 'tryv_rostu': 0.8, 'maks_vysota': 2600}, None)):
        if not treba(kod):
            continue

        def kam_(R, b=kam):
            if b == 'blyzko':
                R.kam(0, (30.508, 50.452), 12.6, 55, -15).kam(TRYV, (30.518, 50.458), 13.1, 62, -55, e='io')
            else:
                R.kam(0, (30.53, 50.445), 10.6, 50, 10).kam(TRYV, (30.53, 50.445), 11.0, 62, -40, e='io')
        if st is None:
            R = soty_misto(L, kod, 'temna', None, styl_sot='sait', nazva=nazva, kam=kam_, vysota=((0, 1),), maks_vysota=2600)
            S2 = soty_misto(L, kod, 'svitla', None, styl_sot='sait', nazva=nazva, kam=kam_, vysota=((0, 1),), maks_vysota=2600)
        else:
            R = soty_misto(L, kod, 'temna', st, nazva=nazva, kam=kam_)
            S2 = soty_misto(L, kod, 'svitla', st, nazva=nazva, kam=kam_)
        L.zberehty(R, kod, 'Соти', nazva, shcho, dlia, svitla=S2)

    # ---------------- нові теми (кожна — своє тло, соти над дорогами + вершини, стовпчики)
    for tema, nazva, shcho, dlia in (
        ('nich', 'Тема «Нічне місто»', 'Майже чорне тло, неоновий індиго, вершини — яскрава м\'ята. Найконтрастніша темна.',
         'День і ніч (нічна половина), Місто за N секунд, нічні години'),
        ('papir', 'Тема «Папір і чорнило»', 'Кремове тло, соти — відтінки чорнила, заголовок — книжковий шрифт. Як карта з '
         'газети чи атласу — спокійно й «серйозно».', 'Історії з даних, Календар року, ролики для Facebook і ОСББ'),
        ('vechir', 'Тема «Тепла вечірня»', 'Сливове тло, шкала сот від фіолетового до бурштину; вершини — м\'ята бренду. '
         'Тепло, але без червоного.', 'Тур району, Вулиця тижня, ролики з голосом увечері'),
        ('sontse', 'Тема «На сонці»', 'Біле тло, темні дороги, насичений індиго й чорний текст — максимум контрасту для '
         'телефона на вулиці.', 'Будь-який ролик, коли тест покаже низьке утримання на світлій'),
        ('monokhrom', 'Тема «Монохром з акцентом»', 'Усе сіре, лише найбільші соти — м\'ятні. Погляд одразу йде в одне місце.',
         'Сота розпадається, Міф чи факт, «знайди точку»')):
        if not treba(tema):
            continue

        def kam_(R):
            R.kam(0, (30.52, 50.45), 10.7, 30, 0).kam(TRYV, (30.525, 50.452), 11.6, 58, -38, e='io')
        R = soty_misto(L, tema, tema, None, styl_sot='sait', nazva=nazva, kam=kam_, vysota=((0, 0.2), (TRYV, 1)), maks_vysota=2400)
        L.zberehty(R, tema, 'Теми', nazva, shcho, dlia)

    # ---------------- адреси (не соти): місця точкою й числом, без номерів будинків
    if treba('svitni'):
        a = dict(styl={'typ': 'svitni', 'z_ref': 14.4}, nazva='Світні точки', hook='Кожна точка —\n*місце з подіями*')
        R, _ = adresy(L, 'svitni', 'temna', **a)
        S2, _ = adresy(L, 'svitni', 'svitla', **a)
        L.zberehty(R, 'svitni', 'Адреси', 'Світні точки', 'Кожне місце — світна точка з ореолом; розмір — скільки подій, колір — '
                   'вид. Вискакують по черзі, ореол ледь пульсує.', 'Адреса зблизька, POV: застава завтра, карта підписника', svitla=S2)
    if treba('sonyashnyk'):
        R = L.rolyk('sonyashnyk', 'temna', 'Соняшник подій')
        R.kam(0, VOKZAL, 14.3, 35, 0).kam(TRYV, VOKZAL, 14.8, 55, -50, e='io')
        pp = [p for p in P if D.vidstan_m(VOKZAL[1], VOKZAL[0], p.lat, p.lon) <= 80]
        pp.sort(key=lambda p: (p.data or '9'))
        hr = list(D.HRUPY)
        chasy = [round(0.3 + 3.6 * (i / max(1, len(pp) - 1)) ** 0.6, 3) for i in range(len(pp))]
        R.S['styl'] = [{'typ': 'sonyashnyk', 'c': list(VOKZAL), 'z_ref': 14.5, 'krok': 19, 'rozmir': 9,
                        'podii': {'g': [hr.index(p.vyd) if p.vyd in hr else 0 for p in pp], 't': chasy}}]
        R.mitka(0.2, TRYV + 1, VOKZAL, 'Центральний вокзал', dy=-430)
        R.S['novynky'] = [1.5, 3.0, 4.5]
        hachok(R, f'{D.chyslo(len(pp))} {fp(len(pp))}\n*біля вокзалу*')
        R.meta['publichni'] = ['Центральний вокзал']
        S2 = L.rolyk('sonyashnyk', 'svitla', 'Соняшник подій')
        S2.S.update({k: v for k, v in R.S.items() if k not in ('id', 'tema')})
        L.zberehty(R, 'sonyashnyk', 'Адреси', 'Соняшник подій довкола місця', 'Події одного публічного місця розкладаються '
                   'спіраллю довкола нього (по одній, у порядку дат), у центрі — лічильник. Лише публічні місця (вокзал, ТЦ, ринок).',
                   'Адреса зблизька, Одна подія-петля (розгортка), Що всередині соти', svitla=S2)
    if treba('khvyli'):
        a = dict(styl={'typ': 'khvyli', 'z_ref': 14.2}, nazva='Кільця-хвилі', hook='Де події\n*повторюються*', maks=160)
        R, _ = adresy(L, 'khvyli', 'temna', **a)
        S2, _ = adresy(L, 'khvyli', 'svitla', **a)
        L.zberehty(R, 'khvyli', 'Адреси', 'Кільця-хвилі', 'Кожне місце «пульсує» кільцями; що більше подій, то ширше й частіше. '
                   'Як сонар — видно, де повторюється.', 'Петлі, фон під голос, Де повторюється', svitla=S2)
    if treba('shpyli'):
        a = dict(styl={'typ': 'shpyli', 'r': 11, 'm_na_podiu': 9, 'maks_n': 160, 'tryv_rostu': 0.8}, nazva='Тонкі 3D-шпилі',
                 hook='Вище шпиль —\n*більше подій*', z=(14.0, 14.6), p=(55, 68), b=(20, -35), poriadok='vid_tsentru', radius=1600)
        R, _ = adresy(L, 'shpyli', 'temna', **a)
        S2, _ = adresy(L, 'shpyli', 'svitla', **a)
        L.zberehty(R, 'shpyli', 'Адреси', 'Тонкі 3D-шпилі', 'На кожному місці — вузький шпиль, висота — кількість подій; шпилі '
                   'виростають хвилею від центру. Видно і «ліс», і окремі піки.', 'Тур району, Вулиця тижня, «вау»-наближення',
                   svitla=S2)
    if treba('bulbashky'):
        a = dict(styl={'typ': 'bulbashky', 'z_ref': 14.2}, nazva='Бульбашки з числом', hook='Скільки подій\n*у кожному місці*',
                 maks=22, min_m=420, poriadok='vid_bilshykh', z=(13.9, 14.3), p=(20, 35), b=(0, -15))
        R, _ = adresy(L, 'bulbashky', 'temna', **a)
        S2, _ = adresy(L, 'bulbashky', 'svitla', **a)
        L.zberehty(R, 'bulbashky', 'Адреси', 'Бульбашки з числом', 'Найбільші місця — кружки з числом подій (лише число, без '
                   'адреси), спливають по черзі від більшого до меншого.', 'Вгадай де, Міф чи факт, Вулиця тижня', svitla=S2)
    if treba('teplo'):
        a = dict(styl={'typ': 'teplo', 'z_ref': 13, 'radius': 30, 'ln_maks': 4.0, 'tryv': 2.2}, nazva='Теплова пляма',
                 hook='Де подій\n*найщільніше*', c=(30.515, 50.452), z=(12.6, 13.3), p=(0, 30), b=(0, -20), radius=4500)
        R, _ = adresy(L, 'teplo', 'temna', **a)
        S2, _ = adresy(L, 'teplo', 'svitla', **a)
        L.zberehty(R, 'teplo', 'Адреси', 'Теплова пляма', 'Щільність подій розмитою плямою: індиго → м\'ята → майже біле. Без '
                   'червоного. Найзрозуміліше «де густо» з першого погляду.', 'Місто за N секунд (наближення), День і ніч, '
                   'Тур району', svitla=S2)

    # ---------------- не карта
    if treba('infografika'):
        def r(tema):
            R = L.rolyk('infografika', tema, 'Інфографіка')
            orbita(R, KYIV, 10, 10, 0, 0, 0, 0)
            R.S['styl'] = [{'typ': 'infografika', 'zag': 'Події з рішень судів', 'n': n_vsi, 'pid': 'на карті Києва · 2023–2026',
                            'chastky': chastky_100(P)}]
            R.S['novynky'] = [0.6, 1.2, 2.4, 3.6, 4.5]
            return R
        L.zberehty(r('temna'), 'infografika', 'Не карта', 'Інфографіка на весь кадр', 'Велике число, що біжить, і 100 кружків: '
                   'скільки зі ста подій якого виду. Без карти — читається за 2 секунди.', 'Історії з даних, Міф чи факт '
                   '(відповідь), перший кадр-обкладинка', svitla=r('svitla'))
    if treba('hodynnyk'):
        hod = [0] * 24
        for p in P:
            if p.chas and p.chas[:2].isdigit() and int(p.chas[:2]) < 24:
                hod[int(p.chas[:2])] += 1

        def r(tema):
            R = L.rolyk('hodynnyk', tema, 'Годинник')
            orbita(R, KYIV, 10, 10, 0, 0, 0, 0)
            R.S['styl'] = [{'typ': 'hodynnyk', 'zag': 'О котрій годині', 'hodyny': hod, 't1': TRYV,
                            'pid': f'{D.chyslo(sum(hod))} подій з відомим часом'}]
            R.S['novynky'] = [1.2, 2.4, 3.6, 4.5]
            return R
        L.zberehty(r('temna'), 'hodynnyk', 'Не карта', '«Годинник» доби', '24 промені — скільки подій о кожній годині; стрілка '
                   'обходить добу, у центрі — година й число. Лише події з відомим часом.', 'День і ніч, Місто за N секунд '
                   '(година за годиною), POV', svitla=r('svitla'))
    if treba('kalendar'):
        rik = 2025
        d0 = date(rik, 1, 1)
        dni = [0] * 365
        for p in P:
            if (p.data or '').startswith(str(rik)):
                try:
                    i = (date.fromisoformat(p.data) - d0).days
                except ValueError:
                    continue
                if 0 <= i < 365:
                    dni[i] += 1
        nenul = sorted(v for v in dni if v)
        porohy = [nenul[int(len(nenul) * q)] for q in (0.0, 0.25, 0.5, 0.8)]

        def r(tema):
            R = L.rolyk('kalendar', tema, 'Календар року')
            orbita(R, KYIV, 10, 10, 0, 0, 0, 0)
            R.S['styl'] = [{'typ': 'kalendar', 'zag': f'{rik} рік, день за днем', 'rik': rik, 'dni': dni, 'porohy': porohy,
                            'maks_den': dni.index(max(dni)), 'tryv': 3.6, 'pid': f'{fp(sum(dni))} за {rik} рік'}]
            R.S['novynky'] = [1.2, 2.4, 3.6, 4.5]
            return R
        L.zberehty(r('temna'), 'kalendar', 'Не карта', 'Календар-сітка року', '365 клітинок 2025 року світяться день за днем; '
                   'колір — скільки подій того дня (частками), найбільший день — м\'ятний.', 'Календар року, Історії з даних',
                   svitla=r('svitla'))
    if treba('kartka_zvit'):
        po = L.V.po_vulytsi()
        vul, pp = max(po.items(), key=lambda kv: len(kv[1]))
        roky = sorted(Counter((p.data or '')[:4] for p in pp if p.data).items())
        hr = Counter(p.vyd for p in pp if p.vyd in D.HRUPY).most_common(4)
        mis = [0] * 12
        for p in pp:
            if p.data and len(p.data) >= 7:
                mis[int(p.data[5:7]) - 1] += 1

        def r(tema):
            R = L.rolyk('kartka_zvit', tema, 'Картка-звіт')
            orbita(R, KYIV, 10, 10, 0, 0, 0, 0)
            R.S['styl'] = [{'typ': 'kartka_zvit', 'zag': vul, 'pid': 'Що є в даних про вулицю', 't1': TRYV,
                            'chysla': [[len(pp), fp(len(pp))], [len(roky), 'роки даних'],
                                       [len({(round(p.lat, 4), round(p.lon, 4)) for p in pp}), 'місць на вулиці']],
                            'roky': [[r_, n] for r_, n in roky], 'hrupy': [[D.HRUPY[k][0], n, D.HRUPY[k][1]] for k, n in hr],
                            'misiatsi': mis, 'dz': 'Рішення судів (ЄДРСР) · лише те, що дійшло до суду'}]
            R.S['dzherelo'] = ''
            R.S['znak'] = False          # у картки свій логотип у шапці
            R.S['novynky'] = [1.2, 2.4, 3.6, 4.5]
            return R
        L.zberehty(r('temna'), 'kartka_zvit', 'Не карта', 'Картка-звіт, що гортається', f'Картка вулиці ({vul}): числа, роки, '
                   'види, місяці — гортається вниз, як довідка в телефоні. Лише відкриті числа, без будинків.',
                   'Вулиця тижня, продуктові ролики (довідка, підписка), ОСББ', svitla=r('svitla'))


def main():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument('baza', type=Path)
    a.add_argument('--lyshe', help='коди через кому, напр. neon,teplo')
    arg = a.parse_args()
    V = D.Vypusk(arg.baza)
    L = Lab(V.podii, V)
    zbuduvaty(L, set(arg.lyshe.split(',')) if arg.lyshe else None)
    k = VYHID / '139-katalog.json'
    stari = json.loads(k.read_text(encoding='utf-8')) if k.is_file() and arg.lyshe else []
    kody = {z['kod'] for z in L.katalog}
    k.write_text(json.dumps([z for z in stari if z['kod'] not in kody] + L.katalog, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(L.katalog)} виглядів → {k}')


if __name__ == '__main__':
    main()
