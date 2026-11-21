"""«Нове біля дому» — лист і сповіщення підписникам (ZAVDANNYA-119; лінія «Мій район», MV-107). Підписка 399 — раз на
місяць після оновлення даних (ZAVDANNYA-150, `site/prodazh/lyst_stezhu.py`); бот — щотижня.

Стрічку тижня (`nove-<дата>.json`) робить `dani-edrsr/src/nove_tyzhnia.py` — одна на всіх. Тут для кожного підписника
з неї вибирається лише те, що в радіусі `R_M` від **його** адрес «Стежу», і складається лист:

  * підписка (`taryf = 'pidpyska'`) — усі адреси «Стежу»; події з рішень судів — дата, група, місце, переказ ШІ (лише
    перевірений, `site/sait/perekazy.py`), посилання на рішення; скарги 1551 — теми й числа; проблема поруч — одним рядком.
    Чутливі — нарівні (платне, MV-104).
  * безкоштовно (бот, MV-124) — **одна адреса й лише числа**: без місць, описів і посилань на рішення; статеві й щодо
    дітей не рахуються (`vidkr`, MV-102); номер будинку — лише той, який людина сама написала боту.
  * сповіщення застосунку (`docs/ANDROID.md`, розд. 6) — лише числа й вулиця без номера: його видно на заблокованому екрані.

Нового немає: підписнику — короткий «тихий тиждень» (якщо не вимкнув), безкоштовному — нічого.
Правила тексту (AGENTS.md, розд. 4; docs/KOMPAS.md, розд. 6): без «небезпечно», рейтингів, прогнозів і порад; скарга —
звернення, не факт; подія — лише те, що дійшло до суду; без емодзі, без червоного.
"""
from __future__ import annotations

import html
import json
import math
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
for _p in (KORIN / 'site', KORIN / 'site' / 'sait', KORIN / 'brend'):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import perekazy as PK  # noqa: E402
import tsiny as T  # noqa: E402
from adresa_pokazu import bez_nomera  # noqa: E402

R_M = 300                    # як «Стежу» на карті підписника й бот
MAKS_PODII_LYST = 10         # далі — «ще N — у „Стежу“»
MAKS_PODII_TELEGRAM = 5
NBSP = ' '
ADRESA_SAITU = 'https://moya-vulytsya.pages.dev'      # справжній домен — на партнера
HASLO = 'Моя вулиця — що відбувається під боком'
CHESNO = ('Скарга — звернення мешканця до 1551, не перевірений факт. Подія — випадок із рішення суду: лише те, що '
          'дійшло до суду. «Нове в даних» — рішення, що з’явилися в даних за цей період; сама подія могла статися раніше.')
MISIATSI = ('січня', 'лютого', 'березня', 'квітня', 'травня', 'червня', 'липня', 'серпня', 'вересня', 'жовтня',
            'листопада', 'грудня')
HRUPY = {h['kliuch']: h for h in json.loads((KORIN / 'brend' / 'hrupy.json').read_text(encoding='utf-8'))['hrupy']}

# Кольори листа — світла тема сайту (docs/STYL.md, «Змінні CSS»): у пошті змінних CSS немає, тож — готові значення.
K = dict(ground='#F4F5FB', surface='#FFFFFF', tint='#EDEFFE', ink='#1C1E2D', ink2='#3E4155', muted='#5F6275',
         line='#DFE1E9', mezha='#76798C', bort='#585B69', accent='#4447A6', soft='#DFE3FC', on='#FFFFFF')
SHRYFT = "'IBM Plex Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"

# Що в листі бути не може (AGENTS.md, розд. 4; KOMPAS, розд. 6) — перевіряється перед кожним надсиланням.
ZABORONENI = re.compile(
    r'небезпечн|безпечн|рейтинг|найгірш|найкращ|страшн|найімовірніше|імовірно, буде|станеться знову|триває й далі|'
    r'будьте уважн|дивіться уважн|уникайте|не ходіть|тримайте речі|не підбирайте|уважнішим|макет|конвеєр|медіана|'
    r'\bMV-\d|ОСОБА|АДРЕСА_|\bП\d+[–-]П\d+', re.I)
EMODZI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')


