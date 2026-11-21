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
import shi_api  # noqa: E402
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka'))
import perevirka_formy  # noqa: E402

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
            'v = a[a.index("--vyhid") + 1]\n'
            'rezhym = "dovidka" if "--dovidka" in a else "povnyi"\n'
            'pathlib.Path(v.replace("<режим>", rezhym)).write_text(f"<!doctype html><title>{rezhym}</title><h1>{a[0]}</h1><p>Опис події — лише платно</p>", encoding="utf-8")\n'
            # ZAVDANNYA-178: «картка для мешканців» — лише числа
            'if "--kartka" in a: pathlib.Path(v.replace("<режим>", "kartka")).write_text(f"<!doctype html><title>kartka</title><h1>{a[0]}</h1><p>Скарг 1551: 12</p>", encoding="utf-8")\n',
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
        self.assertEqual(sum(1 for l in lysty if l['komu'] == 'bo@poshta.ua' and l['tema'].startswith('Довідка')), 2)

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
        lyst = next(l for l in lysty if l['komu'] == 'ana@poshta.ua' and l['tema'].startswith('Повний звіт'))
        shliakh = re.search(r'https?://[^/]+(/dovidka/\S+)', lyst['tekst']).group(1)
        st, h, html = self.vidkryty(shliakh)
        self.assertEqual(st, 200)
        self.assertIn('<title>povnyi</title>', html)
        self.assertIn('проспект Оболонський, 16', html)
        self.assertIn('no-store', h['cache-control'])
        st, _, html = self.vidkryty(shliakh.split('?')[0])
        self.assertEqual(st, 404, 'без ключа з листа — ні')
        self.assertNotIn('Опис події', html)
        # ZAVDANNYA-178: у листі — і посилання на картку для мешканців; відкривається своїм ключем, без описів справ
        kartka = re.search(r'https?://[^/]+(/dovidka/\S+/kartka/\?k=\S+)', lyst['tekst']).group(1)
        st, _, html = self.vidkryty(kartka)
        self.assertEqual(st, 200)
        self.assertIn('<title>kartka</title>', html)
        self.assertNotIn('Опис події', html)
        self.assertEqual(self.vidkryty(kartka.split('?')[0] + '?' + shliakh.split('?')[1])[0], 404, 'ключ довідки картку не відкриває')
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


class ShiApi(unittest.TestCase):
    """Переказ через API Claude (ZAVDANNYA-133, п. 3): формат як у `claude -p`, кеш інструкції, стеля, збої — без ключа."""

    ZAPYT = 'ІНСТРУКЦІЯ ' * 50 + '\nВид події: КРАД\nСтаття: 185\n\nФабула:\nвигадана фабула\n'

    class Klient:
        def __init__(self, vidpovid=None, zbii=None):
            self.vyklyky, self.vidpovid, self.zbii = [], vidpovid, zbii
            self.messages = self

        def create(self, **k):
            self.vyklyky.append(k)
            if self.zbii:
                raise self.zbii
            return self.vidpovid

    @staticmethod
    def vidpovid(tekst='{"perekaz": "вигадано"}', stop='end_turn'):
        from types import SimpleNamespace as N
        return N(content=[N(type='thinking', thinking=''), N(type='text', text=tekst)], stop_reason=stop,
                 usage={'input_tokens': 300, 'cache_read_input_tokens': 4000, 'cache_creation_input_tokens': 0, 'output_tokens': 400})

    def setUp(self):
        self.t = tempfile.mkdtemp(prefix='shi-')
        self.addCleanup(shutil.rmtree, self.t, True)
        self.env = {'ZVIT_KESH': self.t, 'SHI_STELIA_USD': '1', 'ANTHROPIC_API_KEY': 'ne-spravzhnii'}

    def test_format_i_kesh_instruktsii(self):
        k = self.Klient(self.vidpovid())
        v = shi_api.vyklykaty(self.ZAPYT, k, self.env)
        self.assertFalse(v['is_error'])
        self.assertEqual(v['result'], '{"perekaz": "вигадано"}')
        self.assertEqual(list(v['modelUsage']), ['claude-haiku-5-5'])
        # 300 × 0,10 + 4000 × 0,01 + 400 × 0,50 = 270 $ / млн
        self.assertAlmostEqual(v['total_cost_usd'], 0.00027, places=8)
        bl = k.vyklyky[0]['messages'][0]['content']
        self.assertEqual(bl[0]['cache_control'], {'type': 'ephemeral'})
        self.assertTrue(bl[1]['text'].startswith('\nВид події:'))
        self.assertEqual(bl[0]['text'] + bl[1]['text'], self.ZAPYT, 'запит не змінено, лише поділено')
        self.assertEqual(k.vyklyky[0]['output_config'], {'effort': 'low'})

    def test_stelia_mistsia(self):
        k = self.Klient(self.vidpovid())
        shi_api.Rakhunok(Path(self.t), 1).dodaty(1.0)
        v = shi_api.vyklykaty(self.ZAPYT, k, self.env)
        self.assertTrue(v['is_error'])
        self.assertTrue(v['bez_povtoru'])
        self.assertEqual(k.vyklyky, [], 'за стелею в API не ходимо')

    def test_zbii_i_vidmova(self):
        v = shi_api.vyklykaty(self.ZAPYT, self.Klient(zbii=OSError('мережа')), self.env)
        self.assertTrue(v['is_error'])
        self.assertFalse(v['bez_povtoru'], 'мережа — генератор спробує ще')
        v = shi_api.vyklykaty(self.ZAPYT, self.Klient(self.vidpovid('', 'refusal')), self.env)
        self.assertTrue(v['is_error'] and v['bez_povtoru'])

    def test_bez_kliucha_odrazu_pravyla(self):
        env = dict(self.env)
        del env['ANTHROPIC_API_KEY']
        v = shi_api.vyklykaty(self.ZAPYT, None, env)
        self.assertTrue(v['is_error'] and v['bez_povtoru'])

    def test_bez_kliucha_u_fajli(self):
        t = (KORIN / 'site' / 'prodazh' / 'shi_api.py').read_text(encoding='utf-8')
        self.assertNotRegex(t, r'sk-ant-[A-Za-z0-9]')


