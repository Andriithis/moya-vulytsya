"""Перевірки рушія роликів (ZAVDANNYA-11): сценарії, перевірка тексту, файл сот.

Запуск: python -m unittest tests/test_video.py
Рендер у браузері тут не запускається (він довгий) — див. video/rendery.py і ZVIT-11.md.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'video'))

import perevirka  # noqa: E402

STSENARII = sorted((KORIN / 'video' / 'stsenarii').glob('*.json'))


def zavantazhyty(f):
    return json.loads(f.read_text(encoding='utf-8'))


class Stsenarii(unittest.TestCase):
    def test_try_shablony_i_vsi_proxodiat(self):
        shablony = set()
        for f in STSENARII:
            S = zavantazhyty(f)
            shablony.add(S['shablon'])
            self.assertEqual(perevirka.pereviryty(S, f.name), [], f.name)
        self.assertEqual(shablony, {'tur', 'vhadai', 'tsyfry'})

    def test_tryvalist_20_35(self):
        for f in STSENARII:
            t = perevirka.tryvalist(zavantazhyty(f))
            self.assertTrue(20 <= t <= 35, f'{f.name}: {t}')


class Perevirka(unittest.TestCase):
    def setUp(self):
        self.S = zavantazhyty(KORIN / 'video' / 'stsenarii' / 'tur-pechersk.json')

    def zauv(self, S):
        return perevirka.pereviryty(S, 't')

    def test_dovhyi_tekst(self):
        S = copy.deepcopy(self.S)
        S['tochky'][0]['tekst'] = 'а' * 141
        self.assertTrue(any('141 знаків' in z for z in self.zauv(S)))

    def test_zaboroneni_slova(self):
        for slovo in ('Тут небезпечно', 'рейтинг вулиць', 'безпечний район'):
            S = copy.deepcopy(self.S)
            S['kinets']['tekst'] = slovo
            self.assertTrue(self.zauv(S), slovo)

    def test_slidy_imen_i_nomeriv(self):
        S = copy.deepcopy(self.S)
        S['tochky'][1]['tekst'] = 'ОСОБА_1 керував авто НОМЕР_1'
        self.assertTrue(self.zauv(S))

    def test_mv4(self):
        S = copy.deepcopy(self.S)
        S['tochky'][1]['vyd'] = 'Домашнє насильство'
        self.assertTrue(self.zauv(S))

    def test_tochka_poza_kyievom(self):
        S = copy.deepcopy(self.S)
        S['tochky'][0]['lat'], S['tochky'][0]['lon'] = 50.62, 30.20
        self.assertTrue(any('поза межею' in z for z in self.zauv(S)))

    def test_bez_posylannia(self):
        S = copy.deepcopy(self.S)
        S['tochky'][0]['rishennya_url'] = ''
        self.assertTrue(any('посилання' in z for z in self.zauv(S)))

    def test_pauza_vhadai(self):
        S = zavantazhyty(KORIN / 'video' / 'stsenarii' / 'vhadai.json')
        S['tochky'][0]['pauza'] = 2
        self.assertTrue(any('пауза' in z for z in self.zauv(S)))


class NomerBudynkuMV60(unittest.TestCase):
    """MV-60: номер будинку — лише для публічних місць; номер рішення й «лише те, що дійшло до суду» — у кожному ролику."""

    def tochka(self, **kw):
        S = zavantazhyty(KORIN / 'video' / 'stsenarii' / 'tur-pechersk.json')
        S['tochky'][0].update(kw)
        return perevirka.pidhotuvaty(S)['tochky'][0]

    def test_zhytlo_i_nevidomo_lyshe_vulytsia(self):
        for typ in ('zhytlo', 'vulytsia', 'nevidomo', None):
            p = self.tochka(adresa='вул. П. Орлика, 10', typ_mistsia=typ)
            self.assertEqual(p['adresa'], 'вул. П. Орлика', typ)

    def test_publichne_mistse_z_nomerom(self):
        for typ in ('tts', 'mahazyn', 'vokzal', 'parkovka', 'perekhrestia', 'zaklad'):
            self.assertEqual(self.tochka(adresa='вул. Х, 6/8', typ_mistsia=typ)['adresa'], 'вул. Х, 6/8', typ)

    def test_chutlyva_sprava_bez_nomera(self):
        p = self.tochka(adresa='вул. Х, 3', typ_mistsia='mahazyn', vyd='Домашнє насильство')
        self.assertEqual(p['adresa'], 'вул. Х')

    def test_nevidomyi_typ(self):
        S = zavantazhyty(KORIN / 'video' / 'stsenarii' / 'tur-pechersk.json')
        S['tochky'][0]['typ_mistsia'] = 'kvartyra'
        self.assertTrue(any('typ_mistsia' in z for z in perevirka.pereviryty(S, 't')))

    def test_usi_stsenarii_na_ekrani(self):
        for f in STSENARII:
            S = perevirka.pidhotuvaty(zavantazhyty(f))
            self.assertTrue(S['pidhotovano'])
            for p in S['tochky'] + [S.get('tsentr') or {}]:
                if p.get('adresa') and p.get('typ_mistsia') not in perevirka.PUBLICHNI:
                    self.assertNotRegex(p['adresa'], r',\s*\d', f'{f.name}: номер будинку не публічного місця')
                if S['shablon'] != 'tsyfry' and 'rishennya_url' in p:
                    self.assertRegex(p['rishennya_nomer'], r'^\d+$', f.name)

    def test_bez_nomera_rishennya(self):
        S = zavantazhyty(KORIN / 'video' / 'stsenarii' / 'vhadai.json')
        S['tochky'][0]['id'] = 'x'
        self.assertTrue(any('номера рішення' in z for z in perevirka.pereviryty(S, 't')))

    def test_stsena_pokazuie_lyshe_pidhotovanyi(self):
        js = (KORIN / 'video' / 'stsena.js').read_text(encoding='utf-8')
        self.assertIn('if (!S.pidhotovano) throw', js)
        self.assertIn('Рішення суду № ', js)
        self.assertIn('лише те, що дійшло до суду', js)
        self.assertIn('лише те, що дійшло до суду', (KORIN / 'video' / 'stsena.html').read_text(encoding='utf-8'))
        self.assertIn('perevirka.pidhotuvaty(S)', (KORIN / 'video' / 'rendery.py').read_text(encoding='utf-8'))


class Soty(unittest.TestCase):
    def test_lyshe_chysla_bez_adres(self):
        fc = zavantazhyty(KORIN / 'video' / 'dani' / 'soty-kyiv.geojson')
        self.assertGreater(len(fc['features']), 100)
        for f in fc['features']:
            self.assertEqual(set(f['properties']), {'n', 'k'})
            self.assertGreaterEqual(f['properties']['n'], fc['properties']['min_podiy'])
            self.assertIn(f['properties']['k'], (1, 2, 3, 4, 5))
            self.assertEqual(f['geometry']['type'], 'Polygon')


if __name__ == '__main__':
    unittest.main()
