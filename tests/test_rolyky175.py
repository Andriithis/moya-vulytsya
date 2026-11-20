"""Виправлення роликів за критиком ZVIT-170 (ZAVDANNYA-175): правдивий гачок, заклик на сторінку, що існує, одне «усього
подій», рух у перші 1,5 с, читабельний логотип, видима точка, позначка голосу, записи сайту 1080×1920.

Запуск: python -m unittest tests/test_rolyky175.py
База випуску й браузер не потрібні: перевіряємо правила, що вирішують, чи можна ролик зібрати.
"""
from __future__ import annotations

import copy
import importlib.util
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
VAU = KORIN / 'video' / 'vau'


def modul(imia, fail):
    spec = importlib.util.spec_from_file_location(imia, VAU / fail)
    m = importlib.util.module_from_spec(spec)
    sys.modules[imia] = m
    spec.loader.exec_module(m)
    return m


P = modul('vau_perevirka175', 'perevirka.py')
HS = modul('vau_holos_servis175', 'holos_servis.py')

META = {'nazva': 'Проба', 'hachok': 'гачок', 'meta': 'перевірка', 'kudy': '/vulytsia/proba/', 'kintsivka': 'посилання в профілі',
        'pravyla': 175, 'shar': 'tochky'}
CHYSTYI = {
    'id': 'proba175', 'tryvalist': 6, 'tema': 'temna',
    'kamera': [{'t': 0, 'c': [30.5234, 50.4501], 'z': 11}, {'t': 1.2, 'c': [30.5234, 50.4501], 'z': 11.4},
               {'t': 6, 'c': [30.5234, 50.4501], 'z': 11.6}],
    'tochky': [{'dani': {'x': [3052340], 'y': [5045010], 'g': [0], 't': [0.0]}}],
    'tekst': [{'t0': 0, 't1': 2, 'styl': 'hook', 'tekst': 'Кожна точка — *подія*'},
              {'t0': 1.8, 't1': 4, 'styl': 'lich', 'do': 10, 'pidpys': '{f} у даних', 'formy': ['подія', 'події', 'подій']},
              {'t0': 3.8, 't1': 5, 'styl': 'velykyi', 'tekst': 'Одне місто'},
              {'t0': 5, 't1': 6, 'styl': 'baner', 'zag': 'Знайди вулицю', 'knopka': 'посилання в профілі'}],
}


def z(f=None, meta=None):
    S = copy.deepcopy(CHYSTYI)
    m = dict(META, **(meta or {}))
    if f:
        f(S)
    return P.pereviryty(S, m)


class Bazovyi(unittest.TestCase):
    def test_chystyi_prokhodyt(self):
        self.assertEqual(z(), [])


class PoznakaHolosu(unittest.TestCase):
    """MV-171: голос Андрія, перетворений програмою, — «Голос змінено програмою»; Piper — «Голос згенеровано»."""

    def setUp(self):
        self.staryi = os.environ.get('MV_HOLOS')

    def tearDown(self):
        if self.staryi is None:
            os.environ.pop('MV_HOLOS', None)
        else:
            os.environ['MV_HOLOS'] = self.staryi

    def test_za_servisom(self):
        self.assertEqual(HS.poznaka('teka'), 'Голос змінено програмою')
        self.assertEqual(HS.poznaka('piper'), 'Голос згенеровано')
        os.environ['MV_HOLOS'] = 'teka'
        self.assertEqual(HS.poznaka(), 'Голос змінено програмою')
        os.environ.pop('MV_HOLOS')
        self.assertEqual(HS.poznaka(), 'Голос згенеровано')

    def test_perevirka(self):
        def holos(p):
            return lambda s: (s.update(zvuk={'holos': [{'t': 0.5, 'tekst': 'Кожна точка — подія.'}]}, holos_poznaka=p))
        self.assertEqual(z(holos('Голос змінено програмою')), [])
        self.assertEqual(z(holos('Голос згенеровано')), [])
        self.assertTrue(any('MV-171' in x for x in z(holos('Голос ШІ'))))
        self.assertTrue(any('позначки' in x for x in z(holos(None))))

    def test_ne_zostalos_ruchnoi_poznaky(self):
        for f in ('stsenarii.py', 'zapys_saitu.py', 'zapys155.py'):
            self.assertNotIn("'Голос згенеровано'", (VAU / f).read_text(encoding='utf-8'), f)


