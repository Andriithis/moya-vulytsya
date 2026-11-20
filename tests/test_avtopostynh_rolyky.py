"""Черга роликів і заміри (ZAVDANNYA-159): розклад з черги файлів, позначка «Голос змінено програмою» (MV-171), мітки
`?dzherelo=`, TikTok вручну, збір чисел YouTube / Instagram / Facebook на підроблених відповідях мереж, імпорт
вивантаження TikTok, тижневий підсумок за правилами `docs/ROLYKY-SYSTEMA.md`, розд. 4.4. Без мережі й без ключів.

Запуск: python -m unittest tests.test_avtopostynh_rolyky -v
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlsplit

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'avtopostynh'))

import cherha as C  # noqa: E402
import cherha_rolykiv as CR  # noqa: E402
import khmara as K  # noqa: E402
import merezhi as M  # noqa: E402
import pravyla as P  # noqa: E402
import servis as SV  # noqa: E402
import zamiry as Z  # noqa: E402

SAIT = 'https://moyavulytsya.com.ua'
PN_12 = datetime(2026, 11, 23, 10, 0, tzinfo=timezone.utc)      # понеділок 12:00 за Києвом
ROBOCHYI = KORIN / 'avtopostynh' / 'github' / 'zamiry.yml'
ROBOCHYI_AVTO = KORIN / 'avtopostynh' / 'github' / 'avtopostynh.yml'


class Sitka:
    """Підроблена мережа: записує запити; відповідь — за першим шаблоном адреси, що підійшов (або чергою)."""

    def __init__(self, vidpovidi):
        self.vidpovidi, self.zapyty = list(vidpovidi), []

    def __call__(self, metod, url, zaholovky=None, tilo=None, chas=120):
        self.zapyty.append((metod, url, zaholovky or {}, tilo))
        for i, (shablon, st, t) in enumerate(self.vidpovidi):
            if re.search(shablon, url):
                if shablon.startswith('^'):        # «^…» — одноразова відповідь
                    self.vidpovidi.pop(i)
                tilo_ = t.encode() if isinstance(t, str) else json.dumps(t).encode()
                return M.Vidpovid(st, {'location': 'https://upload.example/1'} if st == 200 else {}, tilo_)
        raise AssertionError(f'несподіваний запит {metod} {url}')


def opys(**k) -> dict:
    d = {'id': '129-t5', 'typ': 'Місто за N секунд', 'fail': '129-t5.mp4',
         'varianty': 'темна · соти · місто · без голосу · гачок А', 'dovzhyna_s': 9, 'holos': False,
         'zaholovok': 'Київ за 9 секунд',
         'pidpys': 'Кожна сота — події з рішень судів за роки даних. Колір — кількість даних, а не оцінка місця.',
         'kudy': '/karta/', 'kudy_nazva': 'Карта Києва'}
    d.update(k)
    return d


class Osnova(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.t = Path(self._t.name)
        self.media = self.t / 'media'
        (self.media / 'cherha').mkdir(parents=True)
        env = mock.patch.dict(os.environ, {'MV_ROLYKY_SLOTY': '18:00', 'MV_MEDIA_URL': ''})
        env.start()
        self.addCleanup(env.stop)

    def poklasty(self, nomer: int, **k) -> dict:
        d = opys(**k)
        (self.media / 'cherha' / d['fail']).write_bytes(b'\x00' * 1000)
        (self.media / 'cherha' / f'{nomer:03d}-{d["id"]}.json').write_text(json.dumps(d, ensure_ascii=False),
                                                                          encoding='utf-8')
        return d

    def servis(self) -> SV.Servis:
        sv = SV.Servis(self.t / 'stan', True, self.media, SAIT, {'Ролики': '@moyavulytsya'})
        self.addCleanup(sv.q.zakryty)
        return sv


# ==================================================================== черга й розклад
class Cherha(Osnova):
    def test_typy_z_reiestru(self):
        t = CR.typy()
        for nazva in ('Місто за N секунд', 'Сота розпадається', 'Вгадай, де це було', 'POV: застава завтра (К-25)'):
            self.assertIn(nazva, t)
        self.assertIn('гра', t['Вгадай, де це було']['format'])
        self.assertIsNone(CR.typ_z_reiestru('Місто за N секунд', t))
        self.assertIn('Місто за N секунд', CR.typ_z_reiestru('Місто за n секунд', t))

    def test_po_odnomu_na_slot_po_poriadku(self):
        self.poklasty(2, id='b2', fail='b2.mp4')
        self.poklasty(1, id='a1', fail='a1.mp4', merezhi=['youtube', 'tiktok', 'instagram'])
        sv = self.servis()
        zvit = sv.rolyky_z_cherhy(PN_12)
        self.assertFalse([x for x in zvit if 'НЕ ПРОЙШЛО' in x], zvit)
        vsi = sv.q.vsi()
        a1 = {o['merezha']: o for o in vsi if o['rolyk_id'] == 'a1'}
        b2 = {o['merezha']: o for o in vsi if o['rolyk_id'] == 'b2'}
        self.assertEqual(set(a1), {'youtube', 'tiktok', 'instagram'})
        self.assertEqual(set(b2), {'youtube', 'tiktok'})                        # типово Shorts + TikTok (MV-161)
        self.assertEqual(a1['youtube']['chas'], '2026-11-23T16:00+00:00')      # сьогодні 18:00 за Києвом
        self.assertEqual(b2['youtube']['chas'], '2026-11-24T16:00+00:00')      # завтра
        self.assertEqual(a1['tiktok']['stan'], CR.STAN_VRUCHNU)
        self.assertEqual(a1['youtube']['stan'], 'chekaie')
        # повторний запуск нічого не додає
        self.assertEqual(sv.rolyky_z_cherhy(PN_12 + timedelta(hours=1)), [])
        self.assertEqual(len(sv.q.vsi()), 5)

    def test_dva_sloty_na_den(self):
        for i in range(3):
            self.poklasty(i, id=f'r{i}', fail=f'r{i}.mp4')
        sv = self.servis()
        with mock.patch.dict(os.environ, {'MV_ROLYKY_SLOTY': '18:00,20:30'}):
            sv.rolyky_z_cherhy(PN_12)
        chasy = sorted({o['chas'] for o in sv.q.vsi()})
        self.assertEqual(chasy, ['2026-11-23T16:00+00:00', '2026-11-23T18:30+00:00', '2026-11-24T16:00+00:00'])

    def test_ne_ranishe(self):
        self.poklasty(1, ne_ranishe='2026-11-26')
        sv = self.servis()
        sv.rolyky_z_cherhy(PN_12)
        self.assertTrue(all(o['chas'].startswith('2026-11-26') for o in sv.q.vsi()))

    def test_mitka_i_posylannia(self):
        self.poklasty(1, merezhi=['youtube', 'instagram', 'facebook', 'telegram', 'tiktok'])
        sv = self.servis()
        sv.rolyky_z_cherhy(PN_12)
        for o in sv.q.vsi():
            q = parse_qs(urlsplit(o['posylannia']).query)
            self.assertEqual(q['dzherelo'], [f'{P.KOD_MEREZHI[o["merezha"]]}-129-t5'])
            self.assertEqual(urlsplit(o['posylannia']).path, '/karta/')
            self.assertLessEqual(len(q['dzherelo'][0]), 16)                     # вміщається в мітку входу 153
            if o['merezha'] == 'tiktok':
                self.assertNotIn('http', o['tekst'])                              # у TikTok — посилання в профілі
            else:
                self.assertIn(o['posylannia'], o['tekst'])
            self.assertEqual(o['stan'], CR.STAN_VRUCHNU if o['merezha'] == 'tiktok' else 'chekaie', o['zauvazhennia'])
        tg = next(o for o in sv.q.vsi() if o['merezha'] == 'telegram')
        self.assertEqual(tg['kanal'], 'Ролики')

    def test_poznachka_holosu(self):
        self.poklasty(1, holos=True, varianty='світла · адреси · вулиця · голос · гачок Б')
        sv = self.servis()
        sv.rolyky_z_cherhy(PN_12)
        for o in sv.q.vsi():
            self.assertIn('Голос змінено програмою', o['tekst'])
            self.assertNotIn('згенеровано', o['tekst'].lower())
        o = dict(sv.q.vsi()[0], tekst='Без позначки — на сайті: ' + sv.q.vsi()[0]['posylannia'])
        self.assertTrue(any('Голос змінено програмою' in z for z in P.pereviryty(o, SAIT, self.media)))
        bez = dict(o, holos=False)
        self.assertFalse(any('Голос' in z for z in P.pereviryty(bez, SAIT, self.media)))

    def test_typ_ne_z_reiestru_vidkhyleno(self):
        self.poklasty(1, typ='Щось нове')
        sv = self.servis()
        zvit = sv.rolyky_z_cherhy(PN_12)
        self.assertTrue(all(o['stan'] == 'vidkhyleno' for o in sv.q.vsi()))
        self.assertTrue(any('не з реєстру' in x for x in zvit))
        # виправили опис — плануємо знову, на інший вільний слот
        self.poklasty(1, typ='Місто за N секунд')
        sv.rolyky_z_cherhy(PN_12)
        dobri = [o for o in sv.q.vsi() if o['stan'] != 'vidkhyleno']
        self.assertEqual({o['merezha'] for o in dobri}, {'youtube', 'tiktok'})

    def test_pravyla_dlia_rolykiv(self):
        self.poklasty(1, pidpys='Найнебезпечніше місто за 9 секунд.')
        self.poklasty(2, id='x2', fail='x2.mp4', kudy='/oplata/')
        sv = self.servis()
        sv.rolyky_z_cherhy(PN_12)
        for o in sv.q.vsi():
            self.assertEqual(o['stan'], 'vidkhyleno')
        zh = ' '.join(z for o in sv.q.vsi() for z in o['zauvazhennia'])
        self.assertIn('заборонене слово', zh)
        self.assertIn('не на сторінку', zh)

    def test_pohanyi_opys_ne_lamaie(self):
        (self.media / 'cherha' / '000-zle.json').write_text('{не json', encoding='utf-8')
        self.poklasty(1, id='Велике ID')
        self.poklasty(2, id='ok1', fail='ok1.mp4')
        sv = self.servis()
        zvit = sv.rolyky_z_cherhy(PN_12)
        self.assertTrue(any('000-zle.json' in x for x in zvit))
        self.assertTrue(any('id «Велике ID»' in x for x in zvit))
        self.assertEqual({o['rolyk_id'] for o in sv.q.vsi()}, {'ok1'})

    def test_publikatsiia_bez_tiktok(self):
        self.poklasty(1, merezhi=['youtube', 'tiktok'])
        sv = self.servis()
        sv.hodyna(None, None, PN_12)                                       # 12:00 — став у слот 18:00
        zvit = sv.hodyna(None, None, PN_12 + timedelta(hours=6, minutes=23))
        self.assertTrue(any(x.startswith('youtube') and 'опубліковано' in x for x in zvit), zvit)
        self.assertFalse(any(x.startswith('tiktok') for x in zvit))
        tt = next(o for o in sv.q.vsi() if o['merezha'] == 'tiktok')
        self.assertEqual(tt['stan'], CR.STAN_VRUCHNU)                           # чекає людину, не «пропущено»
        sv.hodyna(None, None, PN_12 + timedelta(days=2))
        self.assertEqual(sv.q.odna(tt['id'])['stan'], CR.STAN_VRUCHNU)


# ==================================================================== TikTok вручну
class TikTokVruchnu(Osnova):
    def test_cheklist_faily_i_komanda(self):
        self.poklasty(1, holos=True)
        stan, vkhid = self.t / 'stan2', self.t / 'vkhid'
        (vkhid / 'media').mkdir(parents=True)
        os.rename(self.media / 'cherha', vkhid / 'media' / 'cherha')
        a = argparse.Namespace(id='', prychyna='', mistse=False, usi_merezhi=False, merezha='', posylannia='',
                               tiktok_teka=self.t / 'tt')
        with mock.patch.dict(os.environ, {'MV_ADRESA_SAITU': SAIT, 'MV_PROBNYI': '1'}):
            zvit = K.zapustyty(stan, vkhid, 'hodyna', a, PN_12)
        self.assertTrue(any('TikTok: 1' in x for x in zvit), zvit)
        md = (stan / K.TIKTOK).read_text(encoding='utf-8')
        self.assertIn('`129-t5`', md)
        self.assertIn('Голос змінено програмою', md)
        self.assertIn('Вміст, створений ШІ', md)
        self.assertIn(f'{SAIT}/?dzherelo=tt', md)
        faily = sorted(p.name for p in (self.t / 'tt').iterdir())
        self.assertEqual(faily, ['1123-1800-129-t5.mp4', '1123-1800-129-t5.txt'])
        # Микита поставив і вписав посилання
        a.id, a.posylannia = '129-t5', 'https://www.tiktok.com/@moyavulytsya/video/7400000000000000001'
        with mock.patch.dict(os.environ, {'MV_ADRESA_SAITU': SAIT}):
            zvit = K.zapustyty(stan, vkhid, 'tiktok', a, PN_12 + timedelta(hours=7))
        self.assertIn('записано', zvit[-1])
        q = C.Cherha(stan / 'cherha.db')
        tt = next(o for o in q.vsi() if o['merezha'] == 'tiktok')
        q.zakryty()
        self.assertEqual((tt['stan'], tt['zovnishnii_id']), ('opublikovano', '7400000000000000001'))
        # погане посилання — не записуємо
        q = C.Cherha(stan / 'cherha.db')
        self.addCleanup(q.zakryty)
        self.assertIn('https://www.tiktok.com', CR.tiktok_postavleno(q, '129-t5', 'tiktok.com/x', PN_12))
        self.assertIn('немає ролика', CR.tiktok_postavleno(q, 'nema', a.posylannia, PN_12))


# ==================================================================== мережі: публікація
class Publikatsiia(Osnova):
    def setUp(self):
        super().setUp()
        (self.media / 'r.mp4').write_bytes(b'\x00' * 100)
        self.o = {'id': 'x', 'merezha': 'instagram', 'typ': 'rolyk', 'fail': 'r.mp4', 'tekst': 'Підпис', 'nazva': 'Н'}

    def test_instagram_chastynamy_bez_publichnoi_adresy(self):
        s = Sitka([(r'^.*/ig/media$', 200, {'id': 'c1', 'uri': 'https://rupload.facebook.com/ig-api-upload/v27.0/c1'}),
                   (r'rupload\.facebook\.com', 200, {'success': True}),
                   (r'/c1\?', 200, {'status_code': 'FINISHED'}),
                   (r'media_publish', 200, {'id': 'm1'}),
                   (r'/m1\?', 200, {'permalink': 'https://www.instagram.com/reel/m1'})])
        with mock.patch.dict(os.environ, {'MV_INSTAGRAM_ID': 'ig', 'MV_META_PAGE_TOKEN': 'PT', 'MV_MEDIA_URL': ''}):
            r = M.Instagram(http_=s, teka_media=self.media, spaty=lambda x: None).opublikuvaty(self.o)
        self.assertTrue(r.ok, r.pomylka)
        self.assertIn('upload_type=resumable', s.zapyty[0][3].decode())
        self.assertNotIn('video_url', s.zapyty[0][3].decode())
        self.assertEqual(s.zapyty[1][2]['Authorization'], 'OAuth PT')
        self.assertEqual(s.zapyty[1][2]['file_size'], '100')
        self.assertEqual(r.url, 'https://www.instagram.com/reel/m1')

    def test_youtube_zminenyi_vmist_lyshe_z_holosom(self):
        for holos, ochikuiemo in ((True, True), (False, False)):
            s = Sitka([(r'oauth2', 200, {'access_token': 'AT'}),
                       (r'^.*uploadType=resumable', 200, {}),
                       (r'upload\.example', 200, {'id': 'v1'})])
            env = {'MV_YOUTUBE_CLIENT_ID': 'c', 'MV_YOUTUBE_CLIENT_SECRET': 's', 'MV_YOUTUBE_REFRESH_TOKEN': 'r'}
            with mock.patch.dict(os.environ, env):
                os.environ.pop('MV_YOUTUBE_SYNTETYCHNYI', None)
                r = M.YouTube(http_=s, teka_media=self.media).opublikuvaty(dict(self.o, merezha='youtube', holos=holos))
            self.assertTrue(r.ok)
            meta = json.loads(s.zapyty[1][3])
            self.assertIs(meta['status']['containsSyntheticMedia'], ochikuiemo)


# ==================================================================== заміри
def reiestr_db(shliakh: Path, rolyky: list[tuple]) -> None:
    """rolyky: (id, typ, merezha, зовнішній id, дата публікації, варіанти, довжина)."""
    q = C.Cherha(shliakh)
    for i, (rid, typ, m, zid, data, var, dovzh) in enumerate(rolyky):
        o = {'id': f'u{i}', 'tyzhden': '2026-W48', 'merezha': m, 'typ': 'rolyk', 'chas': f'{data}T16:00+00:00',
             'dzherelo': 'cherha', 'rolyk_id': rid, 'typ_rolyka': typ, 'varianty': var, 'dovzhyna_s': dovzh,
             'holos': False, 'kudy': '/karta/'}
        q.dodaty(o, [])
        q.stan(o['id'], 'opublikovano', zovnishnii_id=zid, opublikovano=f'{data}T16:05+00:00',
               url_dopysu=f'https://www.tiktok.com/@mv/video/{zid}' if m == 'tiktok' else f'https://x/{zid}')
    q.dodaty({'id': 'stare', 'tyzhden': '2026-W48', 'merezha': 'youtube', 'typ': 'rolyk', 'chas': '2026-11-20T16:00+00:00',
              'dzherelo': 'manifest'}, [])                                      # не з черги — у реєстр не йде
    q.zakryty()


class Zamiry(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.t = Path(self._t.name)
        self.db = self.t / 'cherha.db'
        self.zamiry = self.t / 'zamiry'
        reiestr_db(self.db, [
            ('t5', 'Місто за N секунд', 'youtube', 'YT1', '2026-11-23', 'темна · гачок А', 9),
            ('t5', 'Місто за N секунд', 'instagram', 'IG1', '2026-11-23', 'темна · гачок А', 9),
            ('t5', 'Місто за N секунд', 'facebook', 'FB1', '2026-11-23', 'темна · гачок А', 9),
            ('t5', 'Місто за N секунд', 'tiktok', '7400000000000000001', '2026-11-23', 'темна · гачок А', 9),
        ])

    def sitka(self):
        return Sitka([
            (r'oauth2', 200, {'access_token': 'AT'}),
            (r'youtube/v3/videos', 200, {'items': [{'id': 'YT1', 'statistics': {'viewCount': '1500', 'likeCount': '40',
                                                                                 'commentCount': '6'}}]}),
            (r'dimensions=video&', 200, {'columnHeaders': [{'name': 'video'}, {'name': 'engagedViews'},
                                                           {'name': 'averageViewDuration'},
                                                           {'name': 'averageViewPercentage'}, {'name': 'shares'}],
                                         'rows': [['YT1', 900, 6.5, 72.3, 4]]}),
            (r'elapsedVideoTimeRatio', 200, {'rows': [[0.1, 1.2], [0.3, 0.9], [0.34, 0.81], [0.5, 0.7]]}),
            (r'/IG1/insights', 200, {'data': [{'name': 'views', 'values': [{'value': 800}]},
                                              {'name': 'likes', 'values': [{'value': 30}]},
                                              {'name': 'comments', 'values': [{'value': 2}]},
                                              {'name': 'shares', 'values': [{'value': 1}]},
                                              {'name': 'saved', 'values': [{'value': 5}]},
                                              {'name': 'ig_reels_avg_watch_time', 'values': [{'value': 5400}]}]}),
            (r'/FB1/video_insights', 200, {'data': [
                {'name': 'blue_reels_play_count', 'values': [{'value': 300}]},
                {'name': 'post_video_avg_time_watched', 'values': [{'value': 4100}]},
                {'name': 'post_video_social_actions', 'values': [{'value': {'COMMENT': 1, 'SHARE': 2}}]},
                {'name': 'post_video_likes_by_reaction_type', 'values': [{'value': {'REACTION_LIKE': 7, 'REACTION_LOVE': 1}}]}]}),
            (r'vyvantazhennia/podiya', 200, 'den,nazva,kanal,n\r\n2026-11-24,klik,vh-meshk-yt-t5,3\r\n'
                                             '2026-11-24,klik,priamo,9\r\n'),
            (r'vyvantazhennia/skoro', 200, 'id,poshta,tovar,budynok,adresa,kanal,stvoreno,napysano\r\n'
                                            '1,a@b,dovidka,,,oplata-dovidka-vh-meshk-yt-t5,2026-11-24,\r\n'),
        ])

    def env(self, **k):
        e = {'MV_YOUTUBE_CLIENT_ID': 'c', 'MV_YOUTUBE_CLIENT_SECRET': 's', 'MV_YOUTUBE_REFRESH_TOKEN': 'r',
             'MV_META_PAGE_TOKEN': 'PT', 'MV_ADRESA_SAITU': SAIT, 'MV_ADMIN_KLIUCH': 'ADM'}
        e.update(k)
        return mock.patch.dict(os.environ, e)

    def test_reiestr_z_typom(self):
        r = Z.reiestr(self.db)
        self.assertEqual(len(r), 4)
        self.assertEqual({x['typ'] for x in r}, {'Місто за N секунд'})
        self.assertEqual({x['mitka'] for x in r}, {'yt-t5', 'ig-t5', 'fb-t5', 'tt-t5'})
        Z.pysaty_csv(self.zamiry / 'rolyky.csv', Z.REIESTR, r)
        with open(self.zamiry / 'rolyky.csv', encoding='utf-8') as f:
            self.assertIn('typ', next(csv.reader(f)))

    def test_zbir_z_pidroblenymy_merezhamy(self):
        s = self.sitka()
        with self.env():
            zvit = Z.zibraty(self.db, self.zamiry, date(2026, 11, 25), http_=s)
        self.assertFalse([x for x in zvit if 'не зібрано' in x or 'не налаштовано' in x], zvit)
        z = {r['merezha']: r for r in Z.chytaty_csv(self.zamiry / 'znimky.csv')}
        self.assertEqual(set(z), {'youtube', 'instagram', 'facebook', 'tiktok'})   # TikTok — лише дії на сайті
        yt = z['youtube']
        self.assertEqual((yt['typ'], yt['perehliady'], yt['perehliady_spravzhni'], yt['komentari']),
                         ('Місто за N секунд', '1500', '900', '6'))
        self.assertEqual(yt['chastka_perehliadu'], '0.723')
        self.assertEqual(yt['utrymannia_3s'], '0.81')                             # точка ≥ 3 с з 9 с
        self.assertEqual((yt['perekhody'], yt['zaiavky']), ('3', '1'))             # канал «vh-meshk-yt-t5» — наш
        self.assertEqual((z['instagram']['perehliady'], z['instagram']['serednii_chas_s']), ('800', '5.4'))
        self.assertEqual((z['facebook']['perehliady'], z['facebook']['lajky'], z['facebook']['komentari']),
                         ('300', '8', '1'))
        # ключі не пишуться у файли
        for f in self.zamiry.iterdir():
            if f.is_file():
                t = f.read_text(encoding='utf-8')
                for kl in ('AT', 'PT', 'ADM'):
                    self.assertNotRegex(t, rf'\b{kl}\b')
        # Analytics: свій канал і лише наші ролики
        a = next(u for _, u, _, _ in s.zapyty if 'dimensions=video&' in u)
        self.assertIn('ids=channel%3D%3DMINE', a)
        self.assertIn('filters=video%3D%3DYT1', a)

    def test_bez_kliuchiv_ne_padaie(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            zvit = Z.zibraty(self.db, self.zamiry, date(2026, 11, 25), http_=Sitka([]))
        self.assertTrue(any('YouTube: не налаштовано' in x for x in zvit))
        self.assertTrue(any('дії на сайті не зібрано' in x for x in zvit))
        self.assertTrue((self.zamiry / 'rolyky.csv').is_file())

    def test_pomylka_merezhi_ne_zupyniaie_inshi(self):
        s = Sitka([(r'oauth2', 400, {'error': 'invalid_grant'}), *self.sitka().vidpovidi[4:]])
        with self.env():
            zvit = Z.zibraty(self.db, self.zamiry, date(2026, 11, 25), http_=s)
        self.assertTrue(any(x.startswith('YouTube: не зібрано') for x in zvit), zvit)
        self.assertTrue(any(x.startswith('Instagram: знімків 1') for x in zvit), zvit)

    def test_tiktok_vyvantazhennia(self):
        (self.zamiry / 'tiktok').mkdir(parents=True)
        (self.zamiry / 'tiktok' / 'studio-2026-11-30.csv').write_text(
            'Video link;Post time;Total views;Total likes;Comments;Shares;Average watch time;Watched full video;For You\n'
            'https://www.tiktok.com/@mv/video/7400000000000000001;23.11.2026;1,2K;80;5;3;6.1s;35%;82%\n'
            'https://www.tiktok.com/@mv/video/1111111;23.11.2026;10;1;0;0;1s;1%;10%\n', encoding='utf-8')
        zn, zauv = Z.tiktok_import(self.zamiry / 'tiktok', Z.reiestr(self.db), date(2026, 12, 1))
        self.assertEqual(len(zn), 1)
        self.assertEqual((zn[0]['data'], zn[0]['id'], zn[0]['perehliady'], zn[0]['chastka_perehliadu'], zn[0]['dlia_tebe']),
                         ('2026-11-30', 't5', 1200.0, 0.35, 0.82))
        self.assertEqual(len(zauv), 1)
        (self.zamiry / 'tiktok' / 'zle.csv').write_text('a,b\n1,2\n', encoding='utf-8')
        _, zauv = Z.tiktok_import(self.zamiry / 'tiktok', Z.reiestr(self.db), date(2026, 12, 1))
        self.assertTrue(any('не знайшов колонки переглядів' in x for x in zauv))


class Pidsumok(unittest.TestCase):
    """Правила розд. 4.4 на штучних числах."""

    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.zamiry = Path(self._t.name)

    def dani(self, rolyky):
        """rolyky: (id, typ, перегляди, утримання 3 с, коментарі, гачок)."""
        reiestr, znimky = [], []
        pochatok = date(2026, 11, 2)
        for i, (rid, typ, p, u, k, h) in enumerate(rolyky):
            d = pochatok + timedelta(days=i)
            reiestr.append({'id': rid, 'typ': typ, 'varianty': f'темна · гачок {h}', 'merezha': 'tiktok',
                            'opublikovano': f'{d}T16:00+00:00', 'mitka': f'tt-{rid}'})
            znimky.append({'data': (d + timedelta(days=7)).isoformat(), 'id': rid, 'typ': typ, 'merezha': 'tiktok',
                           'perehliady': p, 'utrymannia_3s': u, 'komentari': k})
        Z.pysaty_csv(self.zamiry / 'rolyky.csv', Z.REIESTR, reiestr)
        Z.pysaty_csv(self.zamiry / 'znimky.csv', Z.ZNIMKY, znimky)

    def ryadok(self, md: str, typ: str) -> str:
        return next(r for r in md.splitlines() if r.startswith(f'| {typ} |'))

    def test_posylyty_tryamaty_prybraty_chekaty(self):
        r = []
        for i in range(5):
            r.append((f's{i}', 'Сота розпадається', 3000, 0.85, 3, 'А'))       # ≥ 2× медіани акаунта → посилити
            r.append((f'm{i}', 'Міф чи факт', 1000, 0.7, 3, 'А'))              # біля медіани → тримати
            r.append((f'k{i}', 'Календар року', 200, 0.4, 0, 'А'))             # нижче за все → прибрати
        r += [(f'n{i}', 'Найдивніша справа тижня', 900, 0.7, 1, 'А') for i in range(3)]   # 3 з 5 → чекати
        self.dani(r)
        _, md = Z.pidsumok(self.zamiry, date(2026, 11, 30))
        self.assertIn('**посилити**', self.ryadok(md, 'Сота розпадається'))
        self.assertIn('**тримати**', self.ryadok(md, 'Міф чи факт'))
        self.assertIn('**прибрати**', self.ryadok(md, 'Календар року'))
        self.assertIn('**чекати**', self.ryadok(md, 'Найдивніша справа тижня'))
        self.assertIn('3 з 5', self.ryadok(md, 'Найдивніша справа тижня'))
        self.assertTrue((self.zamiry / 'tyzhden-2026-11-30.md').is_file())

    def test_odyn_rolyk_3x(self):
        r = [(f'm{i}', 'Міф чи факт', 1000, 0.7, 1, 'А') for i in range(6)]
        r += [(f'v{i}', 'Вулиця тижня (К-44)', 900 if i else 5000, 0.7, 1, 'А') for i in range(5)]
        self.dani(r)
        _, md = Z.pidsumok(self.zamiry, date(2026, 11, 30))
        rr = self.ryadok(md, 'Вулиця тижня (К-44)')
        self.assertIn('**посилити**', rr)
        self.assertIn('v0', rr)

    def test_ihry_za_komentariamy(self):
        r = [(f'm{i}', 'Міф чи факт', 1000, 0.7, 1, 'А') for i in range(6)]
        r += [(f'h{i}', 'Вгадай, де це було', 400, 0.3, 20, 'А') for i in range(5)]   # мало переглядів, але коментарі
        self.dani(r)
        _, md = Z.pidsumok(self.zamiry, date(2026, 11, 30))
        rr = self.ryadok(md, 'Вгадай, де це було')
        self.assertIn('**посилити**', rr)
        self.assertIn('гра', rr)

    def test_hachky(self):
        r = [(f'a{i}', 'Одна подія-петля («Самокат»)', 1000, 0.80, 1, 'А') for i in range(3)]
        r += [(f'b{i}', 'Одна подія-петля («Самокат»)', 1000, 0.82, 1, 'Б') for i in range(3)]
        r += [(f'c{i}', 'Міф чи факт', 1000, 0.60, 1, 'А') for i in range(3)]
        r += [(f'd{i}', 'Міф чи факт', 1000, 0.75, 1, 'В') for i in range(3)]
        self.dani(r)
        _, md = Z.pidsumok(self.zamiry, date(2026, 11, 30))
        self.assertRegex(md, r'Одна подія-петля.*випадковість')
        self.assertRegex(md, r'Міф чи факт: .*кращий гачок В')

    def test_typ_ne_z_reiestru_vydno(self):
        self.dani([('x1', 'Щось нове', 100, 0.5, 0, 'А')])
        _, md = Z.pidsumok(self.zamiry, date(2026, 11, 30))
        self.assertIn('Типи не з реєстру', md)

    def test_na_den(self):
        z = [{'data': '2026-11-24'}, {'data': '2026-11-30'}, {'data': '2026-12-10'}]
        self.assertEqual(Z.na_den(z, '2026-11-23T16:00')['data'], '2026-11-30')
        self.assertEqual(Z.na_den(z[2:], '2026-11-23T16:00')['data'], '2026-12-10')


# ==================================================================== робочі процеси
class RobochiProtsesy(unittest.TestCase):
    def test_zamiry_yml(self):
        t = ROBOCHYI.read_text(encoding='utf-8')
        self.assertRegex(t, r"cron: '\d+ \d+ \* \* \*'")
        self.assertNotRegex(t, r"cron: '0 ")
        self.assertIn('kod/avtopostynh/zamiry.py', t)
        self.assertIn('avtopostynh-stan', t)
        for imia in ('MV_YOUTUBE_REFRESH_TOKEN', 'MV_META_PAGE_TOKEN', 'MV_ADMIN_KLIUCH'):
            self.assertIn(f'secrets.{imia}', t)
        for blok in re.findall(r'run: \|\n((?:          .*\n|\n)+)', t):
            self.assertNotIn('${{', blok)

    def test_avtopostynh_yml_cherha_i_tiktok(self):
        t = ROBOCHYI_AVTO.read_text(encoding='utf-8')
        self.assertIn('sparse-checkout: cherha', t)
        self.assertIn('tiktok)', t)
        self.assertIn('upload-artifact', t)
        self.assertIn('--tiktok-teka', t)
        # останній слот (20:30 за Києвом) ще в межах розкладу запусків
        hod = re.search(r"cron: '\d+ (\d+)-(\d+) ", t)
        self.assertGreaterEqual(int(hod[2]), 19)


if __name__ == '__main__':
    unittest.main()
