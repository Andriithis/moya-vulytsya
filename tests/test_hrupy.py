# -*- coding: utf-8 -*-
"""Групи подій — один словник (MV-116, ZAVDANNYA-108).

Правда — dani-edrsr/src/hrupy.py; у продукті — копія brend/hrupy.json і читач brend/hrupy.py. Тут перевіряємо: сім груп
MV-116 у порядку легенди, склад (грабіж — у насильстві, розпивання — в алкоголі), «нетверезі за кермом» — першим пунктом
«Порушень водіїв», і що в коді продукту немає ні старих назв груп, ні власних копій нових.

Запуск: python -m unittest tests/test_hrupy.py
"""
import json
import re
import sys
import types
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'brend'))
import hrupy as HR  # noqa: E402

MV_116 = ['ДТП', 'Порушення водіїв', 'Крадіжки й шкода майну', 'Насильство й грабежі', 'Наркотики',
          'Хуліганство й порядок', 'Алкоголь, тютюн і торгівля']
# назви груп карти Києва й старі короткі — у коді їх більше немає
STARI = ['Громадський порядок', 'Майнові', 'Алкоголь і торгівля', 'Насильство проти особи', 'Порушення на дорозі',
         "'Майно'", "'Дороги'", "'Алкоголь'", '«Насильство»', 'Торгівля алкоголем']
# нові назви, яких немає ніде, крім словника (ДТП й Наркотики — звичайні слова, їх не шукаємо)
OSOBLYVI = MV_116[1:4] + MV_116[5:]
KOD = ('*.py', '*.js', '*.html', '*.css')
TEKY = ('site', 'video', 'brend')


def faily():
    for t in TEKY:
        for vz in KOD:
            for f in (KORIN / t).rglob(vz):
                if 'biblioteka' in f.parts or '__pycache__' in f.parts:
                    continue
                yield f


class Slovnyk(unittest.TestCase):
    def test_sim_hrup_mv116(self):
        self.assertEqual([n for _, n in HR.HRUPY], MV_116)
        self.assertEqual(len(set(HR.KLIUCHI)), 7)
        for t in ('svitla', 'temna'):
            self.assertEqual(len(HR.KOLIR[t]), 7)
            self.assertEqual(len(set(HR.KOLIR[t])), 7, t)
            for k in HR.KOLIR[t]:
                self.assertRegex(k, r'^#[0-9A-F]{6}$')

    def test_sklad(self):
        for vyd, st, treba in (('ДТП', 'ст.124 КУпАП · ДТП', 'ДТП'), ('ДОР', "ст.130 КУпАП · керування у стані сп'яніння", 'Порушення водіїв'),
                               ('МАЙ', 'ст.185 КК · крадіжка', 'Крадіжки й шкода майну'), ('МАЙ', 'ст.186 КК · грабіж', 'Насильство й грабежі'),
                               ('МАЙ', 'ст.187 КК · розбій', 'Насильство й грабежі'), ('НАС', 'ст.125 КК · легке тілесне', 'Насильство й грабежі'),
                               ('НАР', 'ст.309 КК', 'Наркотики'), ('ГП', 'ст.173 КУпАП · дрібне хуліганство', 'Хуліганство й порядок'),
                               ('ГП', "ст.178 КУпАП · розпивання алкоголю або п'яний вигляд", 'Алкоголь, тютюн і торгівля'),
                               ('ГП', 'ст.175-1 КУпАП · куріння', 'Алкоголь, тютюн і торгівля'),
                               ('АЛК', 'ст.160 КУпАП · торгівля з рук', 'Алкоголь, тютюн і торгівля')):
            self.assertEqual(HR.nazva(vyd, st), treba, (vyd, st))
        self.assertIsNone(HR.hrupa('ПОЗА', 'ст.184 КУпАП'))

    def test_netverezi_pershi(self):
        self.assertEqual(HR.pershyi('vod', "ст.130 КУпАП · керування у стані сп'яніння"), 0)
        self.assertEqual(HR.pershyi('vod', 'ст.126 КУпАП · без прав'), 1)

    def test_kopiia_z_dani_edrsr(self):
        d = json.loads((KORIN / 'brend' / 'hrupy.json').read_text(encoding='utf-8'))
        self.assertIn('dani-edrsr/src/hrupy.py', d['_pro'])


class BezInshykhNazv(unittest.TestCase):
    def test_bez_starykh_nazv(self):
        zh = [f'{f.relative_to(KORIN)}: {s}' for f in faily() for s in STARI if s in f.read_text(encoding='utf-8')]
        self.assertEqual(zh, [], 'старі назви груп у коді — брати з brend/hrupy.json')

    def test_bez_kopii_nazv(self):
        dozv = {KORIN / 'site' / 'zahlushka' / 'zrazok.html'}     # статичний зразок звіту — перевірено нижче
        zh = [f'{f.relative_to(KORIN)}: {s}' for f in faily() if f not in dozv
              for s in OSOBLYVI if s in f.read_text(encoding='utf-8')]
        self.assertEqual(zh, [], 'назви груп у коді — лише з brend/hrupy.json')

    def test_zrazok_nazvy_zi_slovnyka(self):
        html = (KORIN / 'site' / 'zahlushka' / 'zrazok.html').read_text(encoding='utf-8')
        nazvy = re.findall(r'class="zvit-katehoriya"[^>]*>\s*<span[^>]*>([^<]+)</span>', html)
        self.assertTrue(nazvy)
        self.assertEqual([n for n in nazvy if n not in MV_116 + ['Інше']], [])

    def test_filtr_karty_zi_slovnyka(self):
        sys.path.insert(0, str(KORIN / 'site'))
        import zibraty_sait as Z
        html = Z.ekran_karty(types.SimpleNamespace(versiia='2026-11-08'))
        self.assertEqual(re.findall(r'data-hrupa="(\w+)"', html), HR.KLIUCHI)
        for n in MV_116:
            self.assertIn(n, html)


if __name__ == '__main__':
    unittest.main()
