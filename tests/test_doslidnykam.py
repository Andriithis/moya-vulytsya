"""Сторінка «Дані для дослідників» (ZAVDANNYA-158): два режими, без чисел і службових слів, розмітка Dataset лише з DOI."""
import json
import re
import sys
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(KORIN / 'tests'))

try:
    import h3  # noqa: F401
    import storinka_doslidnykam as SD
    from test_sait import ZABORONENI_SLOVA, ZABORONENO_V_HTML, perevirka_storinky
    PROPUSTYTY = ''
except ImportError as pomylka:   # без бібліотек збирання сайту (h3) — як test_sait
    PROPUSTYTY = str(pomylka)

ADRESA = 'https://mv.test'
SLUZHBOVI = re.compile(r'медіан|\bMV-\d|docs/|[A-Z-]+\.md\b|макет|конвеєр|ZAVDANNYA', re.I)


def ld(html_):
    return [json.loads(m.replace('<\\/', '</')) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html_, re.S)]


@unittest.skipIf(PROPUSTYTY, PROPUSTYTY)
class DoslidnykamTests(unittest.TestCase):
    def setUp(self):
        self.hotuiemo = SD.storinka(ADRESA, {'doi': '', 'versiia': '', 'period': '', 'litsenziia': 'CC BY 4.0'})
        self.hotovyi = SD.storinka(ADRESA, {'doi': '10.5281/zenodo.1234567', 'versiia': '2026-12-01',
                                            'period': '01.2016 — 11.2026', 'litsenziia': 'CC BY 4.0'})

    def test_nalashtuvannia_v_repozytorii_bez_doi(self):
        """поки набір не викладено (робить Микита після «так»), DOI порожній — сторінка «готуємо»"""
        n = SD.nalashtuvannia()
        self.assertEqual(n['doi'], '')
        self.assertEqual(n['litsenziia'], 'CC BY 4.0')

    def test_html_pravylnyi(self):
        for t in (self.hotuiemo, self.hotovyi):
            self.assertEqual(perevirka_storinky(t), [])

    def test_bez_sluzhbovykh_i_zaboronenykh_sliv(self):
        for t in (self.hotuiemo, self.hotovyi):
            vydyme = re.sub(r'<script\b[^>]*>.*?</script>|<!--.*?-->', '', t, flags=re.S)
            self.assertIsNone(SLUZHBOVI.search(vydyme))
            self.assertIsNone(ZABORONENI_SLOVA.search(t))
            self.assertIsNone(ZABORONENO_V_HTML.search(t))

    def test_hotuiemo(self):
        t = self.hotuiemo
        self.assertIn('Готуємо', t)
        self.assertIn('/zahlushka/?dzherelo=doslidnykam#peredzamovlennya', t)
        self.assertNotIn('doi.org', t)
        self.assertEqual([o['@type'] for o in ld(t)], ['BreadcrumbList'])   # без файлу — без Dataset

    def test_hotovyi_dataset_dlia_google(self):
        t = self.hotovyi
        self.assertIn('href="https://doi.org/10.5281/zenodo.1234567"', t)
        self.assertNotIn('dzherelo=doslidnykam', t)
        d = [o for o in ld(t) if o['@type'] == 'Dataset'][0]
        self.assertEqual(d['license'], 'https://creativecommons.org/licenses/by/4.0/deed.uk')
        self.assertEqual(d['identifier'], 'https://doi.org/10.5281/zenodo.1234567')
        self.assertEqual(d['creator']['name'], 'Моя вулиця')          # автор — проєкт, не людина
        self.assertTrue(50 <= len(d['description']) <= 5000)          # вимога Google Dataset Search
        self.assertIn('Моя вулиця. Події з рішень судів і скарги 1551 за районами й місяцями — Київ (версія 2026-12-01) '
                      '[набір даних]. https://doi.org/10.5281/zenodo.1234567', t)

    def test_shcho_obitsiaiemo_zbihaietsia_z_naborom(self):
        """сторінка обіцяє те саме, що робить генератор dani-edrsr/src/vidkrytyi_nabir.py (S-Д.12)"""
        t = self.hotuiemo
        for fraza in ('від 1 до 4 приховано', 'Статевих злочинів і справ щодо дітей', 'сімома групами', 'CSV',
                      'Адрес, точок на карті, назв вулиць, описів подій, номерів справ', 'не перевірений факт',
                      'учасники OpenStreetMap'):
            self.assertIn(fraza, t)
        self.assertNotRegex(re.sub(r'<[^>]+>|https?://\S+', '', t), r'\b(?!1551\b)\d{3,}\b',
                            'на сторінці немає чисел з даних')

    def test_posylannia_v_pidvali(self):
        import zibraty_sait as Z
        self.assertIn('<a href="/doslidnykam/">Дані для дослідників</a>',
                      Z.storinka(shlyakh='/x/', title='x', opys='x', tilo='', adresa_saitu=ADRESA))


if __name__ == '__main__':
    unittest.main()
