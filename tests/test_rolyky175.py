"""Виправлення роликів за критиком ZVIT-170 (ZAVDANNYA-175): правдивий гачок, заклик на сторінку, що існує, одне «усього
подій», рух у перші 1,5 с, читабельний логотип, видима точка, позначка голосу, записи сайту 1080×1920.

Запуск: python -m unittest tests/test_rolyky175.py
База випуску й браузер не потрібні: перевіряємо правила, що вирішують, чи можна ролик зібрати.
"""
from __future__ import annotations

import copy
import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
VAU = KORIN / 'video' / 'vau'


def modul(imia, fail):
    spec = importlib.util.spec_from_file_location(imia, VAU / fail)
    m = importlib.util.module_from_spec(spec)
    sys.modules[imia] = m
    spec.loader.exec_module(m)
    return m


P = modul('vau_perevirka175', 'perevirka.py')
sys.path.insert(0, str(VAU))
HS = modul('vau_holos_servis175', 'holos_servis.py')

META = {'nazva': 'Проба', 'hachok': 'гачок', 'meta': 'перевірка', 'kudy': '/vulytsia/proba/', 'kintsivka': 'посилання в профілі',
        'pravyla': 175, 'shar': 'tochky'}
CHYSTYI = {
    'id': 'proba175', 'tryvalist': 6, 'tema': 'temna',
    'kamera': [{'t': 0, 'c': [30.5234, 50.4501], 'z': 11}, {'t': 1.2, 'c': [30.5234, 50.4501], 'z': 11.4},
               {'t': 6, 'c': [30.5234, 50.4501], 'z': 11.6}],
    'tochky': [{'dani': {'x': [3052340], 'y': [5045010], 'g': [0], 't': [0.0]}}],
    'tekst': [{'t0': 0, 't1': 2, 'styl': 'hook', 'tekst': 'Кожна точка — *подія*'},
              {'t0': 1.8, 't1': 4, 'styl': 'lich', 'do': 10, 'pidpys': '{f} у даних', 'formy': ['подія', 'події', 'подій']},
              {'t0': 3.8, 't1': 5, 'styl': 'velykyi', 'tekst': 'Одне місто'},
              {'t0': 5, 't1': 6, 'styl': 'baner', 'zag': 'Знайди вулицю', 'knopka': 'посилання в профілі'}],
}


def z(f=None, meta=None):
    S = copy.deepcopy(CHYSTYI)
    m = dict(META, **(meta or {}))
    if f:
        f(S)
    return P.pereviryty(S, m)


class Bazovyi(unittest.TestCase):
    def test_chystyi_prokhodyt(self):
        self.assertEqual(z(), [])


class PoznakaHolosu(unittest.TestCase):
    """MV-171: голос Андрія, перетворений програмою, — «Голос змінено програмою»; Piper — «Голос згенеровано»."""

    def setUp(self):
        self.staryi = os.environ.get('MV_HOLOS')

    def tearDown(self):
        if self.staryi is None:
            os.environ.pop('MV_HOLOS', None)
        else:
            os.environ['MV_HOLOS'] = self.staryi

    def test_za_servisom(self):
        self.assertEqual(HS.poznaka('teka'), 'Голос змінено програмою')
        self.assertEqual(HS.poznaka('piper'), 'Голос згенеровано')
        os.environ['MV_HOLOS'] = 'teka'
        self.assertEqual(HS.poznaka(), 'Голос змінено програмою')
        os.environ.pop('MV_HOLOS')
        self.assertEqual(HS.poznaka(), 'Голос згенеровано')

    def test_perevirka(self):
        def holos(p):
            return lambda s: (s.update(zvuk={'holos': [{'t': 0.5, 'tekst': 'Кожна точка — подія.'}]}, holos_poznaka=p))
        self.assertEqual(z(holos('Голос змінено програмою')), [])
        self.assertEqual(z(holos('Голос згенеровано')), [])
        self.assertTrue(any('MV-171' in x for x in z(holos('Голос ШІ'))))
        self.assertTrue(any('позначки' in x for x in z(holos(None))))

    def test_ne_zostalos_ruchnoi_poznaky(self):
        for f in ('stsenarii.py', 'zapys_saitu.py', 'zapys155.py'):
            self.assertNotIn("'Голос згенеровано'", (VAU / f).read_text(encoding='utf-8'), f)


if __name__ == '__main__':
    unittest.main()
