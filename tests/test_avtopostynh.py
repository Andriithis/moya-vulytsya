"""Перевірки автопостингу (ZAVDANNYA-107): правила, розклад, черга, повтори, зупинка мережі, «прибрати», перехідники
мереж на штучних відповідях, сторінка-перегляд. Без мережі й без токенів.

Запуск: python -m unittest tests.test_avtopostynh -v
"""
from __future__ import annotations

import http.client
import json
import os
import sys
import tempfile
import threading
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlencode

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'avtopostynh'))

import cherha as C  # noqa: E402
import dzherela as D  # noqa: E402
import merezhi as M  # noqa: E402
import perehliad as H  # noqa: E402
import pravyla as P  # noqa: E402
import rozklad as R  # noqa: E402
import servis as SV  # noqa: E402
import zahlushka as Z  # noqa: E402

SAIT = 'https://moya-vulytsya.pages.dev'
PN = date(2026, 11, 23)          # понеділок, тиждень 2026-W48 (парний)


def odynytsia(**k) -> dict:
    o = {'id': 'x1', 'tyzhden': '2026-W48', 'merezha': 'telegram', 'kanal': 'Шевченківський', 'typ': 'dopys',
         'chas': '2026-11-23T07:00+00:00',
         'tekst': 'Історія з вулиці · Шевченківський район\n\nУ магазині взяли батончик на 214 грн і вийшли, не заплативши.'
                  '\n\nвулиця Хрещатик · 2025\nРішення № 128903549 — лише те, що дійшло до суду.',
         'knopky': [{'tekst': 'Що ще було', 'url': f'{SAIT}/vulytsia/khreshchatyk/?dzherelo=telegram-shevchenkivskyi'}],
         'mistse': {'shliakh': '/vulytsia/khreshchatyk/'}, 'podii': ['k2'], 'perepysano': True}
    o.update(k)
    return o


# Штучний генератор дописів з тим самим інтерфейсом, що bot/kanaly.py (ZAVDANNYA-97).
KANALY_PY = '''
from datetime import timedelta
class Henerator:
    def __init__(self, indeks, adresa_saitu='https://moya-vulytsya.pages.dev'):
        self.i, self.sait = indeks, adresa_saitu
    def pachka(self, vid, dniv, vzhe=None):
        vzhe = set(vzhe or ())
        r = []
        for rayon in sorted(x['n'] for x in self.i['rayony']):
            s = [x['s'] for x in self.i['rayony'] if x['n'] == rayon][0]
            podii = [p for p in self.i['koloda'] if p['rayon'] == rayon and p['id'] not in vzhe]
            for d in range(dniv):
                den = vid + timedelta(days=d)
                if not podii:
                    break
                p = podii.pop(0)
                r.append({'typ': 'istoriia', 'data': den.isoformat(), 'rayon': rayon, 'chernetka': True,
                          'perepysano': p.get('perepysano', False), 'podiia': p['id'], 'vulytsia': p['vs'],
                          'tekst': p['tekst'] + '\\nРішення № ' + p['n'] + ' — лише те, що дійшло до суду.',
                          'knopky': [[{'tekst': 'Уся вулиця', 'url': self.sait + '/vulytsia/' + p['vs'] + '/?dzherelo=tg-' + s}]]})
        return r
'''
INDEKS = {'versiia': '2026-11-08',
          'rayony': [{'n': 'Шевченківський', 's': 'shevchenkivskyi'}, {'n': 'Дарницький', 's': 'darnytskyi'}],
          'koloda': [{'id': f'p{i}', 'rayon': 'Шевченківський' if i % 2 else 'Дарницький', 'vs': 'khreshchatyk',
                      'n': f'12890354{i}', 'perepysano': True,
                      'tekst': f'У магазині взяли {i} шоколадок і вийшли, не заплативши.'} for i in range(1, 9)]}


class Sitka:
    """Штучна мережа: записує запити, віддає заготовлені відповіді."""

    def __init__(self, vidpovidi):
        self.vidpovidi, self.zapyty = list(vidpovidi), []

    def __call__(self, metod, url, zaholovky=None, tilo=None, chas=120):
        self.zapyty.append((metod, url, zaholovky or {}, tilo))
        st, zah, t = self.vidpovidi.pop(0)
        return M.Vidpovid(st, zah, json.dumps(t).encode() if isinstance(t, (dict, list)) else t)


