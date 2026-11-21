# -*- coding: utf-8 -*-
"""ZAVDANNYA-190, крок 1: витяг подій повного Києва для макета картки району й публічного місця.

Лише читає випуск (`events-<дата>.db` з Release) і код `dani-edrsr/src` (механізм, ціль, уразливість — той самий, що в
карті Києва) та правило чутливих сайту (`site/sait/dani.py`, MV-102). Результат — pickle у тимчасовій теці (у git не йде).

    python docs/makety-190/vytiah.py <events.db> <../dani-edrsr> <vykhid.pkl>
"""
import datetime as dt
import pickle
import re
import sqlite3
import sys
from multiprocessing import Pool
from pathlib import Path

KORIN = Path(__file__).resolve().parents[2]
BAZA, DANI, VYKHID = sys.argv[1], Path(sys.argv[2]).resolve(), sys.argv[3]
sys.path.insert(0, str(DANI / 'src'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
import mech  # noqa: E402
import tsil  # noqa: E402
import dani as D  # noqa: E402

SUDY = {'Golosiivskyi': 'Голосіївський', 'Darnytskyi': 'Дарницький', 'Desnianskyi': 'Деснянський',
        'Dniprovskyi': 'Дніпровський', 'Obolonskyi': 'Оболонський', 'Pecherskyi': 'Печерський',
        'Podilskyi': 'Подільський', 'Sviatoshynskyi': 'Святошинський', 'Solomianskyi': "Солом'янський",
        'Shevchenkivskyi': 'Шевченківський'}
RAY = D.Rayony(KORIN / 'data' / 'borders.json')

# Марки — словник цього макета (як у 189, розд. 7); точність не мірялась — розмітка в ZAVDANNYA-192.
TELEFONY = [('Apple', r'iphone|айфон|apple|епл'), ('Samsung', r'samsung|самсунг'),
            ('Xiaomi', r'xiaomi|сяом|redmi|редмі|poco\b'), ('Huawei', r'huawei|хуавей'), ('Motorola', r'motorola|моторол'),
            ('Nokia', r'nokia|нокі'), ('Oppo', r'\boppo\b'), ('Realme', r'realme'), ('Tecno', r'\btecno\b')]
AVTO = [('Toyota', r'toyota|тойот'), ('Volkswagen', r'volkswagen|фольксваген|\bvw\b'), ('Renault', r'renault|рено\b'),
        ('Skoda', r'skoda|шкода\s+(?:octavia|fabia|superb|rapid|kodiaq|karoq|yeti)|škoda'), ('Hyundai', r'hyundai|хюндай|хундай'),
        ('Kia', r'\bkia\b|\bкіа\b'), ('BMW', r'\bbmw\b|\bбмв\b'), ('Mercedes-Benz', r'mercedes|мерседес'),
        ('Daewoo', r'daewoo|деу\b|дэу'), ('ВАЗ', r'\bваз\b|\blada\b|\bлада\b|жигул'), ('Nissan', r'nissan|ніссан'),
        ('Ford', r'\bford\b|\bфорд\b'), ('Chevrolet', r'chevrolet|шевроле'), ('Audi', r'\baudi\b|\bауді\b'),
        ('Mazda', r'mazda|мазда'), ('Mitsubishi', r'mitsubishi|міцубіс'), ('Honda', r'\bhonda\b|\bхонда\b'),
        ('Lexus', r'lexus|лексус'), ('Opel', r'\bopel\b|\bопель\b'), ('Peugeot', r'peugeot|пежо'), ('Tesla', r'tesla|тесла'),
        ('Volvo', r'volvo|вольво'), ('Subaru', r'subaru|субару'), ('Geely', r'geely|джилі'), ('Chery', r'\bchery\b|\bчері\b'),
        ('ЗАЗ', r'\bзаз\b|таврі|ланос|lanos'), ('Citroen', r'citro[eë]n|сітроен'), ('Fiat', r'\bfiat\b|\bфіат\b')]
TELEFONY = [(k, re.compile(v, re.I)) for k, v in TELEFONY]
AVTO = [(k, re.compile(v, re.I)) for k, v in AVTO]
SPIANINNIA = re.compile(r"сп['’ʼ]?ян[іi]нн|алкогольн\w+\s+сп|наркотичн\w+\s+сп", re.I)
# Без назви механізму в словнику — за статтею (людською мовою)
NAZVA_ZA_STATTEIU = {'ст.155-1 КУпАП': 'торгівля без касового чека', 'ст.155 КУпАП': 'порушення правил торгівлі',
                     'ст.172-20 КУпАП': 'розпивання алкоголю'}


def marky(slovnyk, t, n=3):
    """усі названі марки (до n) у порядку згадки, без повторів"""
    z = sorted(((m.start(), k) for k, rx in slovnyk for m in [rx.search(t)] if m), key=lambda x: x[0])
    out = []
    for _, k in z:
        if k not in out:
            out.append(k)
    return out[:n]


def obrobyty(r):
    eid, doc, data, chas, vyd, st, fab, chut, lat, lon, adresa, tochn, sud, kod, drish = r
    if (bool(chut) or bool(D.CHUTLYVI_STATTI.search(st or ''))) and not D.domashnie(st):
        return None                         # статеві й щодо дітей — ні (MV-102)
    hr = D.HR.hrupa(vyd, st or '')
    if not hr:
        return None
    sim = mech.simgroup(kod)
    if sim == 'ДОР_ДТП':
        sim = mech.dtp_chastyna(fab)
    try:
        ts = tsil.tsil(vyd, sim, fab, cat=kod)
    except Exception:
        ts = {}
    ts.pop('merezha', None)                 # назви мереж — ніде (MV-206)
    ts.pop('sposib', None)                  # спосіб здобуття наркотиків — почерк суду, не за районами (MV-206)
    if ts.get('khto') == 'поліцейський' and hr == 'por':
        ts.pop('khto'); ts['na_koho'] = 'поліція'
    if ts.get('khto') == 'дитина':
        ts.pop('khto')
    try:
        vr = tsil.vrazlyvist(vyd, sim, fab) if vyd == 'МАЙ' else None
    except Exception:
        vr = None
    try:
        d = dt.date.fromisoformat(data[:10]) if data and len(data) >= 10 else None
    except ValueError:
        d = None
    god = None
    if chas and re.match(r'^\d{1,2}:\d{2}', chas):
        h, m = int(chas.split(':')[0]), int(chas.split(':')[1][:2])
        if 0 <= h <= 23 and not (h == 0 and m == 0):      # «00:00» — найчастіше «час не вказано»
            god = h
    t = fab or ''
    st0 = (st or '').split(' · ')[0]
    nazva = mech.simname(sim) or NAZVA_ZA_STATTEIU.get(st0, '')
    return dict(eid=eid, doc=doc, hr=hr, sim=sim, nazva=nazva, st=st0, ts=ts, vr=vr,
                tel=marky(TELEFONY, t, 1) if ts.get('berut') == 'телефон' else [],
                avto=marky(AVTO, t) if hr == 'dtp' else [],
                spian=bool(SPIANINNIA.search(t)),
                rik=int(data[:4]) if data and data[:4].isdigit() else None,
                mis=f'{d.year:04d}-{d.month:02d}' if d else None, dn=d.weekday() if d else None, god=god,
                data=data[:10] if d else '', drish=(drish or '')[:10],
                lat=lat, lon=lon, adresa=adresa, tochn=tochn,
                r_tochka=RAY.rayon(lat, lon) if lat is not None else None, r_sud=SUDY.get(sud))


POLIA = ('typ_mistsia', 'tiazhkist', 'kvalifikatsiia', 'pokarannia', 'dodatkove', 'stat', 'nepovnolitnii', 'vikova_hrupa',
         'shkoda', 'vartist', 'povernuto')

if __name__ == '__main__':
    con = sqlite3.connect(f'file:{BAZA}?mode=ro', uri=True)
    versiia = con.execute('select versiia, podii from release').fetchone()
    rows = con.execute('''SELECT e.event_id, e.doc_id, e.data_podii, e.chas, e.vyd, e.stattia, e.fabula, e.chutlyva,
        l.lat, l.lon, l.adresa, l.tochnist, d.sud, d.kod_kategorii, d.data_rishennia
        FROM event e LEFT JOIN location l ON l.location_id = e.location_id JOIN document d ON d.doc_id = e.doc_id
        WHERE e.doc_id NOT IN (SELECT doc_id FROM withdrawal)''').fetchall()
    with Pool(4) as p:
        podii = [x for x in p.imap(obrobyty, rows, chunksize=2000) if x]
    pasport = {}
    q = 'select doc_id, pole, znachennia from pasport where pole in (%s)' % ','.join('?' * len(POLIA))
    for doc, pole, zn in con.execute(q, POLIA):
        pasport.setdefault(doc, {}).setdefault(pole, zn)
    for x in podii:
        x['pas'] = pasport.get(x['doc'], {})
    print('випуск', versiia, '· подій у випуску', len(rows), '· у 7 групах без статевих і щодо дітей', len(podii), file=sys.stderr)
    pickle.dump({'versiia': versiia, 'podii': podii}, open(VYKHID, 'wb'))
