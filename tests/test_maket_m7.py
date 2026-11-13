"""Перевірки макета М7 (ZAVDANNYA-42, етап А): напрями кольору в OKLCH, контраст, без кольорів «небезпеки»,
один шрифт, рух вимикається системою, відгук на дотик, кадр ролика.

Запуск: python -m unittest tests.test_maket_m7 -v
"""
from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path

from tests.test_maket_m4 import ZABORONENI_SLOVA

KORIN = Path(__file__).resolve().parents[1]
MAKET = KORIN / 'maket' / 'm7'
_spec = importlib.util.spec_from_file_location('kontrast_m7', MAKET / 'kontrast_m7.py')
kontrast_m7 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kontrast_m7)


class NapryamyM7(unittest.TestCase):
    def setUp(self):
        self.N = dict(kontrast_m7.napryamy())

    def test_pyat_napryamiv_i_biryuza_dlya_porivnyannya(self):
        self.assertGreaterEqual(len(self.N), 5)
        self.assertLessEqual(len(self.N), 6)
        self.assertIn('biryuza', self.N)

    def test_kontrast_usikh_napryamiv(self):
        _, zle = kontrast_m7.rozrakhunok()
        self.assertEqual(zle, [])

    def test_nemaye_chervonoho_y_pomaranchevoho(self):
        """Кольори сот, вершин і акценту — не в червоно-помаранчевому секторі OKLCH (h 0…75 і 340…360) при помітній насиченості."""
        for k, n in self.N.items():
            for t in ('svitla', 'temna'):
                p = n[t]
                for c in p['sc'] + p['pk'] + [p['accent']]:
                    if c[1] >= 0.04:
                        self.assertFalse(c[2] < 75 or c[2] > 340, f'{k}/{t}: {c}')

    def test_temna_ne_chorna(self):
        for k, n in self.N.items():
            self.assertGreaterEqual(n['temna']['bg'][0], 0.18, k)
            self.assertGreater(n['temna']['bg'][1], 0.02, k)


class StorinkaM7(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (MAKET / 'index.html').read_text(encoding='utf-8')

    def test_nemaye_zaboronenykh_sliv(self):
        self.assertIsNone(ZABORONENI_SLOVA.search(self.html))

    def test_odyn_shryft_plex(self):
        self.assertNotIn('data-shr', self.html)
        self.assertNotIn('Fixel', self.html.split('<style>')[1].split('</style>')[0].replace('Fixel (MacPaw', ''))
        self.assertIn('--sans:Plex', self.html)

    def test_nemaye_khvyli_y_perelitu_na_starti(self):
        self.assertIn('const KHVYLYA=false, PERELIT=false;', self.html)
        self.assertNotIn('data-vau', self.html)

    def test_rukh_vymykaye_systema(self):
        self.assertIn("matchMedia('(prefers-reduced-motion: reduce)')", self.html)
        self.assertIn("const TYKHO=SYSTEMA_TYKHO&&RUH!=='zavzhdy';", self.html)
        self.assertIn('body.tykho', self.html)

    def test_vidhuk_na_dotyk(self):
        for x in ("['feature-state','tysk']", "['feature-state','naved']", 'function natysnuty', '@keyframes kz', 'ANIM_SEL'):
            self.assertIn(x, self.html)

    def test_zblyzka_soty_prozorishayut(self):
        self.assertIn('[14.0,1],[15.2,.42]', self.html)
        self.assertIn("'k-hexo-'", self.html)

    def test_kadr_rolyka_bez_adres(self):
        self.assertIn("parU.get('kadr')==='1'", self.html)
        kadr = self.html.split('// ==== Кадр ролика 1080×1920')[1]
        self.assertNotIn('oriyentyr', kadr)

    def test_bez_cervonoho_v_stylyakh(self):
        self.assertNotIn('--attention', self.html)


class EtapBM7(unittest.TestCase):
    """Етап Б: розміщення в обраному напрямі «Індиго й м'ята»."""

    @classmethod
    def setUpClass(cls):
        cls.html = (MAKET / 'index.html').read_text(encoding='utf-8')

    def test_obranyi_napryam_za_zamovchuvannyam(self):
        self.assertIn(":'nich';", self.html)

    def test_kartka_v_povitri(self):
        self.assertIn('#kartka{position:absolute;z-index:6;right:16px;top:16px;max-height:calc(100% - 64px);width:372px;', self.html)

    def test_nichoho_ne_rukhayetsya(self):
        self.assertNotIn('zPidKartky', self.html)
        self.assertNotIn('body.k-vidkr #', self.html)

    def test_nemaye_lehendy_i_plyus_minus(self):
        self.assertNotIn('id="lehenda"', self.html)
        self.assertNotIn('NavigationControl', self.html)

    def test_keruvannya_v_ryadku_z_poshukom(self):
        ryad = self.html.split('<div id="verkh-ryad">')[1].split('</div>\n<ul id="pidkazky"')[0]
        for x in ('id="poshuk"', 'id="f3d"', 'id="ftema"', 'id="finfo"'):
            self.assertIn(x, ryad)

    def test_dzherela_u_kuti_i_v_info(self):
        self.assertIn('#dzherela{position:absolute;z-index:4;right:8px;bottom:6px;', self.html)
        self.assertIn('<h3>Джерела</h3><p>${DZHERELA}</p>', self.html)

    def test_dva_varianty_filtra_i_try_vydilennya(self):
        for x in ('data-filtr="spysok"', 'data-filtr="znachky"', 'data-vyd="a"', 'data-vyd="b"', 'data-vyd="v"', 'function prytsil'):
            self.assertIn(x, self.html)

    def test_poshuk_dvadtsyat_vidomykh_mists(self):
        vidomi = self.html.split('const VIDOMI=[')[1].split('];')[0]
        self.assertGreaterEqual(vidomi.count("',"), 20 * 2)
        self.assertIn('duration:TYKHO?0:1200', self.html)

    def test_korotka_kartka(self):
        self.assertIn('за типову соту`', self.html)
        self.assertIn('Пік: ${b.pik}', self.html)