class PravdaHachka(unittest.TestCase):
    """Топ-10 №2: число в гачку — з бази; «одне й те саме» — лише для одного виду; «в судах» — не підміна «у даних»."""

    def hook(self, tekst):
        return lambda s: s['tekst'].__setitem__(0, {'t0': 0, 't1': 2, 'styl': 'hook', 'tekst': tekst})

    def test_chyslo_bez_bazy(self):
        self.assertTrue(any('не підтверджене' in x for x in z(self.hook('Біля ТЦ —\n*64 події*'))))

    def test_chyslo_z_bazy(self):
        self.assertEqual(z(self.hook('Біля ТЦ —\n*64 події*'), {'fakty': {'podii': 64}}), [])
        self.assertEqual(z(self.hook('*71 428* подій'), {'fakty': {'vsi': 71428}}), [])
        self.assertTrue(z(self.hook('*71 428* подій'), {'fakty': {'vsi': 71417}}))       # «71 417» у базі, «71 428» у гачку

    def test_chyslo_z_opysu_podii(self):
        h = self.hook('Самокат.\n00:46.\n*1,68 проміле.*')
        fab = 'ОСОБА_1 о 00 год. 46 хв. керував електросамокатом, результат огляду 1,68 проміле'
        self.assertEqual(z(h, {'fabula': fab}), [])
        self.assertTrue(z(h, {'fabula': fab.replace('1,68', '1,86')}))

    def test_ne_dani(self):
        for t in ('Київ за 9 секунд', 'Знайди точку за 3 секунди', 'Скільки разів у 1551?', 'Один день 2025-го'):
            self.assertEqual(z(self.hook(t)), [], t)
        self.assertEqual(z(self.hook('Квартира — за 2 мільйони'), {'chysla_ne_z_bazy': ['2']}), [])

    def test_odne_i_te_same(self):
        h = self.hook('Біля ТЦ суд розбирав\n*одне й те саме*\n64 рази')
        self.assertTrue(any('вид один' in x for x in z(h, {'fakty': {'podii': 64, 'vydiv': 2}})))     # n7: 39 + 25 — два види
        self.assertEqual(z(h, {'fakty': {'podii': 64, 'vydiv': 1}}), [])

    def test_v_sudakh(self):
        self.assertTrue(any('у наших даних' in x for x in z(self.hook('Найчастіша справа\nв судах Києва —\n*крадіжка*'))))
        self.assertEqual(z(self.hook('Найчастіша подія\nу наших даних —\n*крадіжка*')), [])

    def test_opys_hachka_tezh(self):
        self.assertTrue(z(None, {'hachok': '«Біля ТЦ одне й те саме 64 рази»'}))


