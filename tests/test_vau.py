"""Перевірки рушія роликів «Вау» (ZAVDANNYA-127): правила сценаріїв, текст для голосу, дані для сцени.

Запуск: python -m unittest tests/test_vau.py
Рендер у браузері й база випуску тут не потрібні: перевіряємо те, що вирішує, чи можна ролик показувати людям.
Модулі вантажимо під окремими іменами — у video/ і site/sait/ є свої perevirka.py і dani.py.
"""
from __future__ import annotations

import colorsys
import copy
import importlib.util
import re
import sys
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


P = modul('vau_perevirka', 'perevirka.py')
HT = modul('vau_holos_tekst', 'holos_tekst.py')
D = modul('vau_dani', 'dani.py')

META = {'nazva': 'Проба', 'hachok': 'гачок', 'meta': 'перевірка', 'kudy': '/karta/', 'kintsivka': 'посилання в профілі'}
CHYSTYI = {
    'id': 'proba', 'tryvalist': 10, 'tema': 'temna',
    'kamera': [{'t': 0, 'c': [30.5234, 50.4501], 'z': 11}],
    'tochky': [{'dani': {'x': [3052340], 'y': [5045010], 'g': [0], 't': [1.0]}}],
    'tekst': [{'t0': 0, 't1': 3, 'styl': 'hook', 'tekst': 'Кожна точка — *справжня подія*'},
              {'t0': 3, 't1': 6, 'styl': 'kartka', 'tekst': 'Серпень, 13:46. Стріла шлагбаума опустилася на вантажівку.',
               'dz': 'вул. Тираспольська · рішення суду № 123214075'}],
    'mitky': [{'t0': 1, 't1': 2, 'c': [30.52, 50.45], 'tekst': 'ДТП'}],
    'zvuk': {'holos': [{'t': 0.5, 'tekst': 'Кожна точка — справжня подія.'}]},
    'holos_poznaka': 'Голос згенеровано',
}


def zi_zminoiu(f):
    S = copy.deepcopy(CHYSTYI)
    f(S)
    return S


class Pravyla(unittest.TestCase):
    def test_chystyi_prokhodyt(self):
        self.assertEqual(P.pereviryty(CHYSTYI, META), [])

    def test_zaboroneni_slova(self):
        for slovo in ('Тут небезпечно', 'Рейтинг вулиць', 'Найгірший район', 'Будьте уважні ввечері', 'Прогноз на зиму'):
            S = zi_zminoiu(lambda s: s['tekst'].append({'t0': 0, 't1': 1, 'styl': 'velykyi', 'tekst': slovo}))
            self.assertTrue(any('заборонене' in z for z in P.pereviryty(S, META)), slovo)

    def test_zaboroneni_i_v_golosi(self):
        S = zi_zminoiu(lambda s: s['zvuk']['holos'].append({'t': 1, 'tekst': 'Це найнебезпечніша вулиця'}))
        self.assertTrue(P.pereviryty(S, META))

    def test_nomer_zhytlovogo_budynku(self):
        S = zi_zminoiu(lambda s: s['mitky'].append({'t0': 0, 't1': 1, 'c': [30.5, 50.45], 'tekst': 'вул. Тираспольська, 60'}))
        self.assertTrue(any('MV-25' in z for z in P.pereviryty(S, META)))

    def test_nomer_publichnogo_mistsia_dozvoleno(self):
        S = zi_zminoiu(lambda s: s['mitky'].append({'t0': 0, 't1': 1, 'c': [30.5, 50.45], 'tekst': 'ТЦ «Глобус», вул. Хрещатик, 1'}))
        self.assertEqual(P.pereviryty(S, dict(META, publichni=['Глобус'])), [])

    def test_slidy_znoosoblennia_i_chutlyve(self):
        for t in ('ОСОБА_1 керував', 'кв. 12', 'справа щодо дитини'):
            S = zi_zminoiu(lambda s: s['tekst'].append({'t0': 0, 't1': 1, 'styl': 'mala', 'tekst': t}))
            self.assertTrue(P.pereviryty(S, META), t)

    def test_slovo_kvartyra_bez_nomera_mozhna(self):
        S = zi_zminoiu(lambda s: s['tekst'].append({'t0': 0, 't1': 1, 'styl': 'hook', 'tekst': 'Орендуєш квартиру?'}))
        self.assertEqual(P.pereviryty(S, META), [])

    def test_kamera_i_tochky_v_kyievi(self):
        S = zi_zminoiu(lambda s: s['kamera'].append({'t': 5, 'c': [24.03, 49.84], 'z': 12}))
        self.assertTrue(any('поза Києвом' in z for z in P.pereviryty(S, META)))
        self.assertEqual(P.pereviryty(S, dict(META, za_mezhamy=True)), [])
        S = zi_zminoiu(lambda s: s['tochky'][0]['dani'].update(x=[2403000], y=[4984000]))
        self.assertTrue(any('точка поза' in z for z in P.pereviryty(S, META)))

    def test_kintsivka_obovyazkova(self):
        m = dict(META)
        del m['kintsivka']
        self.assertTrue(any('кінцівки' in z for z in P.pereviryty(CHYSTYI, m)))
        self.assertFalse(any('кінцівки' in z for z in P.pereviryty(CHYSTYI, dict(m, obryv=True))))

    def test_holos_z_poznakoiu(self):
        S = zi_zminoiu(lambda s: s.pop('holos_poznaka'))
        self.assertTrue(any('MV-150' in z for z in P.pereviryty(S, META)))

    def test_dovzhyna(self):
        for t in (3, 70):
            self.assertTrue(P.pereviryty(zi_zminoiu(lambda s: s.update(tryvalist=t)), META))


