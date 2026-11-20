"""Сайт до запуску (ZAVDANNYA-132): перемикач «скоро», форми в базі сайту, дані партнера, П4, robots.txt, лічба відвідувань,
скрипт викладки (site/vyklasty.py) — на штучному випуску з tests/test_sait.py. Наскрізно: зібраний сайт + справжній
скрипт Workers (site/worker/testy/mistsevyi.mjs) + перевірки, які скрипт викладки робить на живому сайті.

Запуск: python -m pytest -q tests/test_zapusk.py
"""
from __future__ import annotations

import json
import lzma
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(KORIN / 'site' / 'zahlushka'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_sait import BUDYNKY, YE_H3, stvoryty_bazu, stvoryty_pereimenuvannya  # noqa: E402

D1 = '0123abcd-0000-4000-8000-0123456789ab'
TOKEN = '0123456789abcdef0123456789abcdef'
ZAPOVNENNYA = json.loads((KORIN / 'site' / 'zapovnennya.zrazok.json').read_text(encoding='utf-8'))
MISTSE = re.compile(r"\[[А-ЯІЇЄҐ][А-ЯІЇЄҐ ,'’-]*\]")


def node_z_sqlite() -> str | None:
    node = shutil.which('node')
    if not node:
        return None
    return node if subprocess.run([node, '-e', "require('node:sqlite')"], capture_output=True).returncode == 0 else None


def wrangler_konfig(teka: Path) -> dict:
    return json.loads((teka / 'wrangler.jsonc').read_text(encoding='utf-8').split('\n', 1)[1])


@unittest.skipUnless(YE_H3, 'немає бібліотеки h3 — збирання сайту пропущено')
class Zapusk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zibraty_sait
        import tsiny
        cls.zs, cls.T = zibraty_sait, tsiny
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        cls.baza, cls.pereim, cls.budynky = t / 'events-2026-11-08.db', t / 'pereim.csv', t / 'budynky.json'
        stvoryty_bazu(cls.baza)
        stvoryty_pereimenuvannya(cls.pereim)
        cls.budynky.write_text(json.dumps(BUDYNKY, ensure_ascii=False), encoding='utf-8')
        cls.skoro = t / 'skoro'
        cls.zv_skoro = cls.zibraty(cls.skoro, khostynh='workers', oplata='skoro', zapovnennya=ZAPOVNENNYA,
                                   dlya_publikatsiyi=True, cf_analityka=TOKEN, domen='moyavulytsya.com.ua',
                                   prodazh={'d1': D1, 'servis': None, 'adresa': 'https://moyavulytsya.com.ua',
                                            'poshta': 'zahlushka', 'vars': {'POSHTA_PARTNERA': 'p@moyavulytsya.com.ua'}})
        cls.tak = t / 'tak'
        cls.zv_tak = cls.zibraty(cls.tak, khostynh='workers', oplata='tak',
                                 prodazh={'d1': D1, 'servis': 'test', 'adresa': 'https://moyavulytsya.com.ua', 'poshta': 'zahlushka'})

    @classmethod
    def zibraty(cls, vykhid, **kw):
        try:
            return cls.zs.zibraty_sait(cls.baza, vykhid, cls.pereim, KORIN / 'data' / 'borders.json',
                                       adresa_saitu='https://moyavulytsya.com.ua', budynky=cls.budynky, **kw)
        finally:
            cls.T.OPLATA['rezhym'] = 'skoro'
            cls.zs.CSP, cls.zs.ANALITYKA = cls.zs.csp_i_analityka('')

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def budynok(self, teka: Path, zv: dict) -> str:
        import khostynh as KH
        slug = 'khreshchatyk/22'
        n = KH.fnv1a(slug) % zv['pachok_budynkiv']
        return KH.rozpakuvaty((teka / '_budynky' / KH.nazva_pachky(n, False)).read_bytes(), slug).decode('utf-8')

    # ------------------------------------------------------------ 1. перемикач «скоро»

    def test_skoro_na_vsikh_knopkakh_oplaty(self):
        """У «скоро» кожна кнопка, що веде на /oplata/, має другий рядок «Скоро — залиште пошту»; ціни й адреси ті самі."""
        knopka = re.compile(r'<a class="knopka[^"]*" href="/oplata/\?[^"]*">(.*?)</a>', re.S)
        vsogo = 0
        for f in list(self.skoro.rglob('*.html')) + [None]:
            t = self.budynok(self.skoro, self.zv_skoro) if f is None else f.read_text(encoding='utf-8')
            for m in knopka.finditer(t):
                if m.group(1) == 'Залишити пошту':      # вітрина «Судова практика — скоро»: це й так «залиште пошту»
                    continue
                vsogo += 1
                self.assertIn('<small class="knopka__skoro">Скоро — залиште пошту</small>', m.group(1), f)
        self.assertGreater(vsogo, 10)
        b = self.budynok(self.skoro, self.zv_skoro)
        self.assertEqual(b.count('Скоро — залиште пошту'), 3)
        self.assertIn(f'Довідка — {self.T.tsina("dovidka")}', b)
        self.assertIn('href="/oplata/?tovar=dovidka&amp;budynok=', b)
        self.assertEqual(self.zv_skoro['oplata'], 'skoro')

    def test_tak_bez_skoro(self):
        """Оплату ввімкнено — жодного «Скоро — залиште пошту» на кнопках; ті самі ціни й адреси кнопок."""
        for f in self.tak.rglob('*.html'):
            t = f.read_text(encoding='utf-8')
            for m in re.finditer(r'<a class="knopka[^"]*knopka--skoro" href="([^"]+)"', t):
                tovar = re.search(r'tovar=([a-z]+)', m.group(1)).group(1)
                self.assertNotIn(tovar, self.T.prodaietsia(), f'{f}: товар у продажу, а кнопка «скоро»')
        b = self.budynok(self.tak, self.zv_tak)
        self.assertIn(f'>Довідка — {self.T.tsina("dovidka")}</a>', b)
        k = wrangler_konfig(Path(self.zv_tak['teka_workera']))
        self.assertEqual((k['vars']['PRODAZH'], k['vars']['PLATIZHNYI_SERVIS']), ('tak', 'test'))
        self.assertIn('r2_buckets', k)
        self.assertEqual(k['triggers'], {'crons': ['17 2 * * *', '*/10 * * * *']}, 'щодня: прибирання й лист ОСББ (П7); кожні 10 хв — черга видавача')

    def test_wrangler_skoro(self):
        k = wrangler_konfig(Path(self.zv_skoro['teka_workera']))
        self.assertEqual(k['vars']['PRODAZH'], 'skoro')
        self.assertNotIn('PLATIZHNYI_SERVIS', k['vars'])
        self.assertEqual(k['d1_databases'][0]['database_id'], D1)
        self.assertEqual(k['d1_databases'][0]['database_name'], 'moya-vulytsya-prodazh')
        self.assertNotIn('r2_buckets', k)
        self.assertEqual(k['routes'], [{'pattern': 'moyavulytsya.com.ua', 'custom_domain': True}])
        self.assertTrue(k['keep_vars'], 'змінні з панелі Cloudflare не стираються')
        self.assertEqual(k['vars']['POSHTA_PARTNERA'], 'p@moyavulytsya.com.ua')
        self.assertNotRegex(json.dumps(k), r'(?i)token|secret|ключ|private')

    def test_pomylky_peremykacha(self):
        t = Path(self.tmp.name)
        with self.assertRaisesRegex(SystemExit, 'лише з сервером продажу'):
            self.zibraty(t / 'x1', khostynh='workers', oplata='tak', prodazh={'d1': D1, 'servis': None})
        with self.assertRaisesRegex(SystemExit, 'Невідомий режим'):
            self.zibraty(t / 'x2', oplata='zaraz')
        with self.assertRaisesRegex(SystemExit, 'Незаповнені'):
            self.zibraty(t / 'x3', khostynh='workers', zapovnennya={'ВЛАСНИК': 'ФОП'}, dlya_publikatsiyi=True,
                         prodazh={'d1': D1, 'servis': None, 'adresa': 'https://moyavulytsya.com.ua'})
        with self.assertRaisesRegex(SystemExit, 'Токен'):
            self.zibraty(t / 'x4', cf_analityka='<script>')
        import khostynh as KH
        with self.assertRaisesRegex(SystemExit, 'Невідомі змінні'):
            KH.pidhotuvaty_worker(t / 'x5', 1, prodazh={'d1': D1, 'vars': {'LIQPAY_PRIVATE_KEY': 'x'}}, oplata='skoro')

    # ------------------------------------------------------------ форми, дані партнера

    def test_formy_u_bazu_saitu_i_dani_partnera(self):
        z = self.skoro / 'zahlushka'
        self.assertIn("skhovyshche: 'sait'", (z / 'config.js').read_text(encoding='utf-8'))
        for f in z.glob('*.html'):
            t = f.read_text(encoding='utf-8')
            self.assertNotIn('supabase', t, f)
            self.assertIsNone(MISTSE.search(t), f'{f.name}: незаповнене місце')
        self.assertIn(ZAPOVNENNYA['ВЛАСНИК'].replace("'", '&#x27;'), (z / 'oferta.html').read_text(encoding='utf-8'))
        self.assertEqual(self.zv_skoro['formy'], 'sait')
        # без бази (Pages) — як раніше: Supabase зі змінних середовища (MV-8)
        self.assertEqual(self.zv_tak['formy'], 'sait')

    def test_pages_bez_bazy_iak_ranishe(self):
        t = Path(self.tmp.name) / 'pages'
        zv = self.zibraty(t)
        self.assertEqual((zv['formy'], zv['oplata']), ('supabase', 'skoro'))
        self.assertIn('ZAMINITY', (t / 'zahlushka' / 'config.js').read_text(encoding='utf-8'))
        self.assertIn('Оплата скоро', (t / 'oplata' / 'index.html').read_text(encoding='utf-8'))
        self.assertGreater(zv['nezapovneno'], 0, 'без даних партнера — є незаповнені (для перегляду можна)')

    # ------------------------------------------------------------ П4, robots, лічба

    def test_p4_pro_dani(self):
        t = (self.skoro / 'pro-dani' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('Рішення, що ще не набрали законної сили', t)
        self.assertRegex(t, r'не минув строк на оскарження або подано апеляцію')
        self.assertIn('пояснення одне для всього сайту', t)

    def test_robots_i_karta_saitu(self):
        r = (self.skoro / 'robots.txt').read_text(encoding='utf-8')
        for z in ('/oplata/', '/kabinet/', '/dovidka/', '/api/', '/zahlushka/zvernennya.html'):
            self.assertIn(f'Disallow: {z}\n', r)
        self.assertIn('Sitemap: https://moyavulytsya.com.ua/sitemap.xml', r)
        s = (self.skoro / 'sitemap.xml').read_text(encoding='utf-8')
        self.assertIn('<loc>https://moyavulytsya.com.ua/</loc>', s)
        self.assertNotIn('/oplata/', s)

    def test_lichba_bez_kuki(self):
        """Cloudflare Web Analytics: скрипт на кожній сторінці, де він є, — дозволений у CSP; без токена — ніде."""
        beacon = f'data-cf-beacon=\'{{"token": "{TOKEN}", "spa": false}}\''
        z_lichboiu = 0
        for f in self.skoro.rglob('*.html'):
            t = f.read_text(encoding='utf-8')
            if beacon in t:
                z_lichboiu += 1
                csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', t).group(1)
                self.assertIn('script-src \'self\' https://static.cloudflareinsights.com', csp, f)
                self.assertIn('https://cloudflareinsights.com', csp, f)
        for shl in ('index.html', 'karta/index.html', 'pro-dani/index.html', 'zahlushka/oferta.html', 'zahlushka/index.html'):
            self.assertIn(beacon, (self.skoro / shl).read_text(encoding='utf-8'), shl)
        self.assertGreater(z_lichboiu, 20)
        self.assertIn(beacon, self.budynok(self.skoro, self.zv_skoro))
        for f in self.tak.rglob('*.html'):
            self.assertNotIn('cloudflareinsights', f.read_text(encoding='utf-8'), f)

    # ------------------------------------------------------------ скрипт викладки

    def test_vyklasty_zminni_i_faily(self):
        import vyklasty as V
        stari = dict(os.environ)
        try:
            for k in list(os.environ):
                if k.startswith('MV_') or k.startswith('CLOUDFLARE_'):
                    del os.environ[k]
            with self.assertRaises(V.Zupynka) as e:
                V.zminni(suho=False)
            for n in ('MV_DOMEN', 'MV_D1', 'MV_ZAPOVNENNYA', 'CLOUDFLARE_API_TOKEN'):
                self.assertIn(n, str(e.exception))
            self.assertEqual(V.zminni(suho=True)['oplata'], 'skoro')
            os.environ.update(MV_OPLATA='tak')
            with self.assertRaisesRegex(V.Zupynka, 'MV_PLATIZHNYI_SERVIS'):
                V.zminni(suho=True)
            # ZAVDANNYA-150, п. 4: продаж підписки — лише з картою підписника й щомісячним листом
            os.environ.update(MV_PLATIZHNYI_SERVIS='test')
            with self.assertRaisesRegex(V.Zupynka, 'MV_KARTA_R2=tak'):
                V.zminni(suho=True)
            os.environ.update(MV_KARTA_R2='tak')
            with self.assertRaisesRegex(V.Zupynka, 'MV_LYST_STEZHU=tak'):
                V.zminni(suho=True)
            os.environ.update(MV_LYST_STEZHU='tak')
            self.assertEqual(V.zminni(suho=True)['oplata'], 'tak')
            os.environ.update(MV_OPLATA='skoro', MV_DOMEN='https://evil.test/шлях')
            with self.assertRaisesRegex(V.Zupynka, 'MV_DOMEN'):
                V.zminni(suho=True)
        finally:
            os.environ.clear()
            os.environ.update(stari)
        # тека випуску: .db.xz розпаковується; пробні файли — лише якщо інших немає; чого немає — None
        t = Path(self.tmp.name) / 'reliz'
        t.mkdir()
        with open(self.baza, 'rb') as vh, lzma.open(t / 'events-2026-11-21.db.xz', 'wb') as out:
            out.write(vh.read())
        shutil.copyfile(self.budynky, t / 'budynky-2026-11-21.json')
        (t / 'probnyi-perekazy-2026-11-21.json').write_text('{}', encoding='utf-8')
        (t / 'perekazy-2026-11-21.json').write_text('{}', encoding='utf-8')
        (t / 'koloda-2026-11-21.json').write_text('{"zlamana": true}', encoding='utf-8')
        robocha = Path(self.tmp.name) / 'robocha'
        robocha.mkdir()
        f = V.faily_vypusku(t, robocha, None)
        self.assertEqual(f['baza'], robocha / 'events-2026-11-21.db')
        self.assertEqual(f['baza'].read_bytes(), self.baza.read_bytes())
        self.assertEqual(f['perekazy'].name, 'perekazy-2026-11-21.json')
        self.assertIsNone(f['koloda'], 'колода, що не проходить перевірку, — сайт без гри, а не зупинка')
        self.assertIsNone(f['sudova_praktyka'])

    @unittest.skipUnless(node_z_sqlite(), 'немає Node 22+ — наскрізну перевірку пропущено')
    def test_naskrizno_perevirky_vyklasty(self):
        """Зібраний сайт «скоро» + справжній скрипт Workers локально → ті самі перевірки, що скрипт викладки робить на
        живому сайті: усі проходять; «скоро» записує пошту; форма пише в базу."""
        import vyklasty as V
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        p = subprocess.Popen([node_z_sqlite(), str(KORIN / 'site' / 'worker' / 'testy' / 'mistsevyi.mjs'), str(port), str(self.skoro)],
                             env={**os.environ, 'PRODAZH': 'skoro'}, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            adresa = f'http://127.0.0.1:{port}'
            for _ in range(100):
                try:
                    socket.create_connection(('127.0.0.1', port), timeout=0.2).close()
                    break
                except OSError:
                    time.sleep(0.1)
            # robots.txt і карта сайту зібрані під справжній домен — перевіряємо решту; їх — тести вище.
            budynok = V.pershyi_budynok(self.skoro)
            self.assertRegex(budynok, r'^/budynok/[a-z0-9-]+/[a-z0-9-]+/$')
            rez = {n: (ok, d) for n, ok, d in V.perevirky(adresa, 'skoro', budynok)}
            rez.pop('robots.txt')
            for n, (ok, d) in rez.items():
                self.assertTrue(ok, f'{n}: {d}')
            st, t = V.vidkryty(adresa + '/oplata/?tovar=zvit&budynok=/budynok/khreshchatyk/22/')
            self.assertEqual(st, 200)
            self.assertIn('вулиця Хрещатик, 22', t)
        finally:
            p.terminate()
            p.wait(timeout=10)


if __name__ == '__main__':
    unittest.main()