def vady_tekstu(t: str) -> list[str]:
    """Чому текст листа не можна надіслати; порожньо — можна."""
    v = [f'заборонене: «{m.group(0)}»' for m in ZABORONENI.finditer(t)]
    if EMODZI.search(t):
        v.append('емодзі')
    return v


# ---------------------------------------------------------------- дані підписника

@dataclass
class Adresa:
    adresa: str                 # як людина бачила її в «Стежу» («вулиця Зразкова, 5»)
    lat: float
    lon: float
    nazva: str = ''             # її власна позначка («Дім», «Робота»), необов'язково


@dataclass
class Pidpysnyk:
    id: str                     # непрозорий номер (не пошта): з ним ідуть посилання відписки
    taryf: str                  # 'pidpyska' | 'bezkoshtovno'
    adresy: list[Adresa] = field(default_factory=list)
    tykhyi_lyst: bool = True    # підписнику: «тихий тиждень», коли нового немає

    @property
    def platno(self) -> bool:
        return self.taryf == 'pidpyska'


@dataclass
class Rozdil:
    adresa: Adresa
    podii: list[dict]
    skarhy: dict                # група -> число за тиждень
    budynkiv: int               # у скількох будинках були звернення
    problema: dict | None

    @property
    def nove(self) -> bool:
        return bool(self.podii or self.skarhy)


@dataclass
class Lyst:
    pidpysnyk_id: str
    platno: bool
    vid: str
    do: str
    rozdily: list[Rozdil]
    pershyi: bool = False       # перший лист на новому випуску: «нового» не рахуємо (ZAVDANNYA-195)

    @property
    def tykhyi(self) -> bool:
        return not any(r.nove for r in self.rozdily)


# ---------------------------------------------------------------- збирання

def metriv(la1, lo1, la2, lo2) -> float:
    kx = 111_320 * math.cos(math.radians((la1 + la2) / 2))
    return math.hypot((la1 - la2) * 110_540, (lo1 - lo2) * kx)


def rozdil(strichka: dict, a: Adresa, platno: bool, r_m: int = R_M) -> Rozdil:
    poruch = lambda x: metriv(a.lat, a.lon, x['lat'], x['lon']) <= r_m  # noqa: E731
    podii = [p for p in strichka.get('podii', []) if poruch(p) and (platno or p.get('vidkr', 1))]
    podii.sort(key=lambda p: (p.get('data') or '', p['id']), reverse=True)
    skarhy, budynkiv = {}, 0
    for b in strichka.get('skarhy', []):
        if poruch(b):
            budynkiv += 1
            for h, n in b['hrupy'].items():
                skarhy[h] = skarhy.get(h, 0) + n
    skarhy = dict(sorted(skarhy.items(), key=lambda x: (-x[1], x[0])))
    # ZAVDANNYA-195 (MV-195): згасла проблема (`chynna: false`) — не «місце, де повторюються»; у листі — лише чинні
    pr = sorted(((metriv(a.lat, a.lon, p['lat'], p['lon']), p['id'], p) for p in strichka.get('problemy', [])
                 if poruch(p) and p.get('chynna', True)), key=lambda x: x[:2])
    problema = dict(pr[0][2], vidstan=round(pr[0][0] / 10) * 10) if pr else None
    return Rozdil(a, podii, skarhy, budynkiv, problema)


def zibraty(strichka: dict, p: Pidpysnyk, r_m: int = R_M) -> Lyst | None:
    """Лист одному підписнику — лише з його адрес. None — нічого не надсилаємо."""
    adresy = p.adresy if p.platno else p.adresy[:1]          # безкоштовно — одна адреса (MV-124)
    if not adresy:
        return None
    t = strichka['tyzhden']
    pershyi = bool(strichka.get('pershyi_lyst'))
    rr = [rozdil(strichka, a, p.platno, r_m) for a in adresy]
    if pershyi:                 # перший лист на новому випуску (ZAVDANNYA-195): жодна подія не «нова», навіть якщо стрічка інша
        for r in rr:
            r.podii = []
    l = Lyst(p.id, p.platno, t['vid'], t['do'], rr, pershyi)
    if l.tykhyi and not (p.platno and p.tykhyi_lyst):
        return None
    return l


