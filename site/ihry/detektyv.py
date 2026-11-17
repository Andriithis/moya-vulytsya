# -*- coding: utf-8 -*-
"""«Детектив тижня» (ZAVDANNYA-117, MV-129): перевірка справи перед випуском.

  python site/ihry/detektyv.py site/ihry/spravy/*.json            — перевірити справи, надрукувати звуження
  python site/ihry/detektyv.py --vulytsi vulytsi.txt справа.json  — і звірити «справжню вулицю» зі списком вулиць

Справа — вигадана історія за мотивами справжньої справи (MV-129). Програма не пускає справу, якщо порушено хоч одне:

Три запобіжники MV-129
  З1. Позначка «Вигадана історія за мотивами справжньої справи» — дослівно, у полі `poznachka`.
  З2. Заклади вигадані й без адрес: у назві закладу немає цифр і слів адреси; справжні назви з рішення
      (`rishennia.spravzhni_nazvy`) не трапляються в жодному тексті для гравця; кожна назва в «лапках» — або вигаданий
      заклад, або варіант відповіді, або публічний орієнтир із `oriientyry`. Вулиця — справжня (`vulytsia`; з `--vulytsi`
      звіряється зі списком вулиць міста).
  З3. Вигадані персонажі — без прикмет людини (вік, стать-прикмети, зовнішність, одяг, походження) — у будь-якому тексті.

Межі гри (IHRY-2, розд. 2.2–2.3; AGENTS.md, розд. 4)
  — не чутлива справа (статеві, домашнє насильство, щодо дітей), не тема можливої кризи людини (колії, дах, міст);
  — не «шукати людину»: слів «підозрюваний», «злочинець», «винний», «хто це зробив» немає;
  — немає «небезпечн», «безпечн», «рейтинг», номерів будинків і міток знеособлення (ОСОБА_…).

«Детектив, не лотерея» (IHRY-2, розд. 2.4) — звуження рахує програма за ознаками варіантів, а не автор:
  П1. Кожен варіант відповіді має ознаки; кожна умова сліду — це «ознака = значення» для одного поля.
  П2. Після всіх слідів у кожному полі лишається рівно одна відповідь — та, що в `vidpovid`.
  П3. Після сліду 3 у полі «де» — щонайменше 3 місця (не розкривається надто рано).
  П4. Сліди 1–5 відсікають хоча б один варіант; слід 6 — або відсікає, або лише підтверджує розкрите.
  П5. Відповідь жодного поля не названа прямо у виклику й слідах 1–3 (лише виводиться).
  П6. Схованки слідів 1–5 — щонайменше за 500 м від місця відповіді; слід 6 — на самому місці.
  П7. Кожне речення «з рішення суду» має цитату, і цитата дослівно є в уривках рішення (`rishennia.uryvky`).
  П9. Вигадка не звужує: речення з міткою «вигадка» не мають умов (гра на папері, ZAVDANNYA-117) — вирішальні
      факти йдуть лише з мітками «з рішення суду», «з карти» чи «підказка гри».
  П8. Відповідь — справжня: місце й частина доби збігаються з рішенням, вид — зі статтею рішення.
Звуження друкується для звіту: після якого сліду розкрито кожне поле і «Холмс розкрив після сліду N».

Ця сама логіка звуження — у `ihry-yadro.js` (гравцеві); тест звіряє, що обидві дають однаковий результат.
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import re
import sys
from pathlib import Path

POZNACHKA = 'Вигадана історія за мотивами справжньої справи'
POLIA = ('de', 'shcho', 'koly', 'pole')
OCHKY = {'de': 1000, 'shcho': 500, 'koly': 250, 'pole': 250}
DZHERELA = {'rishennia': 'з рішення суду', 'vyhadka': 'вигадка', 'karta': 'з карти', 'pidkazka': 'підказка гри',
            'dovidnyk': 'з довідника'}
SLIDIV = 6
MIN_DE_PISLIA_3 = 3
MIN_VIDSTAN_M = 500
MEZHI_KYIEVA = (50.21, 50.60, 30.23, 30.83)

# Частини доби — однакові для всіх справ (довідник детектива).
CHASTYNY_DOBY = (('ranok', 6, 12), ('den', 12, 17), ('vechir', 17, 23), ('nich', 23, 6))

ZABORONENI = re.compile(r'небезпечн|безпечн|рейтинг', re.I)
ZNEOSOBLENNIA = re.compile(r'ОСОБА_|АДРЕСА_|ІНФОРМАЦІЯ_|НОМЕР_')
# «Шукати людину» (IHRY-2, 2.3) — ні.
LIUDYNA = re.compile(r'підозрюван|злочин(ець|ця|цю|цем|ці)|винн(ий|ого|ому|а|у)\b|хто (це )?зроби|знайдіть (його|її|винн)', re.I)
# Прикмети людини (MV-129, З3): вік, зовнішність, одяг, походження.
PRYKMETY = re.compile(
    r'\b\d{1,2}\s*(-?\s*)?(рок|літ)|рок(ів|и|у)\s+\d|рок(ів|у) від роду|молод(ий|а|ик)|літн|похил|підліт|'
    r'зріст|висок(ий|а|ого)\s+(на зріст|чолов|жін)|низьк(ий|а)\s+(на зріст|чолов|жін)|худ(ий|а|орляв)|повн(ий|а)\s+(чолов|жін)|'
    r'волосс|брюнет|блонд|рудий|руда\b|лис(ий|а)\b|бород|вуса|вусат|татуюв|шрам|родимк|окуляр|'
    r'куртк|капюшон|кепк|шапк|штан|джинс|кросівк|черевик|пальт|сукн|спідниц|'
    r'національн|акцент|ром(и|а|ів)\b|колір шкіри|смаглив', re.I)
# Теми можливої кризи людини й чутливі справи (IHRY-2, 2.2; MV-12, MV-69).
KRYZA = re.compile(r'колі[яїй]|на даху|з мосту|на мосту|самогуб|стрибн', re.I)
CHUTLYVI_STATTI = re.compile(r'\bст\.\s*(15[2-6]|126-1|135|137|150|166|304|301-1)\b|173-2', re.I)
# Номер будинку після назви вулиці — ніде в текстах гравця (заклади вигадані, вулиця — без номера).
NOMER_BUDYNKU = re.compile(r'(вул\.|вулиц|просп|проспект|бульв|пров\.|провул|узвіз|шосе|площ)[^.;:\n]{0,40}?,\s*(буд\.\s*)?\d+', re.I)
ADRESA_SLOVA = re.compile(r'\d|вул\.|вулиц|просп|бульв|провул|шосе|буд\.', re.I)
LAPKY = re.compile(r'«([^«»]+)»')


class PomylkaSpravy(ValueError):
    pass


def chastyna_doby(chas: str) -> str:
    h = int(chas.split(':')[0])
    for kl, a, b in CHASTYNY_DOBY:
        if (a <= h < b) if a < b else (h >= a or h < b):
            return kl
    raise PomylkaSpravy(f'час {chas!r} не розпізнано')


def vidstan_m(a: dict, b: dict) -> float:
    r = 6371008.8
    f1, f2 = math.radians(a['lat']), math.radians(b['lat'])
    df, dl = f2 - f1, math.radians(b['lon'] - a['lon'])
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def vidpovidaie(kandydat: dict, umova: dict) -> bool:
    """Умова сліду: ознака варіанта дорівнює значенню (або не дорівнює, якщо `ne`)."""
    z = kandydat.get('oznaky', {}).get(umova['oznaka'])
    tak = z == umova['znachennia']
    return not tak if umova.get('ne') else tak


def zvuzhennia(sprava: dict) -> list[dict]:
    """Скільки варіантів лишається в кожному полі на старті (індекс 0) і після кожного сліду 1..6."""
    zalyshok = {p: [k['id'] for k in sprava['polia'][p]['kandydaty']] for p in POLIA}
    kroky = [{p: list(v) for p, v in zalyshok.items()}]
    za_id = {p: {k['id']: k for k in sprava['polia'][p]['kandydaty']} for p in POLIA}
    for slid in sprava['slidy']:
        for r in slid['rechennia']:
            for u in r.get('umovy', []):
                p = u['pole']
                zalyshok[p] = [i for i in zalyshok[p] if vidpovidaie(za_id[p][i], u)]
        kroky.append({p: list(v) for p, v in zalyshok.items()})
    return kroky


def teksty_hravtsia(sprava: dict) -> list[tuple[str, str]]:
    """Усі тексти, які бачить гравець: (де, текст)."""
    t = [('назва', sprava['nazva']), ('виклик', sprava['vyklyk'])]
    for s in sprava['slidy']:
        t.append((f'загадка {s["n"]}', s['zahadka']))
        for r in s['rechennia']:
            t.append((f'слід {s["n"]}', r['tekst']))
    for p in POLIA:
        t.append((f'питання {p}', sprava['polia'][p]['pytannia']))
        for k in sprava['polia'][p]['kandydaty']:
            t.append((f'варіант {p}', k['nazva']))
    for kl in ('spravzhnie', 'vyhadka'):
        t.append((f'розкриття {kl}', sprava['rozkryttia'][kl]))
    for z in sprava.get('zaklady', []):
        t.append(('заклад', z['nazva'] + ' ' + z.get('rol', '')))
    for o in sprava.get('personazhi', []):
        t.append(('персонаж', o['imia'] + ' ' + o['rol']))
    return t


def perevirka(sprava: dict, vulytsi: set[str] | None = None) -> dict:
    """Перевіряє справу. Помилка — PomylkaSpravy з усіма порушеннями; інакше — звіт про звуження."""
    zh: list[str] = []
    try:
        _perevirka(sprava, vulytsi, zh)
    except (KeyError, TypeError, ValueError) as e:
        if isinstance(e, PomylkaSpravy):
            raise
        zh.append(f'будова справи: {e!r}')
    if zh:
        raise PomylkaSpravy(f'{sprava.get("id", "?")}: ' + '; '.join(zh))
    return zvit(sprava)


def _perevirka(sprava: dict, vulytsi: set[str] | None, zh: list[str]) -> None:
    # --- MV-129, З1
    if sprava.get('poznachka') != POZNACHKA:
        zh.append(f'З1: позначка має бути дослівно «{POZNACHKA}»')
    tyzhden = datetime.date.fromisoformat(sprava['tyzhden'])
    if tyzhden.weekday() != 0:
        zh.append('тиждень справи має починатися з понеділка')
    r = sprava['rishennia']
    if not re.fullmatch(r'\d{6,12}', str(r['nomer'])) or r['url'] != f'https://reyestr.court.gov.ua/Review/{r["nomer"]}':
        zh.append('посилання на рішення — https://reyestr.court.gov.ua/Review/<номер>')
    uryvky = r.get('uryvky') or []
    if not uryvky:
        zh.append('П7: немає уривків рішення')
    if CHUTLYVI_STATTI.search(r.get('stattia', '')):
        zh.append('чутлива стаття — не для гри (MV-12, MV-69)')

    teksty = teksty_hravtsia(sprava)
    vse = '\n'.join(t for _, t in teksty)
    for de, t in teksty:
        for nazva, rx in (('заборонене слово', ZABORONENI), ('мітка знеособлення', ZNEOSOBLENNIA),
                          ('«шукати людину»', LIUDYNA), ('прикмета людини (З3)', PRYKMETY),
                          ('тема можливої кризи', KRYZA), ('номер будинку', NOMER_BUDYNKU)):
            m = rx.search(t)
            if m:
                zh.append(f'{de}: {nazva} «{m.group(0)}»')

    # --- MV-129, З2: заклади вигадані, без адрес; справжні назви не просочуються
    for z in sprava.get('zaklady', []):
        if z.get('vyhadanyi') is not True:
            zh.append(f'З2: заклад «{z["nazva"]}» має бути позначений як вигаданий')
        if ADRESA_SLOVA.search(z['nazva']):
            zh.append(f'З2: у назві закладу «{z["nazva"]}» — адреса чи цифри')
    for n in r.get('spravzhni_nazvy', []):
        if n and n.lower() in vse.lower():
            zh.append(f'З2: справжня назва з рішення «{n}» у тексті для гравця')
    dozvoleni = {z['nazva'] for z in sprava.get('zaklady', [])} | set(sprava.get('oriientyry', []))
    for p in POLIA:
        dozvoleni |= {k['nazva'] for k in sprava['polia'][p]['kandydaty']}
    dozvoleni_lapky = set()
    for d in dozvoleni:
        dozvoleni_lapky |= set(LAPKY.findall(d)) | {d}
    for de, t in teksty:
        for x in LAPKY.findall(t):
            if x not in dozvoleni_lapky and not any(x.startswith(d[:max(4, len(d) - 3)]) for d in dozvoleni_lapky):
                zh.append(f'З2: {de}: назва «{x}» — не вигаданий заклад, не варіант і не орієнтир')
    vul = sprava.get('vulytsia', '').strip()
    if not vul:
        zh.append('З2: справжня вулиця справи не вказана')
    elif vulytsi is not None and vul.lower() not in vulytsi:
        zh.append(f'З2: вулиці «{vul}» немає в списку вулиць міста')
    # --- MV-129, З3: персонажі вигадані, без прикмет
    for o in sprava.get('personazhi', []):
        if o.get('vyhadanyi') is not True:
            zh.append(f'З3: персонаж «{o["imia"]}» має бути позначений як вигаданий')
        if len(o.get('rol', '')) > 80:
            zh.append(f'З3: опис персонажа «{o["imia"]}» задовгий — лише роль, без прикмет')

    # --- П1: поля й ознаки
    for p in POLIA:
        pole = sprava['polia'][p]
        ids = [k['id'] for k in pole['kandydaty']]
        if len(ids) < 4 or len(set(ids)) != len(ids):
            zh.append(f'П1: у полі {p} має бути щонайменше 4 різні варіанти')
        if pole['vidpovid'] not in ids:
            zh.append(f'П1: відповіді поля {p} немає серед варіантів')
        for k in pole['kandydaty']:
            if not k.get('oznaky'):
                zh.append(f'П1: варіант {p}/{k["id"]} без ознак')
    for k in sprava['polia']['de']['kandydaty']:
        if not ('lat' in k and 'lon' in k and MEZHI_KYIEVA[0] <= k['lat'] <= MEZHI_KYIEVA[1]
                and MEZHI_KYIEVA[2] <= k['lon'] <= MEZHI_KYIEVA[3]):
            zh.append(f'П1: місце {k["id"]} без точки в межах Києва')
    slidy = sprava['slidy']
    if [s['n'] for s in slidy] != list(range(1, SLIDIV + 1)):
        zh.append(f'сліди мають бути 1..{SLIDIV}, по одному на день (пн–сб)')
    for s in slidy:
        for rch in s['rechennia']:
            if rch.get('dzherelo') not in DZHERELA:
                zh.append(f'слід {s["n"]}: джерело речення — одне з {sorted(DZHERELA)}')
            for u in rch.get('umovy', []):
                if u.get('pole') not in POLIA:
                    zh.append(f'слід {s["n"]}: умова для невідомого поля {u.get("pole")}')
                elif not any(u['oznaka'] in k['oznaky'] for k in sprava['polia'][u['pole']]['kandydaty']):
                    zh.append(f'слід {s["n"]}: ознаки «{u["oznaka"]}» немає в жодного варіанта поля {u["pole"]}')
            if rch.get('dzherelo') == 'vyhadka' and rch.get('umovy'):
                zh.append(f'П9: слід {s["n"]}: речення-вигадка звужує відповідь — вирішальний факт не може бути вигадкою')
            # --- П7: «з рішення» — лише з цитатою, що дослівно є в уривках
            if rch.get('dzherelo') == 'rishennia':
                ts = rch.get('tsytata', '')
                if not ts or not any(ts in u for u in uryvky):
                    zh.append(f'П7: слід {s["n"]}: речення «з рішення суду» без цитати з уривків рішення')
    if zh:
        return

    # --- П2–П4: звуження
    kroky = zvuzhennia(sprava)
    kin = kroky[-1]
    for p in POLIA:
        if kin[p] != [sprava['polia'][p]['vidpovid']]:
            zh.append(f'П2: після всіх слідів у полі {p} лишається {kin[p]} — має лишитися лише відповідь')
    if len(kroky[3]['de']) < MIN_DE_PISLIA_3:
        zh.append(f'П3: після сліду 3 у полі «де» лише {len(kroky[3]["de"])} — розкривається надто рано')
    for i in range(1, SLIDIV + 1):
        zminy = any(len(kroky[i][p]) < len(kroky[i - 1][p]) for p in POLIA)
        if not zminy:
            rozkryto = all(len(kroky[i - 1][p]) == 1 for p in POLIA)
            if i < SLIDIV or not rozkryto:
                zh.append(f'П4: слід {i} нічого не відсікає')

    # --- П5: відповідь не названа прямо до сліду 4
    rannie = [sprava['vyklyk']] + [s['zahadka'] for s in slidy[:3]] + \
             [rch['tekst'] for s in slidy[:3] for rch in s['rechennia']]
    for p in POLIA:
        k = next(x for x in sprava['polia'][p]['kandydaty'] if x['id'] == sprava['polia'][p]['vidpovid'])
        for slovo in [k['nazva']] + k.get('slova', []):
            for t in rannie:
                if slovo and re.search(r'(?<!\w)' + re.escape(slovo.lower()), t.lower()):
                    zh.append(f'П5: відповідь поля {p} («{slovo}») названо прямо до сліду 4')
                    break

    # --- П6: схованки
    de = next(x for x in sprava['polia']['de']['kandydaty'] if x['id'] == sprava['polia']['de']['vidpovid'])
    for s in slidy:
        t = s['tsil']
        if not (MEZHI_KYIEVA[0] <= t['lat'] <= MEZHI_KYIEVA[1] and MEZHI_KYIEVA[2] <= t['lon'] <= MEZHI_KYIEVA[3]):
            zh.append(f'П6: схованка сліду {s["n"]} поза Києвом')
        if not 200 <= t.get('radius_m', 0) <= 1000:
            zh.append(f'П6: радіус схованки сліду {s["n"]} — від 200 до 1000 м')
        v = vidstan_m(t, de)
        if s['n'] < SLIDIV and v < MIN_VIDSTAN_M:
            zh.append(f'П6: схованка сліду {s["n"]} за {v:.0f} м від відповіді (треба ≥ {MIN_VIDSTAN_M})')
        if s['n'] == SLIDIV and v > t.get('radius_m', 0):
            zh.append('П6: схованка сліду 6 має бути на місці відповіді')

    # --- П8: відповідь справжня
    if not any(de['nazva'].strip('«»') in u or de['nazva'] in u for u in uryvky):
        zh.append(f'П8: місця відповіді «{de["nazva"]}» немає в уривках рішення')
    koly = sprava['polia']['koly']['vidpovid']
    if r.get('chas') and chastyna_doby(r['chas']) != koly:
        zh.append(f'П8: час рішення {r["chas"]} — не «{koly}»')
    shcho = next(x for x in sprava['polia']['shcho']['kandydaty'] if x['id'] == sprava['polia']['shcho']['vidpovid'])
    if shcho.get('stattia') and shcho['stattia'] not in r.get('stattia', ''):
        zh.append(f'П8: вид «{shcho["nazva"]}» не збігається зі статтею рішення {r.get("stattia")}')


def zvit(sprava: dict) -> dict:
    kroky = zvuzhennia(sprava)
    rozkryto = {p: next(i for i, k in enumerate(kroky) if len(k[p]) == 1) for p in POLIA}
    return {'id': sprava['id'], 'kroky': [{p: len(k[p]) for p in POLIA} for k in kroky],
            'rozkryto_pislia': rozkryto, 'kholms': max(rozkryto.values())}


def prochytaty(shlyakh: Path) -> dict:
    return json.loads(Path(shlyakh).read_text(encoding='utf-8'))


def dlia_saitu(sprava: dict) -> dict:
    """Що йде на сайт: усе, крім уривків рішення й службових полів (цитати — лише для перевірки)."""
    z = zvit(sprava)
    s = json.loads(json.dumps(sprava))
    s['rishennia'] = {k: v for k, v in sprava['rishennia'].items() if k in ('nomer', 'url', 'sud', 'data', 'stattia')}
    for sl in s['slidy']:
        for r in sl['rechennia']:
            r.pop('tsytata', None)
    s['rozkryto_pislia'] = z['rozkryto_pislia']
    s['kholms'] = z['kholms']
    s.pop('spravzhni_nazvy', None)
    return s


def main(argv=None) -> int:
    a = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    a.add_argument('spravy', nargs='+', type=Path)
    a.add_argument('--vulytsi', type=Path, help='файл: одна назва вулиці на рядок')
    x = a.parse_args(argv)
    vulytsi = None
    if x.vulytsi:
        vulytsi = {r.strip().lower() for r in x.vulytsi.read_text(encoding='utf-8').splitlines() if r.strip()}
    pady = 0
    for f in x.spravy:
        try:
            z = perevirka(prochytaty(f), vulytsi)
        except PomylkaSpravy as e:
            print(f'НЕ ГОДИТЬСЯ {f.name}: {e}')
            pady += 1
            continue
        ryadky = ' → '.join('/'.join(str(k[p]) for p in POLIA) for k in z['kroky'])
        print(f'так  {f.name}: де/що/коли/поле {ryadky}; Холмс — після сліду {z["kholms"]}')
    return 1 if pady else 0


if __name__ == '__main__':
    sys.exit(main())