class Vidsotok(unittest.TestCase):
    """Топ-10 №5: відсоток — лише з базою >= 50 подій, інакше «k з n» (AGENTS.md розд. 6)."""

    def split(self, n):
        return lambda s: s['tekst'].append({'t0': 2, 't1': 4, 'styl': 'split', 'riady': [
            {'zag': 'Тут', 'n': n, 'pislia': ' %', 'tekst': 'поїхав з місця ДТП'}]})

    def test_bez_bazy(self):
        self.assertTrue(any('відсоток' in x for x in z(self.split(26))))
        self.assertTrue(any('відсоток' in x for x in z(self.split(26), {'vidsotky': [{'v': 26, 'k': 10, 'n': 38}]})))

    def test_z_bazoiu(self):
        self.assertEqual(z(self.split(17), {'vidsotky': [{'v': 17, 'k': 10, 'n': 60}]}), [])

    def test_holos_tezh(self):
        f = lambda s: s.update(zvuk={'holos': [{'t': 3, 'tekst': 'Тут двадцять шість відсотків'}, {'t': 4, 'tekst': 'Тут 26 відсотків'}]},
                               holos_poznaka='Голос згенеровано')
        self.assertTrue(any('відсоток' in x for x in z(f)))

    def test_rolyk_vidsotok(self):
        # у video/ і site/sait/ є свої perevirka.py і dani.py — на час імпорту прибрати чужі з sys.modules
        chuzhi = {k: sys.modules.pop(k) for k in ('dani', 'perevirka', 'stsenarii') if k in sys.modules}
        sys.path.insert(0, str(VAU))
        try:
            ST = modul('vau_stsenarii175', 'stsenarii.py')
        except ImportError as e:
            self.skipTest(str(e))
        finally:
            sys.path.remove(str(VAU))
            for k in ('dani', 'perevirka', 'stsenarii'):
                sys.modules.pop(k, None)
            sys.modules.update(chuzhi)
        R = ST.Rolyk('x', 6, pravyla=175)
        self.assertIsNone(R.vidsotok(10, 38))
        self.assertEqual(R.vidsotok(10, 60), 17)
        self.assertEqual(R.meta['vidsotky'], [{'v': 17, 'k': 10, 'n': 60}])
        self.assertEqual(ST.karta_tut((30.52341, 50.45012), 15), '/karta/#15/50.45012/30.52341')


class Zaklyk(unittest.TestCase):
    """Топ-10 №3: заклик — на сторінку того самого місця, і вона є в зібраному сайті."""

    def test_konkretne_mistse(self):
        for k in ('/vulytsia/teremkivska/', '/rayon/podilskyi/', '/mistse/tts-hlobus/', '/miy-budynok/', '/karta/?ihry',
                  '/karta/#15/50.45012/30.52341', '/oplata/?tovar=pidpyska'):
            self.assertEqual(z(None, {'kudy': k}), [], k)

    def test_karta_zahalom(self):
        for k in ('/karta/', '/karta/?z=15', '/'):
            self.assertTrue(any('конкретне місце' in x for x in z(None, {'kudy': k})), k)
        self.assertEqual(z(None, {'kudy': '/karta/', 'pro_misto': True}), [])

    def test_storinka_isnuie(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / 'vulytsia' / 'teremkivska').mkdir(parents=True)
            (Path(d) / 'vulytsia' / 'teremkivska' / 'index.html').write_text('x')
            (Path(d) / 'karta').mkdir()
            (Path(d) / 'karta' / 'index.html').write_text('x')
            self.assertEqual(P.posylannia({'kudy': '/vulytsia/teremkivska/'}, d), [])
            self.assertEqual(P.posylannia({'kudy': '/karta/#15/50.4/30.5'}, d), [])
            self.assertEqual(P.posylannia({'kudy': '/karta/?ihry'}, d), [])
            self.assertTrue(any('404' in x for x in P.posylannia({'kudy': '/mistse/globus/'}, d)))       # n7 у ZVIT-170
        self.assertTrue(P.posylannia({'kudy': '/vulytsia/x/'}, None))          # без зібраного сайту — не збираємо

    def test_stsenarii_pereviriaiut_posylannia(self):
        for f in ('stsenarii.py', 'zapys_saitu.py', 'zapys155.py'):
            self.assertIn('perevirka.posylannia(', (VAU / f).read_text(encoding='utf-8'), f)
        for f in ('stsenarii.py', 'stsenarii129.py', 'stsenarii138.py', 'zapys155.py'):
            self.assertIn("'--sait'", (VAU / f).read_text(encoding='utf-8'), f)

    def test_kudy_v_stsenariiakh(self):
        """Жоден сценарій 129/138/155 не веде на «карту загалом» без позначки «про все місто», ні на /mistse/globus/."""
        for f in ('stsenarii129.py', 'stsenarii138.py', 'zapys_saitu.py', 'zapys155.py'):
            t = (VAU / f).read_text(encoding='utf-8')
            self.assertNotIn("/karta/?z=", t, f)
            self.assertNotIn("/mistse/globus/", t, f)
            for m in re.finditer(r"kudy='/karta/'[^\n]*", t):
                self.assertTrue('pro_misto=True' in m.group() or "riven='misto'" in m.group(), f'{f}: {m.group()}')