# ---------------------------------------------------------------- слова

def chyslo(n: int) -> str:
    return f'{n:,}'.replace(',', NBSP)


def vidminok(n: int, formy: tuple[str, str, str]) -> str:
    n = abs(n) % 100
    if 11 <= n <= 14:
        return formy[2]
    return formy[0] if n % 10 == 1 else formy[1] if 2 <= n % 10 <= 4 else formy[2]


def podii_slovo(n: int) -> str:
    return f'{chyslo(n)} {vidminok(n, ("подія", "події", "подій"))}'


def skarh_slovo(n: int) -> str:
    return f'{chyslo(n)} {vidminok(n, ("звернення", "звернення", "звернень"))}'


def data_slovamy(d: str) -> str:
    """'2026-11-03' -> '3 листопада 2026'; лише місяць чи рік — як є."""
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', d or '')
    if not m:
        return d or 'дата невідома'
    return f'{int(m.group(3))} {MISIATSI[int(m.group(2)) - 1]} {m.group(1)}'


def misiachnyi(l: Lyst) -> bool:
    """ZAVDANNYA-150, п. 4: лист підписці — раз на місяць після оновлення даних (стрічка за місяць); бот — щотижня."""
    return (date.fromisoformat(l.do) - date.fromisoformat(l.vid)).days >= 27


def slova_periodu(l: Lyst) -> dict:
    if misiachnyi(l):
        return {'tykhyi': 'Тихий місяць', 'tsoho': 'Цього місяця', 'za': 'за місяць'}
    return {'tykhyi': 'Тихий тиждень', 'tsoho': 'Цього тижня', 'za': 'за тиждень'}


def nemaie_skarh(l: Lyst) -> str:
    return f'Звернень до 1551 {slova_periodu(l)["za"]} немає.'


def tyzhden(l: Lyst) -> str:
    v, d = date.fromisoformat(l.vid), date.fromordinal(date.fromisoformat(l.do).toordinal() - 1)
    if v.month == d.month:
        return f'{v.day}–{d.day} {MISIATSI[d.month - 1]}'
    return f'{v.day} {MISIATSI[v.month - 1]} – {d.day} {MISIATSI[d.month - 1]}'


def zaholovok_adresy(a: Adresa) -> str:
    return f'{a.nazva} · {a.adresa}' if a.nazva else a.adresa


def opys(p: dict) -> str | None:
    """Переказ ШІ, лише якщо проходить перевірку і тут (друга лінія після dani-edrsr)."""
    t = p.get('perekaz')
    return t if t and not PK.vady(t) else None


def ryadok_problemy(pr: dict) -> str:
    h = HRUPY.get(pr['hrupa'], {}).get('slovo', '')
    de = f' — {pr["nazva"]}' if pr.get('nazva') else ''
    return (f'Поруч (≈{NBSP}{chyslo(pr["vidstan"])}{NBSP}м) — місце, де повторюються {h}{de}: '
            f'{podii_slovo(pr["podii"])} у даних за всі роки.')


def ryadok_skarh(r: Rozdil, skilky_tem: int = 3) -> str:
    n = sum(r.skarhy.values())
    temy = ', '.join(f'{h} — {chyslo(k)}' for h, k in list(r.skarhy.items())[:skilky_tem])
    inshi = n - sum(list(r.skarhy.values())[:skilky_tem])
    if inshi:
        temy += f', інше — {chyslo(inshi)}'
    bud = f' з {chyslo(r.budynkiv)} {vidminok(r.budynkiv, ("будинку", "будинків", "будинків"))}'
    return f'Звернень до 1551: {chyslo(n)}{bud} ({temy}).'


def ryadok_podii_chyslom(r: Rozdil) -> str:
    po = {}
    for p in r.podii:
        po[p['hrupa']] = po.get(p['hrupa'], 0) + 1
    hr = ', '.join(f'{HRUPY[h]["slovo"]} — {chyslo(n)}' for h, n in sorted(po.items(), key=lambda x: (-x[1], x[0])))
    return f'Нових подій з рішень судів у даних: {chyslo(len(r.podii))} ({hr}).'


# ---------------------------------------------------------------- лист: текст і HTML

