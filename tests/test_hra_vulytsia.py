"""Друга гра «Вулиця дня» (ZAVDANNYA-101, прототип): перевірка однозначності загадки, ядро гри, межі показу.

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
const b = Y.vulytsia(['b', 'вулиця Мечникова', 'вулиця', 'Печерський', 62, 'Наркотики', 50.4385, 30.5400]);
const p = Y.porivnyaty(a, b), t = Y.porivnyaty(b, b);
process.stdout.write(JSON.stringify({ p, t, v0: Y.vidkryti(0), v3: Y.vidkryti(3), v5: Y.vidkryti(5),
  poshuk: Y.shukaty([a, b], 'мечн').map(x => x.slug), poshuk2: Y.shukaty([a, b], 'хрещ', { a: true }).length,
  tekst: Y.tekstPodilytysia('2026-11-17', [p, t], true, 7, 'sait') }));''')
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
        self.assertEqual(r['v5'], ['rayon', 'podiia', 'typ'])
        self.assertEqual(r['poshuk'], ['b'])
        self.assertEqual(r['poshuk2'], 0, 'уже названу вулицю вдруге не пропонуємо')
        self.assertNotIn('Мечникова', r['tekst'], '«Поділитися» без назви вулиці')
        self.assertIn('з 2-ї спроби з 7', r['tekst'])

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

    def test_prototyp_ne_publikuietsia(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            k = tmp / 'k.json'
            k.write_text(json.dumps(spravzhnia_koloda(), ensure_ascii=False), encoding='utf-8')
            zibraty.zibraty(tmp / 'z', test_hra.ZbyrannyaHryTests.URL, 'test-publichnyi', test_hra.ZbyrannyaHryTests.ZAPOVNENNYA, True, k)
            self.assertFalse(list((tmp / 'z' / 'hra').glob('vulytsia*')), 'прототип «Вулиця дня» не йде в публікацію')
        except zibraty.PomylkaZbyrannya as e:
            self.skipTest(f'збирання для публікації вимагає інших заповнень: {e}')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
