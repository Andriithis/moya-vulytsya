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

    def test_starshi_roky_lyshe_variant_a(self):
        self.assertNotIn('data-v="a"', self.html)
        self.assertNotIn('років історії — у підписці', self.html)
        self.assertIn('неповний рік', self.html)

    def test_temy_i_kharakter_mistsia(self):
        self.assertIn('tiles.openfreemap.org/styles/dark', self.html)
        for kolir in ('#F1F7F6', '#0B6B6B', '#1C2A2B', '#6FC9BF'):
            self.assertIn(kolir, self.html)
        self.assertIn('Характер місця', self.html)
        self.assertIn('у підписці', self.html)
        self.assertNotIn('data-vyh', self.html)

    def test_tema_za_systemoyu_i_pamiat_z_try_catch(self):
        self.assertIn("prefers-color-scheme: dark", self.html)
        self.assertIn("try{TEMA=localStorage.getItem('mv-tema')}catch(e){}", self.html)
        self.assertIn("try{localStorage.setItem('mv-tema',t)}catch(e){}", self.html)

    def test_paliatra_hrup_lyshe_v_kharakteri(self):
        self.assertIn("KHARAKTER?HRUPY[b.gi][2]:SHKALA", self.html)
        self.assertIn("KHARAKTER?HRUPY[i][2]:'var(--line-strong)'", self.html)

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

    def test_vikno_rokiv(self):
        self.assertEqual(self.d['meta']['roky'], [2024, 2025, 2026])
        self.assertEqual(self.d['meta']['stari'], list(range(2016, 2024)))
        self.assertEqual(self.d['meta']['nepovnyi'], 2026)

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
