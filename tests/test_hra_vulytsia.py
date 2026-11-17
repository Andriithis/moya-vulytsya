"""Друга гра «Вулиця дня» (MV-126; ZAVDANNYA-101, ZAVDANNYA-114): перевірка однозначності загадки, ядро гри, межі показу,
збирання для публікації.

Запуск: python -m unittest tests/test_hra_vulytsia.py
Справжні дані (випуск і колода) не потрібні: перевірка — на умовних вулицях; ядро — через Node.js.
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
HRA = KORIN / 'site' / 'hra'
sys.path.insert(0, str(HRA))
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import vulytsia_dnia as VD  # noqa: E402
import zibraty  # noqa: E402
import test_hra  # noqa: E402
from test_hra import spravzhnia_koloda  # noqa: E402


def vul(slug, rayon='Печерський', vyrizn='Крадіжка', n=30, typ='вулиця', lat=50.43, lon=30.54):
    return {'slug': slug, 'nazva': f'вулиця {slug}', 'typ': typ, 'rayon': rayon, 'n': n, 'hrupa': 'dtp',
            'vyrizn': vyrizn, 'lat': lat, 'lon': lon}


def misto(dodaty=()):
    """30 вулиць у Печерському й 30 в інших районах з різними ознаками."""
    v = [vul(f'p{i}', vyrizn=('ДТП' if i % 2 else 'Наркотики'), n=10 + i) for i in range(30)]
    v += [vul(f'i{i}', rayon='Подільський', n=10 + i) for i in range(30)]
    return v + list(dodaty)


class Perevirka(unittest.TestCase):
    def test_odnoznachna_zahadka_prokhodyt(self):
        vsi = misto([vul('vidp', vyrizn='Крадіжка', n=25)])
        ok, zv = VD.perevirka_zahadky(vsi[-1], vsi, [v['n'] for v in vsi])
        self.assertTrue(ok, zv)
        self.assertEqual(zv['typ'], 1)
        self.assertGreaterEqual(zv['rayon'], VD.MIN_STARTU)

    def test_dvi_odnakovi_vulytsi_ne_prokhodiat(self):
        dvi = [vul('vidp', vyrizn='Крадіжка', n=25), vul('dviinyk', vyrizn='Крадіжка', n=26)]
        vsi = misto(dvi)
        ok, zv = VD.perevirka_zahadky(dvi[0], vsi, [v['n'] for v in vsi])
        self.assertFalse(ok, 'дві вулиці з однаковими ознаками — лотерея')

    def test_malo_vulyts_u_raioni_nadto_lehko(self):
        vsi = [vul(f'i{i}', rayon='Подільський', n=10 + i) for i in range(40)] + [vul('vidp', vyrizn='Крадіжка')]
        ok, zv = VD.perevirka_zahadky(vsi[-1], vsi, [v['n'] for v in vsi])
        self.assertFalse(ok)
        self.assertIn('легко', zv['chomu'])


class Spalni(unittest.TestCase):
    def test_chastyna_raionu(self):
        seredyna = {'lat': 50.50, 'lon': 30.60}
        self.assertEqual(VD.chastyna_rayonu({'lat': 50.53, 'lon': 30.65}, seredyna), 'північно-східна частина району')
        self.assertEqual(VD.chastyna_rayonu({'lat': 50.47, 'lon': 30.60}, seredyna), 'південна частина району')
        self.assertEqual(VD.chastyna_rayonu({'lat': 50.505, 'lon': 30.60}, seredyna), 'ближче до середини району')

    def test_mezha_spalnoho(self):
        self.assertLess(VD.vidstan_km(VD.TSENTR, {'lat': 50.4437, 'lon': 30.5136}), VD.SPALNYI_KM, 'центр — не спальний')
        self.assertGreater(VD.vidstan_km(VD.TSENTR, {'lat': 50.5146, 'lon': 30.6034}), VD.SPALNYI_KM, 'Троєщина — спальний')


def node(skrypt: str):
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8', dir=HRA) as f:
        f.write(skrypt)
    try:
        return json.loads(subprocess.check_output(['node', f.name], timeout=30))
    finally:
        Path(f.name).unlink()


@unittest.skipUnless(shutil.which('node'), 'немає Node.js — перевірку ядра пропущено')
class Yadro(unittest.TestCase):
    def test_porivnyannia_i_pidkazky(self):
        r = node(r'''
const Y = require('./vulytsia-yadro.js');
const a = Y.vulytsia(['a', 'вулиця Хрещатик', 'вулиця', 'Шевченківський', 100, 'ДТП', 50.4470, 30.5220]);
const b = Y.vulytsia(['b', 'вулиця Мечникова', 'вулиця', 'Печерський', 62, 'Наркотики', 50.4385, 30.5400, 'вулиця Стара']);
const p = Y.porivnyaty(a, b), t = Y.porivnyaty(b, b);
process.stdout.write(JSON.stringify({ p, t, v0: Y.vidkryti(0), v3: Y.vidkryti(3), v5: Y.vidkryti(5),
  poshuk: Y.shukaty([a, b], 'мечн').map(x => x.slug), stara: Y.shukaty([a, b], 'стара').map(x => x.slug),
  litera: Y.persha(b), poshuk2: Y.shukaty([a, b], 'хрещ', { a: true }).length,
  tekst: Y.tekstPodilytysia('2026-11-17', [p, t], true, 7, 'sait'),
  ni: Y.tekstPodilytysia('2026-11-17', [p], false, 7, 'sait'),
  sp1: Y.vidkryti(1, { spalnyi: true, chastyna: 'південна частина району' }),
  sp2: Y.vidkryti(2, { spalnyi: true, chastyna: 'південна частина району' }),
  sp4: Y.vidkryti(4, { spalnyi: true, chastyna: 'південна частина району' }),
  tsentr4: Y.vidkryti(4, { spalnyi: false }),
  data: [Y.dataZAdresy('2026-11-10', '2026-11-17'), Y.dataZAdresy('2026-11-18', '2026-11-17'), Y.dataZAdresy('бла', '2026-11-17')] }));''')
        p, t = r['p'], r['t']
        self.assertFalse(p['tak'])
        self.assertTrue(1500 < p['vidstanM'] < 1800, p['vidstanM'])
        self.assertEqual(p['napryam'], 'пд-сх')
        self.assertEqual(p['n'], -1, 'у загаданої менше подій')
        self.assertFalse(p['rayon'])
        self.assertTrue(p['typ'])
        self.assertTrue(t['tak'] and t['vidstanM'] == 0 and t['n'] == 0)
        self.assertEqual(r['v0'], ['rayon'])
        self.assertEqual(r['v3'], ['rayon', 'podiia'])
        self.assertEqual(r['v5'], ['rayon', 'podiia', 'litera'])
        self.assertEqual(r['litera'], 'М')
        self.assertEqual(r['stara'], ['b'], 'вулицю знаходимо й за старою назвою')
        self.assertEqual(r['poshuk'], ['b'])
        self.assertEqual(r['poshuk2'], 0, 'уже названу вулицю вдруге не пропонуємо')
        self.assertNotIn('Мечникова', r['tekst'], '«Поділитися» без назви вулиці')
        self.assertIn('з 2-ї спроби з 7', r['tekst'])
        self.assertIn('не розгадано за 7', r['ni'])
        self.assertEqual(r['sp1'], ['rayon', 'chastyna'], 'спальний район — частина району після 1-ї')
        self.assertEqual(r['sp2'], ['rayon', 'chastyna', 'podiia'])
        self.assertEqual(r['sp4'], ['rayon', 'chastyna', 'podiia', 'litera'])
        self.assertEqual(r['tsentr4'], ['rayon', 'podiia'], 'центр — як було')
        self.assertEqual(r['data'], ['2026-11-10', '2026-11-17', '2026-11-17'], 'майбутню загадку наперед не відкриваємо')

    def test_zahadka_dnia_stala(self):
        r = node(r'''
const Y = require('./vulytsia-yadro.js');
const z = Array.from({ length: 50 }, (_, i) => ({ slug: 's' + i }));
const dni = ['2026-11-17', '2026-11-18', '2026-11-19'].map(d => Y.zahadkaDnya(z, d).id);
process.stdout.write(JSON.stringify({ dni, znovu: Y.zahadkaDnya(z, '2026-11-17').id }));''')
        self.assertEqual(r['dni'][0], r['znovu'])
        self.assertEqual(len(set(r['dni'])), 3)


class Mezhi(unittest.TestCase):
    def test_tekst_bez_zaboronenykh_sliv(self):
        for f in ('vulytsia.html', 'vulytsia.js', 'vulytsia-yadro.js'):
            t = (HRA / f).read_text(encoding='utf-8')
            t = t.replace('Це не рейтинг і не оцінка безпеки вулиці.', '')   # чесна примітка — дозволено
            self.assertIsNone(re.search(r'небезпечн|безпечн|рейтинг|найгірш', t, re.I), f)

    def test_bez_prototypnykh_slidiv(self):
        html = (HRA / 'vulytsia.html').read_text(encoding='utf-8')
        js = (HRA / 'vulytsia.js').read_text(encoding='utf-8')
        for slovo in ('Прототип', 'прототип', 'noindex', 'Ще одна загадка'):
            self.assertNotIn(slovo, html)
        self.assertNotIn('poradok', js, 'у робочій версії — одна загадка на добу')

    def test_podii_rakhunku(self):
        js = (KORIN / 'site' / 'zahlushka' / 'nadsylannya.js').read_text(encoding='utf-8')
        vd = (HRA / 'vulytsia.js').read_text(encoding='utf-8')
        sql = (KORIN / 'docs' / 'hra-podii.sql').read_text(encoding='utf-8')
        for nazva in ('vd_start', 'vd_kinets', 'vd_storinka', 'vd_pidpyska', 'vd_podilytysia'):
            self.assertIn(f"'{nazva}'", js)
            self.assertIn(f"nadislaty('{nazva}')", vd)
            self.assertIn(f"'{nazva}'", sql)


def koloda_i_zahadky(tmp: Path, demo=False, chuzha_podiia=False):
    koloda = spravzhnia_koloda()
    koloda['zibrano'] = '2026-11-08'
    k = tmp / 'k.json'
    k.write_text(json.dumps(koloda, ensure_ascii=False), encoding='utf-8')
    url = 'https://reyestr.court.gov.ua/Review/999' if chuzha_podiia else koloda['podii'][0]['rishennya_url']
    vd = {'versiia': 2, 'koloda': '2026-11-08', 'demo': demo, 'sprob': 7, 'roky': '2024–2026', 'hrupy': {},
          'vulytsi': [['a', 'вулиця А', 'вулиця', 'Печерський', 30, 'ДТП', 50.43, 30.54, '']],
          'zahadky': [{'slug': 'a', 'zvuzhennia': {}, 'spalnyi': False, 'chastyna': None,
                       'podiia': {'vyd': 'ДТП', 'rik': 2025, 'opys': 'опис', 'url': url, 'nomer': '1'}}]}
    f = tmp / 'vd.json'
    f.write_text(json.dumps(vd, ensure_ascii=False), encoding='utf-8')
    return k, f


class Zbyrannia(unittest.TestCase):
    """Робоча версія (ZAVDANNYA-114): з загадками — сторінка й пункт меню; без — нічого; звірка з колодою."""

    def zibraty(self, tmp, k, vd):
        T = test_hra.ZbyrannyaHryTests
        zibraty.zibraty(tmp / 'z', T.URL, 'test-publichnyi', T.ZAPOVNENNYA, True, k, vd)
        return tmp / 'z' / 'hra'

    def test_z_zahadkamy_publikuietsia(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k, vd = koloda_i_zahadky(tmp)
            hra = self.zibraty(tmp, k, vd)
            self.assertTrue((hra / 'vulytsia.html').is_file())
            self.assertTrue((hra / 'vulytsia-dnia.json').is_file())
            self.assertFalse((hra / 'vulytsia_dnia.py').exists(), 'код збирача на сайт не йде')
            self.assertIn('href="vulytsia.html"', (hra / 'index.html').read_text(encoding='utf-8'))
            sw = (tmp / 'z' / 'sw.js').read_text(encoding='utf-8')
            self.assertIn('hra/vulytsia.html', sw)
            storinka = (hra / 'vulytsia.html').read_text(encoding='utf-8')
            self.assertIn(test_hra.ZbyrannyaHryTests.URL, storinka, 'адреса сховища для рахунку подій')
            self.assertNotIn('[САЙТ]', storinka)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_bez_zahadok_nemaie_ni_storinky_ni_punktu(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k, _ = koloda_i_zahadky(tmp)
            hra = self.zibraty(tmp, k, None)
            self.assertFalse(list(hra.glob('vulytsia*')))
            self.assertNotIn('vulytsia', (hra / 'index.html').read_text(encoding='utf-8'))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_demo_i_chuzha_podiia_ne_publikuiutsia(self):
        for kw in ({'demo': True}, {'chuzha_podiia': True}):
            tmp = Path(tempfile.mkdtemp())
            try:
                k, vd = koloda_i_zahadky(tmp, **kw)
                with self.assertRaises(zibraty.PomylkaZbyrannya, msg=str(kw)):
                    self.zibraty(tmp, k, vd)
            finally:
                shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