def tema(l: Lyst) -> str:
    if l.tykhyi:
        return f'{slova_periodu(l)["tykhyi"]} біля дому · {tyzhden(l)}'
    n_p = sum(len(r.podii) for r in l.rozdily)
    n_s = sum(sum(r.skarhy.values()) for r in l.rozdily)
    chastyny = [x for x in (podii_slovo(n_p) if n_p else '', skarh_slovo(n_s) + ' до 1551' if n_s else '') if x]
    return f'Нове біля дому · {tyzhden(l)}: ' + ' і '.join(chastyny)


PERSHYI = ('Це перший лист «Стежу» на оновлених даних. Нові події з рішень судів рахуємо від наступного оновлення: '
           'тоді в листі буде те, що з’явилося в даних після цього. Цього разу — звернення до 1551 за місяць.')


def tekst(l: Lyst, posylannia: dict) -> str:
    """Простий текст листа (друга частина листа поруч із HTML). posylannia: stezhu, vidpyska."""
    r_ = [HASLO, '', tema(l), ''] + ([PERSHYI, ''] if l.pershyi else [])
    if l.tykhyi:
        r_ += [f'{slova_periodu(l)["tsoho"]} в радіусі {R_M}{NBSP}м від ваших адрес нових рішень судів і звернень до 1551 у даних немає.', '']
        r_ += [f'— {zaholovok_adresy(r.adresa)}' for r in l.rozdily] + ['']
    for r in ([] if l.tykhyi else l.rozdily):
        r_ += [zaholovok_adresy(r.adresa).upper(), f'Радіус {R_M}{NBSP}м.', '']
        if r.podii:
            r_.append(f'Події з рішень судів — {podii_slovo(len(r.podii))}:')
            for p in r.podii[:MAKS_PODII_LYST]:
                mistse = f' · {p["mistse"]}' if p.get('mistse') else ''
                r_.append(f'  {data_slovamy(p.get("data"))} · {HRUPY[p["hrupa"]]["nazva"]}{mistse}')
                o = opys(p)
                r_.append(f'    {o}' if o else '    Опису ще немає.')
                r_.append(f'    Рішення суду: {p["url"]}')
            if len(r.podii) > MAKS_PODII_LYST:
                r_.append(f'  Ще {podii_slovo(len(r.podii) - MAKS_PODII_LYST)} — на карті підписника.')
        else:
            r_.append('Нових подій з рішень судів у даних немає.')
        r_.append(ryadok_skarh(r) if r.skarhy else nemaie_skarh(l))
        if r.problema:
            r_.append(ryadok_problemy(r.problema))
        r_.append('')
    r_ += [CHESNO, '', f'Відкрити «Стежу»: {posylannia["stezhu"]}',
           f'{posylannia.get("vidpyska_napys", "Не надсилати ці листи (один дотик)")}: {posylannia["vidpyska"]}']
    return '\n'.join(r_) + '\n'


def _e(t) -> str:
    return html.escape(str(t), quote=True)


def _knopka(tekst_: str, url: str, holovna: bool = False) -> str:
    tlo, kolir = (K['accent'], K['on']) if holovna else (K['surface'], K['ink'])
    return (f'<a href="{_e(url)}" style="display:inline-block;padding:10px 16px;margin:4px 8px 4px 0;border:1.5px solid '
            f'{K["mezha"]};border-radius:12px;box-shadow:0 3px 0 {K["bort"]};background:{tlo};color:{kolir};'
            f'font-weight:600;font-size:14px;line-height:20px;text-decoration:none">{_e(tekst_)}</a>')


