"""Застосунок Android (ZAVDANNYA-144, MV-126): налаштування оболонки, файли сайту для неї, «у застосунку без продажу»."""
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
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka'))

TWA = json.loads((KORIN / 'android' / 'twa-manifest.json').read_text(encoding='utf-8'))
DOMEN = 'moyavulytsya.com.ua'
VIDBYTOK = ':'.join(['AB'] * 32)


class Nalashtuvannia(unittest.TestCase):
    def test_domen_i_paket(self):
        self.assertEqual(TWA['packageId'], 'ua.moyavulytsya.app')
        self.assertEqual(TWA['host'], DOMEN)
        for k in ('iconUrl', 'maskableIconUrl', 'monochromeIconUrl', 'webManifestUrl', 'fullScopeUrl'):
            self.assertTrue(TWA[k].startswith(f'https://{DOMEN}/'), k)

    def test_bez_oplaty_google_play(self):
        """MV-126: у застосунку нічого не продаємо."""
        self.assertFalse(TWA['features']['playBilling']['enabled'])

    def test_start_i_yarlyky_z_poznachkoiu_dodatku(self):
        for u in [TWA['startUrl']] + [s['url'] for s in TWA['shortcuts']]:
            self.assertRegex(u, r'[?&]dzherelo=dodatok(&|$)', u)
        self.assertLessEqual(len(TWA['shortcuts']), 4)          # Android показує до 4 ярликів

    def test_rivni_android(self):
        self.assertGreaterEqual(TWA['minSdkVersion'], 24)

    def test_ikony_isnuiut(self):
        teka = KORIN / 'site' / 'zahlushka' / 'ikony'
        for k in ('iconUrl', 'maskableIconUrl', 'monochromeIconUrl'):
            self.assertTrue((teka / Path(TWA[k]).name).exists(), k)
        for s in TWA['shortcuts']:
            self.assertTrue((teka / Path(s['chosenIconUrl']).name).exists())

    def test_kliuchiv_nemaie(self):
        self.assertNotIn('password', json.dumps(TWA).lower())
        hit = (KORIN / 'android' / '.gitignore').read_text(encoding='utf-8')
        self.assertIn('*.keystore', hit)
        self.assertIn('*.jks', hit)


class FailySaitu(unittest.TestCase):
    def setUp(self):
        import zibraty_sait
        self.zs = zibraty_sait
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_manifest_bez_poznachky_dodatku(self):
        self.assertEqual(self.zs.android_faily(self.tmp), 0 if not TWA.get('fingerprints') else len(TWA['fingerprints']))
        m = json.loads((self.tmp / 'manifest.webmanifest').read_text(encoding='utf-8'))
        self.assertEqual(m['start_url'], '/')
        self.assertNotIn('dodatok', json.dumps(m))
        self.assertEqual(m['related_applications'][0]['id'], TWA['packageId'])
        self.assertEqual(len(m['shortcuts']), len(TWA['shortcuts']))

    def test_assetlinks_lyshe_z_vidbytkom(self):
        if not TWA.get('fingerprints'):
            self.zs.android_faily(self.tmp)
            self.assertFalse((self.tmp / '.well-known' / 'assetlinks.json').exists())
        n = self.zs.android_faily(self.tmp, [VIDBYTOK.lower(), VIDBYTOK])
        self.assertEqual(n, 1 + len(TWA.get('fingerprints', [])))
        a = json.loads((self.tmp / '.well-known' / 'assetlinks.json').read_text(encoding='utf-8'))
        self.assertEqual(a[0]['relation'], ['delegate_permission/common.handle_all_urls'])
        self.assertEqual(a[0]['target']['package_name'], 'ua.moyavulytsya.app')
        self.assertIn(VIDBYTOK, a[0]['target']['sha256_cert_fingerprints'])

    def test_pohanyi_vidbytok(self):
        with self.assertRaises(SystemExit):
            self.zs.android_faily(self.tmp, ['AB:CD'])


class BezProdazhu(unittest.TestCase):
    """tema.js (у <head> кожної сторінки сайту й кабінету) ховає ціни в застосунку; перевірка — на node."""
    TEMA = (KORIN / 'site' / 'sait' / 'tema.js').read_text(encoding='utf-8')

    def test_poznachka_i_referrer(self):
        self.assertIn('dzherelo=dodatok', self.TEMA)
        self.assertIn("android-app://ua.moyavulytsya.app", self.TEMA)
        self.assertIn('sessionStorage', self.TEMA)
        self.assertIn('html[data-dodatok="hotuiu"] body', (KORIN / 'site' / 'sait' / 'sait.css').read_text(encoding='utf-8'))

    @unittest.skipUnless(shutil.which('node'), 'немає node')
    def test_vyraz_tsiny(self):
        rx = re.search(r'var TSINA = (/.*?/gi);', self.TEMA).group(1)
        vypadky = {
            'скарги 1551 і події біля будинку; довідка — 199 грн': 'скарги 1551 і події біля будинку',
            'Довідка про будинок — 199 грн': 'Довідка про будинок',
            'Підписка — 399 грн на місяць': 'Підписка',
            'Будинок для ОСББ — 1 490 грн на рік': 'Будинок для ОСББ',
            'Скарги 1551, події з 2016 року': 'Скарги 1551, події з 2016 року',
        }
        kod = f'const R={rx};const v={json.dumps(list(vypadky), ensure_ascii=False)};' \
              'console.log(JSON.stringify(v.map(s=>s.replace(R,""))));'
        r = subprocess.run(['node', '-e', kod], capture_output=True, text=True, encoding='utf-8', check=True)
        self.assertEqual(json.loads(r.stdout), list(vypadky.values()))


if __name__ == '__main__':
    unittest.main()