class PidpysVulytsi(unittest.TestCase):
    """Топ-10 №7: «вул. Вишгородська · 45» читається як номер будинку — число окремим рядком «45 подій»."""

    def mitka(self, **kw):
        return lambda s: s['mitky'].append(dict({'t0': 1, 't1': 2, 'c': [30.5, 50.45], 'tekst': 'вул. Вишгородська', 'styl': 'velyka'}, **kw))

    def test_dvoinyk(self):
        S = copy.deepcopy(CHYSTYI)
        S['mitky'] = []
        for kw in ({'n': ' · 45'}, {'n': ', 45'}):
            f = self.mitka(**kw)
            self.assertTrue(any('номер будинку' in x for x in z(lambda s: (s.update(mitky=[]), f(s)))), kw)
        self.assertEqual(z(lambda s: (s.update(mitky=[]), self.mitka(n=45)(s))), [])

    def test_stsena(self):
        js = (VAU / 'stsena.js').read_text(encoding='utf-8')
        self.assertIn("vidm(m.n, ['подія', 'події', 'подій'])", js)
        self.assertIn('b.lich', (VAU / 'stsena.css').read_text(encoding='utf-8'))
        self.assertNotIn("n=f' · {len(v)}'", (VAU / 'stsenarii138.py').read_text(encoding='utf-8'))


class Zapys1080(unittest.TestCase):
    """ZVIT-155 розд. 4 п. 2: запис сайту — 1080×1920 (без clip зі scale браузер знімає 540×960; перевірено 20.11.2026)."""

    def test_znimok_zi_scale(self):
        t = (VAU / 'zapys_saitu.py').read_text(encoding='utf-8')
        self.assertIn("'clip': {'x': 0, 'y': 0, 'width': 540, 'height': 960, 'scale': 2}", t)
        for f in ('zapys_saitu.py', 'zapys139.py'):
            t = (VAU / f).read_text(encoding='utf-8')
            self.assertNotIn("captureScreenshot', {'format': 'jpeg', 'quality': 93})", t, f)
            self.assertIn("scale=1080:1920", t, f)


class Mif(unittest.TestCase):
    """Критик ZVIT-170: печатка «МІФ» — після доказу; у картках порівняння немає кадру «7 570 / 0»."""

    def test_shtamp_pislia_dokazu(self):
        for f, dokaz in (('stsenarii129.py', "'split', riady=riady"), ('stsenarii138.py', "'kolony', riady=riady, y=820")):
            t = (VAU / f).read_text(encoding='utf-8')
            self.assertLess(t.index(dokaz), t.index("'shtamp', 'МІФ'"), f)
            t0_dokaz = float(re.search(r"R\.tekst\(([\d.]+), [\d.]+, " + re.escape(dokaz), t).group(1))
            t0_shtamp = float(re.search(r"R\.tekst\(([\d.]+), [\d.]+, 'shtamp', 'МІФ'\)", t).group(1))
            self.assertLess(t0_dokaz, t0_shtamp, f)

    def test_bez_nulia(self):
        js = (VAU / 'stsena.js').read_text(encoding='utf-8')
        self.assertIn("kn <= 0 ? ''", js)


if __name__ == '__main__':
    unittest.main()