def html_lysta(l: Lyst, posylannia: dict, zrazok: str = '') -> str:
    """HTML листа: стилі в рядку (поштові програми не читають файли стилів), світла тема сайту."""
    st_p = f'margin:0 0 8px;font-size:16px;line-height:24px;color:{K["ink"]}'
    st_m = f'margin:0 0 8px;font-size:13px;line-height:18px;color:{K["muted"]}'
    b = []
    if zrazok:
        b.append(f'<p style="{st_m};text-align:center">{_e(zrazok)}</p>')
    b.append(f'<p style="margin:0 0 4px;font-size:13px;line-height:18px;font-weight:600;color:{K["accent"]}">Моя вулиця</p>'
             f'<p style="margin:0 0 16px;font-size:13px;color:{K["muted"]}">що відбувається під боком</p>')
    b.append(f'<h1 style="margin:0 0 16px;font-size:24px;line-height:30px;font-weight:700;color:{K["ink"]}">{_e(tema(l))}</h1>')
    if l.pershyi:
        b.append(f'<p style="{st_p}">{_e(PERSHYI)}</p>')
    if l.tykhyi:
        b.append(f'<div style="background:{K["surface"]};border:1px solid {K["line"]};border-radius:16px;padding:20px;margin:0 0 16px">'
                 f'<p style="{st_p}">{slova_periodu(l)["tsoho"]} в радіусі {R_M}{NBSP}м від ваших адрес нових рішень судів і звернень до 1551 '
                 f'у даних немає.</p>' + ''.join(f'<p style="{st_m}">{_e(zaholovok_adresy(r.adresa))}</p>' for r in l.rozdily)
                 + '</div>')
    for r in ([] if l.tykhyi else l.rozdily):
        s = [f'<p style="margin:0 0 2px;font-size:18px;line-height:22px;font-weight:700;color:{K["ink"]}">'
             f'{_e(zaholovok_adresy(r.adresa))}</p><p style="{st_m}">радіус {R_M}{NBSP}м · {_e(tyzhden(l))}</p>']
        n_s = sum(r.skarhy.values())
        s.append('<table role="presentation" cellpadding="0" cellspacing="0" style="margin:8px 0 12px"><tr>'
                 + ''.join(f'<td style="padding:0 24px 0 0;vertical-align:top"><div style="font-size:34px;line-height:40px;'
                           f'font-weight:800;color:{K["ink"]};font-variant-numeric:tabular-nums">{chyslo(n)}</div>'
                           f'<div style="{st_m}">{_e(pid)}</div></td>'
                           for n, pid in ((len(r.podii), 'нових подій з рішень судів'), (n_s, 'звернень до 1551')))
                 + '</tr></table>')
        for p in r.podii[:MAKS_PODII_LYST]:
            h = HRUPY[p['hrupa']]
            o = opys(p)
            s.append(f'<div style="border-top:1px solid {K["line"]};padding:10px 0">'
                     f'<p style="margin:0 0 4px;font-size:13px;line-height:18px;color:{K["ink2"]}">'
                     f'<span style="display:inline-block;width:10px;height:10px;border-radius:999px;background:{h["svitla"]};'
                     f'margin-right:6px"></span><b>{_e(h["nazva"])}</b> · {_e(data_slovamy(p.get("data")))}'
                     + (f' · {_e(p["mistse"])}' if p.get('mistse') else '') + '</p>'
                     + (f'<p style="{st_p}">{_e(o)}</p>' if o else f'<p style="{st_m}">Опису ще немає.</p>')
                     + f'<p style="margin:0;font-size:13px"><a href="{_e(p["url"])}" style="color:{K["accent"]}">Рішення суду</a></p></div>')
        if len(r.podii) > MAKS_PODII_LYST:
            s.append(f'<p style="{st_m}">Ще {podii_slovo(len(r.podii) - MAKS_PODII_LYST)} — на карті підписника.</p>')
        if not r.podii:
            s.append(f'<p style="{st_m}">Нових подій з рішень судів у даних немає.</p>')
        s.append(f'<p style="{st_p};border-top:1px solid {K["line"]};padding-top:10px">'
                 + _e(ryadok_skarh(r) if r.skarhy else nemaie_skarh(l)) + '</p>')
        if r.problema:
            s.append(f'<p style="margin:8px 0 0;padding:10px 12px;background:{K["soft"]};border-radius:12px;font-size:14px;'
                     f'line-height:20px;color:{K["ink"]}">{_e(ryadok_problemy(r.problema))}</p>')
        b.append(f'<div style="background:{K["surface"]};border:1px solid {K["line"]};border-radius:16px;padding:20px;'
                 f'margin:0 0 16px">{"".join(s)}</div>')
    b.append('<p style="margin:8px 0 16px">' + _knopka('Відкрити «Стежу»', posylannia['stezhu'], holovna=True) + '</p>')
    b.append(f'<p style="{st_m}">{_e(CHESNO)}</p>')
    b.append(f'<p style="{st_m}"><a href="{_e(posylannia["vidpyska"])}" style="color:{K["muted"]}">Не надсилати ці листи</a>'
             f' — один дотик, без входу. Ви отримали лист, бо стежите за адресами в підписці «Моя вулиця».</p>')
    return ('<!DOCTYPE html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            f'<title>{_e(tema(l))}</title></head><body style="margin:0;padding:0;background:{K["ground"]}">'
            f'<div style="max-width:600px;margin:0 auto;padding:24px 16px;font-family:{SHRYFT}">{"".join(b)}</div></body></html>')


