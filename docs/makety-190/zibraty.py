# -*- coding: utf-8 -*-
"""ZAVDANNYA-190, крок 2: картка району й публічного місця на справжніх числах повного Києва (макет, на сайт не йде).

Бере витяг кроку 1 (`vytiah.py`), рахує числа й пише:
  * `chysla.json` — усі числа карток (лише зведені числа, без адрес і описів);
  * `<slug>.html` — макет-сторінки в оболонці сайту (`site/zibraty_sait.storinka`, CSS сайту + `kartka-190.css`);
  * `rayon-sud-tochka.json` — район «за точкою» (як на сайті) проти «за судом» (як у 189).

    python docs/makety-190/zibraty.py <vytiah.pkl> <../dani-edrsr>

Правила (MV-207, ZAVDANNYA-190): усі 7 груп однаковими блоками в порядку легенди; динаміка 2016–2026 з поправкою на
неповні свіжі місяці (`dani-edrsr/src/povnota.py`, S-Р.9); «найчастіше», ціль і всі поля, що заповнені достатньо; порівняння
з Києвом — лише позначкою біля великої й невипадкової різниці; без способу здобуття наркотиків, «повторно», «судимий»
(почерк суду, MV-206); без статевих і щодо дітей (MV-102); без номерів будинків і назв мереж.
"""
from __future__ import annotations

import html
import json
import math
import pickle
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
PKL, DANI = sys.argv[1], Path(sys.argv[2]).resolve()
sys.path.insert(0, str(DANI / 'src'))
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
import povnota  # noqa: E402
import zibraty_sait as Z  # noqa: E402
import tsiny as T  # noqa: E402
import dani as D  # noqa: E402

e, chyslo = Z.e, Z.chyslo
NB = '\u00a0'
ROKY = list(range(2016, 2027))
BAZA_ROKY = (2016, 2017, 2018)
HR = D.HR
MIS = ('січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень', 'жовтень',
       'листопад', 'грудень')
MIS_R = ('січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня', 'листопада',
         'грудня')