class Holos(unittest.TestCase):
    def test_lyshe_mali_literi_i_vidomi_znaky(self):
        t = HT.tekst_dlia_holosu('Сто сорок: «71 428» подій — 12%!')
        self.assertEqual(t, t.lower())
        self.assertTrue(set(t) <= HT.DOZVOLENI, set(t) - HT.DOZVOLENI)
        self.assertIn('сто сорок', t)

    def test_abreviatury_vymovoiu(self):
        t = HT.tekst_dlia_holosu('Найчастіше — ДТП біля ТЦ.')
        self.assertIn('де-те-пе', t)
        self.assertIn('те-це', t)

    def test_chysla_slovamy(self):
        self.assertEqual(HT.chyslo_slovamy(71428), 'сімдесят одна тисяча чотириста двадцять вісім')
        self.assertEqual(HT.chyslo_slovamy(2002), 'дві тисячі два')
        self.assertEqual(HT.chyslo_slovamy(11000), 'одинадцять тисяч')
        self.assertIn('сімдесят одна тисяча', HT.tekst_dlia_holosu('71 428'))


class Dani(unittest.TestCase):
    def test_vulytsia_bez_nomera(self):
        self.assertEqual(D.vulytsia('вул. Тираспольська, 60'), 'вул. Тираспольська')
        self.assertEqual(D.vulytsia('просп. Миколи Бажана, 3Г'), 'просп. Миколи Бажана')

    def test_korotki_pidpysy(self):
        self.assertEqual(D.korotko("ст.130 КУпАП · керування у стані сп'яніння", 'ДОР'), "п'яний за кермом")
        self.assertEqual(D.korotko('ст.185 КУпАП · злісна непокора поліцейському', 'ГП'), 'непокора поліції')
        self.assertEqual(D.korotko('ст.185 КК · крадіжка', 'МАЙ'), 'крадіжка')

    def test_nasylstvo_ne_v_rolyky(self):
        self.assertIn('НАС', D.NE_V_ROLYKY)
        self.assertNotIn('НАС', D.HRUPY)

    def test_kolory_ne_chervoni(self):
        for nazva, kolir in D.HRUPY.values():
            r, g, b = (int(kolir[i:i + 2], 16) / 255 for i in (1, 3, 5))
            h = colorsys.rgb_to_hsv(r, g, b)[0] * 360
            self.assertFalse(h < 20 or h > 335, f'{nazva}: {kolir} — червоний (MV-58)')

    def test_soty_shkala_chastkamy(self):
        try:
            import h3  # noqa: F401
        except ImportError:
            self.skipTest('немає h3')
        podii = []
        for i in range(400):
            podii.append(D.Podiia(f'{i}-1', '2025-01-01', '12:00', 'ДТП', 'ст.124', None,
                                  50.40 + (i % 20) * 0.01, 30.40 + (i // 20) * 0.01 + (0.002 if i % 7 == 0 else 0),
                                  'вул. Проба, 1', 'house', 'https://x'))
        g = D.soty(podii, 8)
        klasy = {f['properties']['k'] for f in g['features']}
        self.assertTrue(klasy <= {1, 2, 3, 4, 5})
        vershyny = [f for f in g['features'] if f['properties']['v'] > 0]
        self.assertLessEqual(len(vershyny), max(1, int(len(g['features']) * 0.2)))


class Rushii(unittest.TestCase):
    def test_fayly_na_mistsi_i_bez_cdn(self):
        for f in ('stsena.html', 'stsena.js', 'stsena.css', 'rushii.py', 'zvuk.py', 'stsenarii.py', 'perevirka.py'):
            self.assertTrue((VAU / f).is_file(), f)
        html = (VAU / 'stsena.html').read_text(encoding='utf-8')
        self.assertNotRegex(html, r'src="https?://')   # бібліотека карти — своя копія, не з чужого сервера
        self.assertIn('maplibre-gl-csp.js', html)

    def test_vykhid_ne_v_git(self):
        self.assertIn('video/vyhid/', (KORIN / '.gitignore').read_text(encoding='utf-8'))

    def test_bez_chervonogo_v_stseni(self):
        css = (VAU / 'stsena.css').read_text(encoding='utf-8') + (VAU / 'stsena.js').read_text(encoding='utf-8')
        for h in re.findall(r'#([0-9A-Fa-f]{6})\b', css):
            r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
            hh, s, v = colorsys.rgb_to_hsv(r, g, b)
            self.assertFalse((hh * 360 < 15 or hh * 360 > 340) and s > 0.45 and v > 0.4, f'червоний #{h}')


if __name__ == '__main__':
    unittest.main()


# ------------------------------------------------------------------ ZAVDANNYA-129: правила монтажу й межі MV-151
META129 = dict(META, pravyla=129)
CHYSTYI129 = {
    'id': 'proba129', 'tryvalist': 6, 'tema': 'temna',
    'kamera': [{'t': 0, 'c': [30.5234, 50.4501], 'z': 11}, {'t': 6, 'c': [30.5234, 50.4501], 'z': 11}],
    'tochky': [{'dani': {'x': [3052340], 'y': [5045010], 'g': [0], 't': [0.0]}}],
    'tekst': [{'t0': 0, 't1': 2, 'styl': 'hook', 'tekst': 'Кожна точка — *подія*'},
              {'t0': 1.8, 't1': 4, 'styl': 'lich', 'do': 10, 'pidpys': '{f} у даних', 'formy': ['подія', 'події', 'подій']},
              {'t0': 3.8, 't1': 5, 'styl': 'velykyi', 'tekst': 'Одне місто'},
              {'t0': 5, 't1': 6, 'styl': 'baner', 'zag': 'Знайди вулицю', 'knopka': 'посилання в профілі'}],
}


class Pravyla129(unittest.TestCase):
    def z(self, f=None, meta=META129):
        S = copy.deepcopy(CHYSTYI129)
        if f:
            f(S)
        return P.pereviryty(S, meta)

    def test_chystyi_prokhodyt(self):
        self.assertEqual(self.z(), [])

    def test_stari_chernetky_ne_zachepleno(self):
        S = copy.deepcopy(CHYSTYI129)
        S['tekst'][0]['t0'] = 0.5
        self.assertEqual(P.pereviryty(S, META), [])

    def test_s1_baner_dovshyi_za_sekundu(self):
        self.assertTrue(any('С1' in x for x in self.z(lambda s: s['tekst'][3].update(t0=4.5))))

    def test_s1_neruhoma_kartka(self):
        self.assertTrue(any('С1' in x for x in self.z(lambda s: s['tekst'].append({'t0': 5, 't1': 6, 'styl': 'fin', 'zag': 'x'}))))

    def test_s2_hachok_u_kadri_0(self):
        self.assertTrue(any('С2' in x for x in self.z(lambda s: s['tekst'][0].update(t0=0.3))))

    def test_s4_pauza(self):
        self.assertTrue(any('С4' in x for x in self.z(lambda s: s['tekst'][2].update(t0=4.5))))

    def test_s4_drukarka(self):
        self.assertTrue(any('С4' in x for x in self.z(lambda s: s['tekst'].append(
            {'t0': 1, 't1': 2, 'styl': 'kartka', 'tekst': 'Коротко.', 'drukarka': True}))))

    def test_s7_svitla(self):
        self.assertTrue(any('С7' in x for x in self.z(lambda s: s.update(tema='svitla'))))

    def test_s8_zakhysna_fraza_dovho(self):
        self.assertTrue(any('С8' in x for x in self.z(lambda s: s['tekst'].append(
            {'t0': 1, 't1': 4, 'styl': 'velykyi', 'tekst': 'Це не оцінка місця'}))))

    def test_s10_lich_bez_form(self):
        self.assertTrue(any('С10' in x for x in self.z(lambda s: (s['tekst'][1].pop('formy'), s['tekst'][1].update(pidpys='подій у даних')))))

    def test_zhytlo_zum(self):
        self.assertTrue(any('MV-151' in x for x in self.z(lambda s: s['kamera'][0].update(z=16.5))))

    def test_publichne_mistse_zblyzka_mozhna(self):
        S = copy.deepcopy(CHYSTYI129)
        S['kamera'][0]['z'] = 16.5
        self.assertFalse(any('MV-151' in x for x in P.pereviryty(S, dict(META129, publichni=['Глобус']))))

    def test_nomer_rishennia_lyshe_v_odnii_podii(self):
        dodaty = lambda s: s['tekst'].append({'t0': 1, 't1': 2, 'styl': 'mala', 'tekst': 'рішення суду № 123'})
        self.assertTrue(any('MV-151' in x for x in self.z(dodaty)))
        self.assertFalse(any('MV-151' in x for x in self.z(dodaty, dict(META129, odna_podiia=True))))
        self.assertTrue(any('MV-151' in x for x in self.z(None, dict(META129, odna_podiia=True))))


class Soty129(unittest.TestCase):
    def test_menshe_sot(self):
        from types import SimpleNamespace as N
        podii = [N(lat=50.45, lon=30.52)] * 10 + [N(lat=50.40, lon=30.60)] + [N(lat=50.50, lon=30.40)] * 4
        vsi = D.soty(podii, 8)
        menshe = D.soty(podii, 8, min_chastka=0.3, min_n=3)
        self.assertEqual(len(vsi['features']), 3)
        self.assertEqual(len(menshe['features']), 2)


class Holos129(unittest.TestCase):
    """ZAVDANNYA-129, крок 2: зовнішній голос — лише за змінною середовища, кеш, ключ ніде не пишеться."""

    def setUp(self):
        import os
        import tempfile
        self.os = os
        sys.path.insert(0, str(VAU))
        self.HS = modul('vau_holos_servis', 'holos_servis.py')
        self.tmp = tempfile.TemporaryDirectory()
        self.HS.KESH = Path(self.tmp.name)
        self.stari = {k: os.environ.get(k) for k in ('MV_HOLOS', 'MV_HOLOS_KLUCH')}

    def tearDown(self):
        for k, v in self.stari.items():
            if v is None:
                self.os.environ.pop(k, None)
            else:
                self.os.environ[k] = v
        self.tmp.cleanup()

    def test_bez_zminnoi_piper(self):
        self.os.environ.pop('MV_HOLOS', None)
        self.assertEqual(self.HS.servis(), 'piper')

    def test_platnyi_bez_kliucha_zupyniaietsia(self):
        self.os.environ['MV_HOLOS'] = 'elevenlabs'
        self.os.environ.pop('MV_HOLOS_KLUCH', None)
        with self.assertRaises(SystemExit):
            self.HS.servis()

    def test_kesh_i_kliuch_ne_v_fayli(self):
        if importlib.util.find_spec('numpy') is None:
            self.skipTest('немає numpy')
        self.os.environ['MV_HOLOS'] = 'azure'
        self.os.environ['MV_HOLOS_KLUCH'] = 'SEKRET-123'
        vyklyky = []

        def zapyt(t, imia, sh):
            vyklyky.append(t)
            return self.HS._pcm_v_wav(b'\x00\x10' * 4410, 44100)
        x, sr = self.HS.holos('64 події біля ТЦ', 'tetiana', zapyt=zapyt)
        self.HS.holos('64 події біля ТЦ', 'tetiana', zapyt=zapyt)
        self.assertEqual(len(vyklyky), 1)                       # вдруге — з кешу, не оплачується
        self.assertIn('шістдесят чотири', vyklyky[0])
        self.assertIn('те-це', vyklyky[0])
        self.assertEqual(sr, 44100)
        for f in Path(self.tmp.name).iterdir():
            self.assertNotIn('SEKRET', f.name)
            self.assertNotIn(b'SEKRET', f.read_bytes())
