"""«Для бізнесу» (ZAVDANNYA-157): копія бази в сховище R2, облік клієнтів з командного рядка, сторінка /biznes/.

Запуск: python -m unittest tests.test_biznes -v
Наскрізний тест потребує Node 22+ (node:sqlite); без нього — «пропущено» з причиною. Копія — вигадана (справжні описи подій
лише в приватному сховищі, не в репозиторії).
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'prodazh'))
sys.path.insert(0, str(KORIN / 'tests'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))

import khostynh as KH  # noqa: E402
import biznes_r2  # noqa: E402
import biznes_klienty  # noqa: E402
from test_prodazh import node_z_sqlite, vilnyi_port, WORKER  # noqa: E402

BIZNES_JS = (WORKER / 'prodazh' / 'biznes.js').read_text(encoding='utf-8')


def vyhadana_kopiia(koren: Path, klient='k1', versiia='2026-11-08') -> Path:
    t = koren / f'kopiia-{versiia}-{klient}'
    t.mkdir(parents=True)
    vmist = {'baza.db': b'SQLite format 3\x00 vyhadana', 'csv.zip': b'PK vyhadanyi arkhiv', 'OPYS.md': '# Копія\n'.encode()}
    for k, b in vmist.items():
        (t / k).write_bytes(b)
    (t / 'SHA256SUMS').write_text(''.join(f'{hashlib.sha256(b).hexdigest()}  {k}\n' for k, b in sorted(vmist.items())), encoding='ascii')
    return t


class Uzhodzhenist(unittest.TestCase):
    def test_marshruty_i_fajly_odnakovi(self):
        """Адреси, для яких Cloudflare запускає скрипт, і перелік файлів копії — однакові в Python і в Workers."""
        js = (WORKER / 'prodazh' / 'index.js').read_text(encoding='utf-8')
        m = re.search(r"export const MARSHRUTY = (\[[^\]]*\]);", js)
        self.assertEqual(json.loads(m.group(1).replace("'", '"')), KH.MARSHRUTY_PRODAZHU)
        self.assertIn('/kopiia/*', KH.MARSHRUTY_PRODAZHU)
        self.assertEqual(re.findall(r"'([A-Za-z0-9.]+)': \[", BIZNES_JS.split('export const FAJLY = ')[1].split('};')[0]),
                         list(biznes_r2.FAJLY))

    def test_skhovyshche_lyshe_z_praportsem(self):
        """Сховище BIZNES — у налаштуваннях Workers лише з prodazh['biznes'], і в режимі «скоро» теж (договір — не оплата сайту)."""
        with tempfile.TemporaryDirectory() as t:
            v = Path(t) / '_site'
            v.mkdir()
            for oplata, dod in (('skoro', {}), ('tak', {'servis': 'test'})):
                for biznes in (False, True):
                    k = json.loads(KH.pidhotuvaty_worker(v, 1, prodazh={'d1': 'x', 'adresa': 'https://s', 'biznes': biznes, **dod},
                                                         oplata=oplata).joinpath('wrangler.jsonc').read_text(encoding='utf-8').split('\n', 1)[1])
                    zviazky = [b['binding'] for b in k.get('r2_buckets', [])]
                    self.assertEqual('BIZNES' in zviazky, biznes, (oplata, biznes, zviazky))


class BiznesR2(unittest.TestCase):
    def test_pidhotuvaty_i_do_teky(self):
        with tempfile.TemporaryDirectory() as t:
            k = vyhadana_kopiia(Path(t))
            with contextlib.redirect_stdout(io.StringIO()):
                biznes_r2.main([str(k), '--do-teky', str(Path(t) / 'r2')])
            man = json.loads((Path(t) / 'r2' / 'biznes' / 'k1' / 'potochna.json').read_text(encoding='utf-8'))
            self.assertEqual(man['versiia'], '2026-11-08')
            self.assertEqual([f['imia'] for f in man['fajly']], list(biznes_r2.FAJLY))
            self.assertEqual((Path(t) / 'r2' / 'biznes' / 'k1' / '2026-11-08' / 'csv.zip').read_bytes(), b'PK vyhadanyi arkhiv')

    def test_zupyniaietsia(self):
        with tempfile.TemporaryDirectory() as t:
            k = vyhadana_kopiia(Path(t))
            (k / 'csv.zip').write_bytes(b'poshkodzheno')
            with self.assertRaisesRegex(SystemExit, 'контрольна сума'):
                biznes_r2.pidhotuvaty(k)
            inshe = Path(t) / 'kopiia-zlamana'
            inshe.mkdir()
            with self.assertRaisesRegex(SystemExit, 'має зватися'):
                biznes_r2.pidhotuvaty(inshe)

    def test_bez_tokena_ne_zavantazhuie(self):
        with tempfile.TemporaryDirectory() as t:
            k = vyhadana_kopiia(Path(t))
            env = {x: y for x, y in os.environ.items() if x != 'CLOUDFLARE_API_TOKEN'}
            p = subprocess.run([sys.executable, str(KORIN / 'site' / 'prodazh' / 'biznes_r2.py'), str(k), '--zavantazhyty'],
                               capture_output=True, text=True, env=env)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn('CLOUDFLARE_API_TOKEN', p.stderr)


@unittest.skipUnless(node_z_sqlite(), 'немає Node 22+ з node:sqlite — наскрізний тест пропущено')
class Naskrizno(unittest.TestCase):
    """Місцевий сервер (справжній код Workers) + «сховище» на диску: копія → клієнт → посилання → завантаження → вимкнення,
    усе — тими самими командами, що в docs/BIZNES-DOSTUP.md."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        k = vyhadana_kopiia(Path(cls.tmp.name))
        with contextlib.redirect_stdout(io.StringIO()):
            biznes_r2.main([str(k), '--do-teky', str(Path(cls.tmp.name) / 'r2')])
        cls.port = vilnyi_port()
        cls.adresa = f'http://127.0.0.1:{cls.port}'
        env = dict(os.environ, PRODAZH='skoro', ADMIN_KLIUCH='kliuch-partnera', BIZNES_TEKA=str(Path(cls.tmp.name) / 'r2'))
        cls.srv = subprocess.Popen([node_z_sqlite(), str(WORKER / 'testy' / 'mistsevyi.mjs'), str(cls.port)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.adresa + '/__lysty', timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        cls.env = {'MV_ADRESA_SAITU': cls.adresa, 'MV_ADMIN_KLIUCH': 'kliuch-partnera'}

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(5)
        cls.srv.stdout.close()
        cls.tmp.cleanup()

    def kom(self, *a, env=None):
        b = io.StringIO()
        with contextlib.redirect_stdout(b):
            kod = biznes_klienty.main(list(a), env=self.env if env is None else env)
        return kod, b.getvalue()

    def vidkryty(self, url):
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                return r.status, r.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_shliakh_partnera(self):
        kod, v = self.kom('novyi', 'ТОВ «Вигадана агенція»', 'ofis@vyhadana.ua', '--tarif', 'rik', '--do', '2099-12-31', '--dohovir', 'Л-1')
        self.assertEqual(kod, 0, v)
        klient = json.loads(v)['klient']
        self.assertEqual(klient, 'k1')
        kod, v = self.kom('posylannia', klient, '--dniv', '7', '--maks', '2')
        self.assertEqual(kod, 0, v)
        url = json.loads(v.split('\nПосилання показано')[0])['posylannia']
        st, html = self.vidkryty(url)
        self.assertEqual(st, 200)
        self.assertIn('Вигадана агенція', html.decode())
        self.assertEqual(self.vidkryty(url + 'csv.zip'), (200, b'PK vyhadanyi arkhiv'))
        self.assertEqual(self.vidkryty(url + 'baza.db')[0], 200)
        self.assertEqual(self.vidkryty(url + 'OPYS.md')[0], 429)                     # maks 2
        kod, v = self.kom('spysok')
        self.assertEqual(json.loads(v)['klienty'][0]['zavantazhen'], 2)
        kod, v = self.kom('vymknuty', klient, '--prychyna', 'тест')
        self.assertEqual(kod, 0, v)
        self.assertEqual(self.vidkryty(url)[0], 404)
        self.assertEqual(self.kom('posylannia', klient)[0], 1)

    def test_bez_kliucha(self):
        self.assertEqual(self.kom('spysok', env={'MV_ADRESA_SAITU': self.adresa})[0], 2)
        self.assertEqual(self.kom('spysok', env={**self.env, 'MV_ADMIN_KLIUCH': 'ne-toi'})[0], 1)


class Storinka(unittest.TestCase):
    """Сторінка /biznes/: поля форми — ті, що читає site/sait/biznes.js і перевіряє сервер; без описів справ і службових слів."""

    def test_forma_i_spysky_odnakovi(self):
        import storinky_mv100 as M
        html = M.vitryna_biznes('https://pryklad.ua', None, '2024–2026', [('65 701', 'подія з рішень судів')])
        js = (KORIN / 'site' / 'sait' / 'biznes.js').read_text(encoding='utf-8')
        for pole in ('kompaniia', 'kontakt', 'meta', 'terytoriia', 'strok', 'komentar', 'zghoda'):
            self.assertIn(f'name="{pole}"', html)
            self.assertIn(pole, js)
        meta_html = re.findall(r'<option value="([a-z]+)">', html)
        meta_js = json.loads(re.search(r"var META = (\[[^\]]*\]);", js).group(1).replace("'", '"'))
        meta_srv = re.findall(r"(\w+): '", BIZNES_JS.split('export const META = ')[1].split('};')[0])
        self.assertEqual(meta_html, meta_js)
        self.assertEqual(meta_html, meta_srv)
        stroky_html = re.findall(r'name="strok" value="([a-z_]+)"', html)
        self.assertEqual(stroky_html, re.findall(r"(\w+): '", BIZNES_JS.split('export const STROKY = ')[1].split('};')[0]))
        self.assertIn('/sait/biznes.js', html)
        self.assertIn('ціна за домовленістю', html)
        for zaboroneno in ('ОСОБА_', 'MV-', 'конвеєр', 'макет', 'рейтинг', 'небезпечн', 'уникайте', 'будьте уважні'):
            self.assertNotIn(zaboroneno, html)
        self.assertIn('не оцінка безпечності', html)
        self.assertIn("referrerPolicy: 'same-origin'", js, 'з no-referrer браузер шле Origin: null — форму відхилить сервер')
