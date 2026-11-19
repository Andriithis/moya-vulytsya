"""Сервер продажу (ZAVDANNYA-99): ціни з однієї таблиці, тести Workers у Node, видавач довідок наскрізь.

Запуск: python -m unittest tests.test_prodazh -v
Тести Workers (site/worker/testy/*.test.mjs) потребують Node 22+ (node:sqlite); без нього — «пропущено» з причиною.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'prodazh'))

import tsiny as T  # noqa: E402
import vydavach  # noqa: E402
import karta_r2  # noqa: E402

WORKER = KORIN / 'site' / 'worker'


def node_z_sqlite() -> str | None:
    node = shutil.which('node')
    if not node:
        return None
    p = subprocess.run([node, '-e', "require('node:sqlite')"], capture_output=True)
    return node if p.returncode == 0 else None


class Tsiny(unittest.TestCase):
    def test_tsiny_servera_z_odniiei_tablytsi(self):
        """Сервер бере ціни з site/worker/prodazh/tsiny.js, а той — рівно site/tsiny.py (інакше: python site/tsiny.py)."""
        t = (WORKER / 'prodazh' / 'tsiny.js').read_text(encoding='utf-8')
        self.assertTrue(t.startswith(T.MODUL_JS))
        self.assertEqual(json.loads(t[len(T.MODUL_JS):].rstrip().rstrip(';')), json.loads(json.dumps(T.dlia_servera())),
                         'tsiny.js застарів — запустіть python site/tsiny.py')
        self.assertEqual(T.TSINY['dovidka'], 199)
        self.assertEqual(T.DOVIDOK['rieltor'], 5)
        self.assertEqual(T.PERIOD_MISIATSIV['osbb'], 12)
        self.assertNotIn('biznes', T.NA_PRODAZH)
        self.assertNotIn('dodatkova', T.NA_PRODAZH)

    def test_u_kodi_servera_nemaie_sum_i_kliuchiv(self):
        """Суми — лише з таблиці; ключів, токенів і паролів у файлах сервера немає."""
        for f in sorted(x for x in (WORKER / 'prodazh').glob('*.js') if x.name != 'tsiny.js') + [KORIN / 'site' / 'prodazh' / 'vydavach.py']:
            t = f.read_text(encoding='utf-8')
            for chyslo in (199, 449, 599, 399, 799, 1490):
                self.assertNotRegex(t, rf'(?<![\d.]){chyslo}(?![\d])', f'{f.name}: сума {chyslo} поза таблицею цін')
            self.assertNotRegex(t, r'(?i)(sandbox_[a-z0-9]{8,}|i\d{11}|sk_live|-----BEGIN [A-Z ]*PRIVATE KEY)', f.name)


@unittest.skipUnless(node_z_sqlite(), 'немає Node 22+ з node:sqlite — тести Workers пропущено')
class Workers(unittest.TestCase):
    def test_node(self):
        """Усі тести сервера продажу в Node: ціна, підпис, «чужий не відкриє», підписка, кабінет, видалення."""
        testy = sorted(str(f) for f in (WORKER / 'testy').glob('*.test.mjs'))
        p = subprocess.run([node_z_sqlite(), '--test', *testy], capture_output=True, text=True, cwd=KORIN)
        self.assertEqual(p.returncode, 0, p.stdout[-4000:] + p.stderr[-2000:])
        self.assertRegex(p.stdout, r'# pass \d+')
        self.assertRegex(p.stdout, r'# fail 0')


def vilnyi_port() -> int:
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


class BezPereadresatsii(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


@unittest.skipUnless(node_z_sqlite(), 'немає Node 22+ з node:sqlite — наскрізну перевірку видавача пропущено')
class Vydavach(unittest.TestCase):
    """Наскрізно: місцевий сервер (справжній код Workers) → замовлення → тестова оплата → видавач.py з генератором-
    підміною → лист → довідка за посиланням. Справжній генератор потребує даних (випуск, 1551, OSM) — тут не запускається."""

    @classmethod
    def setUpClass(cls):
        cls.port = vilnyi_port()
        cls.adresa = f'http://127.0.0.1:{cls.port}'
        env = dict(os.environ, VYDACHA_KLIUCH='kliuch-vydavacha', TEST_KLIUCH='test')
        cls.srv = subprocess.Popen([node_z_sqlite(), str(WORKER / 'testy' / 'mistsevyi.mjs'), str(cls.port)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.adresa + '/__lysty', timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.generator = Path(cls.tmp.name) / 'zibraty.py'
        cls.generator.write_text(
            'import sys, pathlib\n'
            'a = sys.argv[1:]\n'
            'if "Неіснуюча" in a[0]: sys.exit(2)\n'
            'v = pathlib.Path(a[a.index("--vyhid") + 1])\n'
            'rezhym = "dovidka" if "--dovidka" in a else "povnyi"\n'
            'v.write_text(f"<!doctype html><title>{rezhym}</title><h1>{a[0]}</h1><p>Опис події — лише платно</p>", encoding="utf-8")\n',
            encoding='utf-8')

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(5)
        cls.srv.stdout.close()
        cls.tmp.cleanup()

    def vidkryty(self, shliakh, dani=None):
        op = urllib.request.build_opener(BezPereadresatsii)
        z = urllib.request.Request(self.adresa + shliakh, data=urllib.parse.urlencode(dani).encode() if dani else None,
                                   headers={'origin': self.adresa})
        try:
            with op.open(z, timeout=10) as r:
                return r.status, r.headers, r.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            return e.code, e.headers, e.read().decode('utf-8')

    def oplatyty(self, tovar, budynok, poshta):
        st, h, _ = self.vidkryty('/api/zamovlennia', {'tovar': tovar, 'budynok': budynok, 'poshta': poshta,
                                                      'zghoda': 'tak', 'odrazu': 'tak'})
        self.assertEqual(st, 303)
        _, _, html = self.vidkryty(urllib.parse.urlparse(h['location']).path)
        forma = re.search(r'<form method="post" action="/api/spovishchennia/test">([\s\S]*?)Оплата пройшла', html).group(1)
        self.assertEqual(self.vidkryty('/api/spovishchennia/test', dict(re.findall(r'name="([^"]+)" value="([^"]*)"', forma)))[0], 303)

    def test_do_porozhnoi_cherhy(self):
        """Запуск GitHub Actions (ZAVDANNYA-133): видавач забирає всю чергу й виходить сам, з кодом 0."""
        self.oplatyty('dovidka', '/budynok/obolonskyi/16/', 'bo@poshta.ua')
        self.oplatyty('dovidka', '/budynok/zhylianska/5/', 'bo@poshta.ua')
        p = subprocess.run([sys.executable, str(KORIN / 'site' / 'prodazh' / 'vydavach.py'), '--server', self.adresa,
                            '--generator', str(self.generator), '--do-porozhnoi', '--maks-khvylyn', '2'],
                           capture_output=True, text=True, timeout=120, env=dict(os.environ, VYDACHA_KLIUCH='kliuch-vydavacha'))
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn('видано за запуск: 2', p.stdout)
        lysty = json.loads(urllib.request.urlopen(self.adresa + '/__lysty').read())
        self.assertEqual(sum(1 for l in lysty if l['komu'] == 'bo@poshta.ua' and 'Довідка' in l['tema']), 2)

    def test_naskrizno(self):
        st, h, _ = self.vidkryty('/api/zamovlennia', {'tovar': 'zvit', 'budynok': '/budynok/obolonskyi/16/',
                                                      'poshta': 'ana@poshta.ua', 'zghoda': 'tak', 'odrazu': 'tak', 'suma': '1'})
        self.assertEqual(st, 303)
        _, _, html = self.vidkryty(urllib.parse.urlparse(h['location']).path)
        forma = re.search(r'<form method="post" action="/api/spovishchennia/test">([\s\S]*?)Оплата пройшла', html).group(1)
        polia = dict(re.findall(r'name="([^"]+)" value="([^"]*)"', forma))
        self.assertEqual(polia['suma'], str(T.TSINY['zvit']))
        st, _, _ = self.vidkryty('/api/spovishchennia/test', polia)
        self.assertEqual(st, 303)

        with self.assertRaises(urllib.error.HTTPError):   # чужий ключ — 401
            vydavach.zapyt(self.adresa, 'ne-toi', 'GET', '/api/vnutr/cherha')
        vziato = vydavach.odyn_obkhid(self.adresa, 'kliuch-vydavacha', self.generator, shi=False, n=5)
        self.assertEqual(vziato, 1)
        lysty = json.loads(urllib.request.urlopen(self.adresa + '/__lysty').read())
        lyst = next(l for l in lysty if l['komu'] == 'ana@poshta.ua' and 'Повний звіт' in l['tema'])
        shliakh = re.search(r'https?://[^/]+(/dovidka/\S+)', lyst['tekst']).group(1)
        st, h, html = self.vidkryty(shliakh)
        self.assertEqual(st, 200)
        self.assertIn('<title>povnyi</title>', html)
        self.assertIn('проспект Оболонський, 16', html)
        self.assertIn('no-store', h['cache-control'])
        st, _, html = self.vidkryty(shliakh.split('?')[0])
        self.assertEqual(st, 404, 'без ключа з листа — ні')
        self.assertNotIn('Опис події', html)
        self.assertEqual(vydavach.odyn_obkhid(self.adresa, 'kliuch-vydavacha', self.generator, shi=False), 0, 'черга порожня')


class KartaR2(unittest.TestCase):
    """Карта підписника → R2 (ZAVDANNYA-133): покажчик точок, маніфест, клітинка та сама, що в скрипті Workers."""

    def setUp(self):
        self.t = Path(tempfile.mkdtemp(prefix='karta-r2-'))
        self.addCleanup(shutil.rmtree, self.t, True)
        k = self.t / 'karta'
        (k / 'dani').mkdir(parents=True)
        (k / 'spravy').mkdir()
        (k / 'index.html').write_text('<!doctype html>', encoding='utf-8')
        (k / 'dani' / 'meta.0123456789.json').write_text(json.dumps({'versiia': '2026-11-08', 'cats': ['Крадіжка']}), encoding='utf-8')
        pts = {'v': ['вулиця Вигадана'], 'p': [[50.45, 30.52, [0, '1'], 1, 'K…', 1], [50.46, 30.53, 'Майдан Вигаданий', 5, 'K…', 1]]}
        (k / 'dani' / 'pts.0123456789.json').write_text(json.dumps(pts, ensure_ascii=False), encoding='utf-8')
        for la, lo in ((50.45, 30.52), (50.46, 30.53)):
            (k / 'spravy' / f'{karta_r2.klitynka(la, lo)}.json').write_text('{}', encoding='utf-8')
        self.k = k

    def test_kliitynka_yak_u_workers(self):
        js = (WORKER / 'prodazh' / 'karta.js').read_text(encoding='utf-8')
        self.assertIn('export const KLITYNKA = [0.018 / 4, 0.028 / 4];', js)
        self.assertEqual(karta_r2.SPRAVY_KL, (0.018 / 4, 0.028 / 4))

    def test_pokazhchyk_i_manifest(self):
        r2 = self.t / 'r2'
        self.assertEqual(karta_r2.main([str(self.k), '--do-teky', str(r2)]), 0)
        m = json.loads((r2 / 'karta' / 'potochna.json').read_text(encoding='utf-8'))
        self.assertEqual(m['versiia'], '2026-11-08')
        self.assertEqual(m['kategorii'], ['Крадіжка'])
        kl = karta_r2.klitynka(50.45, 30.52)
        ind = json.loads((r2 / 'karta' / '2026-11-08' / 'indeks' / f'{kl}.json').read_text(encoding='utf-8'))
        self.assertEqual(ind, [[50.45, 30.52, 0, 'вулиця Вигадана, 1']])
        self.assertTrue((r2 / 'karta' / '2026-11-08' / 'index.html').exists())

    def test_bez_fajla_sprav_zupyniaietsia(self):
        for f in (self.k / 'spravy').glob('*.json'):
            f.unlink()
        with self.assertRaises(SystemExit):
            karta_r2.pidhotuvaty(self.k)


if __name__ == '__main__':
    unittest.main()
