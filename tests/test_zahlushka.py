"""Перевірки сторінки-заглушки (ZAVDANNYA-02, п. 9).

Запуск: python -m unittest tests.test_zahlushka -v
Перевірки в браузері запускаються, лише якщо встановлено Playwright і Chrome
(інакше — позначка «пропущено» з причиною).
"""
from __future__ import annotations

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
SAIT = KORIN / 'site' / 'zahlushka'
sys.path.insert(0, str(SAIT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import zibraty  # noqa: E402
import perevirka_formy  # noqa: E402
import zahlushka_pidmina  # noqa: E402

# Дозволені домени в сторінках: лише сховище з MV-8.
DOZVOLENI_DOMENY = ('supabase.co',)
# Підказки-приклади у формі — не справжні контакти.
DOZVOLENI_KONTAKTY = {'name@pošta.ua', 'name@poshta.ua'}
# Файли, де слово service_role / sb_secret_ стоїть як пояснення або перевірка, а не ключ.
POYASNENNYA_KLYUCHA = {
    'ZAVDANNYA-02.md', 'ZVIT-02.md', 'docs/zahlushka-skhema.sql', 'docs/08-stan.md',
    'site/zahlushka/zibraty.py', 'site/zahlushka/perevirka_formy.py',
    '.github/workflows/perevirka-formy.yml', 'tests/test_zahlushka.py',
}


def faily_saitu(*rozshyrennya):
    return sorted(p for p in SAIT.rglob('*') if p.is_file() and p.suffix in rozshyrennya)


def faily_repozytoriyu():
    vyvid = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=KORIN)
    for nazva in filter(None, vyvid.decode().split('\0')):
        p = KORIN / nazva
        if p.is_file():
            yield nazva, p


def chytaty(p: Path) -> str | None:
    raw = p.read_bytes()
    if b'\0' in raw:
        return None
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return None


class StorinkyTests(unittest.TestCase):
    def test_nemaie_storonnikh_domeniv(self):
        """У HTML, CSS і JS немає адрес сторонніх доменів, крім сховища MV-8."""
        adresa = re.compile(r'(?:https?:)?//([A-Za-z0-9*.-]+\.[A-Za-z]{2,})', re.I)
        pohani = []
        for p in faily_saitu('.html', '.css', '.js'):
            for m in adresa.finditer(p.read_text(encoding='utf-8')):
                domen = m.group(1).lower()
                if not any(domen == d or domen.endswith('.' + d) for d in DOZVOLENI_DOMENY):
                    pohani.append(f'{p.name}: {m.group(0)}')
        self.assertEqual(pohani, [], 'Знайдено сторонні домени')

    def test_nemaie_trekeriv_i_skhovyshcha_v_brauzeri(self):
        zaboroneno = re.compile(r'localStorage|sessionStorage|document\.cookie|indexedDB|'
                                r'googletagmanager|google-analytics|gtag\(|fbq\(|hotjar|captcha|'
                                r'fonts\.googleapis|fonts\.gstatic', re.I)
        for p in faily_saitu('.html', '.js'):
            self.assertIsNone(zaboroneno.search(p.read_text(encoding='utf-8')), p.name)

    def test_shryfty_z_saitu(self):
        css = (SAIT / 'styli.css').read_text(encoding='utf-8')
        for shryft in re.findall(r'url\(([^)]+)\)', css):
            self.assertTrue((SAIT / shryft).is_file(), shryft)
        self.assertIn("font-family: 'Inter'", css)
        self.assertIn("font-family: 'Manrope'", css)
        self.assertTrue((SAIT / 'shryfty' / 'OFL-Inter.txt').is_file())
        self.assertTrue((SAIT / 'shryfty' / 'OFL-Manrope.txt').is_file())

    def test_tsiny_yak_u_mv3(self):
        """Ціни на сторінці: 690 грн аналіз, 299 грн/міс підписка (MV-11) — і жодних інших."""
        rishennya = (KORIN / 'RISHENNYA.md').read_text(encoding='utf-8')
        self.assertIn('**299 грн на місяць**', rishennya)
        self.assertIn('**690 грн**', rishennya)
        html = (SAIT / 'index.html').read_text(encoding='utf-8')
        tsiny = {int(x) for x in re.findall(r'(\d+)\s*грн', html)}
        self.assertEqual(tsiny, {0, 299, 690})
        for blok in re.findall(r'data-tsina="analiz">([^<]+)', html):
            self.assertTrue(blok.startswith('690 грн'), blok)
        for blok in re.findall(r'data-tsina="pidpyska">(.+?)</span>', html):
            self.assertRegex(blok, r'^299 грн(\s*<small>/ місяць</small>|/міс)$')
        self.assertIn('Аналіз адреси — 690 грн', html)
        self.assertIn('Підписка — 299 грн / місяць', html)

    def test_zghoda_u_formi(self):
        html = (SAIT / 'index.html').read_text(encoding='utf-8')
        pole = re.search(r'<input[^>]*id="zghoda"[^>]*>', html)
        self.assertIsNotNone(pole, 'У формі немає згоди')
        self.assertIn('type="checkbox"', pole.group(0))
        self.assertNotIn('checked', pole.group(0), 'Згода не повинна бути відмічена заздалегідь')
        js = (SAIT / 'nadsylannya.js').read_text(encoding='utf-8')
        self.assertIn("dani.zghoda !== true", js)
        self.assertIn('class="pastka"', html, 'Немає поля-пастки для ботів')

    def test_zrazok_pomichenyi(self):
        html = (SAIT / 'zrazok.html').read_text(encoding='utf-8')
        self.assertIn('Зразок: адреса і всі числа вигадані', html)
        self.assertNotIn('{{', html)

    def test_polityka_shablon(self):
        html = (SAIT / 'polityka.html').read_text(encoding='utf-8')
        self.assertIn('<!-- ШАБЛОН — ПЕРЕВІРИТИ ПЕРЕД ПУБЛІКАЦІЄЮ', html)
        for mistse in ('[ВЛАСНИК]', '[КОНТАКТ]', '[СЕРВІС І КРАЇНА ЗБЕРІГАННЯ]'):
            self.assertIn(mistse, html)
        for tekst in ('ст', 'статтею 8', 'стаття 11', '6 місяців', 'Нікому', 'без кукі'):
            self.assertIn(tekst.lower(), html.lower())

    def test_imya_vlasnyka_porozhnie(self):
        html = (SAIT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('[НАЗВА ВЛАСНИКА ПРОЄКТУ]', html)


class KlyuchiIKontaktyTests(unittest.TestCase):
    def test_nemaie_klyuchiv(self):
        shablony = [
            re.compile(r'eyJ[A-Za-z0-9_-]{15,}'),              # ключ-JWT Supabase
            re.compile(r'\bsk_[A-Za-z0-9_]{12,}'),              # секретні ключі сервісів
            re.compile(r'sb_(?:secret|publishable)_[A-Za-z0-9_-]{10,}'),
            re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}'),
        ]
        slovo = re.compile(r'service_role|sb_secret_')
        znaideno = []
        for nazva, p in faily_repozytoriyu():
            tekst = chytaty(p)
            if tekst is None:
                continue
            for sh in shablony:
                if sh.search(tekst):
                    znaideno.append(f'{nazva}: {sh.pattern}')
            if nazva not in POYASNENNYA_KLYUCHA and slovo.search(tekst):
                znaideno.append(f'{nazva}: service_role')
        self.assertEqual(znaideno, [], 'Схоже на ключ у файлах')

    def test_config_lyshe_zrazok(self):
        self.assertTrue((SAIT / 'config.example.js').is_file())
        tracked = subprocess.check_output(['git', 'ls-files', 'site/zahlushka/config.js'], cwd=KORIN)
        self.assertEqual(tracked.strip(), b'', 'config.js не повинен бути в git')
        ignored = subprocess.run(['git', 'check-ignore', '-q', 'site/zahlushka/config.js'], cwd=KORIN)
        self.assertEqual(ignored.returncode, 0, 'config.js має бути в .gitignore')
        zrazok = (SAIT / 'config.example.js').read_text(encoding='utf-8')
        self.assertIn('ZAMINITY', zrazok)

    def test_nemaie_kontaktiv(self):
        poshta = re.compile(r'[\w.+-]+@[\w-]+(?:\.[\w-]+)+')
        telefon = re.compile(r'\+?380\d{9}|\b0\d{2}[ -]?\d{3}[ -]?\d{2}[ -]?\d{2}\b')
        faily = [p for p in SAIT.rglob('*') if p.suffix in ('.html', '.js', '.css', '.py')]
        faily += [KORIN / 'docs' / 'zahlushka-skhema.sql', KORIN / 'docs' / 'zahlushka-chotyry-chysla.sql',
                  KORIN / '.github' / 'workflows' / 'perevirka-formy.yml']
        znaideno = []
        for p in faily:
            tekst = p.read_text(encoding='utf-8')
            for m in poshta.finditer(tekst):
                if m.group(0) not in DOZVOLENI_KONTAKTY:
                    znaideno.append(f'{p.name}: {m.group(0)}')
            for m in telefon.finditer(tekst):
                znaideno.append(f'{p.name}: {m.group(0)}')
        self.assertEqual(znaideno, [], 'Знайдено контакти')


class ZbyrannyaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    URL = 'https://abcdefghijklmnopqrst.supabase.co'
    ZAPOVNENNYA = {'НАЗВА ВЛАСНИКА ПРОЄКТУ': 'Умовна назва', 'ВЛАСНИК': 'Умовний власник',
                   'КОНТАКТ': 'умовний контакт', 'СЕРВІС І КРАЇНА ЗБЕРІГАННЯ': 'Умовний сервіс, ЄС',
                   'ДАТА': '01.01.2027', 'САЙТ': 'умовний-сайт'}

    def test_perehliad_bez_skhovyshcha(self):
        nezapovneni = zibraty.zibraty(self.tmp / 'z', '', '', {}, False)
        self.assertTrue(any('[НАЗВА ВЛАСНИКА ПРОЄКТУ]' in n for n in nezapovneni))
        self.assertIn('ZAMINITY', (self.tmp / 'z' / 'config.js').read_text(encoding='utf-8'))

    def test_publikatsiya_padaie_bez_imeni_vlasnyka(self):
        z = dict(self.ZAPOVNENNYA)
        del z['НАЗВА ВЛАСНИКА ПРОЄКТУ']
        with self.assertRaises(zibraty.PomylkaZbyrannya) as e:
            zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', z, True)
        self.assertIn('[НАЗВА ВЛАСНИКА ПРОЄКТУ]', str(e.exception))

    def test_publikatsiya_padaie_bez_mists_polityky(self):
        for mistse in ('ВЛАСНИК', 'КОНТАКТ', 'СЕРВІС І КРАЇНА ЗБЕРІГАННЯ'):
            z = dict(self.ZAPOVNENNYA)
            z[mistse] = '   '
            with self.assertRaises(zibraty.PomylkaZbyrannya, msg=mistse) as e:
                zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', z, True)
            self.assertIn(f'polityka.html: [{mistse}]', str(e.exception))

    def test_publikatsiya_padaie_bez_skhovyshcha(self):
        with self.assertRaises(zibraty.PomylkaZbyrannya):
            zibraty.zibraty(self.tmp / 'z', '', '', self.ZAPOVNENNYA, True)
        with self.assertRaises(zibraty.PomylkaZbyrannya):
            zibraty.zibraty(self.tmp / 'z', 'http://127.0.0.1:9', 'k', self.ZAPOVNENNYA, True)

    def test_sekretnyi_klyuch_ne_potrapliaie_v_storinku(self):
        # Умовний ключ-JWT з роллю service_role, складений тут же (не справжній).
        chastyna = base64.urlsafe_b64encode(json.dumps({'role': 'service_role'}).encode()).decode().rstrip('=')
        umovnyi = 'x.' + chastyna + '.x'
        with self.assertRaises(zibraty.PomylkaZbyrannya):
            zibraty.zibraty(self.tmp / 'z', self.URL, umovnyi, self.ZAPOVNENNYA, False)
        with self.assertRaises(zibraty.PomylkaZbyrannya):
            zibraty.zibraty(self.tmp / 'z', self.URL, 'sb_secret_' + 'x' * 3, self.ZAPOVNENNYA, False)

    def test_publikatsiya_prokhodyt_koly_vse_zapovneno(self):
        nezapovneni = zibraty.zibraty(self.tmp / 'z', self.URL, 'test-publichnyi', self.ZAPOVNENNYA, True)
        self.assertEqual(nezapovneni, [])
        index = (self.tmp / 'z' / 'index.html').read_text(encoding='utf-8')
        self.assertIn(f"connect-src 'self' {self.URL}", index)
        self.assertIn('Умовна назва', index)
        config = (self.tmp / 'z' / 'config.js').read_text(encoding='utf-8')
        self.assertIn(self.URL, config)


@unittest.skipUnless(shutil.which('node'), 'немає Node.js — перевірку модуля відправки пропущено')
class ModulVidpravkyTests(unittest.TestCase):
    """Модуль nadsylannya.js у Node з підміненим fetch."""

    SKRYPT = r'''
const fs = require('fs');
const vm = require('vm');
const zapyty = [];
const ctx = { window: {}, console, Promise, JSON, String, Error,
  fetch: (url, opt) => { zapyty.push({ url, opt }); return Promise.resolve({ ok: true, status: 201 }); } };
ctx.window.MV_CONFIG = { adresaSkhovyshcha: 'https://abcdefghijklmnopqrst.supabase.co/', publichnyiKlyuch: 'test-publichnyi' };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(process.argv[2], 'utf8'), ctx);
// модуль кладе себе у window
const N = ctx.window.MvNadsylannya;
(async () => {
  const rez = {};
  rez.bezZghody = await N.nadislatyZayavku({ shcho: 'analiz', misto: 'Київ', kontakt: '@test_nik', zghoda: false }).then(() => 'vidpravleno', () => 'vidmova');
  rez.zapytivPislyaVidmovy = zapyty.length;
  rez.zayavka = await N.nadislatyZayavku({ shcho: 'analiz', misto: 'Київ', adresa: '', kontakt: '@test_nik', zghoda: true, dzherelo: 'TikTok' });
  rez.podiya = await N.nadislatyPodiyu('pryishly', null);
  rez.nevidomaPodiya = await N.nadislatyPodiyu('shchos', 'x');
  rez.kanaly = ['telegram-obolon', '', null, 'zle zle', 'a'.repeat(41)].map(N.ochystytyKanal);
  rez.zapyty = zapyty.map(z => ({ url: z.url, metod: z.opt.method, zaholovky: z.opt.headers,
    tilo: JSON.parse(z.opt.body), credentials: z.opt.credentials, referrerPolicy: z.opt.referrerPolicy }));
  process.stdout.write(JSON.stringify(rez));
})();
'''

    def test_modul(self):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False) as f:
            f.write(self.SKRYPT)
        try:
            vyvid = subprocess.check_output(['node', f.name, str(SAIT / 'nadsylannya.js')], timeout=30)
        finally:
            os.unlink(f.name)
        r = json.loads(vyvid)
        self.assertEqual(r['bezZghody'], 'vidmova')
        self.assertEqual(r['zapytivPislyaVidmovy'], 0, 'Без згоди нічого не повинно надсилатися')
        self.assertTrue(r['zayavka'])
        self.assertFalse(r['nevidomaPodiya'])
        self.assertEqual(r['kanaly'], ['telegram-obolon', 'priamo', 'priamo', 'inshe', 'inshe'])
        z, p = r['zapyty']
        self.assertEqual(z['url'], 'https://abcdefghijklmnopqrst.supabase.co/rest/v1/zayavka')
        self.assertEqual(z['tilo'], {'shcho': 'analiz', 'misto': 'Київ', 'adresa': None,
                                     'kontakt': '@test_nik', 'zghoda': True, 'kanal': 'tiktok'})
        self.assertEqual(p['url'], 'https://abcdefghijklmnopqrst.supabase.co/rest/v1/podiya')
        self.assertEqual(p['tilo'], {'nazva': 'pryishly', 'kanal': 'priamo'})
        for zap in r['zapyty']:
            self.assertEqual(zap['metod'], 'POST')
            self.assertEqual(zap['credentials'], 'omit')
            self.assertEqual(zap['referrerPolicy'], 'no-referrer')
            self.assertEqual(zap['zaholovky']['Prefer'], 'return=minimal')
            self.assertNotIn('Authorization', zap['zaholovky'])  # ключ не JWT — лише apikey


