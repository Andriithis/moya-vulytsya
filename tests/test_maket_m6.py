"""Перевірки макета М6 (ZAVDANNYA-36): К3 — шкала частками, вершини без «привидів», без цифр на карті, плашки не
стрибають, «світлодіодна» темна тема, три «вау», три шрифти.

Запуск: python -m unittest tests.test_maket_m6 -v
Перевіряє сторінку maket/m6/index.html; дані — спільні з М1 (maket/m1/dani.json). Частки на живій сторінці рахує
maket/m6/znimky_m6.py chastky (потрібен браузер).
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

from tests.test_maket_m4 import ZABORONENI_SLOVA, kontrast
from tests.test_maket_m5 import stopy

KORIN = Path(__file__).resolve().parents[1]
MAKET = KORIN / 'maket' / 'm6'


class StorinkaM6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (MAKET / 'index.html').read_text(encoding='utf-8')

    def test_nemaye_zaboronenykh_sliv(self):
        self.assertIsNone(ZABORONENI_SLOVA.search(self.html))

    def test_shkala_chastkamy(self):
        """Класи й вершини — частками сот рівня, не сталими числами; частка — (менші + половина рівних) / усіх."""
        self.assertIn('const KVANT=[.2,.4,.6,.88], VERSHYNA=.88', self.html)
        self.assertIn('const q=(i+(j-i)/2)/L_', self.html)
        self.assertIn('const vershyna=b=>b.nf>0&&b.q>=VERSHYNA', self.html)
        # прозорість і висота залежать від частки q, а не від числа подій
        self.assertIn('lo+(hi-lo)*b.q*b.q', self.html)
        self.assertIn('Math.sqrt(clamp((b.q-VERSHYNA)/(1-VERSHYNA),0,1))', self.html)

    def test_lehenda_pro_vershyny(self):
        self.assertIn('Стовпчиком — найгустіші ${vidsotok} % сот', self.html)

    def test_najsvitlishyi_krok_pomitnishyi(self):
        lo = float(re.search(r'const PROZ=\{svitla:\[([\d.]+),', self.html).group(1))
        self.assertGreaterEqual(lo, .12)

    def test_bez_tsyfr_na_karti(self):
        self.assertNotIn('k-numt-', self.html)
        self.assertNotIn('chyslaData', self.html)
        self.assertIn("map.on('mousemove'", self.html)        # число — у підказці при наведенні

    def test_stovpchyky_bez_pryvydiv(self):
        """Два рівні стовпчиків ніколи не видно разом: старий нульовий і погаслий до межі, новий починає з нуля після неї."""
        mn, op = stopy(self.html, 'MN'), stopy(self.html, 'OPS')
        zmina = [float(x) for x in re.search(r'const ZMINA=\[([\d.]+),([\d.]+)\]', self.html).groups()]
        for (staryi, novyi), z in zip((('XL', 'L'), ('L', 'S')), zmina):
            for st in (mn, op):
                self.assertEqual(st[staryi][-1], (z, 0.0), staryi)
                self.assertEqual(st[novyi][0], (z, 0.0), novyi)
        self.assertIn('MEZHI_ST={XL:[0,ZMINA[0]],L:[ZMINA[0],ZMINA[1]],S:[ZMINA[1],24]}', self.html)

    def test_kvartal_nyzhchi_z_14(self):
        s = dict(stopy(self.html, 'MN')['S'])
        self.assertEqual(s[13.6], 1.0)
        self.assertLess(s[14.0], 1.0)
        self.assertLessEqual(s[14.6], .4)

    def test_nazvy_mists_nad_stovpchykamy(self):
        self.assertIn("if(NAZVY_MISTS(l)){map.moveLayer(l.id);", self.html)

    def test_plashky_ne_strybayut(self):
        self.assertNotIn('body.k-vidkr #lehenda{left', self.html)
        self.assertNotIn('bottom:calc(45vh', self.html)
        self.assertIn('body.k-vidkr #lehenda,body.k-vidkr .maplibregl-ctrl-bottom-right{visibility:hidden}', self.html)
        self.assertRegex(self.html, r'#kartka\{position:absolute;z-index:6;right:76px')

    def test_temna_svitlodiodna(self):
        """Вершини — насичена бірюза на 1–2 кроки світліша за найгустіші пласкі соти, не біла (Андрій, 12.11.2026)."""
        self.assertIn("background:'#0C1012'", self.html)                      # нічна підкладка В2
        svitlota = lambda c: sum(int(c[i:i + 2], 16) for i in (1, 3, 5))
        plaski = re.search(r"SHKALA=\{svitla:\[[^\]]+\],temna:\[([^\]]+)\]", self.html).group(1)
        najgustisha = svitlota(plaski.split(',')[-1].strip("'"))
        vt = re.search(r"const VERSH_T=\{spokiyno:\['(#\w{6})','(#\w{6})'\],yaskravo:\['(#\w{6})','(#\w{6})'\]\}", self.html)
        self.assertIsNotNone(vt)
        for c in vt.groups():
            self.assertGreater(svitlota(c), najgustisha, c)                    # світліша за пласкі
            self.assertLess(max(int(c[i:i + 2], 16) for i in (1, 3, 5)), 215, c)  # не біла
            self.assertGreater(int(c[3:5], 16) - int(c[1:3], 16), 100, c)       # насичена бірюза
        self.assertIn('data-yaskr="spokiyno"', self.html)
        self.assertIn('data-yaskr="yaskravo"', self.html)
        self.assertIn("tilo:zmishaty(c,'#000000'", self.html)                 # боки темніші за верх
        self.assertIn("FORMA={XL:{k:.55,H:.9}", self.html)                     # місто: тонші й нижчі
        self.assertNotRegex(self.html, r'filter:\s*blur|backdrop-filter')

    def test_try_vau_okremo_i_tykhyi_rezhym(self):
        for k in ('khvylya', 'svitlo', 'perelit'):
            self.assertIn(f'data-vau="{k}"', self.html)
        self.assertIn("VAU.has('khvylya')&&PERSHE&&!TYKHO", self.html)
        self.assertIn("VAU.has('perelit')&&PERSHE&&!TYKHO", self.html)
        t = int(re.search(r'const t0=performance.now\(\), T=(\d+);', self.html).group(1))
        self.assertLessEqual(t, 1200)
        self.assertNotRegex(self.html, r'linear-gradient|radial-gradient')

    def test_shryfty(self):
        self.assertIn('--sans:Fixel', self.html)
        for f in ('plex', 'arsenal'):
            self.assertIn(f'data-shr="{f}"', self.html)
        for zaboronenyi in ('Inter', 'Roboto', 'Geist', 'Space Grotesk', 'Manrope'):
            self.assertNotIn(f'font-family:{zaboronenyi}', self.html)
        self.assertTrue((MAKET / 'shryfty' / 'OFL-IBM-Plex-Sans.txt').is_file())
        self.assertTrue((MAKET / 'shryfty' / 'OFL-Arsenal.txt').is_file())

    def test_mezhi_plashok_3_do_1(self):
        svitla = re.search(r':root\{[^}]*--mezha:(#[0-9A-F]{6})', self.html).group(1)
        temna = re.search(r'body\[data-t=temna\]\{[^}]*--mezha:(#[0-9A-F]{6})', self.html).group(1)
        for tlo in ('#F7F6F2', '#FFFFFF', '#E9EBE0', '#D5DEDD'):
            self.assertGreaterEqual(kontrast(svitla, tlo), 3.0, tlo)
        for tlo in ('#0C1012', '#141A1D', '#111A1C', '#121816'):
            self.assertGreaterEqual(kontrast(temna, tlo), 3.0, tlo)

    def test_rukh_i_dostupnist(self):
        self.assertIn('prefers-reduced-motion', self.html)
        self.assertNotRegex(self.html, r'transition:\s*all')
        self.assertNotIn('maximum-scale', self.html)
        self.assertIn('font:400 16px/24px var(--sans)', self.html)
        self.assertNotIn('hash:true', self.html)

    def test_lokalni_fajly_ye(self):
        for shlyakh in re.findall(r"url\(([^)]+\.woff2)\)", self.html):
            self.assertTrue((MAKET / shlyakh).resolve().is_file(), shlyakh)
        self.assertTrue((MAKET / '../m1/vendor/maplibre-gl-6.10.0/maplibre-gl.mjs').resolve().is_file())


if __name__ == '__main__':
    unittest.main()
