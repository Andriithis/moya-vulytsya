"""Пошук будинку за тим, що написала людина (ZAVDANNYA-97).

«Хрещатик 22», «вул. Хрещатик, 22», «просп. Перемоги 10а», «Лесі Українки 7-б», «Бандери 12 к2» — у покажчику бота
(`bot/indeks.py`). Без мережі й без зовнішніх геокодерів: шукаємо лише серед будинків, що мають сторінку на сайті.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# Слова типу вулиці — пропускаємо, людина може написати будь-яке або жодного.
TYPY = {'вул', 'вулиця', 'вулиці', 'просп', 'проспект', 'пр', 'бульв', 'бульвар', 'б-р', 'пров', 'провулок', 'пл', 'площа',
        'шосе', 'узвіз', 'наб', 'набережна', 'майдан', 'проїзд', 'алея', 'дорога', 'тупик', 'лінія', 'спуск', 'буд',
        'будинок', 'м', 'київ', 'києві', 'місто'}
LAT_KYR = str.maketrans({'a': 'а', 'b': 'б', 'c': 'с', 'e': 'е', 'i': 'і', 'k': 'к', 'o': 'о', 'p': 'р', 'x': 'х', 'v': 'в'})
# «22», «10а», «7-б», «12/4», «13-15», «77/13-А», «37 к6», «5 корп. 2»
NOMER = re.compile(r'(\d+(?:\s*[-/]\s*\d+)*(?:\s*-?\s*[а-яіїєґa-z](?![а-яіїєґa-zʼ]))?'
                   r'(?:\s*(?:к|корп|корпус)\.?\s*\d+)?)\s*$')


def norm_slova(tekst: str) -> list[str]:
    t = unicodedata.normalize('NFC', tekst or '').lower()
    t = re.sub(r"[ʼ’'`‘´«»\"“”]", '', t).replace('ґ', 'г')
    t = re.sub(r'[.,;:()\-–—]', ' ', t)
    return [s for s in t.split() if s and s not in TYPY]


def norm_nomer(n: str) -> str:
    """«7-Б» → «7б», «12/4» → «12/4», «37 к6» → «37к6», латинська «a» → кирилична «а»."""
    t = unicodedata.normalize('NFC', n or '').lower().translate(LAT_KYR)
    t = re.sub(r'корпус|корп\.?', 'к', t)
    return re.sub(r'[\s\-–.]', '', t)


@dataclass
class Zapyt:
    vulytsia: list[str]
    nomer: str | None


def rozibraty(tekst: str) -> Zapyt | None:
    """Текст людини → слова вулиці й номер будинку (або None, якщо номера немає)."""
    t = unicodedata.normalize('NFC', tekst or '').strip().lower()
    t = re.sub(r'(?<![а-яіїєґ])(буд\.|буд(?![а-яіїєґ])|будинок(?![а-яіїєґ]))\s*', ' ', t)
    t = re.sub(r'[,;]', ' ', t).strip()
    m = NOMER.search(t)
    nomer = None
    if m and m.start() > 0:
        nomer = m.group(1)
        t = t[:m.start()]
    slova = norm_slova(t)
    if not slova:
        return None
    return Zapyt(slova, norm_nomer(nomer) if nomer else None)


@dataclass
class Poshuk:
    budynky: list = field(default_factory=list)       # знайдені будинки (записи покажчика)
    vulytsi: list = field(default_factory=list)       # знайдені вулиці (назва, slug або None)
    zapyt: Zapyt | None = None


class Pokazhchyk:
    def __init__(self, indeks: dict):
        self.indeks = indeks
        self.za_vulytseyu: dict[str, list] = {}
        self.slova_vulytsi: dict[str, list[str]] = {}
        self.slug_vulytsi: dict[str, str | None] = {}
        for b in indeks['budynky']:
            self.za_vulytseyu.setdefault(b['v'], []).append(b)
            self.slova_vulytsi.setdefault(b['v'], norm_slova(b['v']))
            if b.get('vs'):
                self.slug_vulytsi[b['v']] = b['vs']
        self.vulytsi_saitu = {v['s']: v for v in indeks.get('vulytsi', [])}

    @staticmethod
    def _pasuie(zapyt: list[str], nazva: list[str]) -> int:
        """0 — не пасує; більше — краще. Кожне слово запиту — початок якогось слова назви («бандери» → «степана бандери»)."""
        if not all(any(n.startswith(z) for n in nazva) for z in zapyt):
            return 0
        tochni = sum(1 for z in zapyt if z in nazva)
        return 10 * tochni + len(zapyt) - len(nazva)

    def znaity(self, tekst: str) -> Poshuk:
        z = rozibraty(tekst)
        if z is None:
            return Poshuk()
        ocinky = [(self._pasuie(z.vulytsia, sl), v) for v, sl in self.slova_vulytsi.items()]
        ocinky = [(o, v) for o, v in ocinky if o]
        if not ocinky:
            return Poshuk(zapyt=z)
        naikrashcha = max(o for o, _ in ocinky)
        vulytsi = sorted(v for o, v in ocinky if o == naikrashcha)
        rez = Poshuk(vulytsi=[(v, self.slug_vulytsi.get(v)) for v in vulytsi], zapyt=z)
        if z.nomer:
            for v in vulytsi:
                for b in self.za_vulytseyu[v]:
                    if norm_nomer(b['n']) == z.nomer:
                        rez.budynky.append(b)
        return rez