class PerevirkaFormyTests(unittest.TestCase):
    """Скрипт перевірки двічі на добу — проти локальної підміни сховища."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.server, self.skh, self.url = zahlushka_pidmina.zapustyty(self.tmp)

    def tearDown(self):
        self.server.shutdown()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_perevirka_prokhodyt_i_prybyraie(self):
        self.skh.ryadky['podiya'].append({'id': 999, 'nazva': 'pryishly', 'kanal': 'tiktok', 'chas': ''})
        pochatok = time.monotonic()
        perevirka_formy.perevirka(self.url, zahlushka_pidmina.PUBLICHNYI, zahlushka_pidmina.SEKRETNYI, vyvid=lambda *_: None)
        self.trivalist = time.monotonic() - pochatok
        self.assertEqual(self.skh.ryadky['zayavka'], [])
        self.assertEqual([r['kanal'] for r in self.skh.ryadky['podiya']], ['tiktok'], 'Справжні події не чіпаємо')
        metody = [z[0] for z in self.skh.zapyty]
        self.assertEqual(metody.count('POST'), 2)
        self.assertEqual(metody.count('DELETE'), 2)
        for metod, _, zaholovky in self.skh.zapyty:
            klyuch = zaholovky.get('apikey')
            if metod == 'POST':
                self.assertEqual(klyuch, zahlushka_pidmina.PUBLICHNYI, 'Додавати — публічним ключем, як сторінка')
            if metod == 'DELETE':
                self.assertEqual(klyuch, zahlushka_pidmina.SEKRETNYI)

    def test_perevirka_chervona_pry_zboi(self):
        self.skh.zbii = True
        with self.assertRaises(perevirka_formy.Zbii):
            perevirka_formy.perevirka(self.url, zahlushka_pidmina.PUBLICHNYI, zahlushka_pidmina.SEKRETNYI, vyvid=lambda *_: None)

    def test_perevirka_chervona_pry_vytoku(self):
        # Якщо публічний ключ раптом може читати — це витік, запуск має бути червоним.
        with self.assertRaises(perevirka_formy.Zbii) as e:
            perevirka_formy.perevirka(self.url, zahlushka_pidmina.SEKRETNYI, zahlushka_pidmina.SEKRETNYI, vyvid=lambda *_: None)
        self.assertIn('ВИТІК', str(e.exception))

    def test_bez_zviazku(self):
        with self.assertRaises(perevirka_formy.Zbii):
            perevirka_formy.perevirka('http://127.0.0.1:9', 'a', 'b', vyvid=lambda *_: None)


def brauzer_dostupnyi():
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return None
    for shlyakh in (os.environ.get('MV_CHROME'), shutil.which('google-chrome'), shutil.which('chromium'),
                    shutil.which('chromium-browser')):
        if shlyakh:
            return shlyakh
    return None


CHROME = brauzer_dostupnyi()


@unittest.skipUnless(CHROME, 'немає Playwright або Chrome — перевірку в браузері пропущено')
class BrauzerTests(unittest.TestCase):
    """Справжній браузер + локальна підміна сховища: форма, чотири числа, помилка мережі."""

    @classmethod
    def setUpClass(cls):
        from playwright.sync_api import sync_playwright
        cls.tmp = Path(tempfile.mkdtemp())
        cls.server, cls.skh, cls.url = zahlushka_pidmina.zapustyty(str(cls.tmp))
        zibraty.zibraty(cls.tmp / 'zahlushka', cls.url, zahlushka_pidmina.PUBLICHNYI, {}, False)
        cls.pw = sync_playwright().start()
        cls.brauzer = cls.pw.chromium.launch(executable_path=CHROME, args=['--no-sandbox'])

    @classmethod
    def tearDownClass(cls):
        cls.brauzer.close()
        cls.pw.stop()
        cls.server.shutdown()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        self.skh.ryadky = {'zayavka': [], 'podiya': []}
        self.skh.zapyty.clear()
        self.skh.zbii = False

    def vidkryty(self, shyryna=1280, dzherelo='tiktok'):
        kontekst = self.brauzer.new_context(viewport={'width': shyryna, 'height': 900})
        storinka = kontekst.new_page()
        self.zovnishni = []
        self.pomylky = []
        storinka.on('request', lambda z: z.url.startswith(self.url) or z.url.startswith('data:') or self.zovnishni.append(z.url))
        storinka.on('console', lambda m: m.type == 'error' and self.pomylky.append(m.text))
        storinka.on('pageerror', lambda e: self.pomylky.append(str(e)))
        q = f'?dzherelo={dzherelo}' if dzherelo else ''
        storinka.goto(f'{self.url}/zahlushka/index.html{q}')
        storinka.wait_for_load_state('networkidle')
        return kontekst, storinka

    def podii(self):
        return [(p['nazva'], p['kanal']) for p in self.skh.ryadky['podiya']]

    def chekaty(self, umova, sekund=5):
        kinets = time.monotonic() + sekund
        while time.monotonic() < kinets:
            if umova():
                return True
            time.sleep(0.05)
        return umova()

    def test_povnyi_shlyakh_i_chotyry_chysla(self):
        kontekst, s = self.vidkryty()
        self.assertTrue(self.chekaty(lambda: ('pryishly', 'tiktok') in self.podii()))
        # Порожня адреса — події «adresa» немає.
        s.click('.poshuk__knopka')
        s.fill('#adresa', 'Хрещатик, 1')
        s.click('.poshuk__knopka')
        self.assertTrue(self.chekaty(lambda: ('adresa', 'tiktok') in self.podii()))
        self.assertEqual(self.podii().count(('adresa', 'tiktok')), 1)
        self.assertEqual(s.input_value('#adresa2'), 'Хрещатик, 1')
        # Кнопка «Передзамовити аналіз» у картці.
        s.click('[data-peredzamovyty="analiz"]')
        self.assertTrue(self.chekaty(lambda: ('peredzamovyty', 'tiktok') in self.podii()))
        self.assertEqual(s.input_value('#shcho'), 'analiz')
        # Без згоди — заявки немає.
        s.fill('#kontakt', '@test_nik')
        s.click('#forma-knopka')
        self.assertIn('згоди', s.inner_text('#forma-stan'))
        time.sleep(0.3)
        self.assertEqual(self.skh.ryadky['zayavka'], [])
        # Зі згодою — є.
        s.check('#zghoda')
        s.click('#forma-knopka')
        s.wait_for_selector('#vdacha', state='visible')
        self.assertIn('Ви в списку', s.inner_text('#vdacha'))
        self.assertIn('Напишемо, коли ваше місто відкриється', s.inner_text('#vdacha'))
        self.assertTrue(self.chekaty(lambda: ('kontakt', 'tiktok') in self.podii()))
        [z] = self.skh.ryadky['zayavka']
        self.assertEqual((z['shcho'], z['misto'], z['adresa'], z['kontakt'], z['zghoda'], z['kanal']),
                         ('analiz', 'Київ', 'Хрещатик, 1', '@test_nik', True, 'tiktok'))
        # Нічого, крім часу (його ставить сховище), назви й каналу.
        for p in self.skh.ryadky['podiya']:
            self.assertEqual(set(p) - {'id', 'chas'}, {'nazva', 'kanal'})
        # Без кукі, без сховища в браузері, без сторонніх доменів.
        self.assertEqual(kontekst.cookies(), [])
        self.assertEqual(s.evaluate('localStorage.length + sessionStorage.length'), 0)
        self.assertEqual(self.zovnishni, [])
        self.assertEqual(self.pomylky, [])
        for metod, shlyakh, zaholovky in self.skh.zapyty:
            self.assertNotIn('cookie', zaholovky)
            self.assertNotIn('referer', zaholovky)
        kontekst.close()

    def test_kanal_za_zamovchuvanniam(self):
        kontekst, s = self.vidkryty(dzherelo=None)
        self.assertTrue(self.chekaty(lambda: ('pryishly', 'priamo') in self.podii()))
        kontekst.close()

    def test_pastka_dlia_botiv(self):
        kontekst, s = self.vidkryty()
        s.fill('#kontakt', '@test_nik')
        s.check('#zghoda')
        s.evaluate("document.getElementById('sait').value = 'http-bot'")
        s.click('#forma-knopka')
        s.wait_for_selector('#vdacha', state='visible')
        time.sleep(0.3)
        self.assertEqual(self.skh.ryadky['zayavka'], [])
        self.assertNotIn(('kontakt', 'tiktok'), self.podii())
        kontekst.close()

    def test_pomylka_merezhi_i_sprobuvaty_shche(self):
        self.skh.zbii = True
        kontekst, s = self.vidkryty()
        s.fill('#kontakt', 'test@example.invalid')
        s.check('#zghoda')
        s.click('#forma-knopka')
        s.wait_for_selector('#zboi', state='visible')
        self.assertIn('Не вдалося надіслати', s.inner_text('#zboi'))
        self.assertEqual(self.skh.ryadky['zayavka'], [])
        self.skh.zbii = False
        s.click('#sprobuvaty-shche')
        s.wait_for_selector('#vdacha', state='visible')
        self.assertEqual(len(self.skh.ryadky['zayavka']), 1)
        kontekst.close()

    def test_telefon_bez_horyzontalnoho_prokruchuvannia(self):
        for storinka in ('index.html', 'polityka.html', 'zrazok.html'):
            kontekst = self.brauzer.new_context(viewport={'width': 390, 'height': 844})
            s = kontekst.new_page()
            s.goto(f'{self.url}/zahlushka/{storinka}')
            shyryna = s.evaluate('document.documentElement.scrollWidth')
            self.assertLessEqual(shyryna, 390, storinka)
            kontekst.close()

    def test_shryfty_zavantazheni(self):
        kontekst, s = self.vidkryty()
        s.evaluate('document.fonts.ready')
        self.assertTrue(s.evaluate("document.fonts.check('800 52px Manrope', 'Що')"))
        self.assertTrue(s.evaluate("document.fonts.check('400 16px Inter', 'Що')"))
        self.assertEqual(self.zovnishni, [])
        kontekst.close()


if __name__ == '__main__':
    unittest.main()