@unittest.skipUnless(node_z_sqlite(), 'немає Node 22+ з node:sqlite — перевірку форм на D1 пропущено')
class PerevirkaFormyD1(unittest.TestCase):
    """Щоденна перевірка форм на D1 (ZAVDANNYA-133, п. 4): той самий скрипт, що в GitHub Actions, проти місцевого сервера
    (справжній код Workers, режим «скоро», SQLite замість D1)."""

    @classmethod
    def setUpClass(cls):
        cls.port = vilnyi_port()
        cls.adresa = f'http://127.0.0.1:{cls.port}'
        env = dict(os.environ, PRODAZH='skoro', ADMIN_KLIUCH='kliuch-partnera')
        cls.srv = subprocess.Popen([node_z_sqlite(), str(WORKER / 'testy' / 'mistsevyi.mjs'), str(cls.port)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        for _ in range(100):
            try:
                urllib.request.urlopen(cls.adresa + '/__lysty', timeout=1)
                break
            except OSError:
                time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.srv.terminate()
        cls.srv.wait(5)
        cls.srv.stdout.close()

    def csv(self, t):
        return perevirka_formy.zapyt_sait('GET', f'{self.adresa}/api/admin/vyvantazhennia/{t}', kliuch='kliuch-partnera')[1]

    def test_perevirka_prokhodyt_i_prybyraie_lyshe_svoie(self):
        # справжня заявка людини — має лишитися після перевірки
        kod, _ = perevirka_formy.zapyt_sait('POST', f'{self.adresa}/api/forma/zayavka',
                                            {'shcho': 'analiz', 'misto': 'Київ', 'kontakt': 'liudyna@poshta.ua', 'zghoda': True, 'kanal': 'tg'},
                                            origin=self.adresa)
        self.assertEqual(kod, 201)
        kroky = []
        perevirka_formy.perevirka_d1(self.adresa + '/', 'kliuch-partnera', vyvid=kroky.append)
        self.assertEqual(len(kroky), 8, kroky)
        self.assertIn('liudyna@poshta.ua', self.csv('zayavka'))
        self.assertEqual(perevirka_formy.ryadky_perevirky(self.csv('zayavka')), 0)
        self.assertEqual(perevirka_formy.ryadky_perevirky(self.csv('podiya')), 0)

    def test_khybnyi_kliuch_chervonyi(self):
        with self.assertRaises(perevirka_formy.Zbii):
            perevirka_formy.perevirka_d1(self.adresa, 'ne-toi', vyvid=lambda *_: None)
        perevirka_formy.zapyt_sait('POST', f'{self.adresa}/api/admin/perevirka', kliuch='kliuch-partnera')

    def test_bez_kliucha_prybyraty_ne_mozhna(self):
        kod, _ = perevirka_formy.zapyt_sait('POST', f'{self.adresa}/api/admin/perevirka')
        self.assertEqual(kod, 401)

    def test_saity_nemaie_chervonyi(self):
        with self.assertRaises(perevirka_formy.Zbii):
            perevirka_formy.perevirka_d1('http://127.0.0.1:9', 'k', vyvid=lambda *_: None)


class ShablonVydavacha(unittest.TestCase):
    """Шаблон запуску видавача для репозиторію партнера (ZAVDANNYA-133): вимкнений до налаштування, ключі — лише секрети."""

    def test_shablon(self):
        t = (KORIN / 'site' / 'prodazh' / 'github' / 'vydavach.yml').read_text(encoding='utf-8')
        self.assertIn("if: ${{ vars.VYDAVACH == 'uvimknuto' }}", t)
        self.assertIn('workflow_dispatch:', t)
        self.assertIn('cancel-in-progress: false', t, 'новий поштовх не скасовує запуск, що видає довідку')
        for sekret in ('MV_DANI_TOKEN', 'VYDACHA_KLIUCH', 'ANTHROPIC_API_KEY'):
            self.assertIn('${{ secrets.%s }}' % sekret, t)
        self.assertIn('--do-porozhnoi', t)
        self.assertIn('site/prodazh/shi_api.py', t)
        self.assertNotRegex(t, r'sk-ant-|ghp_|github_pat_')
        self.assertNotIn('schedule:', t, 'розклад — у Workers (кожні 10 хв), щоб не палити хвилини GitHub порожніми запусками')


if __name__ == '__main__':
    unittest.main()


class SudovaPraktyka135(unittest.TestCase):
    """ZAVDANNYA-135: довідка «Судової практики» через того самого видавача; таблиці юриста — у сховище R2, не на сайт."""

    def test_tovary_prodaiutsia_lyshe_z_ofertoiu(self):
        self.assertIn('spdovidka', T.NA_PRODAZH)
        self.assertIn('spyurist', T.NA_PRODAZH)
        for t in T.NE_V_OFERTI:
            self.assertNotIn(t, T.prodaietsia(), 'товар без оферти не продається')
        self.assertEqual((T.REZHYM['spdovidka'], T.PERIOD_MISIATSIV['spyurist'], T.DOVIDOK['spyurist']), ('sp', 1, 3))

    def test_vydavach_sp_inshyi_generator_z_parametramy(self):
        with tempfile.TemporaryDirectory() as t:
            src = Path(t) / 'src'
            (src / 'zvit').mkdir(parents=True)
            (src / 'zvit' / 'zibraty.py').write_text('raise SystemExit(5)\n', encoding='utf-8')
            (src / 'sp_dovidka.py').write_text(
                'import sys, json\na = sys.argv[1:]\nv = a[a.index("--vyhid") + 1]\n'
                'open(v, "w", encoding="utf-8").write("<!doctype html>" + json.dumps(a, ensure_ascii=False))\n', encoding='utf-8')
            d = {'id': 'dabc', 'rezhym': 'sp', 'adresa': 'ст. 130 КУпАП — усі суди міста',
                 'parametry': {'stattia': 'ст.130 КУпАП', 'sud': 'Голосіївський', 'chastyna': '1'}}
            f, kartka = vydavach.zibraty(src / 'zvit' / 'zibraty.py', d, Path(t), shi=True)
            self.assertIsNotNone(f)
            self.assertIsNone(kartka, 'у «Судової практики» картки для мешканців немає')
            a = json.loads(f.read_text(encoding='utf-8')[len('<!doctype html>'):])
            self.assertEqual(json.loads(a[a.index('--parametry') + 1]), d['parametry'])
            self.assertNotIn('--shi', a, 'у довідці «Судової практики» ШІ немає')
            self.assertEqual(a[a.index('--nomer') + 1], 'dabc')

    def test_praktyka_r2_po_failu_na_stattiu(self):
        import praktyka_r2
        dani = {'versiia': '2026-11-19', 'stroky': ['ст.130 КУпАП'], 'statti': [
            {'kodeks': 'КУпАП', 'nomer': '130', 'nazva': 'Н', 'kat': ['штраф'], 'pokarano': ['штраф'], 'ryadky': [['Г', '2025', '1', 'штраф', '', 5, {}]]},
            {'kodeks': 'КК', 'nomer': '185', 'nazva': 'К', 'kat': ['штраф'], 'pokarano': ['штраф'], 'ryadky': []}]}
        with tempfile.TemporaryDirectory() as t:
            dz = Path(t) / 'sp.json'
            dz.write_text(json.dumps(dani, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(praktyka_r2.main([str(dz), '--do-teky', str(Path(t) / 'r2')]), 0)
            r = Path(t) / 'r2' / 'praktyka'
            self.assertEqual(json.loads((r / 'potochna.json').read_text(encoding='utf-8')), {'versiia': '2026-11-19'})
            st = json.loads((r / '2026-11-19' / 'kupap-130.json').read_text(encoding='utf-8'))
            self.assertTrue(st['strok'])
            self.assertEqual(st['stattia'], 'ст.130 КУпАП')
            self.assertFalse(json.loads((r / '2026-11-19' / 'kk-185.json').read_text(encoding='utf-8'))['strok'])

    def test_vypusk_z_release_xz(self):
        """ZAVDANNYA-195: з 21.11 у Release лише .db.xz — видавач і лист «Стежу» беруть вузький, розпаковують і перевіряють,
        що це база випуску; старий events-*.db — теж; немає нічого чи не база — зупинка, без «готового» файла."""
        import lzma, sqlite3, tempfile
        sys.path.insert(0, str(KORIN / 'site' / 'prodazh'))
        import vypusk_z_release as VR
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            def baza(f, versiia):
                c = sqlite3.connect(f); c.execute('CREATE TABLE release (versiia TEXT)')
                c.execute('INSERT INTO release VALUES (?)', (versiia,)); c.commit(); c.close()
            baza(t / 'v.db', 'vuzkyi'); baza(t / 'p.db', 'povnyi')
            rel = t / 'rel'; rel.mkdir()
            for src, nazva in (('v.db', 'vuzkyi-events-2026-11-21.db.xz'), ('p.db', 'events-2026-11-21.db.xz')):
                with open(t / src, 'rb') as f, lzma.open(rel / nazva, 'wb') as g:
                    g.write(f.read())
            for argv, treba in (([], 'vuzkyi'), (['--povnyi'], 'povnyi')):
                self.assertEqual(VR.main([str(rel), str(t / 'out.db'), *argv]), 0)
                c = sqlite3.connect(t / 'out.db')
                self.assertEqual(c.execute('SELECT versiia FROM release').fetchone()[0], treba)
                c.close()
            stara = t / 'stara'; stara.mkdir()
            (t / 'p.db').rename(stara / 'events-2026-11-08.db')
            self.assertEqual(VR.vybraty(stara).name, 'events-2026-11-08.db')
            pusta = t / 'pusta'; pusta.mkdir()
            self.assertEqual(VR.main([str(pusta), str(t / 'nema.db')]), 1)
            (pusta / 'events-2026-11-21.db.xz').write_bytes(lzma.compress(b'not a database' * 100))
            self.assertEqual(VR.main([str(pusta), str(t / 'nema.db')]), 1)
            self.assertFalse((t / 'nema.db').exists() or (t / 'nema.db.chast').exists())

    def test_workflows_na_vypusku_21_11(self):
        """ZAVDANNYA-195: видавач і лист — .db.xz через vypusk_z_release.py; перший лист «Стежу» — без «нового»."""
        for f in ('vydavach.yml', 'lyst_stezhu.yml'):
            t = (KORIN / 'site' / 'prodazh' / 'github' / f).read_text(encoding='utf-8')
            self.assertIn("'vuzkyi-events-*.db.xz'", t, f)
            self.assertIn('vypusk_z_release.py', t, f)
            self.assertNotIn("--pattern 'events-*.db' --output", t, f)
        t = (KORIN / 'site' / 'prodazh' / 'github' / 'lyst_stezhu.yml').read_text(encoding='utf-8')
        self.assertIn('POR="--pershyi"', t)
        self.assertIn('!= "${{ vars.VYPUSK }}"', t)

    def test_workflow_bere_dani_sudovoi_praktyky(self):
        t = (KORIN / 'site' / 'prodazh' / 'github' / 'vydavach.yml').read_text(encoding='utf-8')
        self.assertIn('SP_DANI:', t)
        self.assertIn("--pattern 'sp-dovidka-*.json'", t)
