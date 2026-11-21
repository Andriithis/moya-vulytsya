# -*- coding: utf-8 -*-
"""ZAVDANNYA-194: сторінка району й місця людською мовою + сторінки «вид порушення × місце» (макет, на сайт не йде).

Бере витяг макета 190 (`docs/makety-190/vytiah.py`), словник `slovnyk-vydiv.json` і пише в цю теку:
  * огляд-сторінки: `podilskyi.html`, `darnytskyi.html`, `st-m-zhytomyrska.html`, `vokzalna-ploshcha.html`;
  * сторінки «вид × місце»: `kradizhky-podilskyi.html`, `dtp-darnytskyi.html`, `narkotyky-kyiv.html`;
  * `chysla.json` — усі числа сторінок (лише зведені, без адрес і описів); `pokryttia-slovnyka.json` — які статті з топу
    покрито словником.

    python docs/makety-194/zibraty.py <vytiah.pkl> <../dani-edrsr>

Правила: MV-210 (район — за судом; без «чим закінчилось у суді»; без марок авто), MV-211 (людською мовою, одне число в
реченні, розділи сторінки, не картки), MV-212 (огляд короткий, глибина — на сторінці «вид × місце»). Числа й перевірки
відмінностей — ті самі, що в макеті 190 (`docs/makety-190/zibraty.py`, звідти й беруться).
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parents[1]
_spec = importlib.util.spec_from_file_location('z190', KORIN / 'docs' / 'makety-190' / 'zibraty.py')
Z190 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(Z190)            # той самий sys.argv: <pkl> <dani-edrsr>
Z, T, D = Z190.Z, Z190.T, Z190.D
sys.path.insert(0, str(KORIN / 'site'))
import zaholovky as ZH  # noqa: E402

e, chyslo, NB = Z.e, Z.chyslo, Z190.NB


def vids(x: float) -> str:
    """частка → «8 %», без коми; менше 1 % — «менше 1 %»"""
    return f'{round(100 * x)}{NB}%' if x >= .005 else f'менше 1{NB}%'
ROKY, BAZA_ROKY, HR = Z190.ROKY, Z190.BAZA_ROKY, Z190.HR
SL = json.loads((TUT / 'slovnyk-vydiv.json').read_text(encoding='utf-8'))
VYDY = SL['vydy']
MIN_REChENNIA = 40          # вид у головному реченні — коли «2016–2018 на рік + останній рік» ≥ 40 подій
PIZNO: set = set()         # види, яких у 2016–2018 у даних майже немає (справи тоді не доходили до суду) — заповнює головне
VIKNO_V: dict = {}         # вид → своє «останні 12 повних місяців» (povnota за видом, до 36 місяців назад)
POLITSIIA = ('<p class="blok__pidpys">«Стали ловити» чи «затримувати частіше» — про справи, які з\'являються, лише коли поліція когось затримала: '
             'могло стати більше випадків, а могло — більше перевірок. З даних цього не розрізнити.</p>')
OST_T: dict = {}           # вид → «липня 2026» (кінець його повного року) — для пояснення внизу сторінки
MIN_RAZ = 1.5               # …і зміна щонайменше в півтора раза (і невипадкова, як у 190: z > 2,5)

# Розділи сторінки району (назви — людською мовою; MV-211) і сторінки «вид × місце» (адреса й слова для пошуку — MV-212)
HRM = {
    'dtp': dict(slug='dtp', rozdil='Аварії (ДТП)', h1='ДТП', rod='Аварій', seo='ДТП', dali='ДТП'),
    'vod': dict(slug='vodii', rozdil='Порушення за кермом', h1='Порушення за кермом', rod='Справ про порушення за кермом',
                seo="П'яні за кермом і порушення водіїв", dali='порушення за кермом'),
    'kra': dict(slug='kradizhky', rozdil='Крадіжки й шахрайство', h1='Крадіжки й шахрайство', rod='Крадіжок і шахрайства',
                seo='Крадіжки', dali='крадіжки й шахрайство'),
    'nas': dict(slug='nasylstvo', rozdil='Насильство й грабежі', h1='Насильство й грабежі',
                rod='Випадків насильства й грабежів', seo='Насильство й грабежі', dali='насильство й грабежі'),
    'nar': dict(slug='narkotyky', rozdil='Наркотики', h1='Наркотики', rod='Справ про наркотики', seo='Наркотики',
                dali='наркотики'),
    'por': dict(slug='khuliganstvo', rozdil='Хуліганство й порядок', h1='Хуліганство й порушення порядку',
                rod='Справ про хуліганство й порядок', seo='Хуліганство', dali='хуліганство й порядок'),
    'alk': dict(slug='alkohol', rozdil='Алкоголь, цигарки й торгівля', h1='Алкоголь, цигарки й торгівля',
                rod='Справ про алкоголь, цигарки й торгівлю', seo='Алкоголь, цигарки й торгівля',
                dali='алкоголь, цигарки й торгівля'),
}
# Як люди називають частини району в пошуку («крадіжки Поділ», «ДТП Позняки»)
RAYON_LOK = {
    'Голосіївський': ('у Голосієві й на Теремках', 'Голосіїв, Теремки, Деміївка'),
    'Дарницький': ('на Позняках, Осокорках і Дарниці', 'Позняки, Осокорки, Харківський, Бортничі'),
    'Деснянський': ('на Троєщині й Лісовому', 'Троєщина, Лісовий масив, Биківня'),
    'Дніпровський': ('на Русанівці, Березняках і Лівобережній', 'Русанівка, Березняки, Лівобережна, ДВРЗ'),
    'Оболонський': ('на Оболоні', 'Оболонь, Мінський масив, Пріорка'),
    'Печерський': ('на Печерську', 'Печерськ, Липки, Звіринець'),
    'Подільський': ('на Подолі', 'Поділ, Куренівка, Виноградар'),
    'Святошинський': ('на Святошині й Борщагівці', 'Святошин, Борщагівка, Академмістечко'),
    "Солом'янський": ("на Солом'янці й Чоколівці", "Солом'янка, Чоколівка, Відрадний"),
    'Шевченківський': ('у центрі й на Лук\'янівці', "центр, Лук'янівка, Татарка"),
}
POLIA = {   # (група, поле) → людське питання
    ('dtp', 'zitknennia'): 'З чим зіткнулись',
    ('kra', 'berut'): 'Що крадуть',
    ('nas', 'khto'): 'Хто кривдник', ('nas', 'berut'): 'Що відбирають',
    ('nar', 'rechovyna'): 'Які наркотики',
    ('por', 'na_koho'): 'Проти кого', ('por', 'poriadok'): 'Де саме', ('por', 'zbroia'): 'Яка зброя',
    ('alk', 'shcho_prodaiut'): 'Що продають', ('alk', 'poriadok'): 'Де саме',
}
ZNACHENNIA = {'інше авто': 'з іншим авто', 'припарковане авто': 'з припаркованим авто', 'опора, огорожа': 'з опорою чи огорожею',
              'пішохід': 'з пішоходом', 'велосипед, самокат': 'з велосипедом чи самокатом',
              'магазин': 'з магазинів', 'людина': 'у людей', 'підприємство': 'з підприємств і складів',
              'родина': 'хтось із родини', 'знайомий': 'знайомий', 'незнайомець': 'незнайомець',
              'PVP': '«соль» (синтетичний стимулятор PVP)', 'метадон': 'метадон', 'канабіс': 'канабіс (марихуана)',
              'поліція': 'поліцейських', 'перехожі': 'перехожих', 'майно': 'чужого майна', 'персонал закладу': 'працівників закладу',
              'родина, знайомі': 'родини чи знайомих', 'сусіди': 'сусідів',
              'вулиця, громадське місце': 'на вулиці', 'заклад': 'у кафе, барі чи магазині', 'громадський транспорт': 'у транспорті',
              "двір, під'їзд": "у дворі чи під'їзді", 'житло': 'у житлі',
              'тютюн і вейпи': 'цигарки й вейпи',
              'передав сам': 'власник сам віддав — повірив', 'при собі на виду': 'річ була на виду, при собі',
              'не замкнено': 'не було замкнено', "сон чи сп'яніння власника": "власник спав чи був п'яний",
              'без нагляду': 'лишили без нагляду', 'ключі доступні': 'ключі були під рукою',
              'магазин чи заклад торгівлі': 'магазин', 'двір чи прибудинкова територія': 'двір', "під'їзд чи сходи": "під'їзд",
              'кафе, бар чи ресторан': 'кафе чи бар', 'вокзал чи зупинка': 'вокзал чи зупинка', 'парк чи сквер': 'парк чи сквер'}
DOBA = {'ніч': 'вночі', 'ранок': 'зранку', 'день': 'вдень', 'вечір': 'увечері'}
DNI_Z = ('у понеділок', 'у вівторок', 'у середу', 'у четвер', "у п'ятницю", 'у суботу', 'у неділю')
SEZON_Z = {'зима': 'взимку', 'весна': 'навесні', 'літо': 'влітку', 'осінь': 'восени'}


# ---------------------------------------------------------------- вид події за словником

OSOBLYVI = SL['osoblyvi']


def vyd_podii(p) -> str | None:
    for o in OSOBLYVI:
        if p['st'] in o['statti']:
            if 'mekhanizm' in o and p['sim'] == o['mekhanizm']:
                return o['vyd']
            if 'pole' in o and p['ts'].get(o['pole']) in o['znachennia']:
                return o['vyd']
    return SL['statti'].get(p['st'])


# ---------------------------------------------------------------- слова й числа

SLOVA = {1: ('один', 'одна', 'одне'), 2: ('два', 'дві', 'два'), 3: 'три', 4: 'чотири', 5: "п'ять", 6: 'шість', 7: 'сім',
         8: 'вісім', 9: "дев'ять", 10: 'десять'}


def skilky(n: int, lich) -> str:
    """3, ['аварія', 'аварії', 'аварій', 'ж'] → «три аварії»"""
    s = SLOVA.get(n)
    if isinstance(s, tuple):
        s = s['чжс'.index(lich[3])]
    return f'{s or chyslo(n)} {Z.vidminok(n, lich[:3])}'


DE = ''                   # «на весь район» / «по всьому Києву» — щоб «щодня п'ять аварій» не читали як «у моєму дворі»
TYZHDEN = False           # райони: усе «щотижня» — одна мірка, щоб не рахувати в голові (свіжі очі, раунд 2)
ZA_RIK = False            # місця (коло 300 м): усе — «за рік», щоб рядки можна було порівняти без рахунку в голові


def chastota(n12: int, lich) -> str:
    """скільки за останні 12 повних місяців → «щодня в середньому три аварії на весь район»"""
    if ZA_RIK:
        return f'за рік — {skilky(n12, lich)}'
    if TYZHDEN:
        x = n12 / 52.18
        return (f'щотижня в середньому {skilky(round(x), lich)}{DE}' if x >= .75 else f'за рік — {skilky(n12, lich)}{DE}')
    for za, dilnyk in (('щодня', 365), ('щотижня', 52.18), ('щомісяця', 12)):
        x = n12 / dilnyk
        if x >= 1.5:
            return f'{za} в середньому {skilky(round(x), lich)}{DE}'
    return f'за рік — {skilky(n12, lich)}{DE}' if n12 else 'за рік — жодного'


def raz_sl(r: float) -> str:
    """1,5 → «в півтора раза»; 2 → «удвічі»; 3,2 → «утричі»; 7 → «у 7 разів» (округлення до половини)"""
    if r < 1:
        r = 1 / r
    x = round(r * 2) / 2
    return {1.0: 'трохи', 1.5: 'в півтора раза', 2.0: 'удвічі', 2.5: 'у два з половиною раза', 3.0: 'утричі',
            3.5: 'у три з половиною раза', 4.0: 'учетверо', 4.5: 'у чотири з половиною раза', 5.0: "уп'ятеро"}.get(
        x, f'у {round(r)} разів')


def dynamika(baza: float, n12: int):
    if baza + n12 < 20:
        return ('malo', None)
    r = (n12 + .5) / (baza + .5)
    z = (n12 - baza) / math.sqrt(n12 + baza / 3 + 1)
    if r >= 1.25 and z > 2.5:
        return ('bilshe', r)
    if r <= .8 and z < -2.5:
        return ('menshe', r)
    return ('stabilno', r)


def velyka(s: str) -> str:
    return s[:1].upper() + s[1:]


def v_(slovo_pered: str, dali: str) -> str:
    """«у/в» за милозвучністю: після голосної перед приголосною — «в»"""
    return 'в' if slovo_pered[-1:] in Z.GOLOSNI or dali[:1] in Z.GOLOSNI else 'у'


def u_rayoni(pered: str, r: str) -> str:
    return f'{v_(pered, Z.rayon_mistsevyi(r))} {Z.rayon_mistsevyi(r)} районі'


# ---------------------------------------------------------------- числа одного розділу (група в місці)

def rozdil(dn, h: str, xs: list, ref: list | None) -> dict:
    v12, v36 = dn.vikno12[h], dn.vikno36[h]
    roky = Counter(p['rik'] for p in xs)
    seriia = [roky.get(r, 0) for r in ROKY]
    n12 = sum(1 for p in xs if dn.u_vikni(p, v12))
    baza = sum(roky.get(r, 0) for r in BAZA_ROKY) / len(BAZA_ROKY)
    w = [p for p in xs if dn.u_vikni(p, v36)]
    wr = [p for p in ref if dn.u_vikni(p, v36)] if ref is not None else None
    # види (статті) — частка за 3 роки, частота за рік, зміна проти 2016–2018
    vydy = []
    za_v = defaultdict(list)
    for p in xs:
        za_v[p['vyd']].append(p)
    c36 = Counter(p['vyd'] for p in w)
    cr = Counter(p['vyd'] for p in wr) if wr is not None else None
    perevirky = []
    for v, ps in za_v.items():
        rv = Counter(p['rik'] for p in ps)
        b = sum(rv.get(r, 0) for r in BAZA_ROKY) / len(BAZA_ROKY)
        k12 = sum(1 for p in ps if dn.u_vikni(p, VIKNO_V.get(v, v12)))
        pv = None
        if cr is not None and v and sum(cr.values()) >= 50 and c36[v] >= 10:
            pv = [c36[v], len(w), cr[v] / sum(cr.values()), None]
            perevirky.append(pv)
        vydy.append(dict(vyd=v, n10=sum(rv.get(r, 0) for r in ROKY), n12=k12, baza=b, dyn=dynamika(b, k12),
                         chastka=c36[v] / len(w) if w else 0, pv=pv, pizno=v in PIZNO, vikno=VIKNO_V.get(v, v12)))
    vydy.sort(key=lambda x: (-x['n12'], -x['n10']))
    # група: «останній рік» і 2016–2018 — сума видів, кожен у своєму повному вікні (кримінальні справи доходять до суду
    # роками, адміністративні — за тижні; спільне вікно групи дало б фальшивий спад)
    # зміна розділу — лише за видами, що були в даних і у 2016–2018 (інакше «зростання» — це нові для суду справи)
    n12 = sum(v['n12'] for v in vydy if not v['pizno'])
    baza = sum(v['baza'] for v in vydy if not v['pizno'])
    # поля цілі й обставин — за 3 роки (як у 190)
    polia = []

    def pole(kl, pidpys, porivniaty=True, maks=3):
        top, n, fill = Z190.rozpodil(w, kl, maks, .03)
        if n < Z190.MIN_POLE or fill < Z190.MIN_ZAPOVNENO or not top or (len(top) == 1 and top[0][1] >= .95):
            return
        if wr is not None and porivniaty:
            crr = Counter(kl(p) for p in wr); crr.pop(None, None); crr.pop('', None)
            nr = sum(crr.values())
        zn = []
        for v, ch, k in top:
            pv = None
            if wr is not None and porivniaty and nr >= 50:
                pv = [k, n, crr.get(v, 0) / nr, None]
                perevirky.append(pv)
            zn.append([ZNACHENNIA.get(v, v), ch, k, pv])
        polia.append([pidpys, zn, f'частки — серед рішень, де суд це вказав; таких {vids(fill)}' if fill < .95 else ''])

    for (hh, kl), pidpys in POLIA.items():
        if hh == h:
            pole(lambda p, kl=kl: p['ts'].get(kl), pidpys)
    if h in ('kra', 'nas'):
        pole(lambda p: p['vr'], 'Як це сталося')
        pole(lambda p: p['tel'][0] if p['tel'] else None, 'Які телефони крадуть', porivniaty=False)
    dod = {}
    if h in ('kra', 'nas'):
        sh = [x for x in (Z190.shkoda(p) for p in w if p['ts'].get('berut') or h == 'kra') if x]
        if len(sh) >= Z190.MIN_POLE and len(sh) / len(w) >= Z190.MIN_ZAPOVNENO:
            m = statistics.median(sh)
            dod['shkoda'] = (round(m, -2) if m >= 1000 else round(m, -1), len(sh) / len(w))
        pov = sum(1 for p in w if p['pas'].get('povernuto'))
        if h == 'kra' and pov >= Z190.MIN_POLE:
            dod['povernuto'] = pov / len(w)
    if False and h == 'dtp' and w:      # тяжкість у паспорті заповнена мало — «0,3 % з травмами» вводило б в оману
        nasl = Counter(Z190.NASLIDKY.get(p['pas'].get('tiazhkist')) for p in w)
        dod['naslidky'] = (nasl['травми'], nasl['загибель'], len(w))
    if h in ('nas', 'por', 'dtp') and w:
        sp = sum(1 for p in w if p['spian'] or p['pas'].get('kvalifikatsiia') == "у стані сп'яніння")
        if sp >= Z190.MIN_POLE and sp / len(w) >= .02:
            dod['spian'] = sp / len(w)
    if h not in ('dtp', 'vod'):          # для аварій і водіїв це майже завжди «дорога» — нічого не каже
        pole(lambda p: p['pas'].get('typ_mistsia'), 'Де це сталося', porivniaty=ref is not None)
    stat = [p['pas'].get('stat') for p in w if p['pas'].get('stat') in ('ч', 'ж')]
    if False and len(stat) >= Z190.MIN_OSOBA:    # «навіщо мені це» (свіжі очі, 194) — прибрано
        dod['zhinky'] = stat.count('ж') / len(stat)
    # коли
    kol = {}
    god = [p['god'] for p in w if p['god'] is not None]
    if len(god) >= 30 and len(god) / len(w) >= .5:
        kol['doba'] = [(n_, sum(1 for g in god if a <= g < b) / len(god)) for n_, a, b in Z190.CHASTYNY]
    dni = [p['dn'] for p in w if p['dn'] is not None]
    if len(dni) >= 30:
        kol['dni'] = [sum(1 for x in dni if x == i) / len(dni) for i in range(7)]
    mis = [int(p['mis'][5:7]) for p in w if p['mis']]
    if len(mis) >= 30:
        kol['sezon'] = [(n_, sum(1 for m in mis if m in ms) / len(mis)) for n_, ms in Z190.SEZONY]
    return dict(h=h, seriia=seriia, n10=sum(seriia), n12=n12, baza=baza, dyn=dynamika(baza, n12), vikno12=v12, vikno36=v36,
                nepovni=[r for r in ROKY if f'{r}-12' > dn.ost_mis[h]], n36=len(w), vydy=vydy, polia=polia, dod=dod,
                koly=kol, perevirky=perevirky)


def mistse(dn, xs: list, ref: list | None, min_hrupa: int = 0) -> dict:
    za_hr, ref_hr = defaultdict(list), defaultdict(list)
    for p in xs:
        za_hr[p['hr']].append(p)
    for p in ref or ():
        ref_hr[p['hr']].append(p)
    rozdily, mali, perev = [], [], []
    for h in HR.KLIUCHI:
        n10 = sum(1 for p in za_hr[h] if p['rik'] in ROKY)
        if n10 < max(min_hrupa, 1):
            if n10:
                mali.append((h, n10))
            continue
        r = rozdil(dn, h, za_hr[h], ref_hr[h] if ref is not None else None)
        perev.extend(r['perevirky'])
        rozdily.append(r)
    if perev:
        Z190.bh(perev)
    return dict(rozdily=rozdily, mali=mali, vsogo10=sum(1 for p in xs if p['rik'] in ROKY))


# ---------------------------------------------------------------- речення

def staryi(v: dict) -> str:
    """« (рік до листопада 2023 — новіші справи ще в судах)», коли повний рік виду закінчився давно"""
    kin = VIKNO_V.get(v['vyd'], (None, None))[1]
    naisv = max(x[1] for x in VIKNO_V.values())
    if kin and (int(naisv[:4]) * 12 + int(naisv[5:7])) - (int(kin[:4]) * 12 + int(kin[5:7])) > 12:
        return f' (рік до {OST_T[v["vyd"]]} — новіші справи ще в судах)'
    return ''


def rech_chasto(v: dict, pochatok: str = 'Найчастіше') -> str:
    s = VYDY[v['vyd']]
    return f'{pochatok} — {s["nazva"]}: {chastota(v["n12"], s["lich"])}{staryi(v)}.'


def rech_zmina(v: dict) -> str:
    s = VYDY[v['vyd']]
    t = s['zrist'] if v['dyn'][0] == 'bilshe' else s['spad']
    return t.format(raz=raz_sl(v['dyn'][1])) + ', ніж у 2016–2018 роках' + staryi(v) + '.'


def holovni(k: dict) -> list:
    """3 головні речення сторінки: найчастіший вид; що найбільше зросло; що найбільше зменшилось (MV-211)"""
    vs = [v for r in k['rozdily'] for v in r['vydy'] if v['vyd'] and VYDY[v['vyd']].get('v_holovni', True) and not v['pizno']]
    out = []
    if vs:
        out.append(('chasto', max(vs, key=lambda v: v['n12'])))
    zm = [v for v in vs if v['baza'] + v['n12'] >= MIN_REChENNIA and v['dyn'][0] in ('bilshe', 'menshe')
          and max(v['dyn'][1], 1 / v['dyn'][1]) >= MIN_RAZ]
    vg = [v for v in zm if v['dyn'][0] == 'bilshe']
    vn = [v for v in zm if v['dyn'][0] == 'menshe']
    if vg:
        out.append(('zmina', max(vg, key=lambda v: v['dyn'][1])))
    if vn:
        out.append(('zmina', min(vn, key=lambda v: v['dyn'][1])))
    inshi = sorted((v for v in vs if all(v is not x for _, x in out)), key=lambda v: -v['n12'])
    while len(out) < 3 and inshi:
        out.append(('dali', inshi.pop(0)))
    res, dali = [], 0
    for t, v in out[:3]:
        if t == 'dali':
            res.append(rech_chasto(v, ('Далі', 'Ще')[min(dali, 1)])); dali += 1
        else:
            res.append(rech_chasto(v) if t == 'chasto' else rech_zmina(v))
    return res


def koly_rech(kol: dict) -> str:
    ch = []
    if 'doba' in kol:
        n, x = max(kol['doba'], key=lambda t: t[1])
        ch.append(DOBA[n] + {'ніч': ' (0–6)', 'ранок': ' (6–12)', 'день': ' (12–18)', 'вечір': ' (18–24)'}[n]
                  if x >= .35 else 'у будь-яку пору доби')
    if 'dni' in kol:
        d = kol['dni']
        i = max(range(7), key=lambda j: d[j])
        if d[i] >= 1.3 / 7:
            ch.append(DNI_Z[i])
        elif d[5] + d[6] <= 2 / 7 * .8:
            ch.append('у будні')
        else:
            ch.append('в усі дні тижня приблизно однаково')
    t = 'Найчастіше — ' + (', '.join(ch) if ch else 'без помітної пори')
    if 'sezon' in kol:
        n, x = max(kol['sezon'], key=lambda t: t[1])
        if x >= .29:
            t += f'; найбільше — {SEZON_Z[n]}'
    return t + '.'


# ---------------------------------------------------------------- розмітка

def svg_roky(r: dict, maly: bool = False) -> str:
    s = r['seriia']
    maks = max(s) or 1
    W, H, bw, gap = (240, 44, 16, 6) if maly else (330, 72, 24, 6)
    ch = []
    for i, (rik, n) in enumerate(zip(ROKY, s)):
        h = max(round(n / maks * (H - 14)), 2)
        x = i * (bw + gap)
        kl = 'st-nul' if not n else 'st-nep' if rik in r['nepovni'] else 'st'
        ch.append(f'<rect class="{kl}" x="{x}" y="{H - 14 - h}" width="{bw}" height="{h}" rx="2"><title>{rik}: {chyslo(n)}'
                  f'{" — рік ще неповний" if rik in r["nepovni"] else ""}</title></rect>')
        if rik in ((2016, 2026) if maly else (2016, 2021, 2026)):
            yak = 'start' if rik == 2016 else 'end' if rik == 2026 else 'middle'
            xx = x if rik == 2016 else x + bw if rik == 2026 else x + bw / 2
            ch.append(f'<text x="{xx}" y="{H - 1}" text-anchor="{yak}">{rik}</text>')
    return (f'<svg class="roky{" roky--maly" if maly else ""}" viewBox="0 0 {len(ROKY) * (bw + gap) - gap} {H}" role="img" '
            f'aria-label="Скільки за роками 2016–2026: {", ".join(f"{a} — {b}" for a, b in zip(ROKY, s))}">'
            + ''.join(ch) + '</svg>')


ZMINA_SL = {'bilshe': 'більше', 'menshe': 'менше', 'stabilno': 'приблизно стільки ж', 'malo': 'замало подій, щоб казати про зміну'}


def krapka(h: str) -> str:
    return f'<span class="gr__krapka gr__krapka--{h}" aria-hidden="true"></span>'


def rozdil_korotko(r: dict, posylannia: str, dali_t: str) -> str:
    """розділ огляд-сторінки: назва, одне речення, малий графік, «Детальніше →» (MV-212)"""
    holovnyi = (next((v for v in r['vydy'] if v['vyd'] and VYDY[v['vyd']].get('v_holovni', True)), None)
                or next((v for v in r['vydy'] if v['vyd']), None))
    rech = rech_chasto(holovnyi, 'Найчастіше') if holovnyi else ''
    return f'''<section class="rz" id="rz-{r['h']}">
<h2 class="rz__nazva">{krapka(r['h'])}{e(HRM[r['h']]['rozdil'])}</h2>
<p class="rz__rech">{e(rech)}</p>
<div class="rz__gr">{svg_roky(r, maly=True)}</div>
<a class="rz__dali" href="{posylannia}">Детальніше: {e(dali_t)} →</a>
</section>'''


def poshuk_html(zaholovok: str, pidpys: str, dzherelo: str) -> str:
    return f'''<section class="blok plat plat--poshuk"><h2>{e(zaholovok)}</h2>
<p class="blok__pidpys">{pidpys}</p>
<form class="plat__poshuk" action="/miy-budynok/" method="get" role="search">
<label class="prykhovano" for="adresa-{dzherelo}">Вулиця й номер будинку</label>
<input class="plashka plat__pole" id="adresa-{dzherelo}" name="adresa" type="search" placeholder="Вулиця й номер будинку" autocomplete="off">
<input type="hidden" name="dzherelo" value="{dzherelo}">
<button class="knopka plat__knopka" type="submit">Знайти</button></form>
<p class="plat__dali">Пошук безкоштовний: побачите, скільки чого було біля самого будинку. Платити не треба.
Якщо захочете більше — довідка для оренди чи купівлі ({T.TSINY['dovidka']}{NB}грн, коротко про будинок) або повний звіт
({T.TSINY['zvit']}{NB}грн, з описом кожної події).</p>
</section>'''


def problemy_html(zaholovok: str, dzherelo: str) -> str:
    return f'''<section class="blok"><h2>{e(zaholovok)}</h2>
<p class="blok__pidpys">Тут будуть місця, де однакові випадки повторюються роками (у даних ми звемо це «проблемою»). Це не оцінка
місця й не про ваш будинок — лише повтор у рішеннях судів.</p>
<p class="bude">Ще рахуємо для всього Києва — з'явиться після оновлення даних.</p>
</section>'''


def stezhyty_html(shcho: str, dzherelo: str) -> str:
    return f'''<section class="blok plat"><h2>Стежити за {e(shcho)}</h2>
<p class="blok__pidpys">Раз на місяць — лист: що нового з'явилось у рішеннях судів. Це платна підписка — {T.TSINY['pidpyska']}{NB}грн
на місяць; кнопка лише відкриває сторінку з умовами, гроші — тільки після вашого підтвердження.</p>
<p><a class="knopka plat__knopka" href="/oplata/?tovar=pidpyska&amp;dzherelo={dzherelo}-stezhyty">Стежити</a></p>
</section>'''


def pro_dani(de: str) -> str:
    return f'''<section class="blok blok--tykho"><h2>Звідки ці дані</h2>
<p>Усе тут — із рішень судів 2016–2026 років: лише те, що дійшло до суду, а не всі події {de}.</p>
<p>Водіїв напідпитку, наркотики, розпивання на вулиці суд бачить, лише коли людину затримала поліція. Тому «стали ловити частіше»
може означати і що такого стало більше, і що поліція стала більше перевіряти — з даних цього не розрізнити.</p>
<p>Рішення доходять до суду із запізненням: про аварії — за 1–3 місяці, про крадіжки й грабежі — за 1–3 роки. Тому «щотижня» й «за рік» рахуємо за
останні 12 місяців, про які рішення вже майже всі: для аварій — до {OST_T['dtp-doroha']}, для крадіжок у людей і грабежів — лише
до {OST_T['nas-hrabizh']}. Свіжіші роки на графіках світлі: там ще буде більше.</p>
</section>'''


def obolonka(slug: str, title: str, opys: str, kryhty: list, tilo: str, url: str) -> str:
    kr = '<nav class="kryhty" aria-label="Де ви">' + '<span aria-hidden="true">›</span>'.join(
        f'<a href="{h}">{e(n)}</a>' if h else f'<span>{e(n)}</span>' for h, n in kryhty) + '</nav>'
    tilo = (f'<p class="maket-194">Макет · на сайт не викладено · числа справжні, повний Київ (випуск {DN.versiia[0]})</p>\n'
            + kr + '\n' + tilo)
    s = Z.storinka(shlyakh=url, title=title, opys=opys, tilo=tilo, adresa_saitu='https://moya-vulytsya.example', indeksuvaty=True)
    s = re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>\n', '', s)
    s = re.sub(r'<script[^>]*></script>\n?', '', s)
    s = re.sub(r'<link rel="(preload|icon|manifest)"[^>]*>\n', '', s)
    css = (Z.kolory_css() + (KORIN / 'site' / 'sait' / 'sait.css').read_text(encoding='utf-8')
           + (TUT / 'kartka-194.css').read_text(encoding='utf-8')).replace('url(shryfty/', 'url(../../site/sait/shryfty/')
    return s.replace('<link rel="stylesheet" href="/sait/sait.css">', f'<style>\n{css}\n</style>')


# ---------------------------------------------------------------- огляд-сторінка (район чи місце)

def storinka_ohliad(slug, k, h1, pidzag, kryhty, url_dali, dali_de, dodatok_do, pislia, title, opys, url, de_dani) -> str:
    rech = holovni(k)
    rozd = ''.join(rozdil_korotko(r, url_dali(r['h']), f'{HRM[r["h"]]["dali"]} {dali_de}') for r in k['rozdily'])
    if k['mali']:
        rozd += ('<p class="blok__pidpys">Інше тут майже не трапляється: ' + ', '.join(
            f'{HRM[h]["rozdil"].lower()} — {chyslo(n)} за 10 років' for h, n in k['mali']) + '.</p>')
    tilo = f'''<section class="zaholovok"><h1>{e(h1)}</h1>
<p class="zaholovok__opys">{pidzag}</p></section>
<section class="holovne" aria-label="Головне"><ul>{''.join(f'<li>{e(r)}</li>' for r in rech)}</ul>{POLITSIIA if any('ловити' in r or 'затримувати' in r for r in rech) else ''}</section>
{dodatok_do}
<section class="rozdily"><h2 class="rozdily__zag">Що тут відбувається — по темах</h2>
<p class="blok__pidpys">Графік — скільки таких випадків щороку, 2016–2026. Світлі стовпчики — роки, за які рішення ще доходять до суду:
згодом там буде більше.</p>
{rozd}</section>
{pislia}
{pro_dani(de_dani)}'''
    return obolonka(slug, title, opys, kryhty, tilo, url), rech


# ---------------------------------------------------------------- сторінка «вид × місце»

def porivn_rech(r: dict, kyiv_sl: str) -> list:
    """відмінності від решти Києва — великі (≥ удвічі) й невипадкові (Бенджаміні — Гохберг, як у 190)"""
    out = []
    for v in r['vydy']:
        pv = v['pv']
        if pv and pv[3] and v['vyd']:
            ri, p0 = pv[3]
            t = f'{velyka(VYDY[v["vyd"]]["nazva"])} — {raz_sl(ri)} {"частіше" if ri > 1 else "рідше"}, ніж {kyiv_sl}'
            out.append((abs(math.log(ri)), t + f': {vids(pv[0] / pv[1])} проти {vids(p0)}.', t + '.'))
    for pid, zn, _ in r['polia']:
        for v, ch, k, pv in zn:
            if pv and pv[3]:
                ri, p0 = pv[3]
                t = f'{pid}: {v} — {raz_sl(ri)} {"частіше" if ri > 1 else "рідше"}, ніж {kyiv_sl}'
                out.append((abs(math.log(ri)), t + f': {vids(ch)} проти {vids(p0)}.', t + '.'))
    return [(t, k) for _, t, k in sorted(out, key=lambda x: -x[0])][:4]


def smuzhky_html(pary, pidpys: str) -> str:
    return (f'<div class="koly__ch"><span class="koly__t">{pidpys}</span>' + Z190.smuzhky(pary) + '</div>')


def storinka_vyd(slug, r, nazva_mistsia_v, kryhty, title, opys, url, kyiv_sl, posylannia, pislia, de_dani, rayony_html='') -> str:
    h = r['h']
    m = HRM[h]
    holovnyi = [v for v in r['vydy'] if v['vyd']]
    rech = []
    if holovnyi:
        rech.append(rech_chasto(holovnyi[0], 'Найчастіше'))
    if r['dyn'][0] in ('bilshe', 'menshe'):
        if h in Z190.PROAKTYVNI:
            rech.append(f'Таких справ поліція стала виявляти {raz_sl(r["dyn"][1])} {"частіше" if r["dyn"][0] == "bilshe" else "рідше"}, '
                        f'ніж у 2016–2018 роках.')
        else:
            rech.append(f'{m["rod"]} стало {raz_sl(r["dyn"][1])} {ZMINA_SL[r["dyn"][0]]}, ніж у 2016–2018 роках.')
    elif r['dyn'][0] == 'stabilno':
        t = f'{m["rod"]} загалом приблизно стільки ж, як у 2016–2018 роках'
        vv = [v for v in holovnyi[:5] if not v['pizno'] and v['dyn'][0] in ('bilshe', 'menshe') and v['chastka'] >= .05]
        bb = [VYDY[v['vyd']]['nazva'].split(' (')[0] for v in vv if v['dyn'][0] == 'bilshe']
        mm = [VYDY[v['vyd']]['nazva'].split(' (')[0] for v in vv if v['dyn'][0] == 'menshe']
        if bb and mm:
            t += f': {bb[0]} — більше, {mm[0]} — менше'
        rech.append(t + '.')
    porivn = porivn_rech(r, kyiv_sl) if kyiv_sl else []
    if porivn:
        rech.append(porivn[0][1])
    elif len(holovnyi) > 1:
        rech.append(rech_chasto(holovnyi[1], 'Далі'))
    # як змінювалось
    b, n12 = r['baza'], r['n12']
    dyn_t = {'bilshe': 'Стало більше', 'menshe': 'Стало менше', 'stabilno': 'Загалом без великої зміни',
             'malo': 'Замало подій, щоб казати про зміну'}[r['dyn'][0]]
    if h in Z190.PROAKTYVNI and r['dyn'][0] in ('bilshe', 'menshe'):
        dyn_t = 'Справ стало ' + ZMINA_SL[r['dyn'][0]]
    if r['dyn'][0] != 'malo':
        dyn_t += f': у 2016–2018 — близько {chyslo(round(b))} на рік, за останній рік — {chyslo(n12)}.'
    pizni = [VYDY[v['vyd']]['nazva'] for v in r['vydy'] if v['vyd'] and v['pizno'] and v['n12'] >= .05 * max(n12, 1)]
    if pizni:
        dyn_t += (f' Без таких справ: {"; ".join(pizni)} — у 2016–2018 їх у даних майже немає, порівнювати нема з чим.')
    # що саме
    vydy_html = []
    for v in holovnyi[:6]:
        s = VYDY[v['vyd']]
        if v['chastka'] < .01 and len(vydy_html) >= 3:
            break
        zm = 'до 2019 такі справи майже не потрапляли в дані судів — порівнювати нема з чим' if v['pizno'] else {
              'bilshe': '↑ більше випадків, ніж у 2016–2018' if not s.get('proakt') else '↑ ловлять частіше, ніж у 2016–2018',
              'menshe': '↓ менше випадків, ніж у 2016–2018' if not s.get('proakt') else '↓ ловлять рідше, ніж у 2016–2018',
              'stabilno': 'приблизно стільки ж', 'malo': ''}[v['dyn'][0]]
        zk = 'pizno' if v['pizno'] else v['dyn'][0]
        prym = f' <span class="prym">{e(s["prymitka"])}</span>' if s.get('prymitka') and v['dyn'][0] == 'bilshe' else ''
        vydy_html.append(f'<li><span class="vyd__n">{e(velyka(s["nazva"]))}</span><span class="vyd__smuha"><i style="width:'
                         f'{max(2, round(v["chastka"] * 100))}%"></i></span><span class="vyd__ch">{vids(v["chastka"])}</span>'
                         f'<span class="vyd__zm vyd__zm--{zk}">{zm}</span>{prym}</li>')
    # поля
    pol = []
    for pid, zn, prym in r['polia']:
        t = ' · '.join(f'{e(v)} <b>{vids(ch)}</b>' for v, ch, k, pv in zn)
        pol.append(f'<div class="pole"><dt>{e(pid)}</dt><dd>{t}' + (f' <span class="prym">({e(prym)})</span>' if prym else '')
                   + '</dd></div>')
    d = r['dod']
    if 'shkoda' in d:
        pol.append(f'<div class="pole"><dt>Скільки коштувало вкрадене</dt><dd>у половині випадків — до <b>{chyslo(int(d["shkoda"][0]))}{NB}грн</b>'
                   f' <span class="prym">(вказано в {vids(d["shkoda"][1])} рішень)</span></dd></div>')
    if 'povernuto' in d:
        pol.append(f'<div class="pole"><dt>Чи повернули вкрадене</dt><dd>так — у <b>{vids(d["povernuto"])}</b> випадків <span class="prym">(в інших суд про це не пише або не повернули)</span></dd></div>')
    if 'naslidky' in d:
        tr, zag, n = d['naslidky']
        t = f'травмовані люди — у <b>{vids(tr / n)}</b> аварій'
        if zag:
            t += f'; загинули люди — у {skilky(zag, ["аварії", "аваріях", "аваріях", "ж"]).replace("одна", "одній").replace("дві", "двох")}'
        pol.append(f'<div class="pole"><dt>Чи постраждали люди</dt><dd>{t}; в інших — пошкоджені авто чи майно</dd></div>')
    if 'spian' in d:
        pol.append(f'<div class="pole"><dt>Напідпитку</dt><dd>у <b>{vids(d["spian"])}</b> випадків <span class="prym">(за описом у рішенні)</span></dd></div>')
    if 'zhinky' in d:
        pol.append(f'<div class="pole"><dt>Жінки серед порушників</dt><dd><b>{vids(d["zhinky"])}</b></dd></div>')
    kol = r['koly']
    koly_html = ''
    if kol:
        ch = []
        if 'doba' in kol:
            ch.append(smuzhky_html(kol['doba'], 'Пора доби'))
        if 'dni' in kol:
            ch.append(smuzhky_html(list(zip(Z190.DNI, kol['dni'])), 'Дні тижня'))
        if 'sezon' in kol:
            ch.append(smuzhky_html(kol['sezon'], 'Сезон'))
        koly_html = f'''<section class="blok"><h2>Коли</h2><p class="blok__rech">{koly_rech(kol)}</p>
<div class="koly">{''.join(ch)}</div></section>'''
    porivn_html = ''
    if kyiv_sl:
        porivn_html = ('<section class="blok"><h2>Чим відрізняється від решти Києва</h2>'
                       + (('<ul class="spysok">' + ''.join(f'<li>{e(t)}</li>' for t, _ in porivn) + '</ul>'
                           '<p class="blok__pidpys">Лише великі різниці — щонайменше вдвічі, і такі, що не можуть бути випадковістю. '
                           'Частки — серед таких самих випадків за останні 3 роки.</p>') if porivn else
                          '<p>Великих відмінностей немає: тут усе приблизно так, як у решті Києва.</p>') + '</section>')
    v36 = r['vikno36']
    tilo = f'''<section class="zaholovok"><span class="mitka">{krapka(h)}{e(m['rozdil'])}</span><h1>{e(m['h1'])} {e(nazva_mistsia_v)}</h1>
<p class="zaholovok__opys">За рішеннями судів 2016–2026 років; це те, що дійшло до суду, а не всі випадки.</p></section>
<section class="holovne" aria-label="Головне"><ul>{''.join(f'<li>{e(t)}</li>' for t in rech)}</ul>{POLITSIIA if h in Z190.PROAKTYVNI else ''}</section>
<section class="blok"><h2>Як змінювалось за 10 років</h2>{svg_roky(r)}<p class="blok__pidpys">Світлі стовпчики — роки, за які
рішення ще доходять до суду: згодом там буде більше.</p><p class="blok__rech">{dyn_t}</p></section>
<section class="blok"><h2>Що саме</h2><p class="blok__pidpys">Частка серед усіх таких випадків за останні 3 роки
({Z190.mis_t(v36[0])} — {Z190.mis_t(v36[1])}). Під назвою — чи стало таких випадків більше, ніж у 2016–2018 роках.</p><ul class="vydy">{''.join(vydy_html)}</ul></section>
{f'<section class="blok"><h2>Подробиці</h2><p class="blok__pidpys">Із текстів рішень, за останні 3 роки. Суд пише це не завжди — тоді поруч сказано, у скількох рішеннях є.</p><dl class="polia">{"".join(pol)}</dl></section>' if pol else ''}
{koly_html}
{porivn_html}
{rayony_html}
{pislia}
{posylannia}
{pro_dani(de_dani)}'''
    return obolonka(slug, title, opys, kryhty, tilo, url), rech


# ---------------------------------------------------------------- головне

if __name__ == '__main__':
    DN = Z190.Dani(Z190.PKL)
    Z190.DN = DN
    P = DN.podii
    for p in P:
        p['vyd'] = vyd_podii(p)
    Z190.povnota.MAX_MIS = 36           # кримінальні справи: 90 % доходить до суду лише за 2–3 роки
    mezha_v, ost_v = Z190.povnota.mezhi((p['vyd'] or '-', p['data'], p['drish']) for p in P)
    for v in VYDY:
        m_ = Z190.povnota.ostannii_povnyi(v, mezha_v, ost_v)
        VIKNO_V[v] = (Z190.mis_plus(m_, -11), m_)
        OST_T[v] = f'{Z190.MIS_R[int(m_[5:7]) - 1]} {m_[:4]}'
    ser = defaultdict(Counter)
    for p in P:
        if p['vyd'] and p['rik']:
            ser[p['vyd']][p['rik']] += 1
    for v, c in ser.items():
        piznishe = sorted(c.get(r, 0) for r in range(2019, 2026))
        if min(c.get(r, 0) for r in BAZA_ROKY) < .25 * piznishe[len(piznishe) // 2]:
            PIZNO.add(v)
    print('пізно:', sorted(PIZNO), file=sys.stderr)
    print('вікна:', {v: VIKNO_V[v][1] for v in ('nas-hrabizh', 'kra-liudy', 'kra-mahazyn', 'dtp-doroha')}, file=sys.stderr)
    chysla = {'versiia': DN.versiia, 'ostannie_rishennia': DN.ostannie.isoformat(), 'ost_mis': DN.ost_mis, 'storinky': {}}
    RAYONY = sorted({p['r_sud'] for p in P if p['r_sud']})

    def zapysaty(slug, html_, rech, k_or_r):
        (TUT / f'{slug}.html').write_text(html_, encoding='utf-8')
        rr = k_or_r['rozdily'] if 'rozdily' in k_or_r else [k_or_r]
        chysla['storinky'][slug] = {'rechennia': rech, 'rozdily': [
            {x: r[x] for x in ('h', 'n10', 'n12', 'baza', 'seriia', 'nepovni', 'n36', 'koly', 'dod')}
            | {'dyn': [r['dyn'][0], r['dyn'][1]], 'vydy': [{x: v[x] for x in ('vyd', 'n10', 'n12', 'baza', 'chastka')}
                                                           | {'dyn': list(v['dyn']), 'vidminnist': v['pv'][3] if v['pv'] else None}
                                                           for v in r['vydy']],
               'polia': [[pid, [[v, ch, kk, (pv[3] if pv else None)] for v, ch, kk, pv in zn], pr] for pid, zn, pr in r['polia']]}
            for r in rr]}
        print(slug, rech, file=sys.stderr)

    za_rayonom = defaultdict(list)
    for p in P:
        if p['r_sud']:
            za_rayonom[p['r_sud']].append(p)

    # --- огляд районів (район — за судом, MV-210)
    for slug, nazva in (('podilskyi', 'Подільський'), ('darnytskyi', 'Дарницький')):
        DE, ZA_RIK, TYZHDEN = ' на весь район', False, True
        xs = za_rayonom[nazva]
        ref = [p for p in P if p['r_sud'] and p['r_sud'] != nazva]
        k = mistse(DN, xs, ref)
        rs = Z.slug_rayonu(nazva)
        lok, chastyny = RAYON_LOK[nazva]
        dodatok = (poshuk_html(f'Ваш будинок {u_rayoni("Ваш будинок", nazva)}', 'Знайдіть свою адресу — числа саме по вашому будинку.', 'rayon')
                   + problemy_html(f'Проблеми району', 'rayon'))
        pislia = stezhyty_html('районом', 'rayon') + f'''<section class="blok plat"><h2>Для ОСББ</h2>
<p class="blok__pidpys">Для об'єднання мешканців будинку. Щомісяця — довідка вашого будинку порівняно із сусідніми. {chyslo(T.TSINY['osbb'])}{NB}грн на рік за будинок.</p>
<p><a class="knopka plat__knopka knopka--druhorydna" href="/osbb/?dzherelo=rayon">Для ОСББ</a></p></section>'''
        html_, rech = storinka_ohliad(
            slug, k, f'Що відбувається {u_rayoni("відбувається", nazva)}',
            f'{chastyny}. За рішеннями судів 2016–2026 років; це те, що дійшло до суду, а не всі події.',
            [('/', 'Головна'), ('', f'{nazva} район')], lambda h: f'/{HRM[h]["slug"]}/{rs}/', u_rayoni('', nazva),
            dodatok, pislia, ZH.title_rayonu(nazva), ZH.opys_rayonu(nazva, 'події', '2016–2026', 'вулиці', None),
            f'/rayon/{rs}/', 'в районі')
        zapysaty(slug, html_, rech, k)

    # --- огляд публічних місць (коло 300 м, як у 190)
    sitka = Z190.Sitka(P)
    tsentry = Z190.tsentry_mists(P)
    stantsii = [a for a in tsentry if a.startswith('ст. м. ') or a.startswith('вокзал ')]
    for slug, nazva, imia_r, h1 in (('st-m-zhytomyrska', 'ст. м. «Житомирська»', 'станції метро «Житомирська»',
                                     'Що відбувається біля станції метро «Житомирська»'),
                                    ('vokzalna-ploshcha', 'Вокзальна площа', 'Вокзальної площі',
                                     'Що відбувається на Вокзальній площі')):
        DE, ZA_RIK = ' у колі 300 м', True
        la, lo = tsentry[nazva]
        idx = set(sitka.kolo(la, lo, Z190.R_MISTSIA))
        xs = [P[i] for i in idx]
        ref_i = set()
        for a in stantsii:
            la2, lo2 = tsentry[a]
            if a != nazva and Z190.vidstan(la, lo, la2, lo2) >= 2 * Z190.R_MISTSIA:
                ref_i.update(sitka.kolo(la2, lo2, Z190.R_MISTSIA))
        ref = [P[i] for i in ref_i - idx]
        k = mistse(DN, xs, ref, min_hrupa=5)
        dodatok = (poshuk_html('Живете чи орендуєте поруч?', f'Знайдіть свою адресу біля {imia_r} — числа саме по вашому будинку.', 'mistse')
                   + problemy_html('Проблеми поруч', 'mistse'))
        pislia = stezhyty_html('цим місцем', 'mistse') + f'''<section class="blok plat"><h2>Для бізнесу поруч</h2>
<p class="blok__pidpys">Магазин, кафе чи аптека біля {e(imia_r)}: звіт про вашу адресу — крадіжки, аварії на парковці, порядок поруч,
по місяцях і годинах. Ціна — за домовленістю.</p>
<p><a class="knopka plat__knopka knopka--druhorydna" href="/biznes/?dzherelo=mistse">Запит для бізнесу</a></p></section>'''
        imia = 'Станція метро «Житомирська»' if 'Житомирськ' in nazva else 'Вокзальна площа'
        html_, rech = storinka_ohliad(
            slug, k, h1, f'У колі 300{NB}м навколо — вулиці, переходи, заклади поруч. За рішеннями судів 2016–2026 років; '
                         f'це те, що дійшло до суду, а не всі події.',
            [('/', 'Головна'), ('', imia)], lambda h: f'/{HRM[h]["slug"]}/{slug}/', f'біля {imia_r}',
            dodatok, pislia, f'{imia}, Київ — що відбувається поруч за рішеннями судів',
            f'{imia} у Києві: що відбувається в колі 300 м за рішеннями судів 2016–2026 — аварії, крадіжки, порядок, '
            f'наркотики. Перевірте свій будинок поруч.', f'/mistse/{slug}/', 'тут')
        zapysaty(slug, html_, rech, k)

    # --- «вид × район» і «вид × Київ»
    def vyd_rayon(slug, h, nazva):
        global DE, ZA_RIK, TYZHDEN
        DE, ZA_RIK, TYZHDEN = ' на весь район', False, True
        xs = [p for p in za_rayonom[nazva] if p['hr'] == h]
        ref = [p for p in P if p['r_sud'] and p['r_sud'] != nazva and p['hr'] == h]
        k = mistse(DN, xs, ref)
        r = k['rozdily'][0]
        rs = Z.slug_rayonu(nazva)
        m = HRM[h]
        lok, chastyny = RAYON_LOK[nazva]
        inshi_vydy = ' · '.join(f'<a href="/{HRM[x]["slug"]}/{rs}/">{e(HRM[x]["rozdil"])}</a>' for x in HR.KLIUCHI if x != h)
        inshi_rayony = ' · '.join(f'<a href="/{m["slug"]}/{Z.slug_rayonu(x)}/">{e(x)}</a>' for x in RAYONY if x != nazva)
        posylannia = f'''<section class="blok blok--tykho"><h2>Ще про {e(nazva)} район</h2>
<p><a href="/rayon/{rs}/">Усе про {e(nazva)} район коротко →</a></p>
<p class="posylannia">{inshi_vydy}</p>
<h2>{e(m['h1'])} в інших районах Києва</h2><p class="posylannia">{inshi_rayony} · <a href="/{m['slug']}/">Увесь Київ</a></p></section>'''
        pislia = (poshuk_html(f'Ваш будинок {u_rayoni("Ваш будинок", nazva)}',
                              'Чи було щось таке біля вашого будинку — знайдіть свою адресу.', f'{m["slug"]}-rayon')
                  + problemy_html(f'Де {m["dali"]} повторюються роками', f'{m["slug"]}-rayon')
                  + stezhyty_html(f'темою «{m["rozdil"]}» {u_rayoni("темою", nazva)}', f'{m["slug"]}-rayon'))
        title = ZH.pershyi_shcho_vlize([f'{m["seo"]} {lok} — {nazva} район Києва', f'{m["seo"]} {lok}',
                                        f'{m["seo"]} — {nazva} район Києва'], ZH.MAKS_TITLE)
        opys = ZH.skorotyty(f'{m["seo"]} {lok} ({chastyny}) за рішеннями судів 2016–2026: скільки щороку, що саме, коли, чим '
                            f'відрізняється від решти Києва. Перевірте свій будинок.')
        assert not ZH.ZABORONENO.search(title + opys)
        html_, rech = storinka_vyd(slug, r, u_rayoni(m['h1'], nazva),
                                   [('/', 'Головна'), (f'/rayon/{rs}/', f'{nazva} район'), ('', m['rozdil'])],
                                   title, opys, f'/{m["slug"]}/{rs}/', 'у решті Києва', posylannia, pislia, 'в районі')
        zapysaty(slug, html_, rech, r)

    vyd_rayon('kradizhky-podilskyi', 'kra', 'Подільський')
    vyd_rayon('dtp-darnytskyi', 'dtp', 'Дарницький')

    # Наркотики — увесь Київ: без порівняння; замість нього — посилання на райони (за абеткою, не рейтинг)
    h = 'nar'
    DE, ZA_RIK, TYZHDEN = ' по всьому Києву', False, False
    m = HRM[h]
    xs = [p for p in P if p['hr'] == h and p['r_sud']]
    k = mistse(DN, xs, None)
    r = k['rozdily'][0]
    rayony_html = ('<section class="blok"><h2>Наркотики по районах</h2><p class="blok__pidpys">За абеткою. Райони не порівнюємо між собою: вони різні за розміром, і число залежить від того, де поліція перевіряє.</p>'
                   '<ul class="rayony-sp">' + ''.join(
                       f'<li><a href="/{m["slug"]}/{Z.slug_rayonu(x)}/">{e(x)}</a></li>'
                       for x in RAYONY) + '</ul></section>')
    posylannia = ('<section class="blok blok--tykho"><h2>Інші теми по Києву</h2><p class="posylannia">' + ' · '.join(
        f'<a href="/{HRM[x]["slug"]}/">{e(HRM[x]["rozdil"])}</a>' for x in HR.KLIUCHI if x != h) + '</p></section>')
    pislia = (poshuk_html('Ваш будинок', 'Що з цього — біля вашого будинку.', 'narkotyky-kyiv')
              + problemy_html('Де справи про наркотики повторюються роками', 'narkotyky-kyiv')
              + stezhyty_html('своїм районом (оберете на наступному кроці)', 'narkotyky-kyiv'))
    title = 'Наркотики в Києві — справи за районами, 2016–2026'
    opys = ZH.skorotyty('Наркотики в Києві за рішеннями судів 2016–2026: скільки справ щороку, які речовини, де й коли, '
                        'по кожному району. Перевірте свій будинок.')
    html_, rech = storinka_vyd('narkotyky-kyiv', r, 'в Києві', [('/', 'Головна'), ('', 'Наркотики в Києві')], title, opys,
                               '/narkotyky/', None, posylannia, pislia, 'в Києві', rayony_html)
    zapysaty('narkotyky-kyiv', html_, rech, r)

    # покриття словника: статті, що трапляються в топі (5 найчастіших у кожній групі кожної сторінки і Києва)
    pokr = {'ne_pokryto': {}, 'pokryto_podii': 0, 'vsogo_podii': len(P)}
    nepokr = Counter(p['st'] for p in P if not p['vyd'])
    pokr['pokryto_podii'] = len(P) - sum(nepokr.values())
    for h in HR.KLIUCHI:
        top = Counter(p['st'] for p in P if p['hr'] == h).most_common(10)
        for st, n in top:
            if not SL['statti'].get(st):
                pokr['ne_pokryto'][st] = n
    pokr['ne_pokryto_naichastishi'] = nepokr.most_common(15)
    (TUT / 'pokryttia-slovnyka.json').write_text(json.dumps(pokr, ensure_ascii=False, indent=1), encoding='utf-8')
    (TUT / 'chysla.json').write_text(json.dumps(chysla, ensure_ascii=False, indent=1), encoding='utf-8')
