"""Черга файлів роликів → розклад публікацій (ZAVDANNYA-159; MV-154, MV-158, MV-161, MV-171).

Тест роликів (`docs/ROLYKY-SYSTEMA.md`, розд. 5) іде не групами компасу (`rozklad.py`), а **типами** з реєстру
`docs/ROLYKY-TYPY.md`: ролик за роликом, у порядку файлів у черзі, по слотах дня (типово один — 18:00 за Києвом; з 3-го
тижня два — змінна `MV_ROLYKY_SLOTY=18:00,20:30`).

**Черга** — тека `cherha/` у приватному репозиторії автопостингу (MV-154). Один ролик — два файли:

    cherha/001-129-t5.json   опис (нижче)
    cherha/129-t5.mp4        сам ролик (вертикальний 9:16, до 3 хв)

Порядок — за назвою json-файлу (тому номер попереду). Опис:

    {"id": "129-t5",                       латиниця й цифри, до 10 знаків — іде в мітку ?dzherelo=yt-129-t5
     "typ": "Місто за N секунд",            дослівно з docs/ROLYKY-TYPY.md, розд. 1
     "fail": "129-t5.mp4",
     "varianty": "темна · соти · місто · без голосу · гачок А",   осі вигляду (ROLYKY-SYSTEMA, розд. 3.3)
     "dovzhyna_s": 9,
     "holos": false,                        є голос (змінений програмою, MV-156) → позначка «Голос змінено програмою»
     "zaholovok": "Київ за 9 секунд",       назва для YouTube (до 100 знаків)
     "pidpys": "Кожна сота — події з рішень судів…",   підпис без посилання (посилання сервіс додає сам)
     "kudy": "/karta/",                     сторінка сайту, куди веде ролик (тип → «Куди веде»)
     "kudy_nazva": "Карта Києва",
     "merezhi": ["youtube", "tiktok"],      типово YouTube Shorts + TikTok (MV-161); Reels і Facebook — лише найкращі,
                                            Telegram — канал «Ролики» з kanaly.json
     "podii": [], "perepysano": true,       як у manifest.json (pravyla.py)
     "ne_ranishe": "2026-11-24"}            необов'язково

**Мітка джерела** (ZAVDANNYA-153): посилання — `<сайт><kudy>?dzherelo=<код мережі>-<id>` (`yt-129-t5`, `ig-…`, `fb-…`,
`tg-…`, `tt-…`). Коротка, бо сторінки-входи 153 дописують до неї свій код, а канал сервера продажу — до 40 знаків.

**TikTok — вручну** (MV-154): одиниця TikTok стає в чергу зі станом `vruchnu`; щодня — чекліст `TikTok.md` і файл у
вкладенні запуску; після публікації Микита запускає команду `tiktok <id> <посилання>` — і ролик іде в заміри.
"""
from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from pravyla import KOD_MEREZHI, POZNACHKA_HOLOSU, z_mitkoiu
from rozklad import KYIV, chas, nazva_tyzhnia

KORIN = Path(__file__).resolve().parents[1]
TYPY_MD = KORIN / 'docs' / 'ROLYKY-TYPY.md'
TEKA_CHERHY = 'cherha'                      # усередині теки медіа (робочий процес копіює туди cherha/ репозиторію)
ID_ROLYKA = re.compile(r'^[a-z0-9][a-z0-9-]{0,9}$')
MEREZHI_TYPOVO = ('youtube', 'tiktok')
MEREZHI_ROLYKA = ('youtube', 'tiktok', 'instagram', 'facebook', 'telegram')
KANAL_TELEGRAM = 'Ролики'                   # ключ у kanaly.json: «Ролики» → @канал проєкту
DNIV_NAPERED = 7
STAN_VRUCHNU = 'vruchnu'


