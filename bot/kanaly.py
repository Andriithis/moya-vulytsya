"""Дописи районних Telegram-каналів (ZAVDANNYA-97, MV-91: окремий канал на кожен з 10 районів Києва).

    # пачка на 14 днів для перегляду людиною (нічого не надсилає):
    python bot/kanaly.py --indeks indeks.json --vid 2026-11-23 --dniv 14 --vykhid pachka.json --perehliad pachka.md
    # надіслати дописи одного дня (на сервері партнера; токен — лише в змінній середовища):
    MV_TELEGRAM_TOKEN=… python bot/kanaly.py --indeks indeks.json --vid 2026-11-23 --dniv 1 \
        --kanaly kanaly.json --nadislaty

Розклад кожного каналу:
  щодня       — «Історія з вулиці»: подія з колоди гри (MV-12) — вулиця без номера будинку (MV-25, MV-60), рік, вид,
                номер рішення, «лише те, що дійшло до суду»; посилання — на сторінку цієї вулиці;
  середа      — «Вгадай, де це було?»: вікторина Telegram (sendPoll) з трьома вулицями району; кнопка — на сторінку
                вулиці-відповіді; цього дня історії немає;
  п'ятниця    — «Цифри тижня»: одна вулиця району — події з рішень і скарги 1551 числом, поруч «зазвичай вулиця району»;
                посилання — на сторінку вулиці; цього дня історії немає.
Кожен допис веде на конкретне місце (docs/KOMPAS.md, розд. 0, 5) з міткою каналу `?dzherelo=tg-<район>`.
Текст історії — чернетка з колоди (короткий опис, вирізаний правилами); перед публікацією його переписує ШІ людською
мовою без нових фактів (MV-21, MV-25), перші 50 читає людина. Поле `chernetka` у пачці — саме про це.
Повторний запуск з тими самими даними й датами дає ту саму пачку.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

TUT = Path(__file__).resolve().parent
KORIN = TUT.parent
sys.path.insert(0, str(TUT))
sys.path.insert(0, str(KORIN / 'brend'))
sys.path.insert(0, str(KORIN / 'video'))

from adresa_pokazu import bez_nomera, chutlyva  # noqa: E402
from perevirka import MV4_KATEGORII, MV4_SLOVA, SLIDY, ZABORONENI  # noqa: E402
from rozmova import ADRESA_SAITU, chyslo, misiats, vidminok  # noqa: E402

DNI_TYZHNIA = ('понеділок', 'вівторок', 'середа', 'четвер', "п'ятниця", 'субота', 'неділя')
DEN_VHADAI = 2
DEN_TSYFR = 4
MIN_PODII_VULYTSI = 3            # «Цифри тижня» — лише вулиці, що є в пошуку Google (як сторінки сайту)
MAKS_ISTORII = 400               # довжина чернетки історії
# Номер будинку в тексті історії: «буд. 5», «будинку 12», «вул. Х, 42» — такий опис не беремо (MV-25, MV-60).
NOMER_U_TEKSTI = re.compile(r'буд\w*\.?\s*№?\s*\d|(вул|просп|бульв|пров|пл)\.?\s+[^,;]{1,50},\s*\d|\bкв\.?\s*\d', re.I)
# Військові справи: місце служби й частина під час війни не показуємо в безкоштовних дописах (не наше правило MV —
# обережність виконавця, питання Андрію в docs/BOT-I-KANALY.md).
VIISKOVI = re.compile(r'військов\w*\s+частин|військовослужбов|мобілізац|в/ч\b|ЗСУ|навідник|взвод|рот[аиі]\s', re.I)
# Категорії, яких немає в іграх і постах (MV-4, MV-69, MV-102): насильство, статеві, щодо дітей.
KATEGORII_NI = MV4_KATEGORII | {'nasylstvo_domashnie', 'statevi_zlochyny'}


def khesh(*chastyny) -> int:
    return int(hashlib.sha1('|'.join(map(str, chastyny)).encode('utf-8')).hexdigest()[:12], 16)


def mitka(rayon_slug: str) -> str:
    return f'tg-{rayon_slug}'


def prydatna(p: dict) -> bool:
    """Чи може подія колоди піти в безкоштовний допис."""
    t = p.get('opys_korotkyi') or ''
    return bool(p.get('vulytsia_slug') and p.get('rayon') and t and p.get('rishennya_nomer')
                and p.get('kategoriia') not in KATEGORII_NI and not MV4_SLOVA.search(t) and not chutlyva(t, p.get('vyd', ''))
                and not ZABORONENI.search(t) and not SLIDY.search(t) and not NOMER_U_TEKSTI.search(t)
                and not VIISKOVI.search(t))


def chernetka(t: str) -> str:
    """Короткий опис колоди → чернетка: «особа» замість імені вже стоїть; обрізаємо до MAKS_ISTORII по реченню."""
    t = re.sub(r'\s+', ' ', t).strip().rstrip('…')
    if len(t) > MAKS_ISTORII:
        t = t[:MAKS_ISTORII].rsplit('. ', 1)[0] + '.'
    return t


class Henerator:
    def __init__(self, indeks: dict, adresa_saitu: str = ADRESA_SAITU):
        self.i = indeks
        self.sait = adresa_saitu.rstrip('/')
        self.rayony = {r['n']: r for r in indeks['rayony']}
        self.vulytsi = {v['s']: v for v in indeks['vulytsi']}
        r0, r1 = indeks.get('roky_podii', [2024, 2026])
        self.roky = f'{r0}–{r1}'
        self.misiatsi = indeks.get('misiatsi_1551') or []
        # скарги 1551 по вулиці сайту — сума будинків вулиці
        self.skarhy_vul = defaultdict(Counter)
        for b in indeks['budynky']:
            if b.get('vs') and b.get('sk'):
                self.skarhy_vul[b['vs']].update(b['sk'])
        self.podii_r = defaultdict(list)
        for p in indeks.get('koloda', []):
            if prydatna(p):
                self.podii_r[p['rayon']].append(p)
        for r in self.podii_r:
            self.podii_r[r].sort(key=lambda p: khesh('istoriia', p['id']))
        self.vulytsi_r = defaultdict(list)
        for v in indeks['vulytsi']:
            if v.get('r'):
                self.vulytsi_r[v['r']].append(v)

    def url(self, shlyakh: str, rayon: str) -> str:
        return f'{self.sait}{shlyakh}?dzherelo={mitka(self.rayony[rayon]["s"])}'

    # ------------------------------------------------------------ дописи

    def istoriia(self, rayon: str, p: dict, den: date) -> dict:
        v = self.vulytsi.get(p['vulytsia_slug'], {})
        nazva = v.get('n') or p.get('vulytsia_nazva') or bez_nomera(p.get('vulytsia', ''))
        tekst = '\n'.join([
            f'Історія з вулиці · {rayon} район', '',
            chernetka(p['opys_korotkyi']), '',
            f'{nazva} · {p.get("rik", "")} · {p.get("vyd", "")}',
            f'Рішення № {p["rishennya_nomer"]} — лише те, що дійшло до суду.'])
        return {'typ': 'istoriia', 'data': den.isoformat(), 'rayon': rayon, 'tekst': tekst, 'chernetka': True,
                'podiia': p['id'], 'vulytsia': p['vulytsia_slug'],
                'knopky': [[{'tekst': f'Що ще було: {nazva}', 'url': self.url(f'/vulytsia/{p["vulytsia_slug"]}/', rayon)}]]}

    def vhadai(self, rayon: str, p: dict, den: date) -> dict | None:
        prav = self.vulytsi.get(p['vulytsia_slug'])
        if not prav:
            return None
        inshi = [v for v in self.vulytsi_r[rayon] if v['s'] != prav['s'] and v['p'] >= MIN_PODII_VULYTSI]
        if len(inshi) < 2:
            return None
        inshi.sort(key=lambda v: khesh('vhadai', p['id'], v['s']))
        varianty = sorted([prav] + inshi[:2], key=lambda v: khesh('poriadok', p['id'], v['s']))
        pytannia = f'Вгадай, де це було? {chernetka(p["opys_korotkyi"])}'
        if len(pytannia) > 300:                        # межа питання вікторини Telegram
            pytannia = pytannia[:297].rsplit(' ', 1)[0] + '…'
        return {'typ': 'vhadai', 'data': den.isoformat(), 'rayon': rayon, 'chernetka': True, 'podiia': p['id'],
                'vulytsia': prav['s'], 'pytannia': pytannia, 'varianty': [v['n'][:100] for v in varianty],
                'pravylna': varianty.index(prav),
                'poiasnennia': f'{prav["n"]}, {p.get("rik", "")}. Рішення № {p["rishennya_nomer"]} — лише те, що дійшло до суду.'[:200],
                'knopky': [[{'tekst': 'Відповідь — уся вулиця', 'url': self.url(f'/vulytsia/{prav["s"]}/', rayon)}]]}

    def tsyfry(self, rayon: str, den: date) -> dict | None:
        vs = [v for v in self.vulytsi_r[rayon] if v['p'] >= MIN_PODII_VULYTSI]
        if not vs:
            return None
        tyzhden = den.isocalendar()
        vs.sort(key=lambda v: khesh('tsyfry', rayon, v['s']))
        v = vs[(tyzhden[0] * 53 + tyzhden[1]) % len(vs)]
        med_p = statistics.median(x['p'] for x in vs)
        sk = self.skarhy_vul.get(v['s'], Counter())
        sk_vs = [sum(self.skarhy_vul.get(x['s'], Counter()).values()) for x in vs]
        med_s = statistics.median(sk_vs)
        period = f'{misiats(self.misiatsi[0])} — {misiats(self.misiatsi[-1])}' if self.misiatsi else '12 місяців'
        ryadky = [f'Цифри тижня · {rayon} район', v['n'], '',
                  f'Подій з рішень судів за {self.roky}: {chyslo(v["p"])} (зазвичай вулиця району — {chyslo(med_p)})']
        if sk:
            ryadky.append(f'Скарг до 1551 за {period}: {chyslo(sum(sk.values()))} '
                          f'(зазвичай вулиця району — {chyslo(med_s)})')
            ryadky.append('Найчастіше скаржились: ' + ', '.join(f'{h} ({chyslo(n)})' for h, n in sk.most_common(2)))
        ryadky += ['', 'Число — скільки записів у даних, а не оцінка вулиці. Скарга — звернення, не перевірений факт; '
                   'подія — лише те, що дійшло до суду.']
        return {'typ': 'tsyfry', 'data': den.isoformat(), 'rayon': rayon, 'tekst': '\n'.join(ryadky), 'chernetka': False,
                'vulytsia': v['s'], 'knopky': [[{'tekst': f'{v["n"]} — уся вулиця', 'url': self.url(f'/vulytsia/{v["s"]}/', rayon)}]]}

    # ------------------------------------------------------------ пачка

    def pachka(self, vid: date, dniv: int, vzhe: set | None = None) -> list[dict]:
        """Дописи на dniv днів від vid для всіх районів. vzhe — id подій, що вже виходили (не повторювати)."""
        vzhe = set(vzhe or ())
        dopysy = []
        for rayon in sorted(self.rayony):
            cherha = [p for p in self.podii_r.get(rayon, []) if p['id'] not in vzhe]
            for d in range(dniv):
                den = vid + timedelta(days=d)
                if den.weekday() == DEN_TSYFR:
                    t = self.tsyfry(rayon, den)
                    if t:
                        dopysy.append(t)
                        continue
                if not cherha:
                    continue
                p = cherha.pop(0)
                if den.weekday() == DEN_VHADAI:
                    t = self.vhadai(rayon, p, den)
                    if t:
                        dopysy.append(t)
                        continue
                dopysy.append(self.istoriia(rayon, p, den))
        dopysy.sort(key=lambda x: (x['data'], x['rayon']))
        return dopysy


def perevirka(dopys: dict) -> list[str]:
    """Те саме, що й для роликів (video/perevirka.py) + посилання лише на місце."""
    zh = []
    tekst = ' '.join([dopys.get('tekst', ''), dopys.get('pytannia', ''), ' '.join(dopys.get('varianty', [])),
                      dopys.get('poiasnennia', '')])
    if ZABORONENI.search(tekst):
        zh.append('заборонене слово')
    if SLIDY.search(tekst):
        zh.append('сліди імен чи квартир')
    if NOMER_U_TEKSTI.search(tekst):
        zh.append('номер будинку')
    if MV4_SLOVA.search(tekst):
        zh.append('чутлива категорія')
    if VIISKOVI.search(tekst):
        zh.append('військова справа')
    urly = [k['url'] for ryad in dopys.get('knopky', []) for k in ryad if k.get('url')]
    if not urly or not all(re.search(r'/(vulytsia|budynok|rayon)/[^/?]+/', u) for u in urly):
        zh.append('посилання не на конкретне місце')
    if dopys['typ'] in ('istoriia', 'vhadai') and 'лише те, що дійшло до суду' not in tekst:
        zh.append('немає «лише те, що дійшло до суду»')
    return zh


def perehliad_md(dopysy: list[dict]) -> str:
    """Пачка для людини: читає, викреслює, решту бот публікує."""
    r = ['# Пачка дописів районних каналів — на перегляд', '',
         'Чернетки історій переписує ШІ (MV-21, MV-25) і читає людина; викреслене — не публікується.', '']
    for d in dopysy:
        r.append(f'## {d["data"]} ({DNI_TYZHNIA[date.fromisoformat(d["data"]).weekday()]}) · {d["rayon"]} · {d["typ"]}')
        if d['typ'] == 'vhadai':
            r.append(f'Вікторина: {d["pytannia"]}')
            r += [f'- {"✔ " if i == d["pravylna"] else ""}{v}' for i, v in enumerate(d['varianty'])]
            r.append(f'Пояснення: {d["poiasnennia"]}')
        else:
            r.append('```\n' + d['tekst'] + '\n```')
        for ryad in d['knopky']:
            for k in ryad:
                r.append(f'Кнопка: [{k["tekst"]}]({k["url"]})')
        zh = perevirka(d)
        if zh:
            r.append('**Перевірка: ' + '; '.join(zh) + '**')
        r.append('')
    return '\n'.join(r)


def nadislaty(dopysy: list[dict], kanaly: dict, token: str) -> list[str]:
    from rozmova import Knopka, Vidpovid
    from telegram import Telegram, rozmitka
    tg = Telegram(token)
    zvit = []
    for d in dopysy:
        chat = kanaly.get(d['rayon'])
        if not chat:
            zvit.append(f'{d["rayon"]}: немає каналу')
            continue
        zh = perevirka(d)
        if zh:
            zvit.append(f'{d["rayon"]} {d["typ"]}: не надіслано — {"; ".join(zh)}')
            continue
        v = Vidpovid('', [[Knopka(k['tekst'], url=k['url']) for k in ryad] for ryad in d['knopky']])
        if d['typ'] == 'vhadai':
            r = tg.vyklyk('sendPoll', chat_id=chat, question=d['pytannia'], options=[{'text': x} for x in d['varianty']],
                          type='quiz', correct_option_id=d['pravylna'], explanation=d['poiasnennia'],
                          is_anonymous=True, reply_markup=rozmitka(v))
        else:
            r = tg.vyklyk('sendMessage', chat_id=chat, text=d['tekst'], disable_web_page_preview=True,
                          reply_markup=rozmitka(v))
        zvit.append(f'{d["rayon"]} {d["typ"]}: {"так" if r.get("ok") else r.get("description", "помилка")}')
    return zvit


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Дописи районних Telegram-каналів.')
    p.add_argument('--indeks', type=Path, required=True)
    p.add_argument('--vid', default=date.today().isoformat(), help='перший день (РРРР-ММ-ДД)')
    p.add_argument('--dniv', type=int, default=14)
    p.add_argument('--vzhe', type=Path, help='попередні пачки (JSON) — події з них не повторювати')
    p.add_argument('--vykhid', type=Path)
    p.add_argument('--perehliad', type=Path, help='Markdown для перегляду людиною')
    p.add_argument('--adresa-saitu', default=ADRESA_SAITU)
    p.add_argument('--kanaly', type=Path, help='JSON: район → @канал або числовий id (не секрет)')
    p.add_argument('--nadislaty', action='store_true')
    a = p.parse_args(argv)
    indeks = json.loads(a.indeks.read_text(encoding='utf-8'))
    vzhe = set()
    if a.vzhe and a.vzhe.exists():
        vzhe = {d.get('podiia') for d in json.loads(a.vzhe.read_text(encoding='utf-8')) if d.get('podiia')}
    h = Henerator(indeks, a.adresa_saitu)
    dopysy = h.pachka(date.fromisoformat(a.vid), a.dniv, vzhe)
    if a.vykhid:
        a.vykhid.write_text(json.dumps(dopysy, ensure_ascii=False, indent=1), encoding='utf-8')
    if a.perehliad:
        a.perehliad.write_text(perehliad_md(dopysy), encoding='utf-8')
    typy = Counter(d['typ'] for d in dopysy)
    print(f'дописів: {len(dopysy)} ({", ".join(f"{k} — {n}" for k, n in sorted(typy.items()))}); '
          f'із зауваженнями перевірки: {sum(1 for d in dopysy if perevirka(d))}')
    if a.nadislaty:
        if not a.kanaly:
            raise SystemExit('Потрібен --kanaly (район → канал).')
        for r in nadislaty(dopysy, json.loads(a.kanaly.read_text(encoding='utf-8')), os.environ.get('MV_TELEGRAM_TOKEN', '')):
            print(r)
    return 0


if __name__ == '__main__':
    sys.exit(main())
