"""«Судова практика» — розділ сайту (ZAVDANNYA-111; MV-121, MV-122): сторінки статей зі зведення dani-edrsr.

Штучне зведення (рядки [суд, рік, частина, категорія, поєднання, справ, {днів: справ}]) — як його дає
`dani-edrsr/src/sudova_praktyka.py sait`. Справжнє — змінною MV_SUDOVA_PRAKTYKA (тоді перевіряються ті самі правила).
"""
from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))

import storinky_sp as SP  # noqa: E402
import tsiny as T  # noqa: E402
import zibraty_sait as Z  # noqa: E402

KAT_KUPAP = ['штраф', 'позбавлення права керування', 'адміністративний арешт', 'громадські роботи', 'попередження',
             'інше стягнення', 'усне зауваження (малозначність)', 'закрито: минули строки', 'закрито: немає складу',
             'протокол повернуто', 'інше закриття']
KAT_KK = ['позбавлення волі реально', 'з випробуванням (умовно)', 'штраф', 'пробаційний нагляд', 'обмеження волі',
          'інше покарання', 'звільнено від покарання', 'звільнено від відповідальності', 'виправдано', 'примусові заходи',
          'інше закриття']
PSH = 'штраф і позбавлення права керування'
ZVEDENNIA = {
    'versiia': '2026-11-17', 'roky_vid': '2016', 'stroky': ['ст.130 КУпАП', 'ст.286 КК'],
    'statti': [
        {'kodeks': 'КУпАП', 'nomer': '130', 'nazva': 'Керування в стані сп’яніння', 'kat': KAT_KUPAP, 'pokarano': KAT_KUPAP[:6],
         'ryadky': [['Голосіївський', '2024', '1', 'штраф', PSH, 500, {'30': 200, '70': 300}],
                    ['Дарницький', '2025', '1', 'штраф', PSH, 400, {'60': 400}],
                    ['Дарницький', '2025', '1', 'штраф', '', 30, {}],
                    ['Дарницький', '2025', '1', 'закрито: минули строки', '', 60, {'200': 60}],
                    ['Голосіївський', '2019', '1', 'штраф', PSH, 777, {}]]},
        {'kodeks': 'КК', 'nomer': '190', 'nazva': 'Шахрайство', 'kat': KAT_KK, 'pokarano': KAT_KK[:7],
         'ryadky': [['Голосіївський', '2025', '1', 'з випробуванням (умовно)', '', 40, {'100': 40}],
                    ['Голосіївський', '2025', '2', 'позбавлення волі реально', '', 20, {}]]},
        {'kodeks': 'КК', 'nomer': '286', 'nazva': 'ДТП з потерпілими', 'kat': KAT_KK, 'pokarano': KAT_KK[:7],
         'ryadky': [['Печерський', '2025', '2', 'з випробуванням (умовно)', 'з випробуванням (умовно) і позбавлення права керування', 8, {'300': 8}],
                    ['Печерський', '2025', '1', 'штраф', 'штраф і позбавлення права керування', 4, {}]]},
    ]}


class SudovaPraktykaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        tmp = Path(cls.tmp.name)
        dz = os.environ.get('MV_SUDOVA_PRAKTYKA')
        cls.spravzhnie = bool(dz)
        if dz:
            cls.dzherelo = Path(dz)
        else:
            cls.dzherelo = tmp / 'sudova-praktyka.json'
            cls.dzherelo.write_text(json.dumps(ZVEDENNIA, ensure_ascii=False), encoding='utf-8')
        cls.sait = tmp / 'sait'
        Z.kopiyuvaty_spilne(cls.sait)
        cls.adresy = SP.zibraty(cls.dzherelo, cls.sait, 'https://pryklad.ua')
        cls.storinky = sorted((cls.sait / 'sudova-praktyka').rglob('index.html'))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def st(self, shl):
        return (self.sait / 'sudova-praktyka' / shl / 'index.html').read_text(encoding='utf-8')

    def ryad(self, t, nazva):
        """Частка в рядку смуги «назва» (перший такий рядок)."""
        m = re.search(r'sp-ryad__nazva">' + re.escape(nazva) + r'</span><span class="sp-smuha">.*?<b>([^<]+)</b>', t)
        return m and m.group(1)

    def test_storinky_i_sitemap(self):
        self.assertTrue((self.sait / 'sudova-praktyka' / 'index.html').is_file())
        if self.spravzhnie:
            return
        for shl in ('kupap/130', 'kk/190', 'kk/286'):
            self.assertTrue((self.sait / 'sudova-praktyka' / shl / 'index.html').is_file(), shl)
        self.assertEqual(self.adresy, ['/sudova-praktyka/', '/sudova-praktyka/kupap/130/'])   # < 100 справ — не для пошуку
        self.assertIn('noindex', self.st('kk/190'))
        self.assertNotIn('noindex', self.st('kupap/130'))
        rozdil = self.st('')
        for shl in ('/sudova-praktyka/kupap/130/', '/sudova-praktyka/kk/190/', '/sudova-praktyka/kk/286/'):
            self.assertIn(f'href="{shl}"', rozdil)

    def test_st130_pozbavlennia_prava_razom_zi_shtrafom(self):
        """MV-122: позбавлення права, призначене разом зі штрафом, — у частці виду покарання, не «< 1 %»; поєднання видно."""
        t = self.st('kupap/130')
        if self.spravzhnie:
            x = self.ryad(t, 'позбавлення права керування')
            self.assertIsNotNone(x)
            self.assertNotIn('<1', x)
            return
        self.assertEqual(self.ryad(t, 'позбавлення права керування'), '91 %')    # 900 з 990 за 2024–2026
        self.assertEqual(self.ryad(t, 'штраф'), '94 %')                          # 930 з 990
        self.assertEqual(self.ryad(t, PSH), '91 %')
        self.assertIn('Поєднання покарань', t)
        self.assertIn(f'{PSH} — у 91 % справ', t)                                 # перше речення — відповідь числом

    def test_roky_vidkryti_i_strok(self):
        if self.spravzhnie:
            self.skipTest('лише штучне')
        t = self.st('kupap/130')
        self.assertIn('990', t)
        self.assertNotIn('1 767', t)                     # 2019 — не в частках за 3 роки
        self.assertIn('за стільки від події вирішено половину справ', t)
        self.assertIn('2,0\u00a0міс.', t)                  # медіана — 60 днів
        # ст. 190 КК не в списку stroky (дата події < 95 %) — строку немає, хоч дні в рядках є
        t190 = self.st('kk/190')
        self.assertNotIn('за стільки від події вирішено половину справ', t190)
        self.assertIn('Строк від події до рішення для цієї статті не показуємо', t190)
        self.assertIn('серед вироків', t190)
        # замало справ — частки не рахуються
        t286 = self.st('kk/286')
        self.assertIn('Справ замало', t286)
        self.assertNotIn('Чим закінчуються справи</h2>', t286)

    def test_platne_za_zamkom(self):
        """По судах — лише назви й замки, без чисел; кнопки — довідка 199 і юристу 490/міс (заглушка /oplata/)."""
        for f in self.storinky:
            t = f.read_text(encoding='utf-8')
            for tabl in re.findall(r'<table class="sp-tablytsia sp-tablytsia--zamk">(.*?)</table>', t, re.S):
                self.assertEqual(re.findall(r'<td[^>]*>[^<]*\d', tabl), [], f)
            self.assertNotIn('sp-dani', t)
        t = self.st('kupap/130') if not self.spravzhnie else self.storinky[1].read_text(encoding='utf-8')
        self.assertRegex(t, r'/oplata/\?tovar=spdovidka&amp;stattia=(kupap|kk)-[0-9-]+&amp;dzherelo=sp-')
        self.assertIn('/oplata/?tovar=spyurist&amp;dzherelo=sp-', t)
        self.assertIn('199 грн', t)
        self.assertIn('490 грн на місяць', t)
        if not self.spravzhnie:
            self.assertIn('Дарницький', t)

    def test_tsiny_lyshe_z_tablytsi(self):
        dozvoleni = T.dozvoleni_sumy()
        self.assertEqual((T.TSINY['spdovidka'], T.TSINY['spyurist']), (199, 490))   # MV-122, п. 4
        for f in self.storinky:
            for n in re.findall(r'(\d[\d  ]*)(?: |\s)?грн', f.read_text(encoding='utf-8')):
                self.assertIn(int(re.sub(r'\D', '', n)), dozvoleni, f)

    def test_bez_imen_prohnoziv_i_ocinok(self):
        zaboroneno = re.compile(r'ОСОБА_|суддя\s+[А-ЯІЇЄҐ]|рейтинг|небезпечн|безпечн|найімовірніше|імовірно|станеться|'
                                r'будьте уважні|медіан|уникайте|вам призначать|м[ʼ’\']якш|суворіш', re.I)
        for f in self.storinky:
            m = zaboroneno.search(f.read_text(encoding='utf-8'))
            self.assertIsNone(m, f'{f}: {m and m.group(0)}')

    def test_rozmitka_dlia_google(self):
        t = self.st('kupap/130') if not self.spravzhnie else self.storinky[1].read_text(encoding='utf-8')
        self.assertRegex(t, r'<title>Стаття \S+ \S+ у судах Києва: чим закінчуються справи')
        self.assertRegex(t, r'<h1>Стаття \S+ \S+ — як вирішують справи суди Києва</h1>')
        typy = {json.loads(x)['@type'] for x in re.findall(r'<script type="application/ld\+json">(.*?)</script>', t)}
        self.assertEqual(typy, {'Dataset', 'FAQPage', 'BreadcrumbList'})
        self.assertNotRegex(t, r'"@type": ?"(Review|Rating|AggregateRating)"')
        self.assertIn('<link rel="canonical" href="https://pryklad.ua/sudova-praktyka/', t)
        self.assertNotIn('style="', t)                                     # CSP: розміри — через sp.js
        self.assertTrue((self.sait / 'sait' / 'sp.js').is_file())
        self.assertTrue((self.sait / 'sait' / 'sp.css').is_file())

    def test_kolory_sp_css_zi_zminnykh(self):
        """Вигляд М7 (docs/STYL.md): лише змінні кольорів, без червоного, градієнтів, розмиття й інших шрифтів."""
        css = (KORIN / 'site' / 'sait' / 'sp.css').read_text(encoding='utf-8')
        self.assertNotRegex(css, r'#[0-9a-fA-F]{3,6}\b|rgb\(|gradient|blur|font-family')

    def test_starе_zvedennia_vidkydaietsia(self):
        p = Path(self.tmp.name) / 'stare.json'
        stare = json.loads(json.dumps(ZVEDENNIA))
        stare['statti'][0]['ryadky'] = [['Голосіївський', '2024', '1', 'штраф', 5, []]]
        p.write_text(json.dumps(stare, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(SystemExit):
            SP.prochytaty(p)


class SaitZRozdilomTests(unittest.TestCase):
    """Повний збирач сайту з --sudova-praktyka: розділ замість вітрини «скоро», сторінки в sitemap, вхід на головній."""

    def test_zibraty_sait(self):
        try:
            import h3  # noqa: F401
        except ImportError:
            self.skipTest('немає бібліотеки h3 — збирання сайту пропущено')
        sys.path.insert(0, str(KORIN / 'tests'))
        import test_sait as TS
        with tempfile.TemporaryDirectory() as t:
            tmp = Path(t)
            TS.stvoryty_bazu(tmp / 'events.db')
            TS.stvoryty_pereimenuvannya(tmp / 'pereim.csv')
            (tmp / 'sp.json').write_text(json.dumps(ZVEDENNIA, ensure_ascii=False), encoding='utf-8')
            zvit = Z.zibraty_sait(tmp / 'events.db', tmp / 'sait', tmp / 'pereim.csv', KORIN / 'data' / 'borders.json',
                                  sudova_praktyka=tmp / 'sp.json')
            self.assertEqual(zvit['sudova_praktyka_u_sitemap'], 1)
            rozdil = (tmp / 'sait' / 'sudova-praktyka' / 'index.html').read_text(encoding='utf-8')
            self.assertNotIn('<span class="mitka">Скоро</span>', rozdil, 'справжній розділ, а не вітрина «скоро»')
            self.assertIn('/sudova-praktyka/kupap/130/', (tmp / 'sait' / 'sitemap.xml').read_text(encoding='utf-8'))
            self.assertIn('чим закінчуються справи', (tmp / 'sait' / 'index.html').read_text(encoding='utf-8'))
            self.assertTrue((tmp / 'sait' / 'sait' / 'sp.js').is_file())


if __name__ == '__main__':
    unittest.main()

    def test_dovidnyk_dlia_servera_bez_chysel(self):
        """ZAVDANNYA-135: довідник замовлення — статті, суди, частини; жодного числа справ."""
        d = json.loads((self.sait / 'sudova-praktyka' / 'dovidnyk.json').read_text(encoding='utf-8'))
        for k, s in d['statti'].items():
            self.assertRegex(k, r'^(kupap|kk)-\d+(-\d+)?$')
            self.assertEqual(set(s), {'stattia', 'nazva', 'sudy', 'chastyny'})
            self.assertTrue(all(isinstance(x, str) for x in s['sudy'] + s['chastyny']))
        if not self.spravzhnie:
            self.assertEqual(d['statti']['kupap-130']['sudy'], ['Голосіївський', 'Дарницький'])

    def test_poshuk_i_zasterezhennia(self):
        """ZAVDANNYA-135: покажчик з пошуком («п'яний за кермом» — у словах ст. 130) і застереження на кожній сторінці."""
        rozdil = self.st('')
        self.assertIn('id="sp-poshuk"', rozdil)
        m = re.search(r'<li class="sp-stattia" data-nomer="130" data-slova="([^"]+)"', rozdil)
        self.assertIsNotNone(m)
        self.assertIn('за кермом', m.group(1))
        for f in self.storinky:
            self.assertIn('не юридична допомога', f.read_text(encoding='utf-8'), f)


class VkhodyVProdukt(unittest.TestCase):
    """ZAVDANNYA-135, п. 4: входи на сторінки статей — сторінки вулиць, картка соти на карті, ролик «Що буває за…»."""

    def test_kliuch_statti(self):
        sys.path.insert(0, str(KORIN / 'site' / 'sait'))
        import dani as D
        self.assertEqual(D.kliuch_statti("ст.130 ч.1 КУпАП · керування у стані сп'яніння"), 'kupap-130')
        self.assertEqual(D.kliuch_statti('ст.173-2 КУпАП'), 'kupap-173-2')
        self.assertEqual(D.kliuch_statti('ст.185 ч.4 КК · крадіжка'), 'kk-185')
        self.assertIsNone(D.kliuch_statti(''))

    def test_blok_vulytsi(self):
        from collections import Counter
        sp = {'kupap-130': {'kodeks': 'КУпАП', 'nomer': '130', 'nazva': 'Керування в стані сп’яніння'},
              'kk-185': {'kodeks': 'КК', 'nomer': '185', 'nazva': 'Крадіжка'}}
        b = Z.blok_sudova_praktyka(Counter({'kupap-130': 7, 'kk-185': 2, 'kupap-51': 9}), sp)
        self.assertIn('href="/sudova-praktyka/kupap/130/"', b)
        self.assertNotIn('kk/185', b, 'менше 3 подій — без посилання')
        self.assertNotIn('51', b, 'статті поза вітриною — ні')
        self.assertEqual(Z.blok_sudova_praktyka(Counter({'kupap-130': 7}), None), '', 'без розділу — без посилань')
        self.assertNotRegex(b, r'уникайте|будьте уважні|найімовірніше')

    def test_karta_i_rolyk(self):
        k = (KORIN / 'site' / 'sait' / 'karta.js').read_text(encoding='utf-8')
        self.assertIn("sudova-praktyka/?q=", k)
        self.assertNotIn("nas: '", k.split('SP_HRUPY')[1].split(';')[0], 'насильство — без посилання')
        r = (KORIN / 'video' / 'vau' / 'stsenarii.py').read_text(encoding='utf-8')
        self.assertIn("kudy='/sudova-praktyka/kupap/130/'", r)
        self.assertNotIn('/sudova-praktyka/st-', r)