# ==================================================================== реєстр типів
def typy(shliakh: Path = TYPY_MD) -> dict[str, dict]:
    """Назви типів з `docs/ROLYKY-TYPY.md`, розд. 1 (обидві таблиці) → {'format', 'kudy', 'stan'}. Відкинуті (✗) — ні."""
    r, v_rozdili = {}, False
    for ryadok in shliakh.read_text(encoding='utf-8').splitlines():
        if ryadok.startswith('## '):
            v_rozdili = ryadok.startswith('## 1.')
            continue
        if not v_rozdili or not ryadok.startswith('|'):
            continue
        k = [x.strip() for x in ryadok.strip().strip('|').split('|')]
        if not k or k[0] in ('Тип', 'Ідея') or set(k[0]) <= set('-: '):
            continue
        if len(k) >= 5 and k[1].startswith(('t', 'n', 'z')) and re.match(r'^[tnz]\d', k[1]):   # таблиця затверджених
            opys = {'format': k[2], 'kudy': k[3], 'stan': k[4]}
        else:                                                                               # таблиця ідей
            opys = {'format': k[1], 'kudy': k[2], 'stan': 'ідея'}
        if '✗' in opys['stan']:
            continue
        r[k[0]] = opys
    return r


def typ_z_reiestru(nazva: str, reiestr: dict) -> str | None:
    """None — тип є; інакше — пояснення з найближчими назвами."""
    if nazva in reiestr:
        return None
    blyzki = difflib.get_close_matches(nazva or '', list(reiestr), n=2, cutoff=0.5)
    return (f'тип «{nazva}» не з реєстру docs/ROLYKY-TYPY.md'
            + (f' — може, {" або ".join(f"«{b}»" for b in blyzki)}?' if blyzki else ''))


# ==================================================================== черга
def pozytsiia(r: dict) -> str:
    return f'cherha:{r["id"]}'


def vidbytok(r: dict, teka: Path) -> str:
    """Що саме лежить у черзі: опис + розмір файлу. Змінили опис відхиленого ролика — плануємо знову."""
    f = teka / str(r.get('fail', ''))
    rozmir = f.stat().st_size if f.is_file() else -1
    return hashlib.sha1((json.dumps(r, ensure_ascii=False, sort_keys=True) + str(rozmir)).encode()).hexdigest()[:12]


def chytaty(teka_media: Path | None) -> tuple[list[dict], list[str]]:
    """Ролики з черги в порядку назв і помилки читання."""
    teka = Path(teka_media) / TEKA_CHERHY if teka_media else None
    if not teka or not teka.is_dir():
        return [], []
    r, pomylky = [], []
    for f in sorted(teka.glob('*.json')):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
            if not isinstance(d, dict):
                raise ValueError('не об\'єкт')
        except (OSError, ValueError) as e:
            pomylky.append(f'{f.name}: не прочитано ({e})')
            continue
        d['_fail_opysu'] = f.name
        r.append(d)
    return r, pomylky


def zauvazhennia_rolyka(r: dict, reiestr: dict) -> list[str]:
    """Перевірки самого опису (до мережевих правил pravyla.py)."""
    zh = []
    if not ID_ROLYKA.match(str(r.get('id', ''))):
        zh.append(f'id «{r.get("id")}»: латиниця, цифри й дефіс, до 10 знаків')
    t = typ_z_reiestru(r.get('typ', ''), reiestr)
    if t:
        zh.append(t)
    if not r.get('fail'):
        zh.append('немає поля fail')
    if not str(r.get('kudy', '')).startswith('/'):
        zh.append('kudy — шлях сторінки сайту, напр. /karta/')
    if not isinstance(r.get('holos'), bool):
        zh.append('holos: true або false (чи є в ролику голос — MV-171)')
    nevidomi = set(r.get('merezhi') or ()) - set(MEREZHI_ROLYKA)
    if nevidomi:
        zh.append(f'невідомі мережі: {", ".join(sorted(nevidomi))}')
    return zh


def sloty(vid: datetime, dniv: int = DNIV_NAPERED) -> list[str]:
    """Слоти (UTC ISO) від `vid` на `dniv` днів уперед за `MV_ROLYKY_SLOTY` (за Києвом, типово 18:00)."""
    godyny = []
    for s in (os.environ.get('MV_ROLYKY_SLOTY') or '18:00').split(','):
        m = re.match(r'^\s*(\d{1,2}):(\d{2})\s*$', s)
        if m:
            godyny.append((int(m[1]), int(m[2])))
    godyny = sorted(set(godyny)) or [(18, 0)]
    den0 = vid.astimezone(KYIV).date()
    vid_iso = vid.isoformat(timespec='minutes')
    r = []
    for i in range(dniv + 1):
        for h, m in godyny:
            c = chas(den0 + timedelta(days=i), h, m)
            if datetime.fromisoformat(c) > datetime.fromisoformat(vid_iso):
                r.append(c)
    return r


