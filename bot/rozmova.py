"""Розмова бота «Мій будинок» (ZAVDANNYA-97) — без Telegram: текст людини → відповідь з кнопками.

Три сценарії на вибір Андрію (`docs/BOT-I-KANALY.md`):
  a — «Одна відповідь»: адреса → одна картка з числами, сторінкою будинку, довідкою 199 і «Стежити» (порада);
  b — «Кроками»: адреса → «що показати?» → скарги / події / сусіди окремими повідомленнями, наприкінці — ті самі кнопки;
  v — «Біля дому»: адреса → спершу що довкола (300 м), головна кнопка — «Стежити» (лінія «Мій район»), потім будинок.

Правила (AGENTS.md розд. 4, 8; docs/KOMPAS.md): лише числа, як на сторінці будинку (MV-99, MV-100, MV-102); число — з
порівнянням «тут · у сусідів»; скарга — звернення, не перевірений факт; подія — випадок із рішення суду, лише те, що
дійшло до суду; без «небезпечно», рейтингів, причин і прогнозів; без емодзі; ціни — лише з `site/tsiny.py`.
"""
from __future__ import annotations

import hashlib
import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tsiny as T  # noqa: E402
from adresa import Pokazhchyk  # noqa: E402

ADRESA_SAITU = 'https://moya-vulytsya.pages.dev'     # як у збирача сайту; справжній домен — на партнера
DZHERELO = 'bot'                                      # мітка каналу для чотирьох чисел (MV-5)
SCENARII = ('a', 'b', 'v')
NBSP = ' '
MISIATSI_NAZYV = ('січень', 'лютий', 'березень', 'квітень', 'травень', 'червень', 'липень', 'серпень', 'вересень',
                  'жовтень', 'листопад', 'грудень')

HASLO = 'Що болить вашому будинку'
OPYS = 'Скарги мешканців і події з рішень судів — по кожному будинку.'
CHESNO = ('Скарга — звернення мешканця до 1551, не перевірений факт. Подія — випадок із рішення суду: '
          'лише те, що дійшло до суду.')
ZBERIHAIEMO = ('Що бот зберігає: лише адресу, за якою ви стежите, і ваш номер у Telegram (без імені й телефону). '
               'Тексти повідомлень не записуємо. «Не стежити» або /stop — і запис видаляється одразу.')


def chyslo(n) -> str:
    if isinstance(n, float) and n != int(n):
        return f'{n:.1f}'.replace('.', ',')
    return f'{int(n):,}'.replace(',', NBSP)


def vidminok(n: int, formy: tuple[str, str, str]) -> str:
    m10, m100 = n % 10, n % 100
    if m10 == 1 and m100 != 11:
        return formy[0]
    if 2 <= m10 <= 4 and not 12 <= m100 <= 14:
        return formy[1]
    return formy[2]


def skarg(n: int) -> str:
    return f'{chyslo(n)} {vidminok(n, ("звернення", "звернення", "звернень"))}'


def podii(n: int) -> str:
    return f'{chyslo(n)} {vidminok(n, ("подія", "події", "подій"))}'


def misiats(ym: str) -> str:
    r, m = ym.split('-')
    return f'{MISIATSI_NAZYV[int(m) - 1]} {r}'


def kod(url: str) -> str:
    """Коротке позначення будинку для кнопки (у Telegram дані кнопки — до 64 байт)."""
    return hashlib.sha1(url.encode('utf-8')).hexdigest()[:10]


@dataclass
class Knopka:
    tekst: str
    url: str | None = None
    dani: str | None = None          # натискання повертається в бот (callback)


@dataclass
class Vidpovid:
    tekst: str
    knopky: list[list[Knopka]] = field(default_factory=list)