# ---------------------------------------------------------------- Telegram і застосунок

def telegram_pidpysnyk(l: Lyst) -> str:
    """Повна версія для підписника: коротше за лист, до MAKS_PODII_TELEGRAM подій на адресу."""
    r_ = [tema(l), '']
    if l.tykhyi:
        r_.append(f'Нових рішень судів і звернень до 1551 в радіусі {R_M}{NBSP}м від ваших адрес у даних немає.')
    for r in ([] if l.tykhyi else l.rozdily):
        r_.append(f'{zaholovok_adresy(r.adresa)} (радіус {R_M}{NBSP}м)')
        for p in r.podii[:MAKS_PODII_TELEGRAM]:
            mistse = f', {p["mistse"]}' if p.get('mistse') else ''
            o = opys(p)
            r_.append(f'— {HRUPY[p["hrupa"]]["nazva"]}, {data_slovamy(p.get("data"))}{mistse}. {o or "Опису ще немає."}')
        if len(r.podii) > MAKS_PODII_TELEGRAM:
            r_.append(f'— ще {podii_slovo(len(r.podii) - MAKS_PODII_TELEGRAM)} — у «Стежу».')
        r_.append(ryadok_skarh(r) if r.skarhy else nemaie_skarh(l))
        if r.problema:
            r_.append(ryadok_problemy(r.problema))
        r_.append('')
    r_.append(CHESNO)
    return '\n'.join(r_).strip()


def telegram_bezkoshtovno(l: Lyst) -> str:
    """Безкоштовно (MV-124): одна адреса, лише числа; без місць, описів і посилань на рішення (MV-25, MV-102)."""
    r = l.rozdily[0]
    r_ = [f'Нове біля дому — {r.adresa.adresa}, радіус {R_M}{NBSP}м, {tyzhden(l)}.', '']
    r_.append(ryadok_podii_chyslom(r) if r.podii else 'Нових подій з рішень судів у даних немає.')
    r_.append(ryadok_skarh(r, 2) if r.skarhy else nemaie_skarh(l))
    r_ += ['', f'Що саме й де — у підписці «Моя вулиця»: описи подій, усі ваші адреси, лист раз на місяць '
           f'({T.tsina("pidpyska")}, одна довідка про будинок включена).', '', CHESNO]
    return '\n'.join(r_)


def push(l: Lyst) -> list[dict]:
    """Сповіщення застосунку (docs/ANDROID.md, розд. 6): одне на адресу з новим; без номерів будинків і описів."""
    out = []
    for i, r in enumerate(l.rozdily):
        if not r.nove:
            continue
        chastyny = [x for x in (podii_slovo(len(r.podii)) if r.podii else '',
                                skarh_slovo(sum(r.skarhy.values())) + ' до 1551' if r.skarhy else '') if x]
        out.append({'title': 'Нове біля дому', 'body': f'Біля: {bez_nomera(r.adresa.adresa)} — '
                    + ' і '.join(chastyny) + f' {slova_periodu(l)["za"]}', 'url': f'/stezhu/?a={i}', 'tag': f'nove-{l.do}-{i}'})
    return out


def usi_teksty(l: Lyst, posylannia: dict) -> list[str]:
    """Усе, що може піти людині з цього листа, — для перевірки перед надсиланням."""
    if l.platno:
        return [tema(l), tekst(l, posylannia), html_lysta(l, posylannia), telegram_pidpysnyk(l)] + \
               [p['body'] for p in push(l)]
    return [telegram_bezkoshtovno(l)] + [p['body'] for p in push(l)]