def pidpys(r: dict, merezha: str, adresa_saitu: str) -> tuple[str, str]:
    """Текст під роликом і посилання з міткою. Позначка голосу — окремим рядком (MV-171)."""
    url = z_mitkoiu(adresa_saitu.rstrip('/') + r['kudy'], f'{KOD_MEREZHI[merezha]}-{r["id"]}')
    chastyny = [str(r.get('pidpys', '')).strip()]
    if r.get('holos'):
        chastyny.append(POZNACHKA_HOLOSU + '.')
    nazva = r.get('kudy_nazva') or 'Моя вулиця'
    if merezha == 'tiktok':
        # у підписі TikTok посилання не клікабельне — веде посилання в профілі (чекліст TikTok.md)
        chastyny.append(f'{nazva} — посилання в профілі.')
    else:
        chastyny.append(f'{nazva} — на сайті: {url}')
    return '\n\n'.join(x for x in chastyny if x), url


def odynytsia(r: dict, merezha: str, chas_: str, adresa_saitu: str, vidb: str) -> dict:
    tekst, url = pidpys(r, merezha, adresa_saitu)
    tyzhden = nazva_tyzhnia(datetime.fromisoformat(chas_).astimezone(KYIV).date()
                            - timedelta(days=datetime.fromisoformat(chas_).astimezone(KYIV).weekday()))
    o = {'tyzhden': tyzhden, 'merezha': merezha, 'kanal': KANAL_TELEGRAM if merezha == 'telegram' else '',
         'typ': 'rolyk', 'hrupa': 'cherha', 'chas': chas_, 'tekst': tekst, 'posylannia': url,
         'fail': f'{TEKA_CHERHY}/{r["fail"]}', 'mistse': {'shliakh': r['kudy'], 'nazva': r.get('kudy_nazva', '')},
         'podii': r.get('podii') or [], 'perepysano': bool(r.get('perepysano', True)),
         'chernetka': bool(r.get('chernetka')), 'pozytsiia': pozytsiia(r), 'vidbytok': vidb, 'dzherelo': 'cherha',
         'rolyk_id': r['id'], 'typ_rolyka': r['typ'], 'varianty': r.get('varianty', ''),
         'dovzhyna_s': r.get('dovzhyna_s', ''), 'holos': bool(r.get('holos')), 'kudy': r['kudy'],
         'zaholovok': r.get('zaholovok', '')}
    if merezha == 'youtube':
        o['nazva'] = (r.get('zaholovok') or r.get('kudy_nazva') or r['id'])[:100]
    if merezha == 'tiktok':
        o['vruchnu'] = True
    o['id'] = hashlib.sha1(f'{pozytsiia(r)}|{vidb}|{merezha}'.encode()).hexdigest()[:16]
    return o