class Bot:
    """Уся логіка розмови; сховище стеження — `stezhennia.Skhovyshche` (або будь-що з тими самими методами)."""

    def __init__(self, indeks: dict, skhovyshche=None, scenarii: str = 'a', adresa_saitu: str = ADRESA_SAITU,
                 zapytiv_na_hodynu: int = 30):
        if scenarii not in SCENARII:
            raise ValueError(f'сценарій {scenarii!r}: лише {", ".join(SCENARII)}')
        self.indeks = indeks
        self.p = Pokazhchyk(indeks)
        self.skh = skhovyshche
        self.scenarii = scenarii
        self.sait = adresa_saitu.rstrip('/')
        self.za_kodom = {kod(b['u']): b for b in indeks['budynky']}
        self.za_url = {b['u']: b for b in indeks['budynky']}
        self.misiatsi = indeks.get('misiatsi_1551') or []
        r0, r1 = indeks.get('roky_podii', [2024, 2026])
        self.roky = f'{r0}–{r1}'
        self.hrupy = indeks.get('hrupy', {})
        self.r_m = indeks.get('r_susidy_m', 300)
        self.zapytiv_na_hodynu = zapytiv_na_hodynu
        self._zapyty: dict[int, list[float]] = {}
        # сітка для «біля дому»: клітинка ≈ 0,005° (≈ 350–550 м)
        self._sitka: dict[tuple, list] = {}
        for b in indeks['budynky']:
            self._sitka.setdefault((int(b['la'] / 0.005), int(b['lo'] / 0.005)), []).append(b)

    # ------------------------------------------------------------ посилання

    def url(self, shlyakh: str) -> str:
        z = '&' if '?' in shlyakh else '?'
        return f'{self.sait}{shlyakh}{z}dzherelo={DZHERELO}'

    def url_oplaty(self, tovar: str, b: dict | None = None) -> str:
        q = f'&budynok={quote(b["u"])}' if b else ''
        return f'{self.sait}/oplata/?tovar={tovar}{q}&dzherelo={DZHERELO}'

    def knopky_budynku(self, b: dict, stezhyty_pershym: bool = False) -> list[list[Knopka]]:
        storinka = [Knopka('Сторінка будинку', url=self.url(b['u']))]
        dovidka = [Knopka(f'Довідка про будинок — {T.tsina("dovidka")}', url=self.url_oplaty('dovidka', b))]
        stezh = [Knopka('Стежити: нове біля дому щотижня', dani=f's:{kod(b["u"])}')]
        return [stezh, storinka, dovidka] if stezhyty_pershym else [storinka, dovidka, stezh]

    # ------------------------------------------------------------ числа

    def navkolo(self, b: dict) -> dict:
        """Будинки в радіусі r_m від b (сам будинок теж): скільки звернень за останній місяць і подій за відкриті роки."""
        i, j = int(b['la'] / 0.005), int(b['lo'] / 0.005)
        m_lat = 111_000.0
        m_lon = 111_000.0 * math.cos(math.radians(b['la']))
        bs = []
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                for x in self._sitka.get((i + di, j + dj), []):
                    if math.hypot((x['la'] - b['la']) * m_lat, (x['lo'] - b['lo']) * m_lon) <= self.r_m:
                        bs.append(x)
        return {'budynkiv': len(bs), 'ostannii': sum(x.get('o', 0) for x in bs),
                'podii': sum(sum(x.get('ph', {}).values()) for x in bs),
                'podii_vsi': sum(x.get('pv', 0) for x in bs)}

    def ryadok_skarh(self, b: dict) -> list[str]:
        sk = b.get('sk', {})
        period = f'{misiats(self.misiatsi[0])} — {misiats(self.misiatsi[-1])}' if self.misiatsi else '12 місяців'
        if not sk:
            return [f'Скарг до 1551 за {period}: 0.']
        r = [f'Скарг до 1551 за {period}: {chyslo(sum(sk.values()))}.']
        su = b.get('su') or {}
        for h, n in list(sk.items())[:2]:
            t = f'— {h}: {chyslo(n)}'
            if h in su:
                t += f' (у сусідніх будинках зазвичай {chyslo(su[h])})'
            r.append(t)
        return r

    def ryadok_podii(self, b: dict) -> str:
        ph = b.get('ph', {})
        if not ph:
            return f'Подій з рішень судів за {self.roky}: 0.'
        chastyny = ', '.join(f'{self.hrupy.get(k, k) if k == "dtp" else self.hrupy.get(k, k).lower()} — {chyslo(n)}'
                             for k, n in sorted(ph.items(), key=lambda x: (-x[1], x[0])))
        return f'Подій з рішень судів за {self.roky}: {chyslo(sum(ph.values()))} ({chastyny}).'

    def zaholovok(self, b: dict) -> str:
        return b['a'] + (f'\n{b["r"]} район' if b.get('r') else '')

    # ------------------------------------------------------------ сценарії

    def kartka(self, b: dict) -> Vidpovid:
        """Сценарій a — одна картка."""
        t = '\n'.join([self.zaholovok(b), '', *self.ryadok_skarh(b), self.ryadok_podii(b), '', CHESNO])
        return Vidpovid(t, self.knopky_budynku(b))

    def kroky_start(self, b: dict) -> Vidpovid:
        """Сценарій b — перший крок."""
        sk, ph = sum(b.get('sk', {}).values()), sum(b.get('ph', {}).values())
        k = kod(b['u'])
        return Vidpovid(f'Знайшов: {self.zaholovok(b)}\n\nЩо показати?', [
            [Knopka(f'Скарги мешканців ({chyslo(sk)})', dani=f'k:{k}')],
            [Knopka(f'Події з рішень судів ({chyslo(ph)})', dani=f'p:{k}')],
            [Knopka('Що біля дому', dani=f'n:{k}')]])

    def kroky_krok(self, chto: str, b: dict) -> Vidpovid:
        k = kod(b['u'])
        if chto == 'k':
            t = '\n'.join([b['a'], '', *self.ryadok_skarh(b), '',
                           'Скарга — звернення мешканця до 1551, не перевірений факт. Тексти звернень і статуси — у довідці.'])
            dali = [Knopka('Події з рішень судів', dani=f'p:{k}'), Knopka('Що біля дому', dani=f'n:{k}')]
        elif chto == 'p':
            t = '\n'.join([b['a'], '', self.ryadok_podii(b), '',
                           'Подія — випадок із рішення суду: лише те, що дійшло до суду. Описи — у довідці.'])
            dali = [Knopka('Скарги мешканців', dani=f'k:{k}'), Knopka('Що біля дому', dani=f'n:{k}')]
        else:
            t = self.tekst_navkolo(b)
            dali = [Knopka('Скарги мешканців', dani=f'k:{k}'), Knopka('Події з рішень судів', dani=f'p:{k}')]
        return Vidpovid(t, [dali] + self.knopky_budynku(b))

    def tekst_navkolo(self, b: dict) -> str:
        n = self.navkolo(b)
        ost = misiats(self.misiatsi[-1]) if self.misiatsi else 'останній місяць'
        return '\n'.join([f'Біля дому: {b["a"]}', f'Радіус {self.r_m}{NBSP}м — {chyslo(n["budynkiv"])} '
                          f'{vidminok(n["budynkiv"], ("будинок", "будинки", "будинків"))} у даних.', '',
                          f'Звернень до 1551 за {ost}: {chyslo(n["ostannii"])}.',
                          f'Подій з рішень судів за {self.roky}: {chyslo(n["podii"])}.', '',
                          'Що саме й де — у підписці. Стежте — і щотижня бот надішле, що нового, числом.'])

    def bilia_domu(self, b: dict) -> Vidpovid:
        """Сценарій v — спершу довкола, головна кнопка — «Стежити»."""
        sk, ph = sum(b.get('sk', {}).values()), sum(b.get('ph', {}).values())
        t = '\n'.join([self.tekst_navkolo(b), '',
                       f'Сам будинок: {skarg(sk)} до 1551 за 12 місяців, {podii(ph)} з рішень судів за {self.roky}.',
                       '', CHESNO])
        return Vidpovid(t, self.knopky_budynku(b, stezhyty_pershym=True))

    def pro_budynok(self, b: dict) -> Vidpovid:
        return {'a': self.kartka, 'b': self.kroky_start, 'v': self.bilia_domu}[self.scenarii](b)

    # ------------------------------------------------------------ вхід

    def zabahato(self, chat_id: int, teper: float) -> bool:
        """Не більше zapytiv_na_hodynu адрес на годину з одного чату — бот не має ставати способом вивантажити всі будинки."""
        z = [t for t in self._zapyty.get(chat_id, []) if teper - t < 3600]
        z.append(teper)
        self._zapyty[chat_id] = z
        return len(z) > self.zapytiv_na_hodynu

    def povidomlennia(self, chat_id: int, tekst: str, teper: float = 0.0) -> Vidpovid:
        t = (tekst or '').strip()
        komanda = t.split()[0].split('@')[0].lower() if t.startswith('/') else ''
        if komanda in ('/start', '/dopomoha', '/help'):
            return self.pryvitannia()
        if komanda == '/stop':
            return self.ne_stezhyty(chat_id)
        if komanda in ('/dani', '/privacy'):
            return Vidpovid(ZBERIHAIEMO + f'\n\nПолітика конфіденційності: {self.url("/zahlushka/polityka.html")}')
        if komanda:
            return Vidpovid('Не знаю такої команди. Напишіть адресу в Києві — наприклад, «Хрещатик 22».')
        if self.zabahato(chat_id, teper):
            return Vidpovid('Забагато адрес за годину. Спробуйте трохи згодом — або подивіться будинки на сайті.',
                            [[Knopka('Сайт «Моя вулиця»', url=self.url('/'))]])
        return self.adresa(t)

    def pryvitannia(self) -> Vidpovid:
        return Vidpovid(f'Мій будинок. {HASLO}.\n{OPYS}\n\n'
                        'Напишіть адресу в Києві — наприклад, «Хрещатик 22» або «просп. Перемоги 10а». Відповім, скільки '
                        'скарг до 1551 і подій з рішень судів має будинок, і порівняю із сусідніми.\n\n' + CHESNO)

    def adresa(self, tekst: str) -> Vidpovid:
        r = self.p.znaity(tekst)
        if r.budynky:
            if len(r.budynky) == 1:
                return self.pro_budynok(r.budynky[0])
            return Vidpovid('Таких адрес кілька — оберіть:',
                            [[Knopka(b['a'] + (f' ({b["r"]})' if b.get('r') else ''), dani=f'b:{kod(b["u"])}')]
                             for b in r.budynky[:6]])
        if not r.vulytsi:
            return Vidpovid('Не впізнав адресу. Напишіть вулицю й номер будинку, наприклад «Хрещатик 22». '
                            'Поки що бот знає лише Київ.')
        knopky = [[Knopka(f'{v} — уся вулиця', url=self.url(f'/vulytsia/{s}/'))] for v, s in r.vulytsi[:3] if s]
        if len(r.vulytsi) > 3:
            knopky.append([Knopka('Покажчик вулиць', url=self.url('/vulytsi/'))])
        if r.zapyt and r.zapyt.nomer:
            vul = f' ({r.vulytsi[0][0]})' if len(r.vulytsi) == 1 else ''
            return Vidpovid(f'Будинку {r.zapyt.nomer}{vul} в даних немає: за 12 місяців до 1551 щодо нього не '
                            'зверталися, і подій з рішень судів з цією адресою немає. Або номер записано інакше — '
                            'перевірте написання (наприклад, «10а», «12/4», «37 к6»).', knopky)
        prykl = ' '.join(w for w in r.vulytsi[0][0].split() if w not in ('вулиця', 'проспект', 'бульвар', 'провулок', 'площа'))
        return Vidpovid(f'Напишіть ще номер будинку — наприклад, «{prykl} 10».', knopky)

    # ------------------------------------------------------------ кнопки

    def natysnuto(self, chat_id: int, dani: str, teper_data: str = '') -> Vidpovid:
        dia, _, k = (dani or '').partition(':')
        b = self.za_kodom.get(k)
        if dia == 'x':
            return self.ne_stezhyty(chat_id)
        if b is None:
            return Vidpovid('Цієї адреси вже немає в даних. Напишіть адресу ще раз.')
        if dia == 'b':
            return self.pro_budynok(b)
        if dia in ('k', 'p', 'n'):
            return self.kroky_krok(dia, b)
        if dia == 's':
            return self.stezhyty(chat_id, b, teper_data)
        return Vidpovid('Не зрозумів кнопку. Напишіть адресу ще раз.')

    def stezhyty(self, chat_id: int, b: dict, teper_data: str) -> Vidpovid:
        if self.skh is None:
            return Vidpovid('Стеження зараз не працює.')
        n = self.navkolo(b)
        self.skh.stezhyty(chat_id, b['u'], teper_data, self.indeks.get('versiia', ''),
                          self.misiatsi[-1] if self.misiatsi else '', n['podii_vsi'])
        return Vidpovid(f'Стежу: {b["a"]}.\n\nЩотижня, коли в даних з’явиться нове в радіусі {self.r_m}{NBSP}м, надішлю '
                        'числом: скільки звернень до 1551 і нових подій з рішень судів. Що саме й де — у підписці '
                        f'({T.tsina("pidpyska")}, з однією довідкою про будинок).\n\n'
                        'Безкоштовно — одна адреса; нова адреса замінює попередню.\n' + ZBERIHAIEMO,
                        [[Knopka('Не стежити', dani='x:')]])

    def ne_stezhyty(self, chat_id: int) -> Vidpovid:
        if self.skh is not None:
            self.skh.vydalyty(chat_id)
        return Vidpovid('Не стежу. Ваш запис видалено. Щоб почати знову — напишіть адресу.')

    # ------------------------------------------------------------ щотижня

    def nove(self, zapys: dict) -> Vidpovid | None:
        """Щотижневе «нове біля дому» для одного запису стеження. None — нового немає, нічого не надсилаємо."""
        b = self.za_url.get(zapys['url'])
        if b is None:
            return None
        n = self.navkolo(b)
        ost = self.misiatsi[-1] if self.misiatsi else ''
        novyi_misiats = bool(ost) and ost != zapys.get('misiats_1551')
        novi_podii = max(0, n['podii_vsi'] - (zapys.get('podii_vsi') or 0))
        if not novyi_misiats and not novi_podii:
            return None
        ryadky = [f'Нове біля дому — {b["a"]}, радіус {self.r_m}{NBSP}м.', '']
        if novyi_misiats:
            ryadky.append(f'Звернень до 1551 за {misiats(ost)}: {chyslo(n["ostannii"])}.')
        if novi_podii:
            ryadky.append(f'Нових подій з рішень судів у даних: {chyslo(novi_podii)}.')
        ryadky += ['', 'Що саме й де — у підписці «Моя вулиця»: карта з адресами й сповіщеннями '
                   f'({T.tsina("pidpyska")}, одна довідка про будинок включена).']
        return Vidpovid('\n'.join(ryadky), [
            [Knopka(f'Підписка — {T.tsina("pidpyska")}', url=self.url_oplaty('pidpyska', b))],
            [Knopka('Сторінка будинку', url=self.url(b['u']))],
            [Knopka('Не стежити', dani='x:')]])


def bez_zaboronenykh(tekst: str) -> bool:
    """Перевірка тексту відповіді на слова, яких у нас немає (docs/KOMPAS.md, розд. 6)."""
    return not re.search(r'небезпечн|безпечн|рейтинг|найгірш|страшн', tekst, re.I)