class FalshyvaMerezha(M.Merezha):
    def __init__(self, rezultaty, vydalennia=None):
        super().__init__()
        self.rezultaty, self.vydalennia, self.vyklyky = list(rezultaty), list(vydalennia or []), []

    def opublikuvaty(self, o):
        self.vyklyky.append(o['id'])
        return self.rezultaty.pop(0) if self.rezultaty else M.Rezultat(True, id='1', url='https://t.me/x/1')

    def vydalyty(self, o):
        return self.vydalennia.pop(0) if self.vydalennia else M.Rezultat(True)


class Teka(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        self.media = self.t / 'media'
        Z.zrobyty(self.media)
        (self.t / 'bot').mkdir()
        (self.t / 'bot' / 'kanaly.py').write_text(KANALY_PY, encoding='utf-8')
        sys.modules.pop('kanaly', None)

    def tearDown(self):
        sys.modules.pop('kanaly', None)
        self._t.cleanup()

    def servis(self, probnyi=True, **k):
        sv = SV.Servis(self.t / 'stan', probnyi, self.media, SAIT, **k)
        self.addCleanup(sv.q.zakryty)
        return sv


# ======================================================================== правила
class Pravyla(unittest.TestCase):
    def zh(self, **k):
        return P.pereviryty(odynytsia(**k), SAIT)

    def test_dobra_odynytsia_prokhodyt(self):
        self.assertEqual(self.zh(), [])

    def test_nomer_zhytlovoho_budynku(self):
        for t in ('вул. Хрещатик, 22', 'вулиця Хрещатик, 22 — тут', 'біля будинку 12', 'Садова, 3/4.'):
            with self.subTest(t=t):
                z = self.zh(tekst=odynytsia()['tekst'].replace('вулиця Хрещатик · 2025', t))
                self.assertTrue(any('номер будинку' in x for x in z), z)

    def test_nomer_publichnoho_mistsia_mozhna(self):
        o = odynytsia(tekst=odynytsia()['tekst'].replace('вулиця Хрещатик · 2025', 'вул. Хрещатик, 22 (ТЦ)'),
                      mistse={'shliakh': '/vulytsia/khreshchatyk/', 'typ_mistsia': 'tts'})
        self.assertEqual(P.pereviryty(o, SAIT), [])

    def test_chysla_ne_plutaiutsia_z_nomeramy(self):
        for t in ('Вранці, 5 кошиків яблук', 'Київ, 2025', 'Шевченківський район, 12 подій'):
            with self.subTest(t=t):
                self.assertEqual(self.zh(tekst=odynytsia()['tekst'] + '\n' + t), [])

    def test_imena_i_slidy(self):
        for t in ('Іваненко І. І. взяв', 'О.П. Петренко', 'суддя Коваленко', 'ОСОБА_1 взяв', 'кв. 5'):
            with self.subTest(t=t):
                self.assertTrue(any("ім'я" in x for x in self.zh(tekst=odynytsia()['tekst'] + ' ' + t)))

    def test_nomer_spravy(self):
        self.assertIn('номер справи', self.zh(tekst=odynytsia()['tekst'] + ' справа 757/1234/24'))

    def test_zaboroneni_slova(self):
        for t in ('небезпечна вулиця', 'безпечний район', 'рейтинг районів', 'найгірший двір', 'топ-5 вулиць',
                  'куди не ходити'):
            with self.subTest(t=t):
                self.assertTrue(any('заборонене' in x for x in self.zh(tekst=odynytsia()['tekst'] + ' ' + t)))

    def test_chutlyvi(self):
        self.assertTrue(any('чутлива' in x for x in self.zh(tekst=odynytsia()['tekst'] + ' домашнє насильство')))
        self.assertTrue(any('чутлива' in x for x in self.zh(kategoriia='statevi')))

    def test_emodzi(self):
        self.assertIn('емодзі', self.zh(tekst=odynytsia()['tekst'] + ' \U0001F600'))

    def test_posylannia(self):
        k = lambda u: [{'tekst': 'x', 'url': u}]  # noqa: E731
        self.assertTrue(any('не на сторінку місця' in x for x in self.zh(knopky=k(f'{SAIT}/?dzherelo=telegram'))))
        self.assertTrue(any('на інше місце' in x
                            for x in self.zh(knopky=k(f'{SAIT}/vulytsia/sadova/?dzherelo=telegram'))))
        self.assertTrue(any('мітка' in x for x in self.zh(knopky=k(f'{SAIT}/vulytsia/khreshchatyk/?dzherelo=tiktok'))))
        self.assertTrue(any('мітка' in x for x in self.zh(knopky=k(f'{SAIT}/vulytsia/khreshchatyk/'))))
        dva = odynytsia()['tekst'] + f' {SAIT}/rayon/pecherskyi/?dzherelo=telegram'
        self.assertTrue(any('рівно одне' in x for x in self.zh(tekst=dva)))
        self.assertTrue(any('рівно одне' in x for x in self.zh(knopky=[])))

    def test_podiia_bez_mv60(self):
        z = self.zh(tekst='Історія: взяли батончик і вийшли.')
        self.assertTrue(any('дійшло до суду' in x for x in z))
        self.assertTrue(any('номера рішення' in x for x in z))

    def test_chernetka_bez_shi(self):
        self.assertTrue(any('чернетка' in x for x in self.zh(chernetka=True, perepysano=False)))
        self.assertEqual(self.zh(chernetka=True, perepysano=True), [])

    def test_mezhi_dovzhyny(self):
        self.assertTrue(any('довший' in x for x in self.zh(tekst=odynytsia()['tekst'] + 'а' * 4100)))
        v = odynytsia(typ='vikteryna', pytannia='?' * 301, varianty=['а', 'б'], pravylna=0,
                      poiasnennia='Рішення № 128903549 — лише те, що дійшло до суду.')
        self.assertTrue(any('pytannia' in x for x in P.pereviryty(v, SAIT)))

    def test_prybrane_i_povtory(self):
        z = {'podiia': {'k2': 'лякає'}, 'mistse': {}, 'tekst': {}, 'pozytsiia': {}}
        self.assertTrue(any('прибирали' in x for x in P.pereviryty(odynytsia(), SAIT, zaboroneno=z)))
        z = {'podiia': {}, 'mistse': {'/vulytsia/khreshchatyk/': 'не те місце'}, 'tekst': {}, 'pozytsiia': {}}
        self.assertTrue(any('більше не пишемо' in x for x in P.pereviryty(odynytsia(), SAIT, zaboroneno=z)))
        self.assertTrue(any('90 днів' in x for x in P.pereviryty(odynytsia(), SAIT, nedavni_podii={'k2'})))

    def test_youtube_i_tiktok_lyshe_rolyky(self):
        o = odynytsia(merezha='youtube', kanal='', knopky=[], nazva='Назва',
                      posylannia=f'{SAIT}/vulytsia/khreshchatyk/?dzherelo=youtube')
        self.assertTrue(any('лише ролики' in x for x in P.pereviryty(o, SAIT)))


# ======================================================================== розклад
class Rozklad(unittest.TestCase):
    def test_tyzhden_za_kompasom(self):
        s = R.sloty_rolykiv(PN)
        hrupy = [x['hrupa'] for x in s]
        self.assertEqual(sorted(hrupy), sorted(['shcho_bolyt', 'istorii', 'istorii', 'hry', 'hry', 'shcho_buvaie',
                                                'zghory', 'istorii_z_danykh', 'yak_pratsiuie']))
        # по одному «основному» ролику (18:00) на кожен день
        vechirni = [x for x in s if x['chas'].endswith('T16:00+00:00')]
        self.assertEqual(len({x['den'] for x in vechirni}), 7)
        self.assertEqual([x for x in s if x['hrupa'] == 'istorii_z_danykh'][0]['merezhi'], ('facebook',))

    def test_yak_pratsiuie_raz_na_dva_tyzhni(self):
        self.assertNotIn('yak_pratsiuie', [x['hrupa'] for x in R.sloty_rolykiv(date(2026, 11, 30))])

    def test_chas_za_kyievom(self):
        self.assertEqual(R.chas(PN, 18), '2026-11-23T16:00+00:00')            # зима, UTC+2
        self.assertEqual(R.chas(date(2026, 7, 6), 18), '2026-07-06T15:00+00:00')  # літо, UTC+3
        self.assertEqual(R.chas_telegram(PN, 3), '2026-11-23T07:06+00:00')


# ======================================================================== пачка й публікація
class Pachka(Teka):
    def test_probnyi_rezhym_naskriz(self):
        sv = self.servis()
        r = sv.pachka(PN, INDEKS, self.t / 'bot', zaraz=datetime(2026, 11, 20, tzinfo=timezone.utc))
        self.assertEqual(r['tyzhden'], '2026-W48')
        vsi = sv.q.vsi('2026-W48')
        tg = [o for o in vsi if o['merezha'] == 'telegram']
        self.assertEqual(len(tg), 8)                         # 4 події на кожен із 2 районів
        self.assertTrue(all('dzherelo=telegram-' in o['knopky'][0]['url'] for o in tg))
        for m in ('youtube', 'tiktok'):
            self.assertEqual(len([o for o in vsi if o['merezha'] == m]), 8)   # 7 днів + «Як це працює»
        self.assertEqual([o['stan'] for o in vsi if o['stan'] != 'chekaie'], [])
        teka = sv.teka / 'pachky' / '2026-W48'
        self.assertTrue((teka / 'pachka.json').is_file())
        html = (teka / 'perehliad.html').read_text(encoding='utf-8')
        self.assertIn('пробний режим', html)
        self.assertNotIn('<form', html)
        # повторне складання нічого не дублює
        self.assertEqual(sv.pachka(PN, INDEKS, self.t / 'bot')['novi'], 0)
        # «публікуємо» понеділок 18:05 за Києвом: Telegram ранку й ролик вечора, по одному на мережу/канал
        zv = sv.publikuvaty(datetime(2026, 11, 23, 16, 5, tzinfo=timezone.utc))
        self.assertEqual(len(zv), 6)                          # 2 канали + 4 мережі ролика
        self.assertEqual(len(list((sv.teka / 'opublikovano').rglob('*.json'))), 6)
        self.assertEqual(len(list((sv.teka / 'opublikovano' / 'youtube').rglob('*.mp4'))), 1)

    def test_bez_henerator_kanaliv(self):
        sv = self.servis()
        r = sv.pachka(PN, INDEKS, self.t / 'nema')
        if not (KORIN / 'bot' / 'kanaly.py').exists():
            self.assertTrue(any('kanaly.py' in x for x in r['propusky']))

    def test_poviazani_podii_ne_povtoriuiutsia(self):
        sv = self.servis()
        sv.pachka(PN, INDEKS, self.t / 'bot')
        sv.pachka(date(2026, 11, 30), INDEKS, self.t / 'bot')
        podii = [p for o in sv.q.vsi() if o['merezha'] == 'telegram' for p in o['podii']]
        self.assertEqual(len(podii), len(set(podii)))
        # ролики наступного тижня — інші позиції (заглушка має 9 роликів: другий тиждень — без повторів, з пропусками)
        poz = [o['pozytsiia'] for o in sv.q.vsi() if o['merezha'] == 'tiktok']
        self.assertEqual(len(poz), len(set(poz)))

    def test_zapiznennia_i_vymknena_merezha(self):
        with mock.patch.dict(os.environ, {'MV_MEREZHI': 'telegram'}):
            sv = self.servis(probnyi=False, merezhi_={'telegram': FalshyvaMerezha([])})
            sv.pachka(PN, INDEKS, self.t / 'bot')
            zv = sv.publikuvaty(datetime(2026, 11, 25, 16, 5, tzinfo=timezone.utc))
        stany = {o['stan'] for o in sv.q.vsi() if o['merezha'] == 'youtube' and o['chas'] < '2026-11-24T16'}
        self.assertEqual(stany, {'propushcheno'})
        self.assertTrue(all('опубліковано' in x for x in zv))
        self.assertTrue(any(o['stan'] == 'propushcheno' and o['merezha'] == 'telegram' for o in sv.q.vsi()))

    def test_hodyna_novyi_vypusk(self):
        (self.t / 'indeks.json').write_text(json.dumps(INDEKS), encoding='utf-8')
        sv = self.servis()
        zaraz = datetime(2026, 11, 18, 10, tzinfo=timezone.utc)      # середа
        zv = sv.hodyna(self.t / 'indeks.json', self.t / 'bot', zaraz)
        self.assertEqual(sorted(sv.q.tyzhni()), ['2026-W47', '2026-W48'])
        self.assertTrue(any('пачка 2026-W48' in x for x in zv))
        self.assertFalse(any('пачка' in x for x in sv.hodyna(self.t / 'indeks.json', self.t / 'bot', zaraz)))


class Pomylky(Teka):
    def pidhotuvaty(self, rezultaty):
        f = FalshyvaMerezha(rezultaty)
        with mock.patch.dict(os.environ, {'MV_MEREZHI': 'telegram'}):
            sv = self.servis(probnyi=False, merezhi_={'telegram': f})
            sv.pachka(PN, INDEKS, self.t / 'bot')
        return sv, f

    def run(self, result=None):
        with mock.patch.dict(os.environ, {'MV_MEREZHI': 'telegram'}):
            return super().run(result)

    def test_povtorna_sproba_i_pomylka(self):
        T = M.Rezultat(False, pomylka='503', typ='tymchasova')
        sv, f = self.pidhotuvaty([T] * 10)
        t = datetime(2026, 11, 23, 7, 30, tzinfo=timezone.utc)
        sv.publikuvaty(t)
        o = [x for x in sv.q.vsi() if x['merezha'] == 'telegram' and x['sproby']]
        self.assertEqual(len(o), 2)
        self.assertGreater(o[0]['nastupna'], C.iso(t))
        sv.publikuvaty(t)                          # ще не час повтору
        self.assertEqual(len(f.vyklyky), 2)

    def test_try_pomylky_pidriad_zupyniaiut_merezhu(self):
        T = M.Rezultat(False, pomylka='503', typ='tymchasova')
        sv, f = self.pidhotuvaty([T] * 10)
        sv.publikuvaty(datetime(2026, 11, 23, 7, 30, tzinfo=timezone.utc))    # 2 канали — 2 помилки
        sv.publikuvaty(datetime(2026, 11, 23, 8, 31, tzinfo=timezone.utc))    # повтор: третя помилка — зупинка
        self.assertEqual(len(f.vyklyky), 3)
        self.assertTrue(sv.q.merezha_zupynena('telegram', datetime(2026, 11, 23, 9, tzinfo=timezone.utc)))
        self.assertFalse(sv.q.merezha_zupynena('telegram', datetime(2026, 11, 24, 9, tzinfo=timezone.utc)))
        self.assertTrue(any(z['podiia'] == 'zupynka' for z in sv.q.zhurnal()))

    def test_blokuvannia_zupyniaie_do_vidnovlennia(self):
        B = M.Rezultat(False, pomylka='Forbidden: bot was kicked', typ='blokuvannia')
        sv, f = self.pidhotuvaty([B])
        zv = sv.publikuvaty(datetime(2026, 11, 23, 7, 30, tzinfo=timezone.utc))
        self.assertTrue(any('ЗУПИНЕНО' in x for x in zv))
        self.assertEqual(len(f.vyklyky), 1)        # другий канал уже не пробує
        sv.publikuvaty(datetime(2026, 11, 30, 7, 30, tzinfo=timezone.utc))
        self.assertEqual(len(f.vyklyky), 1)
        sv.q.vidnovyty('telegram')
        sv.publikuvaty(datetime(2026, 11, 23, 7, 40, tzinfo=timezone.utc))
        self.assertEqual(len(f.vyklyky), 3)

    def test_prybraty(self):
        sv, f = self.pidhotuvaty([])
        sv.publikuvaty(datetime(2026, 11, 23, 7, 30, tzinfo=timezone.utc))
        o = [x for x in sv.q.vsi() if x['stan'] == 'opublikovano'][0]
        self.assertEqual(sv.prybraty(o['id'], 'лякає', mistse=True), ['telegram: видалено'])
        self.assertEqual(sv.q.odna(o['id'])['stan'], 'prybrano')
        z = sv.q.zaboroneno()
        self.assertIn(o['podii'][0], z['podiia'])
        self.assertIn(o['mistse']['shliakh'], z['mistse'])
        # те саме місце в черзі — більше не вийде
        sv.publikuvaty(datetime(2026, 11, 24, 7, 30, tzinfo=timezone.utc))
        self.assertTrue(any('більше не пишемо' in ' '.join(x['zauvazhennia']) for x in sv.q.vsi(stan='vidkhyleno')))

    def test_prybraty_vruchnu(self):
        sv, f = self.pidhotuvaty([])
        f.vydalennia = [M.Rezultat(False, pomylka='message can\'t be deleted', typ='ne_vmiie')]
        sv.publikuvaty(datetime(2026, 11, 23, 7, 30, tzinfo=timezone.utc))
        o = [x for x in sv.q.vsi() if x['stan'] == 'opublikovano'][0]
        self.assertIn('вручну', sv.prybraty(o['id'], 'неточно')[0])
        self.assertEqual(sv.q.odna(o['id'])['stan'], 'prybraty_vruchnu')

    def test_prybraty_rolyk_z_usikh_merezh(self):
        sv = self.servis()
        sv.pachka(PN, None)
        sv.publikuvaty(datetime(2026, 11, 23, 16, 5, tzinfo=timezone.utc))
        o = [x for x in sv.q.vsi() if x['merezha'] == 'youtube' and x['stan'] == 'opublikovano'][0]
        self.assertEqual(len(sv.prybraty(o['id'], 'нецікаво', usi_merezhi=True)), 4)
        self.assertIn(o['pozytsiia'], sv.q.zaboroneno()['pozytsiia'])


# ======================================================================== перехідники на штучних відповідях
class Telegram(unittest.TestCase):
    TOKEN = '123456:SEKRET-token'

    def tg(self, vidpovidi):
        s = Sitka(vidpovidi)
        with mock.patch.dict(os.environ, {'MV_TELEGRAM_TOKEN': self.TOKEN}):
            return M.Telegram({'Шевченківський': '@mv_shevchenkivskyi'}, http_=s), s

    def test_dopys(self):
        t, s = self.tg([(200, {}, {'ok': True, 'result': {'message_id': 7, 'chat': {'username': 'mv_shevchenkivskyi'}}})])
        r = t.opublikuvaty(odynytsia())
        self.assertTrue(r.ok)
        self.assertEqual(r.url, 'https://t.me/mv_shevchenkivskyi/7')
        metod, url, _, tilo = s.zapyty[0]
        self.assertTrue(url.endswith('/sendMessage'))
        j = json.loads(tilo)
        self.assertEqual(j['chat_id'], '@mv_shevchenkivskyi')
        self.assertEqual(j['reply_markup']['inline_keyboard'][0][0]['url'], odynytsia()['knopky'][0]['url'])

    def test_viktoryna(self):
        t, s = self.tg([(200, {}, {'ok': True, 'result': {'message_id': 8, 'chat': {}}})])
        t.opublikuvaty(odynytsia(typ='vikteryna', pytannia='Де?', varianty=['а', 'б', 'в'], pravylna=2, poiasnennia='п'))
        j = json.loads(s.zapyty[0][3])
        self.assertEqual((j['type'], j['correct_option_id'], len(j['options'])), ('quiz', 2, 3))

    def test_pomylky(self):
        t, _ = self.tg([(429, {}, {'ok': False, 'error_code': 429, 'description': 'Too Many Requests',
                                   'parameters': {'retry_after': 33}})])
        r = t.opublikuvaty(odynytsia())
        self.assertEqual((r.typ, r.chekaty_s), ('tymchasova', 33))
        t, _ = self.tg([(403, {}, {'ok': False, 'error_code': 403,
                                   'description': f'Forbidden: bot was kicked {self.TOKEN}'})])
        r = t.opublikuvaty(odynytsia())
        self.assertEqual(r.typ, 'blokuvannia')
        self.assertNotIn(self.TOKEN, r.pomylka)
        t, _ = self.tg([(0, {}, b'')])
        self.assertEqual(t.opublikuvaty(odynytsia()).typ, 'tymchasova')
        t, _ = self.tg([(400, {}, {'ok': False, 'error_code': 400, 'description': "message can't be deleted"})])
        self.assertEqual(t.vydalyty(odynytsia(zovnishnii_id='7')).typ, 'ne_vmiie')

    def test_bez_tokena(self):
        with mock.patch.dict(os.environ, {'MV_TELEGRAM_TOKEN': ''}):
            with self.assertRaises(M.NeNalashtovano):
                M.Telegram({})


class InshiMerezhi(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        (self.t / 'r.mp4').write_bytes(b'video')
        self.o = odynytsia(merezha='youtube', kanal='', typ='rolyk', fail='r.mp4', nazva='Назва', knopky=[],
                           posylannia=f'{SAIT}/vulytsia/khreshchatyk/?dzherelo=youtube')

    def tearDown(self):
        self._t.cleanup()

    def test_youtube(self):
        s = Sitka([(200, {}, {'access_token': 'AT'}), (200, {'Location': 'https://up/1'}, b''), (200, {}, {'id': 'abc'})])
        env = {'MV_YOUTUBE_CLIENT_ID': 'c', 'MV_YOUTUBE_CLIENT_SECRET': 's', 'MV_YOUTUBE_REFRESH_TOKEN': 'rt'}
        with mock.patch.dict(os.environ, env):
            r = M.YouTube(http_=s, teka_media=self.t).opublikuvaty(self.o)
        self.assertEqual(r.url, 'https://www.youtube.com/shorts/abc')
        meta = json.loads(s.zapyty[1][3])
        self.assertEqual(meta['snippet']['title'], 'Назва')
        self.assertEqual(s.zapyty[2][0], 'PUT')
        s = Sitka([(200, {}, {'access_token': 'AT'}),
                   (403, {}, {'error': {'message': 'q', 'errors': [{'reason': 'quotaExceeded'}]}})])
        with mock.patch.dict(os.environ, env):
            r = M.YouTube(http_=s, teka_media=self.t).opublikuvaty(self.o)
        self.assertEqual(r.typ, 'tymchasova')

    def test_facebook_reels(self):
        s = Sitka([(200, {}, {'video_id': 'v1', 'upload_url': 'u'}), (200, {}, {'success': True}),
                   (200, {}, {'success': True})])
        with mock.patch.dict(os.environ, {'MV_META_PAGE_ID': 'pg', 'MV_META_PAGE_TOKEN': 'PT'}):
            r = M.Facebook(http_=s, teka_media=self.t).opublikuvaty(dict(self.o, merezha='facebook'))
        self.assertTrue(r.ok)
        self.assertIn('upload_phase=start', s.zapyty[0][3].decode())
        self.assertIn('rupload.facebook.com', s.zapyty[1][1])
        self.assertIn('video_state=PUBLISHED', s.zapyty[2][3].decode())
        s = Sitka([(400, {}, {'error': {'code': 190, 'message': 'token PT expired'}})])
        with mock.patch.dict(os.environ, {'MV_META_PAGE_ID': 'pg', 'MV_META_PAGE_TOKEN': 'PT'}):
            r = M.Facebook(http_=s, teka_media=self.t).opublikuvaty(dict(self.o, merezha='facebook'))
        self.assertEqual(r.typ, 'blokuvannia')
        self.assertNotIn('PT', r.pomylka.replace('expired', ''))

    def test_instagram(self):
        s = Sitka([(200, {}, {'id': 'c1'}), (200, {}, {'status_code': 'IN_PROGRESS'}), (200, {}, {'status_code': 'FINISHED'}),
                   (200, {}, {'id': 'm1'}), (200, {}, {'permalink': 'https://instagram.com/p/x'})])
        env = {'MV_INSTAGRAM_ID': 'ig', 'MV_META_PAGE_TOKEN': 'PT', 'MV_MEDIA_URL': 'https://media.example/pachky'}
        with mock.patch.dict(os.environ, env):
            r = M.Instagram(http_=s, teka_media=self.t, spaty=lambda s: None).opublikuvaty(dict(self.o, merezha='instagram'))
        self.assertEqual(r.url, 'https://instagram.com/p/x')
        self.assertIn('video_url=https%3A%2F%2Fmedia.example%2Fpachky%2Fr.mp4', s.zapyty[0][3].decode())
        with mock.patch.dict(os.environ, {'MV_INSTAGRAM_ID': 'ig', 'MV_META_PAGE_TOKEN': 'PT', 'MV_MEDIA_URL': ''}):
            r = M.Instagram(http_=Sitka([]), teka_media=self.t).opublikuvaty(dict(self.o, merezha='instagram'))
        self.assertEqual(r.typ, 'blokuvannia')

    def test_tiktok_i_novyi_kliuch(self):
        fail = self.t / 'tiktok.token'
        s = Sitka([(200, {}, {'access_token': 'AT', 'refresh_token': 'NOVYI'}),
                   (200, {}, {'data': {'privacy_level_options': ['SELF_ONLY']}}),
                   (200, {}, {'data': {'publish_id': 'p1'}}),
                   (200, {}, {'data': {'status': 'PUBLISH_COMPLETE', 'publicaly_available_post_id': [99]}})])
        env = {'MV_TIKTOK_CLIENT_KEY': 'k', 'MV_TIKTOK_CLIENT_SECRET': 's', 'MV_TIKTOK_REFRESH_TOKEN': 'STARYI',
               'MV_TIKTOK_TOKEN_FAIL': str(fail), 'MV_MEDIA_URL': 'https://media.example'}
        with mock.patch.dict(os.environ, env):
            r = M.TikTok(http_=s, teka_media=self.t, spaty=lambda s: None).opublikuvaty(dict(self.o, merezha='tiktok'))
        self.assertTrue(r.ok)
        self.assertEqual(fail.read_text(), 'NOVYI')
        self.assertEqual(oct(fail.stat().st_mode)[-3:], '600')
        init = json.loads(s.zapyty[2][3])
        self.assertEqual(init['post_info']['privacy_level'], 'SELF_ONLY')
        self.assertEqual(init['source_info']['source'], 'PULL_FROM_URL')
        self.assertFalse(M.TikTok.vydaliaie)


# ======================================================================== сторінка-перегляд
class Perehliad(Teka):
    PAROL = 'dovhyi-parol-dlia-testu'

    def setUp(self):
        super().setUp()
        hotovo = threading.Event()

        def server():
            sv = SV.Servis(self.t / 'stan', True, self.media, SAIT)      # база — у потоці сервера
            sv.pachka(PN, None)
            sv.publikuvaty(datetime(2026, 11, 23, 16, 5, tzinfo=timezone.utc))
            self.id_ = [o['id'] for o in sv.q.vsi() if o['stan'] == 'opublikovano'][0]
            self.srv = H.HTTPServer(('127.0.0.1', 0), H.obrobnyk(sv, self.PAROL))
            hotovo.set()
            self.srv.serve_forever()
            sv.q.zakryty()
        self.potik = threading.Thread(target=server, daemon=True)
        self.potik.start()
        hotovo.wait(10)
        self.port = self.srv.server_address[1]

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.potik.join(10)
        super().tearDown()

    def zapyt(self, metod, shliakh, polia=None, kuka=''):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=10)
        zah = {'Content-Type': 'application/x-www-form-urlencoded'}
        if kuka:
            zah['Cookie'] = kuka
        c.request(metod, shliakh, urlencode(polia or {}), zah)
        v = c.getresponse()
        return v.status, dict(v.getheaders()), v.read().decode('utf-8', 'replace')

    def test_vkhid_perehliad_prybraty(self):
        st, _, t = self.zapyt('GET', '/?tyzhden=2026-W48')
        self.assertIn('Пароль', t)
        self.assertNotIn('ЗАГЛУШКА', t)
        st, _, _ = self.zapyt('POST', '/vkhid', {'parol': 'ne-toi'})
        self.assertEqual(st, 401)
        st, zah, _ = self.zapyt('POST', '/vkhid', {'parol': self.PAROL})
        self.assertEqual(st, 303)
        kuka = zah['Set-Cookie'].split(';')[0]
        self.assertIn('HttpOnly', zah['Set-Cookie'])
        st, _, t = self.zapyt('GET', '/?tyzhden=2026-W48', kuka=kuka)
        self.assertEqual(st, 200)
        for m in ('YouTube', 'Facebook', 'Instagram', 'TikTok', 'ЗАГЛУШКА', 'вийшло', 'Прибрати'):
            self.assertIn(m, t)
        # без токена форми — ні
        st, _, _ = self.zapyt('POST', '/prybraty', {'id': self.id_, 'prychyna': 'інше'}, kuka)
        self.assertEqual(st, 403)
        csrf = H.pidpys(self.PAROL, 'csrf')
        st, zah, _ = self.zapyt('POST', '/prybraty', {'id': self.id_, 'prychyna': 'лякає чи ранжує', 'csrf': csrf,
                                                       'tyzhden': '2026-W48', 'usi_merezhi': '1'}, kuka)
        self.assertEqual(st, 303)
        self.assertIn('видалено', parse_qs(zah['Location'].split('?', 1)[1])['p'][0])
        _, _, t = self.zapyt('GET', '/?tyzhden=2026-W48', kuka=kuka)
        self.assertIn('прибрано', t)
        self.assertIn('лякає чи ранжує', t)

    def test_media_lyshe_z_teky(self):
        st, zah, _ = self.zapyt('POST', '/vkhid', {'parol': self.PAROL})
        kuka = zah['Set-Cookie'].split(';')[0]
        self.assertEqual(self.zapyt('GET', '/media/kartky/zahlushka-tsyfry-0.png', kuka=kuka)[0], 200)
        self.assertEqual(self.zapyt('GET', '/media/../stan/cherha.db', kuka=kuka)[0], 404)
        self.assertEqual(self.zapyt('GET', '/media/kartky/zahlushka-tsyfry-0.png')[0], 401)


class Dzherela(unittest.TestCase):
    def test_media_bez_povtoriv_i_propusky(self):
        manifest = [{'nazva': 'a', 'typ': 'rolyk', 'hrupa': 'hry', 'fail': 'a.mp4', 'pidpys': 'Гра.',
                     'mistse': {'shliakh': '/vulytsia/x/', 'nazva': 'вулиця X'}}]
        od, pr = D.media_tyzhnia(manifest, PN, set(), SAIT)
        self.assertEqual({o['merezha'] for o in od}, {'youtube', 'facebook', 'instagram', 'tiktok'})
        self.assertTrue(all(o['posylannia'].endswith(f'?dzherelo={o["merezha"]}') for o in od))
        self.assertTrue(any('«Що болить вулиці»' in p for p in pr))
        od, _ = D.media_tyzhnia(manifest, PN, {'a'}, SAIT)
        self.assertEqual(od, [])


if __name__ == '__main__':
    unittest.main()