def zaplanuvaty(cherha_db, teka_media: Path | None, adresa_saitu: str, zaraz: datetime,
                reiestr: dict | None = None) -> tuple[list[dict], list[str]]:
    """Нові ролики з черги → одиниці на вільні слоти. Повертає одиниці й повідомлення для журналу.

    Ролик, що вже стоїть у черзі, вийшов чи чекає TikTok, удруге не плануємо. Якщо всі його одиниці не пройшли
    перевірку, а опис чи файл змінили (інший відбиток) — плануємо знову на новий слот."""
    rolyky, povidomlennia = chytaty(teka_media)
    if not rolyky:
        return [], povidomlennia
    reiestr = reiestr if reiestr is not None else typy()
    teka = Path(teka_media) / TEKA_CHERHY
    vsi = [o for o in cherha_db.vsi() if o.get('dzherelo') == 'cherha']
    zhyvi = {'chekaie', 'opublikovano', STAN_VRUCHNU, 'pomylka', 'prybrano', 'prybraty_vruchnu', 'propushcheno'}
    zaniati = {o['chas'] for o in vsi if o['stan'] in zhyvi}
    vilni = [s for s in sloty(zaraz) if s not in zaniati]
    novi, zaplanovani = [], set()
    for r in rolyky:
        poz = pozytsiia(r) if r.get('id') else None
        if poz in zaplanovani:
            povidomlennia.append(f'{r["_fail_opysu"]}: id {r["id"]} уже є в черзі — пропускаю')
            continue
        svoi = [o for o in vsi if o.get('pozytsiia') == poz]
        vidb = vidbytok({k: v for k, v in r.items() if not k.startswith('_')}, teka)
        if any(o['stan'] in zhyvi for o in svoi) or any(o.get('vidbytok') == vidb for o in svoi):
            continue
        if r.get('ne_ranishe'):
            try:
                mezha = date.fromisoformat(str(r['ne_ranishe']))
            except ValueError:
                povidomlennia.append(f'{r["_fail_opysu"]}: ne_ranishe не дата')
                continue
        else:
            mezha = None
        zh = zauvazhennia_rolyka(r, reiestr)
        if not ID_ROLYKA.match(str(r.get('id', ''))) or not r.get('fail') or not str(r.get('kudy', '')).startswith('/'):
            povidomlennia.append(f'{r["_fail_opysu"]}: ' + '; '.join(zh))      # без цього навіть одиниці не скласти
            continue
        slot = next((s for s in vilni if not mezha or datetime.fromisoformat(s).astimezone(KYIV).date() >= mezha), None)
        if not slot:
            break                                  # слоти на тиждень зайняті — решта почекає
        vilni.remove(slot)
        zaplanovani.add(poz)
        for m in (r.get('merezhi') or MEREZHI_TYPOVO):
            if m in MEREZHI_ROLYKA:
                o = odynytsia(r, m, slot, adresa_saitu, vidb)
                o['zauvazhennia_opysu'] = zh       # тип не з реєстру тощо — одиниця «не пройшла перевірку» з причиною
                novi.append(o)
    return novi, povidomlennia


# ==================================================================== TikTok вручну
def tiktok_md(cherha_db, zaraz: datetime, adresa_saitu: str, dniv_nazad: int = 1, dniv_vpered: int = 2) -> str:
    """Чекліст для Микити: що поставити в TikTok сьогодні й найближчими днями (MV-154: TikTok — вручну)."""
    vid = (zaraz - timedelta(days=dniv_nazad)).isoformat(timespec='minutes')
    do = (zaraz + timedelta(days=dniv_vpered)).isoformat(timespec='minutes')
    rr = [o for o in cherha_db.vsi() if o['merezha'] == 'tiktok' and o.get('dzherelo') == 'cherha'
          and (o['stan'] == STAN_VRUCHNU and o['chas'] <= do or vid <= o['chas'] <= do)]
    sait = adresa_saitu.rstrip('/')
    ch = ['# TikTok — поставити вручну', '',
          f'Оновлено {zaraz.astimezone(KYIV).strftime("%d.%m %H:%M")} за Києвом. Файли — у вкладенні запуску '
          '(Actions → останній запуск «Автопостинг» → Artifacts → `tiktok-…`).', '',
          '## Щоразу (≈ 3 хв на ролик)', '',
          '1. Відкрити TikTok на телефоні (акаунт проєкту) → «+» → завантажити файл ролика з вкладення.',
          '2. Вставити підпис з таблиці нижче дослівно (там уже є «Голос змінено програмою», якщо в ролику голос).',
          '3. «Більше параметрів» → увімкнути **«Вміст, створений ШІ»** (AI-generated content), якщо в рядку «голос — так» '
          '(MV-171: голос змінено програмою). Без голосу — не вмикати.',
          '4. Музику TikTok не додавати (у роликах уже свій звук); коментарі — дозволити; дуети й склейки — вимкнути.',
          '5. Опублікувати **о часі з таблиці** (18:00–21:00 за Києвом) — можна «Запланувати» в TikTok Studio на ПК.',
          '6. Скопіювати посилання на ролик → GitHub → Actions → «Автопостинг» → Run workflow → команда `tiktok`, '
          '«id» — id ролика з таблиці, «posylannia» — посилання. Без цього ролик не потрапить у заміри.',
          '', f'Посилання в профілі TikTok (один раз): `{sait}/?dzherelo=tt` — у підписі TikTok посилання не клікабельні.',
          '']
    if not rr:
        return '\n'.join(ch + ['Найближчими днями нічого ставити не треба.', ''])
    ch += ['## Що поставити', '', '| Коли | id | Тип | Голос | Файл | Стан |', '|---|---|---|---|---|---|']
    for o in rr:
        stan = 'поставити' if o['stan'] == STAN_VRUCHNU else ('вийшло ' + (o.get('url_dopysu') or '')
                                                              if o['stan'] == 'opublikovano' else o['stan'])
        ch.append(f'| {datetime.fromisoformat(o["chas"]).astimezone(KYIV).strftime("%d.%m %H:%M")} | `{o["rolyk_id"]}` '
                  f'| {o["typ_rolyka"]} | {"так" if o.get("holos") else "ні"} | `{Path(o["fail"]).name}` | {stan} |')
    ch.append('')
    for o in rr:
        if o['stan'] != STAN_VRUCHNU:
            continue
        ch += [f'### `{o["rolyk_id"]}` — підпис', '', '```', o['tekst'], '```', '']
    return '\n'.join(ch)


