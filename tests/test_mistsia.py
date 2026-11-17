"""Сторінки публічних місць (ZAVDANNYA-124; MV-54, MV-60, MV-98, MV-116, MV-135).

Запуск: python -m unittest tests/test_mistsia.py
Збирає сайт зі штучного міста (tests/shtuchne_misto.py — там є названі місця) і перевіряє: які місця стають сторінками,
житлового нічого, порівняння за MV-98, Google (заголовок, опис, розмітка, sitemap, тонкі — поза пошуком), «Для медіа».
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))

import mistsia as MS  # noqa: E402


class Rozbir(unittest.TestCase):
    def test_publichni(self):
        for a, typ, nazva in (('ст. м. Вокзальна', 'метро', 'станція метро «Вокзальна»'),
                              ('ТРЦ «Ocean Plaza»', 'ТЦ', 'ТЦ «Ocean Plaza»'),
                              ("Лук'янівський ринок", 'ринок', "Лук'янівський ринок"),
                              ('Центральний залізничний вокзал', 'вокзал', 'Центральний вокзал'),
                              ('пляж Венеція', 'пляж', 'пляж «Венеція»'),
                              ('сквер ім. Шевченка', 'парк', 'сквер «Шевченка»'),
                              ('Південний міст', 'міст', 'Південний міст'),
                              ('Труханів острів', 'острів', 'Труханів острів')):
            r = MS.rozibraty(a)
            self.assertEqual((r[0], r[2]), (typ, nazva), a)

    def test_ne_publichni(self):
        # житло й адреси з номером, зупинки, знеособлене — не сторінка місця (MV-25, MV-60)
        for a in ('вул. Хрещатик, 5', 'просп. Перемоги, 12', 'зупинка «Майдан»', 'ст. м. ОСОБА_1', 'квартира', ''):
            self.assertIsNone(MS.rozibraty(a), a)

    def test_mitka_yak_u_zvity(self):
        """MV-98: те саме правило, що в довідці (dani-edrsr/src/zvit/analityka.mitka_shkaly), без «менше» до повного Києва."""
        an = KORIN.parent / 'dani-edrsr' / 'src' / 'zvit' / 'analityka.py'
        try:
            import scipy  # noqa: F401
        except ImportError:
            self.skipTest('немає scipy')
        if not an.exists():
            self.skipTest('немає dani-edrsr поруч')
        sys.path.insert(0, str(an.parent))
        sys.path.insert(0, str(an.parent.parent))
        import analityka as AN
        for tut in range(0, 40):
            for typ in (0, 1, 2, 3, 5, 8, 12, 20, 35):
                self.assertEqual(MS.mitka(tut, typ), AN.mitka_shkaly(tut, typ, menshe_mozhna=False), (tut, typ))
        self.assertEqual(MS.mitka(2, 3), 'мало даних')
        self.assertEqual(MS.mitka(60, 35), 'більше')


class Sait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import h3  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('немає бібліотеки h3')
        import zibraty_sait as Z
        cls.tmp = Path(tempfile.mkdtemp())
        baza = cls.tmp / 'events.db'
        subprocess.run([sys.executable, str(KORIN / 'tests' / 'shtuchne_misto.py'), str(baza), '--podii', '3000'],
                       check=True, capture_output=True)
        # «Для медіа» — підставний візуал для однієї станції (справжній робить brend/media/zrobyty_media.py)
        media = cls.tmp / 'media'
        for slug, storinka in (('metro-lisova', '/mistse/metro-lisova/'), ('tts-ocean-plaza', '/vulytsia/inshe/')):
            (media / slug).mkdir(parents=True)
            for n, _, _ in Z.MEDIA_FAILY:
                (media / slug / n).write_bytes(b'x')
            (media / slug / 'vizual.json').write_text(json.dumps({
                'typ': 'метро', 'storinka': storinka, 'radius': 300, 'nazva': 'x', 'period': 'січень 2024 — 1 жовтня 2026',
                'podii': 60, 'umovy': 'Безкоштовно для медіа з підписом.', 'versiia': '2026-11-08'}, ensure_ascii=False), encoding='utf-8')
        cls.sait = cls.tmp / 'sait'
        cls.zvit = Z.zibraty_sait(baza, cls.sait, None, KORIN / 'data' / 'borders.json', media=media)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def storinka(self, slug):
        return (self.sait / 'mistse' / slug / 'index.html').read_text(encoding='utf-8')

    def test_mistsia_z_vypusku(self):
        slugy = sorted(p.name for p in (self.sait / 'mistse').iterdir())
        for s in ('metro-lisova', 'metro-teremky', 'tts-ocean-plaza', 'vokzal-tsentralnyi', 'rynok-lukianivskyi',
                  'park-natalka', 'pliazh-venetsiia', 'mist-patona'):
            self.assertIn(s, slugy)
        self.assertFalse(any('zupynk' in s or 'maidan' in s for s in slugy), 'зупинка — не сторінка місця')
        self.assertEqual(self.zvit['mistsia'], len(slugy))

    def test_zhytlovoho_nichoho(self):
        import dani as D
        for p in (self.sait / 'mistse').iterdir():
            t = (p / 'index.html').read_text(encoding='utf-8')
            self.assertNotIn('/budynok/', t, p.name)
            self.assertIsNone(D.NOMER_BUDYNKU.search(re.sub(r'<[^>]+>', ' ', t)), p.name)
            self.assertIsNone(D.ZABORONENI_SLOVA.search(t), p.name)
            for slovo in ('ОСОБА_', 'Штучна подія', 'медіана', 'MV-', 'reyestr.court.gov.ua'):
                self.assertNotIn(slovo, t, p.name)

    def test_lyshe_chysla_i_porivniannia(self):
        t = self.storinka('metro-lisova')
        self.assertIn('Подія — один випадок із рішення суду.', t)
        self.assertIn('Типова станція метро', t)
        self.assertIn('Події за групами', t)
        self.assertIn('Події за роками', t)
        self.assertNotIn('Що поруч', t)
        self.assertIn('Моя вулиця — що відбувається під боком', t)
        # ТЦ у штучному місті лише два — порівнювати чесно нема з чим
        self.assertIn('замало, щоб порівнювати', self.storinka('tts-ocean-plaza'))

    def test_posylannia_mistse_vulytsia_raion(self):
        t = self.storinka('metro-lisova')
        self.assertRegex(t, r'href="/vulytsia/[a-z0-9-]+/"')
        self.assertIn('href="/rayon/desnianskyi/"', t)
        rayon = (self.sait / 'rayon' / 'desnianskyi' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('href="/mistse/metro-lisova/"', rayon)
        vul = re.search(r'href="/vulytsia/([a-z0-9-]+)/"', t).group(1)
        self.assertIn('href="/mistse/metro-lisova/"', (self.sait / 'vulytsia' / vul / 'index.html').read_text(encoding='utf-8'))
        self.assertIn('href="/mistse/metro-lisova/"', (self.sait / 'mistsia' / 'index.html').read_text(encoding='utf-8'))

    def test_park_i_mist_ne_vulytsi(self):
        vulytsi = {p.name for p in (self.sait / 'vulytsia').iterdir()}
        for s in ('park-natalka', 'holosiivskyi-park', 'mist-patona'):
            self.assertNotIn(s, vulytsi)

    def test_google(self):
        t = self.storinka('metro-lisova')
        self.assertRegex(t, r'<title>Станція метро «Лісова», Київ: \d+ под\w+ з рішень судів')
        self.assertIn('<meta name="description"', t)
        ld = [json.loads(x) for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t)]
        place = next(x for x in ld if x['@type'] == 'SubwayStation')
        self.assertIn('latitude', place['geo'])
        self.assertTrue(any(x['@type'] == 'BreadcrumbList' for x in ld))
        self.assertNotIn('noindex', t)
        sitemap = (self.sait / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertIn('/mistse/metro-lisova/', sitemap)
        self.assertIn('/mistsia/', sitemap)
        # тонка (2 події): сторінка є, але не в пошуку й не в sitemap
        self.assertIn('noindex', self.storinka('metro-teremky'))
        self.assertNotIn('/mistse/metro-teremky/', sitemap)

    def test_dlia_media(self):
        t = self.storinka('metro-lisova')
        self.assertIn('id="dlia-media"', t)
        self.assertIn('href="/mistse/metro-lisova/media/kartka-1x1.png"', t)
        self.assertTrue((self.sait / 'mistse' / 'metro-lisova' / 'media' / 'slaidy.pdf').exists())
        # візуал з чужою сторінкою — не показуємо
        self.assertNotIn('id="dlia-media"', self.storinka('tts-ocean-plaza'))
        self.assertEqual(self.zvit['media_mists'], 1)

    def test_spysok_dlia_heneratora(self):
        """Список для dani-edrsr/src/vizual_mistsia.py: ті самі slug і сторінки /mistse/<slug>/, лише публічні типи."""
        import dani as D
        dn = D.zibraty_dani(self.tmp / 'events.db', None, KORIN / 'data' / 'borders.json')
        ryadky = MS.dlia_media(MS.zibraty(dn))
        self.assertTrue(ryadky)
        for r in ryadky:
            self.assertEqual(r['storinka'], f'/mistse/{r["slug"]}/')
            self.assertTrue((self.sait / 'mistse' / r['slug'] / 'index.html').exists())
            self.assertIn(r['typ'], MS.TYPY)


if __name__ == '__main__':
    unittest.main()
