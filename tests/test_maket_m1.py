"""Перевірки макета М1: карта й картка соти (MV-28, MV-30, MV-32, MV-36).

Запуск: python -m unittest tests.test_maket_m1 -v
Перевіряє те, що лежить у репозиторії: сторінку maket/m1/index.html і її дані maket/m1/dani.json.
"""
from __future__ import annotations

import json
import re
import statistics
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
MAKET = KORIN / 'maket' / 'm1'
ZABORONENI_SLOVA = re.compile(r'небезпечн|безпечн|ризик|рейтинг', re.I)
ZNEOSOBLENI = re.compile(r'ОСОБА_|АДРЕСА_')
NOMER_BUDYNKU = re.compile(r',\s*\d+[а-яa-z]?\s*$|\bбуд\.|\bкв\.', re.I)
OCHIKUVANI_HRUPY = ['dtp', 'dor', 'hp', 'mai', 'nar', 'alk', 'nas']


class StorinkaMaketa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (MAKET / 'index.html').read_text(encoding='utf-8')

    def test_nemaye_zaboronenykh_sliv(self):
        self.assertIsNone(ZABORONENI_SLOVA.search(self.html))

    def test_pidkladka_positron_i_atrybutsiia(self):
        self.assertIn('tiles.openfreemap.org/styles/positron', self.html)
        for dzherelo in ('OpenFreeMap', 'OpenMapTiles', 'OpenStreetMap', 'ЄДРСР'):
            self.assertIn(dzherelo, self.html)

    def test_soty_lyshe_330_i_130(self):
        self.assertIn("{id:'L',R:330}", self.html)
        self.assertIn("{id:'S',R:130}", self.html)
        self.assertNotIn('R:30}', self.html)
        self.assertIn('будинки — у підписці', self.html)

    def test_3d_za_zamovchuvanniam(self):
        self.assertIn("let MODE='stovp'", self.html)

    def test_kartka_za_mv32(self):
        for tekst in ('Мало даних', 'Година-пік', 'Повторюється тут', 'Насильство', 'типовій соті Києва', 'За роками'):
            self.assertIn(tekst, self.html)

    def test_dva_varianty_starshykh_rokiv(self):
        self.assertIn('data-v="a"', self.html)
        self.assertIn('data-v="b"', self.html)
        self.assertIn('років історії — у підписці', self.html)

    def test_kartka_vuzka_i_bez_pereletu(self):
        self.assertIn('--shyryna:320px', self.html)
        self.assertNotIn('flyTo', self.html)
        self.assertIn('duration:TYKHO?0:700', self.html)

    def test_lokalni_fajly_ye(self):
        for shlyakh in re.findall(r'(?:href|url\()=?"?((?:vendor|shryfty)/[^")\s]+)', self.html):
            self.assertTrue((MAKET / shlyakh).is_file(), shlyakh)
        self.assertTrue((MAKET / 'vendor/maplibre-gl-6.10.0/maplibre-gl.mjs').is_file())


class DaniMaketa(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tekst = (MAKET / 'dani.json').read_text(encoding='utf-8')
        cls.d = json.loads(cls.tekst)

    def test_sim_hrup(self):
        self.assertEqual([h[0] for h in self.d['hrupy']], OCHIKUVANI_HRUPY)

    def test_lyshe_dvi_sitky(self):
        self.assertEqual(sorted(self.d['soty']), ['L', 'S'])

    def test_try_roky_i_sim_starshykh(self):
        self.assertEqual(len(self.d['meta']['roky']), 3)
        self.assertEqual(len(self.d['meta']['stari']), 7)

    def test_sumy_skhodiatsia(self):
        for riven, soty in self.d['soty'].items():
            for r in soty:
                self.assertEqual(sum(r[4]), r[3], (riven, r[0], 'групи'))
                self.assertEqual(sum(r[5]), r[3], (riven, r[0], 'роки'))

    def test_obydvi_sitky_mistiat_ti_sami_podii(self):
        suma = {riven: sum(r[3] for r in soty) for riven, soty in self.d['soty'].items()}
        self.assertEqual(suma['L'], suma['S'])
        self.assertEqual(suma['S'], self.d['meta']['podii'])

    def test_mediana_po_sotakh_130(self):
        self.assertEqual(self.d['meta']['mediana130'], statistics.median(r[3] for r in self.d['soty']['S']))

    def test_nemaye_adres_i_opysiv(self):
        self.assertIsNone(ZNEOSOBLENI.search(self.tekst))
        self.assertIsNone(ZABORONENI_SLOVA.search(self.tekst))
        for nazva in self.d['oriyentyry'] + self.d['problemy']:
            self.assertIsNone(NOMER_BUDYNKU.search(nazva), nazva)
        # У соті — лише числа й номери довідників, жодного довільного тексту.
        for soty in self.d['soty'].values():
            for r in soty:
                self.assertEqual(len(r), 12)
                self.assertIsInstance(r[0], str)
                self.assertRegex(r[0], r'^-?\d+:-?\d+$')
                for pole in r[1:4] + r[6:11]:
                    self.assertIsInstance(pole, (int, float))


if __name__ == '__main__':
    unittest.main()