def faily_tiktok(cherha_db, zaraz: datetime, teka_media: Path | None, kudy: Path, dniv_vpered: int = 2) -> list[Path]:
    """Файли й підписи TikTok, які треба поставити до `dniv_vpered` днів уперед, — у теку вкладення запуску."""
    do = (zaraz + timedelta(days=dniv_vpered)).isoformat(timespec='minutes')
    r = []
    for o in cherha_db.vsi(stan=STAN_VRUCHNU):
        if o['merezha'] != 'tiktok' or o['chas'] > do or not teka_media:
            continue
        f = Path(teka_media) / o['fail']
        if not f.is_file():
            continue
        kudy.mkdir(parents=True, exist_ok=True)
        imia = datetime.fromisoformat(o['chas']).astimezone(KYIV).strftime('%m%d-%H%M') + f'-{o["rolyk_id"]}'
        (kudy / f'{imia}{f.suffix}').write_bytes(f.read_bytes())
        (kudy / f'{imia}.txt').write_text(o['tekst'] + '\n', encoding='utf-8')
        r.append(kudy / f'{imia}{f.suffix}')
    return r


VIDEO_ID_TIKTOK = re.compile(r'/video/(\d{6,})')


def tiktok_postavleno(cherha_db, id_: str, posylannia: str, zaraz: datetime) -> str:
    """Микита поставив ролик у TikTok: id ролика (`129-t5`) або одиниці → опубліковано з посиланням."""
    posylannia = (posylannia or '').strip()
    if not re.match(r'^https://(www\.|vm\.|vt\.)?tiktok\.com/', posylannia):
        return 'посилання має починатися з https://www.tiktok.com/ (скопіюйте «Поділитися → Копіювати посилання»)'
    tsili = [o for o in cherha_db.vsi() if o['merezha'] == 'tiktok' and o.get('dzherelo') == 'cherha'
             and (o['id'] == id_ or o.get('rolyk_id') == id_)]
    if not tsili:
        return f'немає ролика TikTok з id {id_}'
    o = next((x for x in tsili if x['stan'] == STAN_VRUCHNU), tsili[-1])
    m = VIDEO_ID_TIKTOK.search(posylannia)
    cherha_db.stan(o['id'], 'opublikovano', url_dopysu=posylannia, zovnishnii_id=m[1] if m else '',
                   opublikovano=zaraz.isoformat(timespec='minutes'))
    cherha_db.zapys('opublikovano', f'TikTok вручну: {posylannia}', o, koly=zaraz)
    return f'tiktok {o["rolyk_id"]}: записано {posylannia}'