DNI = ('пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'нд')
DNI_POVNI = ('понеділок', 'вівторок', 'середа', 'четвер', "п'ятниця", 'субота', 'неділя')
CHASTYNY = (('ніч', 0, 6), ('ранок', 6, 12), ('день', 12, 18), ('вечір', 18, 24))
SEZONY = (('зима', (12, 1, 2)), ('весна', (3, 4, 5)), ('літо', (6, 7, 8)), ('осінь', (9, 10, 11)))
# Групи, які здебільшого виявляє сама поліція (189, розд. 4.1): число показує й роботу поліції.
PROAKTYVNI = {'vod', 'nar', 'por', 'alk'}
R_MISTSIA = 300                      # коло публічного місця, м (як візуал «Для медіа», MV-135, і 189)
MIN_POLE = 20                        # рядок поля — коли значення є щонайменше в 20 подіях…
MIN_ZAPOVNENO = .15                  # …і щонайменше в 15 % подій групи
MIN_OSOBA = 30                       # поля особи (стать) — лише з базою ≥ 30 (189, розд. 4.1)
RAZIV = 2.0                          # позначка «частіше / рідше, ніж по Києву» — різниця щонайменше вдвічі…
Q = .01                              # …і невипадкова (Бенджаміні — Гохберг, q = 0,01, на всі перевірки картки)


# ---------------------------------------------------------------- слова й числа

def vids(x: float) -> str:
    """частка → «31 %», малі — з комою"""
    p = 100 * x
    if p >= 9.95:
        return f'{p:.0f}{NB}%'
    if p >= 0.95:
        return f'{p:.1f}'.replace('.', ',') + f'{NB}%'
    return f'{p:.1f}'.replace('.', ',') + f'{NB}%' if p >= .05 else f'<{NB}0,1{NB}%'


def raz(r: float) -> str:
    """1,9 → «удвічі», 3,2 → «у 3,2 раза»"""
    if 1.9 <= r < 2.1:
        return 'удвічі'
    if 2.9 <= r < 3.1:
        return 'утричі'
    if 3.9 <= r < 4.1:
        return 'учетверо'
    return f'у {r:.1f}'.replace('.', ',') + ' раза' if r < 5 else f'у {r:.0f} разів'


def podii_sl(n: int) -> str:
    return Z.vidminok(n, ('подія', 'події', 'подій'))


def mis_t(ym: str) -> str:
    return f'{MIS[int(ym[5:7]) - 1]} {ym[:4]}'


def mis_plus(ym: str, k: int) -> str:
    t = int(ym[:4]) * 12 + int(ym[5:7]) - 1 + k
    return f'{t // 12:04d}-{t % 12 + 1:02d}'


def p_dvobichne(k: int, n: int, p0: float) -> float:
    """біноміальна перевірка частки (нормальне наближення з поправкою на неперервність; бази тут ≥ 20)"""
    if n == 0 or p0 <= 0 or p0 >= 1:
        return 1.0
    mu, sd = n * p0, math.sqrt(n * p0 * (1 - p0))
    z = (abs(k - mu) - .5) / sd if sd else 0
    return math.erfc(max(z, 0) / math.sqrt(2))


# ---------------------------------------------------------------- дані

class Dani:
    def __init__(self, pkl: str):
        d = pickle.load(open(pkl, 'rb'))
        self.versiia = d['versiia']
        self.podii = d['podii']
        mezha, ost = povnota.mezhi((p['hr'], p['data'], p['drish']) for p in self.podii)
        self.ostannie = ost
        # останній повний місяць кожної групи (S-Р.9: очікувана повнота ≥ 90 %)
        self.ost_mis = {h: povnota.ostannii_povnyi(h, mezha, ost) for h in HR.KLIUCHI}
        self.vikno12 = {h: (mis_plus(m, -11), m) for h, m in self.ost_mis.items()}
        self.vikno36 = {h: (mis_plus(m, -35), m) for h, m in self.ost_mis.items()}

    def u_vikni(self, p, vikno) -> bool:
        return bool(p['mis']) and vikno[0] <= p['mis'] <= vikno[1]


# ---------------------------------------------------------------- числа однієї групи

def rozpodil(xs, kl, maks=3, min_chastka=.03):
    """[(значення, частка, k)] серед подій, де значення є; і заповненість"""
    c = Counter(kl(p) for p in xs)
    c.pop(None, None); c.pop('', None)
    n = sum(c.values())
    if not n:
        return [], 0, 0
    return [(v, k / n, k) for v, k in c.most_common(maks) if k / n >= min_chastka], n, n / len(xs) if xs else 0


def pokarannia(p):
    v = p['pas'].get('pokarannia')
    if not v:
        return None
    if 'з випробуванням' in v or v == 'пробаційний нагляд':
        return 'умовно чи нагляд'
    if v == 'позбавлення права керувати':
        return 'позбавлення права керувати'
    return {'штраф': 'штраф', 'звільнено від відповідальності': 'звільнено', 'позбавлення волі': 'позбавлення волі',
            'громадські роботи': 'громадські роботи', 'попередження': 'попередження', 'арешт': 'арешт',
            'обмеження волі': 'обмеження волі'}.get(v, 'інше')


def shkoda(p):
    for f in ('shkoda', 'vartist'):
        v = p['pas'].get(f)
        try:
            x = float(v)
            if 0 < x < 5e6:
                return x
        except (TypeError, ValueError):
            pass
    return None


NASLIDKY = {'легкі тілесні ушкодження': 'травми', 'середньої тяжкості тілесні ушкодження': 'травми',
            'тяжкі тілесні ушкодження': 'травми', 'фізичний біль без ушкоджень': 'травми', 'смерть потерпілого': 'загибель'}

# Поля за групами: (ключ, підпис, функція значення). Порядок — порядок рядків у блоці.
CIL = {
    'dtp': [('zitknennia', 'Зіткнення з')],
    'vod': [],
    'kra': [('berut', 'Беруть'), ('u_koho', 'У кого')],
    'nas': [('khto', 'На кого'), ('berut', 'Беруть')],
    'nar': [('rechovyna', 'Речовина')],
    'por': [('na_koho', 'На кого'), ('poriadok', 'Де саме'), ('zbroia', 'Зброя')],
    'alk': [('shcho_prodaiut', 'Продають'), ('poriadok', 'Де саме')],
}
NAZVY_ZNACHEN = {'PVP': '«соль» (PVP)', 'інше авто': 'інше авто', 'опора, огорожа': 'опора чи огорожа',
                 'велосипед, самокат': 'велосипед чи самокат', 'родина': 'родина (домашнє)'}


def nz(v: str) -> str:
    return NAZVY_ZNACHEN.get(v, v)


def blok_hrupy(dn: Dani, h: str, xs: list, ref: list | None, kyiv_sl: str, rayon: bool) -> dict:
    """усі числа блоку групи h: xs — події місця (усі роки), ref — події порівняння (решта Києва / схожі місця)"""
    v12, v36 = dn.vikno12[h], dn.vikno36[h]
    roky = Counter(p['rik'] for p in xs)
    seriia = [roky.get(r, 0) for r in ROKY]
    n10 = sum(seriia)
    n12 = sum(1 for p in xs if dn.u_vikni(p, v12))
    w = [p for p in xs if dn.u_vikni(p, v36)]
    wr = [p for p in ref if dn.u_vikni(p, v36)] if ref is not None else None
    nepovni = [r for r in ROKY if f'{r}-12' > dn.ost_mis[h]]
    baza = sum(roky.get(r, 0) for r in BAZA_ROKY) / len(BAZA_ROKY)
    # одне речення динаміки
    if baza + n12 < 20:
        dyn = ('malo', 'Подій мало — про зміну за 10 років сказати не можна.')
    else:
        r = (n12 + .5) / (baza + .5)
        z = (n12 - baza) / math.sqrt(n12 + baza / 3 + 1)
        tam = f'≈{NB}{chyslo(round(baza))} на рік у 2016–2018, {chyslo(n12)} — за останні 12 повних місяців'
        if r >= 1.25 and z > 2.5:
            dyn = ('bilshe', f'Стало більше: {tam} ({raz(r) + " більше" if r >= 1.9 else "на " + vids(r - 1) + " більше"}).')
        elif r <= .8 and z < -2.5:
            dyn = ('menshe', f'Стало менше: {tam} ({raz(1 / r) + " менше" if r <= 1 / 1.9 else "на " + vids(1 - r) + " менше"}).')
        else:
            dyn = ('stabilno', f'Приблизно стільки ж: {tam}.')
        dyn = dyn + (r,)
    ryadky = []      # (підпис, [(текст значення, частка, k, перевірка)], примітка)
    perevirky = []   # (k, n, p0, де) — для позначок «частіше, ніж по Києву»

    def ryadok(pidpys, kl, maks=3, porivniaty=True, zapovn=True, min_ch=.03):
        top, n, fill = rozpodil(w, kl, maks, min_ch)
        if n < MIN_POLE or fill < MIN_ZAPOVNENO or not top:
            return
        if top[0][1] >= .95 and len(top) == 1:
            return                          # одне значення на всіх — нічого не каже
        if wr is not None and porivniaty:
            cr = Counter(kl(p) for p in wr); cr.pop(None, None); cr.pop('', None)
            nr = sum(cr.values())
        znach = []
        for v, ch, k in top:
            pv = None
            if wr is not None and porivniaty and nr >= 50:
                p0 = cr.get(v, 0) / nr
                pv = [k, n, p0, None]
                perevirky.append(pv)
            znach.append([nz(v), ch, k, pv])
        ryadky.append([pidpys, znach, f'вказано в {vids(fill)} рішень' if zapovn and fill < .8 else ''])

    ryadok('Найчастіше', lambda p: p['nazva'] or None)
    for kl, pidpys in CIL[h]:
        ryadok(pidpys, lambda p, kl=kl: p['ts'].get(kl))
    if h in ('kra', 'nas'):
        ryadok('Як це сталося', lambda p: p['vr'])
        ryadok('Телефони', lambda p: p['tel'][0] if p['tel'] else None, porivniaty=False)
        sh = [x for x in (shkoda(p) for p in w if p['ts'].get('berut') or h == 'kra') if x]
        if len(sh) >= MIN_POLE and len(sh) / len(w) >= MIN_ZAPOVNENO:
            m = statistics.median(sh)
            m = round(m, -2) if m >= 1000 else round(m, -1)
            ryadky.append(['Шкода', [[f'у половині випадків — до {chyslo(int(m))}{NB}грн', None, None, None]],
                           f'вказано в {vids(len(sh) / len(w))} рішень'])
        pov = sum(1 for p in w if p['pas'].get('povernuto'))
        if h == 'kra' and pov >= MIN_POLE:
            ryadky.append(['Майно повернули', [[f'{vids(pov / len(w))} випадків', None, None, None]], ''])
    if h == 'dtp':
        nasl = Counter(NASLIDKY.get(p['pas'].get('tiazhkist')) for p in w)
        if nasl['травми'] + nasl['загибель'] >= 5:
            t = f'травмовані — {vids(nasl["травми"] / len(w))} ДТП ({chyslo(nasl["травми"])})'
            if nasl['загибель']:
                t += f'; загинули люди — {chyslo(nasl["загибель"])} {Z.vidminok(nasl["загибель"], ("ДТП", "ДТП", "ДТП"))}'
            ryadky.append(['Наслідки', [[t, None, None, None]], 'решта — пошкоджені авто чи майно'])
        # марки — усіх учасників, не лише винуватця (189); частка залежить і від того, скільки таких авто їздить
        c = Counter(m for p in w for m in p['avto'])
        nn = sum(1 for p in w if p['avto'])
        if nn >= MIN_POLE:
            ryadky.append(['Марки авто', [[f'{m} {vids(k / nn)}', None, None, None] for m, k in c.most_common(4)],
                           'усіх учасників; частка залежить і від того, скільки таких авто їздить'])
    if h in ('nas', 'por', 'dtp'):
        sp = sum(1 for p in w if p['spian'] or p['pas'].get('kvalifikatsiia') == "у стані сп'яніння")
        if sp >= MIN_POLE and sp / len(w) >= .02:
            ryadky.append(["У стані сп'яніння", [[f'{vids(sp / len(w))} подій', None, None, None]], 'за описом у рішенні'])
    ryadok('Тип місця', lambda p: p['pas'].get('typ_mistsia'), porivniaty=rayon)
    # коли
    kol = {}
    god = [p['god'] for p in w if p['god'] is not None]
    if len(god) >= 30 and len(god) / len(w) >= .5:
        kol['doba'] = [(n_, sum(1 for g in god if a <= g < b) / len(god)) for n_, a, b in CHASTYNY]
    dni = [p['dn'] for p in w if p['dn'] is not None]
    if len(dni) >= 30:
        kol['dni'] = [sum(1 for x in dni if x == i) / len(dni) for i in range(7)]
    misiatsi = [int(p['mis'][5:7]) for p in w if p['mis']]
    if len(misiatsi) >= 30:
        kol['sezon'] = [(n_, sum(1 for m in misiatsi if m in ms) / len(misiatsi)) for n_, ms in SEZONY]
    # хто: жінки (поле особи — лише зведено, база ≥ 30)
    stat = [p['pas'].get('stat') for p in w if p['pas'].get('stat') in ('ч', 'ж')]
    if len(stat) >= MIN_OSOBA:
        ryadky.append(['Жінки серед порушників', [[vids(stat.count('ж') / len(stat)), None, None, None]], ''])
    # чим закінчилось — залежить від суду: без порівняння з Києвом
    top, n, fill = rozpodil(w, pokarannia, 4, .03)
    if n >= MIN_POLE:
        zn = [[v, ch, k, None] for v, ch, k in top]
        if h in ('vod', 'dtp'):
            pp = sum(1 for p in w if p['pas'].get('dodatkove') == 'позбавлення права керування'
                     or p['pas'].get('pokarannia') == 'позбавлення права керувати')
            if pp >= MIN_POLE:
                zn = [z for z in zn if z[0] != 'позбавлення права керувати']
                zn.append([f'позбавили права керувати — {vids(pp / len(w))}', None, None, None])
        ryadky.append(['Чим закінчилось у суді', zn, 'залежить і від суду'])
    # позначка групи: частка групи серед усіх подій місця за 10 років
    return {'h': h, 'nazva': HR.NAZVA[h], 'n10': n10, 'n12': n12, 'vikno12': v12, 'vikno36': v36, 'seriia': seriia,
            'nepovni': nepovni, 'baza': baza, 'dyn': dyn, 'ryadky': ryadky, 'koly': kol, 'n36': len(w),
            'perevirky': perevirky, 'kyiv_sl': kyiv_sl}


def bh(perevirky: list):
    """Бенджаміні — Гохберг (q = Q) на всі перевірки картки; позначка — лише велика (≥ RAZIV) і невипадкова різниця"""
    ps = []
    for pv in perevirky:
        k, n, p0, _ = pv
        ps.append(p_dvobichne(k, n, p0))
    m = len(ps)
    poriadok = sorted(range(m), key=lambda i: ps[i])
    mezha = -1
    for j, i in enumerate(poriadok, 1):
        if ps[i] <= Q * j / m:
            mezha = j
    prokhodiat = set(poriadok[:mezha]) if mezha > 0 else set()
    for i, pv in enumerate(perevirky):
        k, n, p0, _ = pv
        ch = k / n
        r = ch / p0 if p0 else float('inf')
        if i in prokhodiat and k >= 10 and (r >= RAZIV or r <= 1 / RAZIV):
            pv[3] = (r, p0)


def kartka(dn: Dani, xs: list, ref: list, kyiv_sl: str, rayon: bool, min_hrupa: int = 0) -> dict:
    za_hr = defaultdict(list)
    for p in xs:
        za_hr[p['hr']].append(p)
    ref_hr = defaultdict(list)
    for p in ref:
        ref_hr[p['hr']].append(p)
    vsogo10 = sum(1 for p in xs if p['rik'] in ROKY)
    ref10 = sum(1 for p in ref if p['rik'] in ROKY)
    bloky, mali = [], []
    perev = []
    for h in HR.KLIUCHI:
        n10 = sum(1 for p in za_hr[h] if p['rik'] in ROKY)
        if n10 < min_hrupa:
            if n10:
                mali.append((h, n10))
            continue
        b = blok_hrupy(dn, h, za_hr[h], ref_hr[h], kyiv_sl, rayon)
        k_ref = sum(1 for p in ref_hr[h] if p['rik'] in ROKY)
        b['chastka'] = n10 / vsogo10 if vsogo10 else 0
        b['p_hrupy'] = [n10, vsogo10, k_ref / ref10 if ref10 else 0, None]
        perev.append(b['p_hrupy'])
        perev.extend(b['perevirky'])
        bloky.append(b)
    bh(perev)
    return {'vsogo10': vsogo10, 'bloky': bloky, 'mali': mali}


def rechennia(k: dict, de: str) -> list:
    """3 головні речення — програмою з чисел: що найчастіше; що найбільше зросло; що найбільше зменшилось (або відмінність)"""
    bl = sorted(k['bloky'], key=lambda b: -b['n10'])
    out = []
    if bl:
        dali = ', '.join(f'{HR.SLOVO[b["h"]]} ({vids(b["chastka"])})' for b in bl[1:3])
        out.append(f'З 2016 року в даних судів — {chyslo(k["vsogo10"])} {podii_sl(k["vsogo10"])} з точним місцем {de}; '
                   f'найбільше — {HR.SLOVO[bl[0]["h"]]} ({vids(bl[0]["chastka"])})' + (f', далі — {dali}' if dali else '') + '.')
    zm = [b for b in k['bloky'] if b['dyn'][0] in ('bilshe', 'menshe')]
    vg = sorted((b for b in zm if b['dyn'][0] == 'bilshe'), key=lambda b: -b['dyn'][2])
    vn = sorted((b for b in zm if b['dyn'][0] == 'menshe'), key=lambda b: b['dyn'][2])
    def r_(b, slovo):
        r = b['dyn'][2]
        f = (raz(r) if r >= 1.9 else 'на ' + vids(r - 1)) if r > 1 else (raz(1 / r) if r <= 1 / 1.9 else 'на ' + vids(1 - r))
        return (f'{slovo} за 10 років — {HR.SLOVO[b["h"]]}: ≈{NB}{chyslo(round(b["baza"]))} на рік у 2016–2018 і '
                f'{chyslo(b["n12"])} за останні 12 повних місяців ({f} {"більше" if r > 1 else "менше"}).')
    if vg:
        out.append(r_(vg[0], 'Найбільше зросли'))
    if vn:
        out.append(r_(vn[0], 'Найбільше зменшились'))
    if len(out) < 3:
        # найсильніша позначка відмінності
        kr = []
        for b in k['bloky']:
            for pid, zn, _ in b['ryadky']:
                for v, ch, kk, pv in zn:
                    if pv and pv[3]:
                        kr.append((abs(math.log(pv[3][0])), b, pid, v, ch, pv[3]))
        if kr:
            _, b, pid, v, ch, (r, p0) = max(kr, key=lambda x: x[0])
            dop = '' if pid == 'Найчастіше' else f' ({pid.lower()})'
            out.append(f'Найпомітніша відмінність: {v}{dop} — {vids(ch)} серед подій групи «{b["nazva"]}» '
                       f'({b["kyiv_sl"]} — {vids(p0)}).')
    if len(out) < 3 and len(zm) == 0:
        out.append('Жодна група за 10 років помітно не зросла й не зменшилась.')
    return out[:3]


# ---------------------------------------------------------------- розмітка

def svg_roky(b: dict) -> str:
    s = b['seriia']
    maks = max(s) or 1
    W, H, bw, gap = 330, 64, 24, 6
    ch = []
    for i, (r, n) in enumerate(zip(ROKY, s)):
        h = max(round(n / maks * (H - 14)), 1 if n else 0)
        x = i * (bw + gap)
        kl = 'st-nep' if r in b['nepovni'] else 'st'
        ch.append(f'<rect class="{kl}" x="{x}" y="{H - 14 - h}" width="{bw}" height="{h}" rx="3"><title>{r}: {chyslo(n)}'
                  f'{" — неповний рік" if r in b["nepovni"] else ""}</title></rect>')
        if r in (2016, 2021, 2026):
            ch.append(f'<text x="{x + bw / 2}" y="{H - 1}" text-anchor="middle">{r}</text>')
    nep = (f'<p class="gr__nep">Світлі стовпчики — {", ".join(map(str, b["nepovni"]))}: рік ще неповний, свіжі рішення '
           f'доходять до реєстру із запізненням.</p>' if b['nepovni'] else '')
    return (f'<svg class="gr__roky" viewBox="0 0 {len(ROKY) * (bw + gap) - gap} {H}" role="img" '
            f'aria-label="Події за роками 2016–2026: {", ".join(f"{r} — {n}" for r, n in zip(ROKY, s))}">'
            + ''.join(ch) + '</svg>' + nep)


def poznachka(pv, kyiv_sl: str) -> str:
    if not pv or not pv[3]:
        return ''
    r, p0 = pv[3]
    t = f'{raz(r)} частіше' if r > 1 else f'{raz(1 / r)} рідше'
    return f' <span class="gr__pozn">{t}, ніж {kyiv_sl} ({vids(p0)})</span>'


def smuzhky(pary, klas='') -> str:
    maks = max(ch for _, ch in pary) or 1
    return ('<span class="smuzhky ' + klas + '">' + ''.join(
        f'<span class="smuzhky__st"><span class="smuzhky__stovp"><i class="vys-{min(20, round(ch / maks * 20))}"></i></span>'
        f'<span class="smuzhky__p">{e(n)}</span></span>' for n, ch in pary) + '</span>')


def koly_html(kol: dict) -> str:
    if not kol:
        return ''
    ch = []
    if 'doba' in kol:
        top = max(kol['doba'], key=lambda x: x[1])
        ch.append(f'<div class="koly__ch"><span class="koly__t">Частина доби</span>{smuzhky(kol["doba"])}'
                  f'<span class="koly__p">найчастіше — {top[0]} ({vids(top[1])})</span></div>')
    if 'dni' in kol:
        d = kol['dni']
        i = max(range(7), key=lambda j: d[j])
        vykh = d[5] + d[6]
        ch.append(f'<div class="koly__ch"><span class="koly__t">Дні тижня</span>{smuzhky(list(zip(DNI, d)))}'
                  f'<span class="koly__p">найчастіше — {DNI_POVNI[i]} ({vids(d[i])}); субота й неділя — {vids(vykh)}</span></div>')
    if 'sezon' in kol:
        top = max(kol['sezon'], key=lambda x: x[1])
        ch.append(f'<div class="koly__ch"><span class="koly__t">Сезон</span>{smuzhky(kol["sezon"])}'
                  f'<span class="koly__p">найчастіше — {top[0]} ({vids(top[1])})</span></div>')
    return '<div class="gr__ryad gr__ryad--koly"><dt>Коли</dt><dd><div class="koly">' + ''.join(ch) + '</div></dd></div>'


def blok_html(b: dict) -> str:
    v12 = b['vikno12']
    v36 = b['vikno36']
    pozn_hr = poznachka(b['p_hrupy'], b['kyiv_sl'] + ' (частка серед усіх подій)') if b['p_hrupy'][3] else ''
    if b['p_hrupy'][3]:
        r, p0 = b['p_hrupy'][3]
        pozn_hr = (f'<span class="gr__pozn">{vids(b["chastka"])} усіх подій — {raz(r)} {"більше" if r > 1 else "менше"}, '
                   f'ніж {b["kyiv_sl"]} ({vids(p0)})</span>')
    ryad = []
    for pid, zn, prym in b['ryadky']:
        tz = ' · '.join(
            (f'{e(v)} <b>{vids(ch)}</b>' if ch is not None else e(v)) + poznachka(pv, b['kyiv_sl']) for v, ch, k, pv in zn)
        ryad.append(f'<div class="gr__ryad"><dt>{e(pid)}</dt><dd>{tz}'
                    + (f' <span class="gr__prym">{e(prym)}</span>' if prym else '') + '</dd></div>')
    koly = koly_html(b['koly'])
    # «Коли» — після цілі й полів події, перед «хто» і «чим закінчилось»
    i = next((j for j, r in enumerate(ryad) if 'Жінки серед' in r or 'Чим закінчилось' in r), len(ryad))
    ryad.insert(i, koly)
    proakt = ('<p class="gr__prym gr__politsiia">Такі справи здебільшого виявляє сама поліція — число показує й її роботу.</p>'
              if b['h'] in PROAKTYVNI else '')
    return f'''<section class="gr" id="gr-{b['h']}">
<header class="gr__shapka"><h3><span class="gr__krapka gr__krapka--{b['h']}" aria-hidden="true"></span>{e(b['nazva'])}</h3>
<p class="gr__chysla"><b>{chyslo(b['n10'])}</b> {podii_sl(b['n10'])} з 2016 року · <b>{chyslo(b['n12'])}</b> за останні 12 повних місяців
<span class="gr__prym">({mis_t(v12[0])} — {mis_t(v12[1])})</span></p>{pozn_hr}</header>
{svg_roky(b)}
<p class="gr__dyn gr__dyn--{b['dyn'][0]}">{b['dyn'][1]}</p>
<dl class="gr__polia"><p class="gr__period">Далі — за 3 роки: {mis_t(v36[0])} — {mis_t(v36[1])} ({chyslo(b['n36'])} {podii_sl(b['n36'])}).</p>
{''.join(ryad)}</dl>{proakt}
</section>'''


def hrupy_html(k: dict) -> str:
    out = ''.join(blok_html(b) for b in k['bloky'])
    if k['mali']:
        out += ('<p class="rozdil__pidpys">Інших груп тут майже немає: ' + ', '.join(
            f'{HR.SLOVO[h]} — {chyslo(n)}' for h, n in k['mali']) + ' за 10 років.</p>')
    return out


def lyst_html(nazva: str, lyst: dict) -> str:
    ryad = ''.join(f'<li>{e(HR.NAZVA[h])} — <b>{chyslo(n)}</b></li>' for h, n in lyst['hrupy'])
    vul = ', '.join(e(v) for v in lyst['vulytsi'])
    return f'''<div class="lyst" aria-label="Приклад листа">
<p class="lyst__vid">Моя вулиця · «Нове поруч» · {e(nazva)}</p>
<p class="lyst__tema"><b>У даних з'явилось {chyslo(lyst['vsogo'])} {Z.vidminok(lyst['vsogo'], ('нова подія', 'нові події', 'нових подій'))}</b> — рішення судів, оприлюднені з {lyst['vid']} по {lyst['do']}</p>
<ul class="lyst__hr">{ryad}</ul>
<p class="lyst__p">Найбільше нового — на вулицях: {vul}.</p>
<p class="lyst__p lyst__zamok">У листі підписника — кожна подія з адресою, стислим описом і посиланням на рішення суду.</p>
<p class="lyst__prym">Приклад на справжніх числах: рішення, що вийшли за місяць до {lyst['do']}.</p>
</div>'''


def poshuk_html(zaholovok: str, pidpys: str, dzherelo: str) -> str:
    return f'''<section class="rozdil plat plat--poshuk"><h2>{e(zaholovok)}</h2>
<p class="rozdil__pidpys">{pidpys}</p>
<form class="plat__poshuk" action="/miy-budynok/" method="get" role="search">
<label class="prykhovano" for="adresa-{dzherelo}">Вулиця й номер будинку</label>
<input class="plashka plat__pole" id="adresa-{dzherelo}" name="adresa" type="search" placeholder="Вулиця й номер будинку" autocomplete="off">
<input type="hidden" name="dzherelo" value="{dzherelo}">
<button class="knopka plat__knopka" type="submit">Знайти</button></form>
<p class="plat__dali">Безкоштовно: скарги 1551 і події з рішень судів числом по будинку. Для купівлі чи оренди — довідка про будинок за {T.TSINY['dovidka']}{NB}грн або повний звіт за {T.TSINY['zvit']}{NB}грн.</p>
</section>'''


def problemy_html(de: str, dzherelo: str) -> str:
    return f'''<section class="rozdil problemy-190"><h2>Проблеми {de}</h2>
<p class="rozdil__pidpys">Проблема — місце, де однотипні події повторюються роками. Це не оцінка місця, а повтор у даних.</p>
<div class="problemy-190__ch">
<div class="plashka problemy-190__kl"><span>Тривають</span><b class="bude">буде</b></div>
<div class="plashka problemy-190__kl"><span>Згасли</span><b class="bude">буде</b></div>
</div>
<p class="plat__dali">Назви й кількість — тут, безкоштовно. Де саме, як це відбувається й описи подій — у звіті адреси:
<a href="/miy-budynok/?dzherelo={dzherelo}-problemy">Які проблеми біля вашого будинку →</a></p>
<p class="gr__prym">«буде» — проблеми повного Києва ще рахуються; числа з'являться після повного проходу.</p>
</section>'''


def stezhyty_html(shcho: str, nazva: str, lyst: dict, dzherelo: str) -> str:
    return f'''<section class="rozdil plat"><h2>Стежити за {shcho}</h2>
<p class="rozdil__pidpys">Після кожного оновлення даних — лист «Нове поруч»: що нового з'явилось у рішеннях судів {e(nazva)}. Входить у підписку
за {T.TSINY['pidpyska']}{NB}грн на місяць (з нею — і довідка про будинок щомісяця).</p>
{lyst_html(nazva, lyst)}
<p><a class="knopka plat__knopka" href="/oplata/?tovar=pidpyska&amp;dzherelo={dzherelo}-stezhyty">Стежити — підписка</a></p>
</section>'''


def osbb_html() -> str:
    return f'''<section class="rozdil plat"><h2>Для ОСББ</h2>
<p class="rozdil__pidpys">Щомісяця — довідка вашого будинку: скарги 1551 і події з рішень судів поруч, у порівнянні із сусідніми будинками.
{chyslo(T.TSINY['osbb'])}{NB}грн на рік за будинок.</p>
<p><a class="knopka plat__knopka" href="/osbb/?dzherelo=rayon">Для ОСББ</a></p></section>'''


def biznes_media_html(nazva: str) -> str:
    return f'''<section class="rozdil plat"><h2>Для бізнесу поруч</h2>
<p class="rozdil__pidpys">Магазин, кафе, аптека чи ТЦ біля {e(nazva)}: звіт місця — крадіжки, ДТП на парковці, порушення порядку біля
вашої адреси по місяцях і годинах, у порівнянні зі схожими місцями. Без назв інших мереж. Ціна за домовленістю.</p>
<p><a class="knopka plat__knopka" href="/biznes/?dzherelo=mistse">Запит для бізнесу</a></p></section>
<section class="rozdil plat"><h2>Для медіа</h2>
<p class="rozdil__pidpys">Картки з числами цього місця для статті чи сюжету — з посиланням на джерело.</p>
<p><a href="/doslidnykam/">Дані для дослідників і медіа →</a></p></section>'''


def storinka(slug: str, mitka: str, nazva_h1: str, de: str, k: dict, rech: list, vstup: str, dodatok: str, tilo_pislia: str,
             title: str) -> str:
    tilo = f'''<p class="maket-190">Макет картки · на сайт не викладено · числа справжні, повний Київ (випуск {DN.versiia[0]})</p>
<section class="zaholovok"><span class="mitka">{e(mitka)}</span><h1>{e(nazva_h1)}</h1>
{''.join(f'<p>{r}</p>' for r in rech)}
<p class="zaholovok__opys">{vstup}</p></section>
{dodatok}
<section class="rozdil"><h2>Усі 7 груп подій</h2>
<p class="rozdil__pidpys rozdil__pidpys--holovne"><b>Подія — випадок із рішення суду.</b> Лише те, що дійшло до суду; не всі події
й не оцінка {de}. Числа за останні місяці менші, бо свіжі рішення ще доходять до реєстру; «останні 12 повних місяців» — до місяця,
коли їх уже дійшло щонайменше 90{NB}%.</p>
{hrupy_html(k)}
</section>
{tilo_pislia}'''
    s = Z.storinka(shlyakh=f'/maket-190/{slug}/', title=title, opys=title, tilo=tilo, adresa_saitu='https://moya-vulytsya.example',
                   indeksuvaty=False)
    # Самодостатній файл: без політики безпеки (вбудовані стилі), стилі сайту — всередині, шрифти — з site/sait/shryfty.
    s = re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>\n', '', s)
    s = re.sub(r'<script[^>]*></script>\n?', '', s)
    s = re.sub(r'<link rel="(preload|icon|manifest)"[^>]*>\n', '', s)
    css = (Z.kolory_css() + (KORIN / 'site' / 'sait' / 'sait.css').read_text(encoding='utf-8')
           + (TUT / 'kartka-190.css').read_text(encoding='utf-8')).replace('url(shryfty/', 'url(../../site/sait/shryfty/')
    s = s.replace('<link rel="stylesheet" href="/sait/sait.css">', f'<style>\n{css}\n</style>')
    return s


# ---------------------------------------------------------------- лист «Нове поруч» (приклад)

def lyst_dani(xs: list, ostannie) -> dict:
    import datetime as dt
    do = ostannie
    vid = do - dt.timedelta(days=30)
    nov = [p for p in xs if p['drish'] and vid.isoformat() < p['drish'] <= do.isoformat()]
    vul = Counter()
    for p in nov:
        a = (p['adresa'] or '')
        if p['tochn'] == 'house' and ',' in a:
            vul[a.rsplit(',', 1)[0].strip()] += 1          # без номера будинку
        elif p['tochn'] == 'cross':
            for ch in re.sub(r'^перехрестя\s+', '', a).split(' / '):
                vul[ch.strip()] += 1
    hr = Counter(p['hr'] for p in nov)
    return {'vsogo': len(nov), 'hrupy': [(h, hr[h]) for h in HR.KLIUCHI if hr[h]],
            'vulytsi': [v for v, _ in vul.most_common(3)],
            'vid': f'{vid.day + 1} {MIS_R[vid.month - 1]}', 'do': f'{do.day} {MIS_R[do.month - 1]} {do.year}'}


# ---------------------------------------------------------------- місця

def vidstan(la1, lo1, la2, lo2):
    return math.hypot((la2 - la1) * 111320, (lo2 - lo1) * 111320 * math.cos(math.radians(la1)))


class Sitka:
    def __init__(self, podii):
        self.s = defaultdict(list)
        for i, p in enumerate(podii):
            if p['lat'] is not None:
                self.s[(int(p['lat'] / .005), int(p['lon'] / .007))].append(i)
        self.podii = podii

    def kolo(self, la, lo, r):
        a, b = int(la / .005), int(lo / .007)
        return [i for di in (-1, 0, 1) for dj in (-1, 0, 1) for i in self.s.get((a + di, b + dj), ())
                if vidstan(la, lo, self.podii[i]['lat'], self.podii[i]['lon']) <= r]


def tsentry_mists(podii) -> dict:
    """назване місце (станція метро, вокзал) → середина точок його назви (як site/sait/mistsia.py)"""
    t = defaultdict(list)
    for p in podii:
        a = p['adresa'] or ''
        if p['tochn'] == 'mistse' and (a.startswith('ст. м. ') or a.startswith('вокзал ') or a == 'Вокзальна площа'):
            t[a].append((p['lat'], p['lon']))
    return {a: (statistics.median(x for x, _ in v), statistics.median(y for _, y in v)) for a, v in t.items() if len(v) >= 10}


# ---------------------------------------------------------------- головне

if __name__ == '__main__':
    DN = Dani(PKL)
    P = DN.podii
    z_tochkoiu = [p for p in P if p['lat'] is not None]
    chysla = {'versiia': DN.versiia, 'ostannie_rishennia': DN.ostannie.isoformat(), 'ost_mis': DN.ost_mis, 'kartky': {}}

    # район «за точкою» (як на сайті) і «за судом» (як у 189)
    porivn = {'zbih_tochka_sud': None, 'rayony': {}}
    zb = sum(1 for p in z_tochkoiu if p['r_tochka'] and p['r_tochka'] == p['r_sud'])
    zv = sum(1 for p in z_tochkoiu if p['r_tochka'] and p['r_sud'])
    porivn['zbih_tochka_sud'] = [zb, zv]
    for r in sorted({p['r_tochka'] for p in z_tochkoiu if p['r_tochka']}):
        za_t = Counter(p['hr'] for p in z_tochkoiu if p['r_tochka'] == r and p['rik'] in ROKY)
        za_s = Counter(p['hr'] for p in P if p['r_sud'] == r and p['rik'] in ROKY)
        za_s_t = Counter(p['hr'] for p in z_tochkoiu if p['r_sud'] == r and p['rik'] in ROKY)
        porivn['rayony'][r] = {'tochka': dict(za_t), 'sud': dict(za_s), 'sud_z_tochkoiu': dict(za_s_t)}

    sitka = Sitka(P)
    tsentry = tsentry_mists(P)
    stantsii = [a for a in tsentry if a.startswith('ст. м. ') or a.startswith('вокзал ')]

    zavdannia = [
        ('podilskyi', 'rayon', 'Подільський'),
        ('darnytskyi', 'rayon', 'Дарницький'),
        ('st-m-zhytomyrska', 'mistse', 'ст. м. «Житомирська»'),
        ('vokzalna-ploshcha', 'mistse', 'Вокзальна площа'),
    ]
    for slug, typ, nazva in zavdannia:
        if typ == 'rayon':
            xs = [p for p in z_tochkoiu if p['r_tochka'] == nazva]
            ref = [p for p in z_tochkoiu if p['r_tochka'] and p['r_tochka'] != nazva]
            k = kartka(DN, xs, ref, 'в решті Києва', True)
            de = 'у районі'
            rech = rechennia(k, de)
            # неповнолітні — одним числом на район (MV-206), лише за 3 останні роки повних даних
            w = [p for p in xs if p['rik'] in (2023, 2024, 2025)]
            nep = sum(1 for p in w if p['pas'].get('nepovnolitnii') or p['pas'].get('vikova_hrupa') == '<18')
            vstup = (f'Район — за точкою події в межах району, як на сайті. Неповнолітні серед порушників за 2023–2025 — '
                     f'{vids(nep / len(w))} подій ({chyslo(nep)}); це нижня межа: суд пише вік не завжди.')
            lyst = lyst_dani(xs, DN.ostannie)
            dodatok = (poshuk_html('Перевірити свій будинок у цьому районі',
                                   'Знайдіть свою адресу — на сторінці будинку числа саме по ньому.', 'rayon')
                       + problemy_html('району', 'rayon'))
            pislia = stezhyty_html('районом', f'{nazva} район', lyst, 'rayon') + osbb_html()
            html_ = storinka(slug, 'Київ · район', f'{nazva} район', 'району', k, rech, vstup, dodatok, pislia,
                             f'{nazva} район — події з рішень судів за 10 років | Моя вулиця')
        else:
            la, lo = tsentry[nazva]
            idx = set(sitka.kolo(la, lo, R_MISTSIA))
            xs = [P[i] for i in idx]
            # схожі місця — кола інших станцій метро й вокзалів (без самого місця)
            ref_i = set()
            for a in stantsii:
                if a == nazva:
                    continue
                la2, lo2 = tsentry[a]
                if vidstan(la, lo, la2, lo2) < 2 * R_MISTSIA:
                    continue
                ref_i.update(sitka.kolo(la2, lo2, R_MISTSIA))
            ref_i -= idx
            ref = [P[i] for i in ref_i]
            k = kartka(DN, xs, ref, 'біля інших станцій метро й вокзалів', False, min_hrupa=5)
            de = f'у колі {R_MISTSIA}{NB}м'
            rech = rechennia(k, de)
            vstup = (f'Події з точним місцем у колі {R_MISTSIA}{NB}м навколо {"станції" if "ст. м." in nazva else "площі"} — '
                     f'на вулиці, у переходах, у закладах поруч. Групи — лише ті, що тут трапляються.')
            lyst = lyst_dani(xs, DN.ostannie)
            imia = 'Станція метро «Житомирська»' if 'Житомирськ' in nazva else 'Вокзальна площа'
            imia_r = 'станції метро «Житомирська»' if 'Житомирськ' in nazva else 'Вокзальної площі'
            dodatok = (poshuk_html('Перевірити будинок поруч', f'Живете чи орендуєте біля {imia_r}? Знайдіть свою адресу.',
                                   'mistse')
                       + problemy_html('поруч', 'mistse'))
            pislia = (stezhyty_html('місцем', f'біля {imia_r}', lyst, 'mistse') + biznes_media_html(imia_r))
            mitka = 'Київ · станція метро' if 'ст. м.' in nazva else 'Київ · площа біля вокзалу'
            html_ = storinka(slug, mitka, imia, 'місця', k, rech, vstup, dodatok, pislia,
                             f'{imia} — події з рішень судів за 10 років | Моя вулиця')
        (TUT / f'{slug}.html').write_text(html_, encoding='utf-8')
        chysla['kartky'][slug] = {
            'nazva': nazva, 'typ': typ, 'vsogo10': k['vsogo10'], 'rechennia': rech, 'mali': k['mali'],
            'lyst': lyst,
            'bloky': [{x: b[x] for x in ('h', 'n10', 'n12', 'vikno12', 'vikno36', 'seriia', 'nepovni', 'baza', 'n36', 'koly')}
                      | {'dyn': b['dyn'][1], 'chastka': b['chastka'],
                         'poznachka_hrupy': b['p_hrupy'][3],
                         'ryadky': [[pid, [[v, ch, kk, (pv[3] if pv else None)] for v, ch, kk, pv in zn], prym]
                                    for pid, zn, prym in b['ryadky']]}
                      for b in k['bloky']]}
        print(slug, k['vsogo10'], [(b['h'], b['n10'], b['dyn'][0]) for b in k['bloky']], file=sys.stderr)
    (TUT / 'chysla.json').write_text(json.dumps(chysla, ensure_ascii=False, indent=1), encoding='utf-8')
    (TUT / 'rayon-sud-tochka.json').write_text(json.dumps(porivn, ensure_ascii=False, indent=1), encoding='utf-8')
