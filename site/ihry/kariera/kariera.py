# -*- coding: utf-8 -*-
"""«Кваліфікуй: кар'єра» (ZAVDANNYA-146, прототип): навчальні справи з випуску events-<дата>.db і текстів рішень.

  python site/ihry/kariera/kariera.py --baza events-<дата>.db --teksty <тека з *.jsonl.xz Release teksty> \
      [--vykhid site/ihry/kariera/kariera.json] [--na-chastynu 40]

Що робить:
1. Справа — подія випуску з фабулою (так, як її взяв конвеєр з рішення), одна подія на рішення.
2. Правильна відповідь — **з резолютивної частини того самого рішення** («визнати винним … передбаченого ч. N ст. X …»):
   кодекс, стаття, частина. Лише одна кваліфікація в реченні про вину і та сама стаття, що в події; інакше справа не йде
   (кілька статей, замах, співучасть — для гри неоднозначно).
3. Пояснення — речення самого суду з тексту рішення з тією самою кваліфікацією (найкраще — з «тобто …»); нічого від себе.
4. Знеособлення фабули: статті й кодекси приховано (щоб не підказати відповідь), «ОСОБА_1» → «Особа А», номери машин і
   «ІНФОРМАЦІЯ_N» прибрано, номери будинків прибрано — лише назва вулиці (MV-25: гра безкоштовна).
5. Поза грою (MV-69, MV-165): статеві, щодо дітей, домашнє насильство (`dani-edrsr/src/chutlyvi.py`) і будь-яка фабула,
   де згадано неповнолітніх чи малолітніх.
6. Складність — за частотою статті у випуску (часті — на перших рівнях), частина, рідша за 15 % у своїй статті, — +1.
7. Скасоване чи змінене в апеляції або касації (MV-17, ZAVDANNYA-152) — поза грою: гра показує, як кваліфікував суд, а
   кваліфікація такого рішення вже не діє. Позначка — таблиця `skasuvannia` випуску (S-Т.6, `dani-edrsr/src/skasuvannia.py`):
   поза грою наслідки з `SKASOVANO_NASLIDKY` («без змін» і «не розпізнано» — лишаються: саме подання апеляції подію не
   скасовує). Видалене за зверненням (`withdrawal`) — теж поза грою. Немає таблиці у випуску (пробний 08.11 — стара
   схема) — відсіву немає, і збирач каже про це вголос.

Фабули — з випуску, тож файл даних у git не кладемо (`.gitignore`), як `litopys.json`.
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import lzma
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

TUT = Path(__file__).resolve().parent
KVAL_ZACHATOK = TUT.parent / 'kvalifikuy.json'

# Поза грою: статеві, щодо дітей, домашнє насильство (як dani-edrsr/src/chutlyvi.py: STATTI і DOMASHNIE).
POZA = re.compile(r'ст\.173-2 КУпАП|ст\.173-8 КУпАП|ст\.126-1 КК|ст\.15[2-6] КК|ст\.117 КК|ст\.166 КК|ст\.180 КУпАП|'
                  r'ст\.180-1 КУпАП|ст\.184 КУпАП|ст\.303 КК|ст\.390-1 КК|ст\.13[5-7] КК|ст\.150 КК|ст\.164 КК|'
                  r'ст\.30[14]|ст\.301-1 КК')
SHAPKA = re.compile(r'провадження\s*№|об.єднан|В\s*С\s*Т\s*А\s*Н\s*О\s*В\s*И|зареєстрован|проживаю|уродже|громадян\w+\s+України|не\s+працю')
DITY = re.compile(r'неповнолітн|малолітн|дитин|дітей|дітьми|школяр|учн[яіею]', re.I)

KODEKS = r'(КК|КУпАП|КпАП|КУАП|Кодексу\s+України\s+про\s+адміністративні\s+правопорушення|Кримінального\s+кодексу)'
KVAL = re.compile(r'(?:ч(?:\.|астин\w*)\s*(\d+)\s*)?ст(?:\.|атт\w+)\s*(\d+(?:\s*[-–]\s*\d+)?)\s*,?\s*' + KODEKS)
REZOL = re.compile(r'П\s*О\s*С\s*Т\s*А\s*Н\s*О\s*В\s*И\s*[ВЛ]|У\s*Х\s*В\s*А\s*Л\s*И\s*[ВЛ]|В\s*И\s*Р\s*І\s*Ш\s*И\s*[ВЛ]')
VYNA = re.compile(r'винн|винуват')

# Приховати статті у фабулі (будь-яке «ч. N ст. X …» чи «ст. X»), щоб текст не підказав відповідь.
STATTIA_U_TEKSTI = re.compile(
    r'(?:частин\w+\s+(?:перш|друг|трет|четверт|п.ят|шост|сьом|восьм)\w*\s+)?'
    r'(?:ч(?:\.|астин\w*)\s*\d+\s*,?\s*)?(?:ст\.|статт\w+)\s*\d+(?:\s*[-–]\s*\d+)?(?:\s*,\s*\d+(?:[-–]\d+)?)*'
    r'(?:\s*(?:ч\.?|частин\w*)\s*\d+)?(?:\s*' + KODEKS + r'(?:\s+України)?)?')
ZAIVE_RECHENNIA = re.compile(r'[,;]?\s*(?:що\s+утворює|чим\s+(?:вчинив|скоїв|здійснив)|тобто\s+(?:вчинив|скоїв)|'
                             r'відповідальність\s+за\s+що|за\s+що\s+відповідальність|за\s+що\s+передбачена|які\s+(?:передбачені|кваліфіковано))[^.]*'
                             r'\[\s*стаття\s*\][^.]*', re.I)
VULYTSIA = re.compile(
    r'((?:вул\.|вул\b|пр\.|бул\.|вулиц\w+|просп\.*|пр-т|пр-кт|проспект\w*|бульв\.|бульвар\w*|б-р|пров\.|провулк\w*|пл\.|площ\w+|наб\.|'
    r'набережн\w+|шосе|узвіз\w*|дорог\w+|алея|алеї|майдан\w*)\s*[^,;\d]{2,45}?)\s*,?\s*(?:буд(?:инок|инку)?\.?\s*)?№?\s*\d+[а-яА-ЯіїєґІЇЄҐ]?'
    r'(?:\s*[-/]\s*[\dа-яА-ЯіІ]+)?(?:\s*,?\s*(?:кв\.|квартир\w+|під\'?їзд\w*)\s*№?\s*\d+)?')
# Номер будинку, який не зміг прибрати VULYTSIA (назва з цифрою: «вул. 21-ша Садова, 49») — така справа не йде.
ZALYSHOK_NOMERA = re.compile(r'(?:вул|просп|бул|пров|пл)\.?\s[^,.;]{0,35},\s*\d')
BUKVY = 'АБВГДЕЄЖЗИКЛМНОПРСТУФХЦЧШЩ'
# Наслідки апеляції чи касації (dani-edrsr/src/skasuvannia.py, NASLIDKY), з якими рішення в гру не йде: скасовано (закрито,
# виправдано, новий розгляд, апеляційний вирок) чи змінено — покарання або кваліфікацію; з тексту наслідку не видно, що саме.
SKASOVANO_NASLIDKY = ('zakryto', 'vypravdano', 'novyi_rozghliad', 'apeliatsiinyi_vyrok', 'zmina')


def kod_kodeksu(s: str) -> str:
    return 'КК' if s.startswith(('КК', 'Кримін')) else 'КУпАП'


def kliuch(kodeks: str, nomer: str) -> str:
    return f"{kodeks} {re.sub(r'\s*[-–]\s*', '-', nomer)}"


SLOVA_CHASTYN = {'перш': '1', 'друг': '2', 'трет': '3', 'четверт': '4', 'п': '5', 'шост': '6', 'сьом': '7'}
CHASTYNA_SLOVOM = re.compile(r'частин\w*\s+(перш|друг|трет|четверт|п.ят|шост|сьом)\w*\s+(?=ст)', re.I)


def chastyny_tsyframy(t: str) -> str:
    """«частиною першою статті 130» → «ч. 1 статті 130»: суди пишуть частину й словами."""
    def tsyfra(m):
        slovo = m.group(1).lower()
        return 'ч. ' + SLOVA_CHASTYN['п' if slovo.startswith('п') else slovo] + ' '
    return CHASTYNA_SLOVOM.sub(tsyfra, t)


def znaity_kvalifikatsiiu(tekst: str):
    """(ключ статті, частина або '') з речення про вину в резолютивній частині; None — якщо не одна кваліфікація."""
    tekst = chastyny_tsyframy(tekst)
    m = list(REZOL.finditer(tekst))
    if not m:
        return None
    rez = tekst[m[-1].end():m[-1].end() + 2500]
    # речення — до крапки перед великою літерою (не перед цифрою: «ч. 2 ст. 130» — одне речення)
    for rech in re.split(r'(?<=[.;])\s+(?=[А-ЯІЇЄҐ])', rez):
        if not VYNA.search(rech):
            continue
        # лише до «та призначити / накласти»: далі — покарання (там бувають інші статті: 75, 71 КК тощо)
        rech = re.split(r'\s(?:та|і|й)?\s*(?:призначити|накласти|застосувати|піддати|звільнити)', rech)[0]
        kv = {(kliuch(kod_kodeksu(k), n), ch or '') for ch, n, k in KVAL.findall(rech)}
        # «ст. 124, ч. 2 ст. 130 КУпАП», «ст.ст. 124, 130» — кодекс названо раз на кілька статей: теж неоднозначно
        nomery = set(re.findall(r'ст(?:\.|атт\w+)\s*(\d+(?:-\d+)?)', rech))
        if kv and (len(nomery) > 1 or re.search(r'ст\.\s*ст\.|статтями', rech)):
            return None
        if kv:
            return next(iter(kv)) if len(kv) == 1 else None
    return None


def inshi_statti(tekst: str, kl: str, vidomi) -> bool:
    """Чи судить рішення ще за іншою статтею (об'єднані справи: фабула про одне, кваліфікація про інше)."""
    tekst = chastyny_tsyframy(tekst)
    m = list(REZOL.finditer(tekst))
    do = re.sub(r'\s+', ' ', tekst[:m[-1].start()] if m else tekst)
    for rech in re.split(r'(?<=[.!?])\s+(?=[А-ЯІЇЄҐ])', do):
        if not re.search(r'передбачен|кваліфік|склад', rech):
            continue
        for ch, n, k in KVAL.findall(rech):
            inshyi = kliuch(kod_kodeksu(k), n)
            if inshyi != kl and inshyi in vidomi:
                return True
    return False


def poiasnennia(tekst: str, kl: str, chastyna: str) -> str:
    """Речення суду (до резолютивної частини), де названо ту саму кваліфікацію; найкраще — з «тобто»."""
    tekst = chastyny_tsyframy(tekst)
    m = list(REZOL.finditer(tekst))
    do = tekst[:m[-1].start()] if m else tekst
    nomer = kl.split(' ', 1)[1]
    kandydaty = []
    for rech in re.split(r'(?<=[.!?])\s+(?=[А-ЯІЇЄҐ])', re.sub(r'\s+', ' ', do)):
        for ch, n, _ in KVAL.findall(rech):
            if re.sub(r'\s*[-–]\s*', '-', n) == nomer and (ch or '') == chastyna \
                    and not re.search(r'покаран|санкці|стягнен|призначи|звільни|строк', rech):
                if not re.search(r'кваліфік|доведен|склад\w*\s+(?:адміністративн|кримінальн|правопоруш)|винн|винуват', rech):
                    continue   # речення про наказ, протокол чи процедуру — не пояснення кваліфікації
                bal = (2 if re.search(r'тобто|а\s+саме', rech) else 0) + (1 if re.search(r'кваліфік', rech) else 0)
                kandydaty.append((bal, -abs(len(rech) - 250), rech.strip()))
                break
    if not kandydaty:
        return ''
    rech = max(kandydaty)[2]
    return znejosobyty(rech, prykhovaty_statti=False)[:450]


def znejosobyty(t: str, prykhovaty_statti: bool = True) -> str:
    t = re.sub(r'\s+', ' ', t).strip()
    t = re.sub(r'(?<=[а-яіїєґА-ЯІЇЄҐ])[?`\'](?=[а-яіїєґ])', '\u2019', t)   # «здоров?я», «сп`яніння» → апостроф

    def osoba(m):
        # за номером, а не за порядком появи: та сама людина — та сама буква і у фабулі, і в поясненні суду
        return f'Особа {BUKVY[(int(m.group(1)) - 1) % len(BUKVY)]}'
    t = re.sub(r'(?:обвинувачен\w*|правопорушни\w*|підсудн\w*|засуджен\w*|громадян\w*|гр\.)\s+(?=ОСОБА_)', '', t, flags=re.I)
    t = re.sub(r'ОСОБА_(\d+)', osoba, t)
    t = re.sub(r'\s*,?\s*ІНФОРМАЦІЯ_\d+\s*,?', ',', t)
    t = re.sub(r'НОМЕР_\d+|АДРЕСА_\d+', '…', t)
    t = VULYTSIA.sub(r'\1', t)
    t = re.sub(r'(будин\w+|буд\.)\s*№?\s*\d+[^\s,.;]*', r'\1', t)
    t = re.sub(r'(будин\w+)\s+буд\.?(?=\s)', r'\1', t)
    t = re.sub(r'(?<![\w.])буд\.+(?!\s*\d)', 'будинку', t)      # «біля буд. по вул.» → «біля будинку по вул.»
    if prykhovaty_statti:
        t = STATTIA_U_TEKSTI.sub('[стаття]', t)
        t = ZAIVE_RECHENNIA.sub('', t)
        t = re.sub(r'про\s+адміністративн\w+\s+правопорушенн\w+', '', t)
        t = re.sub(r'(?:адміністративн|кримінальн)\w+\s+(правопорушенн\w*|проступ\w*)', r'\1', t)
        t = re.sub(r'\b(КУпАП|КпАП|КК України)\b', '', t)
    t = re.sub(r'\s+([,.;:])', r'\1', t)
    t = re.sub(r',\s*,', ',', t)
    t = re.sub(r'\s{2,}', ' ', t).strip(' ,')
    return t


def poza_skasovani(con) -> tuple[set, str]:
    """-> (doc_id, які не йдуть у гру; пояснення для журналу). Скасовані/змінені вищим судом і видалені за зверненням."""
    tabl = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    poza, slova = set(), []
    if 'skasuvannia' in tabl:
        q = ','.join('?' * len(SKASOVANO_NASLIDKY))
        poza |= {d for (d,) in con.execute(f'SELECT doc_id FROM skasuvannia WHERE naslidok IN ({q})', SKASOVANO_NASLIDKY)}
        slova.append(f'скасованих чи змінених вищим судом: {len(poza)}')
    else:
        slova.append('у випуску немає таблиці skasuvannia — скасовані в апеляції не відсіяно')
    if 'withdrawal' in tabl:
        vz = {d for (d,) in con.execute('SELECT doc_id FROM withdrawal')}
        slova.append(f'видалених за зверненням: {len(vz)}')
        poza |= vz
    return poza, '; '.join(slova)


def zibraty(baza: Path, teksty: list[Path], na_chastynu: int = 60, log=print) -> dict:
    con = sqlite3.connect(f'file:{baza}?mode=ro', uri=True)
    vypusk = con.execute('SELECT versiia FROM release').fetchone()[0]
    poza, pro_poza = poza_skasovani(con)
    log(pro_poza)
    epizodiv = Counter(d for (d,) in con.execute('SELECT doc_id FROM event'))
    nazvy: dict[str, str] = {}
    chastota: Counter = Counter()
    podii = {}
    for doc, st, fab, vyd, data, url in con.execute(
            'SELECT e.doc_id, e.stattia, e.fabula, e.vyd, d.data_rishennia, d.url FROM event e JOIN document d USING(doc_id) '
            'WHERE e.chutlyva = 0 AND e.fabula IS NOT NULL AND e.stattia IS NOT NULL'):
        m = re.match(r'ст\.(\S+) (КК|КУпАП)(?: · (.+))?', st)
        if not m or POZA.search(st):
            continue
        k = f'{m.group(2)} {m.group(1)}'
        chastota[k] += 1
        nazvy.setdefault(k, m.group(3) or '')
        if epizodiv[doc] == 1 and not DITY.search(fab) and doc not in poza:
            podii[doc] = (k, fab, vyd, data, url)
    zibrano = defaultdict(list)
    for f in teksty:
        with lzma.open(f, 'rt', encoding='utf-8') as fh:
            for ryadok in fh:
                doc = ryadok[12:ryadok.find('"', 12)] if ryadok.startswith('{"doc_id": "') else json.loads(ryadok)['doc_id']
                if doc not in podii:
                    continue
                z = json.loads(ryadok)
                k, fab, vyd, data, url = podii.pop(doc)   # те саме рішення буває в кількох файлах — беремо раз
                kv = znaity_kvalifikatsiiu(z.get('tekst') or '')
                if not kv or kv[0] != k or inshi_statti(z['tekst'], k, chastota):
                    continue
                fabula = znejosobyty(fab)
                if not 120 <= len(fabula) <= 900 or 'ОСОБА_' in fabula or SHAPKA.search(fabula) \
                        or ZALYSHOK_NOMERA.search(fabula):
                    continue
                chomu = poiasnennia(z['tekst'], k, kv[1])
                zibrano[(k, kv[1])].append({'doc': doc, 'fabula': fabula, 'chomu': chomu, 'url': url,
                                            'data': data, 'vyd': vyd})
    # Частини, які справді є: для статей зачатку — його перелік (у ст. 173 КУпАП частин немає, хоч суди й пишуть «ч. 1»);
    # для решти — частина щонайменше в 3 справах і 1 % справ статті. Справа з іншою частиною не йде.
    zachatok = json.loads(KVAL_ZACHATOK.read_text(encoding='utf-8'))['statti'] if KVAL_ZACHATOK.exists() else {}
    vsogo_st = Counter()
    for (k, ch), sp in zibrano.items():
        vsogo_st[k] += len(sp)
    chysti = defaultdict(list)
    for (k, ch), sp in zibrano.items():
        if k in zachatok:
            dozv = zachatok[k].get('chastyny') or []
            if not dozv:
                ch = ''
            elif ch and ch not in dozv:
                continue
        elif ch and (len(sp) < 3 or len(sp) < 0.01 * vsogo_st[k]):
            continue
        chysti[(k, ch)] += sp
    zibrano = chysti
    # Добір: на кожну пару «стаття + частина» — до na_chastynu справ, спершу з поясненням суду; порядок — сталий (хеш).
    spravy = []
    chastyny = defaultdict(Counter)
    for (k, ch), sp in zibrano.items():
        chastyny[k][ch] += len(sp)
        sp.sort(key=lambda s: (not s['chomu'], hashlib.sha1(s['doc'].encode()).hexdigest()))
        spravy += [dict(s, stattia=k, chastyna=ch) for s in sp[:na_chastynu]]
    poriadok = [k for k, _ in chastota.most_common() if k in chastyny]
    statti = {}
    for i, k in enumerate(poriadok):
        riven = 1 if i < 4 else 2 if i < 10 else 3 if i < 20 else 4
        vsi_ch = sorted((set(chastyny[k]) | set((zachatok.get(k) or {}).get('chastyny') or [])) - {''}, key=int)
        statti[k] = {'nazva': (zachatok.get(k) or {}).get('nazva') or nazvy[k], 'korotko': nazvy[k],
                     'kodeks': k.split(' ')[0], 'n': chastota[k], 'riven': riven,
                     'chastyny': vsi_ch, 'chastky': {c or '—': n for c, n in chastyny[k].most_common()}}
    vykhid = []
    for s in sorted(spravy, key=lambda s: hashlib.sha1(s['doc'].encode()).hexdigest()):
        st = statti[s['stattia']]
        vsogo = sum(chastyny[s['stattia']].values())
        ridka = s['chastyna'] and chastyny[s['stattia']][s['chastyna']] / vsogo < 0.15
        vykhid.append([s['doc'], s['stattia'], s['chastyna'], s['fabula'], s['chomu'], s['url'], s['data'],
                       min(5, st['riven'] + (1 if ridka else 0)), s['vyd']])
    return {'versiia': 1, 'vypusk': vypusk, 'skasovani': pro_poza, 'zibrano': datetime.date.today().isoformat(),
            'pole': ['doc', 'stattia', 'chastyna', 'fabula', 'chomu', 'url', 'data', 'skladnist', 'vyd'],
            'statti': statti, 'spravy': vykhid}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    p.add_argument('--baza', required=True, type=Path)
    p.add_argument('--teksty', required=True, type=Path, help='тека з *.jsonl.xz (Release teksty)')
    p.add_argument('--vykhid', type=Path, default=TUT / 'kariera.json')
    p.add_argument('--na-chastynu', type=int, default=60)
    a = p.parse_args()
    d = zibraty(a.baza, sorted(Path(x) for x in glob.glob(str(a.teksty / '*.jsonl.xz'))), a.na_chastynu)
    a.vykhid.write_text(json.dumps(d, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
    print(f"справ: {len(d['spravy'])}, статей: {len(d['statti'])} → {a.vykhid}")


if __name__ == '__main__':
    main()
