# -*- coding: utf-8 -*-
"""«Для медіа» (MV-113, ZAVDANNYA-113): візуал лише для публічних місць, без імен і без «небезпечн-», з підписом
«Джерело: Моя вулиця» і посиланням на сторінку місця; блок на сторінці — лише там, де є візуал цього самого місця."""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(KORIN / 'brend' / 'media'))

import zibraty_sait as ZS          # noqa: E402
import dani as D                   # noqa: E402
import zrobyty_media as ZR       # noqa: E402

ZABOR = re.compile(r'небезпечн|рейтинг|найгірш|ОСОБА_|судд|[А-ЯІЇЄҐ][а-яіїєґ]+ [А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.', re.I)
ZRAZOK = KORIN / 'docs' / 'znimky-113' / 'vokzalna-ploshcha'     # перший справжній візуал (ZAVDANNYA-113)
ZABOR_IMENA = re.compile(r'[А-ЯІЇЄҐ][а-яіїєґʼ’]+ [А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.')


class TestMedia(unittest.TestCase):
    def test_hotovi_vizualy(self):
        """кожен готовий візуал (docs/znimky-113) — публічне місце, усі файли є, підпис і посилання на сторінку, без імен і «небезпечн-»"""
        teky = [t for t in ZRAZOK.parent.iterdir() if t.is_dir()]
        self.assertTrue(teky, 'немає жодного візуалу (перший — Вокзальна площа, docs/znimky-113/)')
        for t in teky:
            d = json.loads((t / 'vizual.json').read_text(encoding='utf-8'))
            self.assertIn(d['typ'], ZS.MEDIA_PUBLICHNI, t.name)
            self.assertEqual(d['dzherelo'], 'Джерело: Моя вулиця')
            self.assertEqual(d['storinka'], f'/vulytsia/{t.name}/')
            self.assertIn(d['storinka'], d['posylannia'])
            for n, _, _ in ZS.MEDIA_FAILY:
                self.assertTrue((t / n).exists(), f'{t.name}/{n}')
            for n in range(1, 9):
                self.assertTrue((t / f'slaid-{n}.png').exists(), f'{t.name}/slaid-{n}.png')
            tekst = json.dumps({k: v for k, v in d.items() if k != 'umovy'}, ensure_ascii=False)
            self.assertIsNone(re.search(r'небезпечн|рейтинг|ОСОБА_|судд', tekst, re.I), t.name)
            self.assertIsNone(ZABOR_IMENA.search(tekst), t.name)

    def test_shablon_bez_zaboronenoho(self):
        js = (KORIN / 'brend' / 'media' / 'vizual.js').read_text(encoding='utf-8')
        teksty = ' '.join(re.findall(r"'([^']*)'", js))
        self.assertNotIn('небезпечн', teksty.lower())
        self.assertNotIn('МАКЕТ', js)
        self.assertNotIn('raziv', js, 'порівняння — два числа «тут · у типовому» (MV-98), не «у N разів»')

    def test_lyshe_publichni(self):
        """zrobyty_media.py не малює візуал для житлового будинку чи місця без сторінки"""
        with tempfile.TemporaryDirectory() as t:
            d = json.loads((ZRAZOK / 'vizual.json').read_text(encoding='utf-8'))
            for zle in (dict(d, typ='житловий будинок'), dict(d, storinka='')):
                f = Path(t) / 'v.json'
                f.write_text(json.dumps(zle, ensure_ascii=False), encoding='utf-8')
                with self.assertRaises(SystemExit):
                    ZR.zrobyty(f, Path(t) / 'vykhid', 'https://x')
                self.assertFalse((Path(t) / 'vykhid' / 'kartka-1x1.png').exists())

    def test_blok_na_storintsi(self):
        """блок «Для медіа» — лише на сторінці того самого публічного місця; на вулиці — ні"""
        with tempfile.TemporaryDirectory() as t:
            media = Path(t)
            shutil.copytree(ZRAZOK, media / 'vokzalna-ploshcha')
            shutil.copytree(ZRAZOK, media / 'khreshchatyk')
            plosha = D.Vulytsia('vokzalna-ploshcha', 'Вокзальна площа', 'площа', 'Вокзальна', 'osm')
            vulytsia = D.Vulytsia('khreshchatyk', 'вулиця Хрещатик', 'вулиця', 'Хрещатик', 'osm')
            inshe = D.Vulytsia('lvivska-ploshcha', 'Львівська площа', 'площа', 'Львівська', 'osm')
            d = ZS.media_mistsia(media, plosha)
            self.assertIsNotNone(d)
            self.assertIsNone(ZS.media_mistsia(media, vulytsia), 'вулиця — не публічне місце')
            self.assertIsNone(ZS.media_mistsia(media, inshe), 'візуалу цього місця немає')
            h = ZS.blok_media(d, plosha.slug)
            self.assertIn('Для медіа', h)
            self.assertIn('Джерело: Моя вулиця', h)
            self.assertIn('Безкоштовно', h)
            for n, _, _ in ZS.MEDIA_FAILY:
                self.assertIn(f'/vulytsia/vokzalna-ploshcha/media/{n}', h)
            self.assertNotIn('небезпечн', h.lower())


if __name__ == '__main__':
    unittest.main()
