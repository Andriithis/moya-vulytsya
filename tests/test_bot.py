"""Перевірки бота «Мій будинок» і дописів районних каналів (ZAVDANNYA-97).

Запуск: python -m unittest tests.test_bot -v
Без мережі й без токена Telegram: розмова — на штучному покажчику; покажчик зі штучної бази сайту — якщо є h3.
"""
from __future__ import annotations

import io
import json
import re
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'bot'))
sys.path.insert(0, str(KORIN / 'site'))

import adresa as A  # noqa: E402
import kanaly as K  # noqa: E402
import rozmova as R  # noqa: E402
import stezhennia as S  # noqa: E402
import tsiny as T  # noqa: E402

ZABORONENI = re.compile(r'небезпечн|безпечн|рейтинг|найгірш|страшн', re.I)
EMODZI = re.compile('[\U0001F300-\U0001FAFF☀-➿]')


def bud(v, n, vs, r, la, lo, sk=None, su=None, ph=None, o=0, pv=0):
    url = f'/budynok/{vs}/{A.norm_nomer(n)}/'
    z = {'a': f'{v}, {n}', 'u': url, 'n': n, 'v': v, 'vs': vs, 'r': r, 'la': la, 'lo': lo}
    if sk:
        z['sk'] = sk
    if su:
        z['su'] = su
    if ph:
        z['ph'] = ph
    if o:
        z['o'] = o
    if pv:
        z['pv'] = pv
    return z


INDEKS = {
    'versiia': '2026-11-08', 'misiatsi_1551': ['2025-11', '2026-10'], 'r_susidy_m': 300, 'roky_podii': [2024, 2026],
    'hrupy': {'dtp': 'ДТП', 'hp': 'Громадський порядок', 'mai': 'Майно'},
    'budynky': [
        bud('вулиця Хрещатик', '22', 'khreshchatyk', 'Шевченківський', 50.4470, 30.5220,
            sk={'тепло': 12, 'світло': 5}, su={'тепло': 4, 'світло': 2}, ph={'dtp': 3, 'hp': 1}, o=2, pv=5),
        bud('вулиця Хрещатик', '24', 'khreshchatyk', 'Шевченківський', 50.4472, 30.5223, sk={'ліфт': 1}, o=1),
        bud('проспект Перемоги', '10-А', 'prospekt-peremohy', 'Шевченківський', 50.4560, 30.4700, ph={'mai': 2}, pv=2),
        bud('Садова вулиця', '3', 'sadova', 'Дарницький', 50.40, 30.60, sk={'світло': 1}),
        bud('вулиця Садова', '3', 'sadova-2', 'Оболонський', 50.50, 30.50, sk={'вода': 2}),
        bud('вулиця Будівельників', '13-15', 'budivelnykiv', 'Дніпровський', 50.45, 30.62, sk={'вода': 1}),
        bud('проспект Степана Бандери', '12/4', 'prospekt-stepana-bandery', 'Оболонський', 50.49, 30.49, ph={'dtp': 1}, pv=1),
    ],
    'vulytsi': [
        {'s': 'khreshchatyk', 'n': 'вулиця Хрещатик', 't': 'вулиця', 'k': 'Хрещатик', 'r': 'Шевченківський', 'p': 40},
        {'s': 'prospekt-peremohy', 'n': 'проспект Перемоги', 't': 'проспект', 'k': 'Перемоги', 'r': 'Шевченківський', 'p': 30},
        {'s': 'volodymyrska', 'n': 'Володимирська вулиця', 't': 'вулиця', 'k': 'Володимирська', 'r': 'Шевченківський', 'p': 12},
        {'s': 'sadova', 'n': 'Садова вулиця', 't': 'вулиця', 'k': 'Садова', 'r': 'Дарницький', 'p': 1},
    ],
    'rayony': [{'n': 'Шевченківський', 's': 'shevchenkivskyi', 'ph': {'dtp': 10}, 'sk': {'тепло': 12}, 'b': 3},
               {'n': 'Дарницький', 's': 'darnytskyi', 'ph': {}, 'sk': {}, 'b': 1}],
    'koloda': [
        {'id': 'k1', 'vyd': 'Торгівля з рук', 'kategoriia': 'stykhiina_torhivlia', 'rik': 2025, 'vulytsia': 'вул. Хрещатик',
         'opys_korotkyi': 'О 16:50 на вулиці з рук продавали синьо-жовті стрічки.', 'rishennya_nomer': '117399819',
         'rishennya_url': 'https://od.reyestr.court.gov.ua/x.rtf', 'vulytsia_slug': 'khreshchatyk',
         'vulytsia_nazva': 'вулиця Хрещатик', 'rayon': 'Шевченківський'},
        {'id': 'k2', 'vyd': 'Дрібна крадіжка', 'kategoriia': 'dribna_kradizhka', 'rik': 2024, 'vulytsia': 'просп. Перемоги',
         'opys_korotkyi': 'У магазині взяли батончик і жуйки на 214 грн і вийшли, не заплативши.', 'rishennya_nomer': '128903549',
         'rishennya_url': 'https://od.reyestr.court.gov.ua/y.rtf', 'vulytsia_slug': 'prospekt-peremohy',
         'vulytsia_nazva': 'проспект Перемоги', 'rayon': 'Шевченківський'},
        *[{'id': f'k1{i}', 'vyd': 'Торгівля з рук', 'kategoriia': 'stykhiina_torhivlia', 'rik': 2025,
           'vulytsia': 'Володимирська вул.', 'opys_korotkyi': f'Вранці на розі продавали {i} кошиків яблук без документів.',
           'rishennya_nomer': f'12000000{i}', 'rishennya_url': 'https://od.reyestr.court.gov.ua/z.rtf',
           'vulytsia_slug': 'volodymyrska', 'vulytsia_nazva': 'Володимирська вулиця', 'rayon': 'Шевченківський'}
          for i in range(2, 7)],
        {'id': 'k3', 'vyd': 'Тілесні', 'kategoriia': 'tilesni', 'rik': 2024, 'vulytsia': 'вул. Хрещатик',
         'opys_korotkyi': 'Біля буд. 5 особа вдарила знайомого.', 'rishennya_nomer': '1',
         'rishennya_url': 'https://x', 'vulytsia_slug': 'khreshchatyk', 'vulytsia_nazva': 'вулиця Хрещатик',
         'rayon': 'Шевченківський'},
        {'id': 'k4', 'vyd': 'Непокора', 'kategoriia': 'nepokora', 'rik': 2025, 'vulytsia': 'вул. Хрещатик',
         'opys_korotkyi': 'Військовослужбовець біля військової частини не виконав наказ.', 'rishennya_nomer': '2',
         'rishennya_url': 'https://x', 'vulytsia_slug': 'khreshchatyk', 'vulytsia_nazva': 'вулиця Хрещатик',
         'rayon': 'Шевченківський'},
        {'id': 'k5', 'vyd': 'Насильство', 'kategoriia': 'domashnie_nasylstvo', 'rik': 2025, 'vulytsia': 'вул. Хрещатик',
         'opys_korotkyi': 'Чоловік вчинив домашнє насильство.', 'rishennya_nomer': '3', 'rishennya_url': 'https://x',
         'vulytsia_slug': 'khreshchatyk', 'vulytsia_nazva': 'вулиця Хрещатик', 'rayon': 'Шевченківський'},
    ],
}


def usi_teksty(v: R.Vidpovid) -> str:
    return v.tekst + ' ' + ' '.join(k.tekst for ryad in v.knopky for k in ryad)


class Adresa(unittest.TestCase):
    def setUp(self):
        self.p = A.Pokazhchyk(INDEKS)

    def test_rizni_napysannia(self):
        for t in ('Хрещатик 22', 'вул. Хрещатик, 22', 'хрещатик,22', 'Хрещатик буд. 22', 'м. Київ, вулиця Хрещатик 22'):
            r = self.p.znaity(t)
            self.assertEqual([b['u'] for b in r.budynky], ['/budynok/khreshchatyk/22/'], t)

    def test_nomer_z_literoiu_i_drobom(self):
        self.assertEqual(len(self.p.znaity('просп. Перемоги 10а').budynky), 1)
        self.assertEqual(len(self.p.znaity('Перемоги 10-А').budynky), 1)
        self.assertEqual(len(self.p.znaity('Перемоги 10 a').budynky), 1)        # латинська «a»
        self.assertEqual(len(self.p.znaity('Бандери 12/4').budynky), 1)       # частина назви

    def test_nazva_na_bud_i_diapazon(self):
        # «Будівельників» не плутати зі словом «буд.»; «13-15» — номер-діапазон
        self.assertEqual(len(self.p.znaity('вул. Будівельників, буд. 13-15').budynky), 1)
        self.assertEqual(A.rozibraty('Будівельників 13-15').vulytsia, ['будівельників'])

    def test_bez_nomera_i_nevidoma(self):
        r = self.p.znaity('Хрещатик')
        self.assertFalse(r.budynky)
        self.assertEqual(r.vulytsi[0][1], 'khreshchatyk')
        self.assertFalse(self.p.znaity('Неіснуюча 5').vulytsi)

    def test_kilka_vulyts(self):
        self.assertEqual(len(self.p.znaity('Садова 3').budynky), 2)


class Rozmova(unittest.TestCase):
    def bot(self, sc='a'):
        return R.Bot(INDEKS, S.Skhovyshche(), sc)

    def test_try_stsenarii_vedut_na_storinku_i_dovidku(self):
        for sc in R.SCENARII:
            b = self.bot(sc)
            v = b.povidomlennia(1, 'Хрещатик 22')
            urly = [k.url for ryad in v.knopky for k in ryad if k.url]
            if sc == 'b':
                v = b.natysnuto(1, v.knopky[0][0].dani)
                urly = [k.url for ryad in v.knopky for k in ryad if k.url]
            self.assertIn('https://moya-vulytsya.pages.dev/budynok/khreshchatyk/22/?dzherelo=bot', urly, sc)
            self.assertTrue(any('/oplata/?tovar=dovidka' in u for u in urly), sc)
            self.assertTrue(any((k.dani or '').startswith('s:') for ryad in v.knopky for k in ryad), sc)

    def test_lyshe_chysla_i_porivniannia(self):
        v = self.bot('a').povidomlennia(1, 'Хрещатик 22')
        self.assertIn('тепло: 12 (у сусідніх будинках зазвичай 4)', v.tekst)
        self.assertIn('Подій з рішень судів за 2024–2026: 4 (ДТП — 3, громадський порядок — 1)', v.tekst)
        self.assertIn('не перевірений факт', v.tekst)
        self.assertIn('лише те, що дійшло до суду', v.tekst)

    def test_bez_zaboronenykh_sliv_i_emodzi_i_lyshe_tsiny_mv100(self):
        dozv = {str(x) for x in T.dozvoleni_sumy()}
        for sc in R.SCENARII:
            b = self.bot(sc)
            vidpovidi = [b.povidomlennia(1, t) for t in ('/start', 'Хрещатик 22', 'Хрещатик', 'Хрещатик 999', 'бла', '/dani')]
            vidpovidi.append(b.natysnuto(1, 's:' + R.kod('/budynok/khreshchatyk/22/'), '2026-11-17'))
            for t in ('k', 'p', 'n'):
                vidpovidi.append(b.natysnuto(1, f'{t}:' + R.kod('/budynok/khreshchatyk/22/')))
            for v in vidpovidi:
                t = usi_teksty(v)
                self.assertFalse(ZABORONENI.search(t), t)
                self.assertFalse(EMODZI.search(t), t)
                for suma in re.findall(r'(\d[\d ]*) грн', t):
                    self.assertIn(suma.replace(' ', ''), dozv, t)

    def test_stezhennia_i_vydalennia(self):
        skh = S.Skhovyshche()
        b = R.Bot(INDEKS, skh, 'a')
        b.natysnuto(7, 's:' + R.kod('/budynok/khreshchatyk/22/'), '2026-11-17')
        self.assertEqual([(z['chat_id'], z['url']) for z in skh.usi()], [(7, '/budynok/khreshchatyk/22/')])
        b.natysnuto(7, 's:' + R.kod('/budynok/khreshchatyk/24/'), '2026-11-18')    # одна адреса: замінює
        self.assertEqual([z['url'] for z in skh.usi()], ['/budynok/khreshchatyk/24/'])
        b.povidomlennia(7, '/stop')
        self.assertEqual(skh.usi(), [])

    def test_zberihaiemo_lyshe_chat_i_adresu(self):
        kolonky = [r[1] for r in S.Skhovyshche().con.execute('PRAGMA table_info(stezhennia)')]
        self.assertEqual(kolonky, ['chat_id', 'url', 'stvoreno', 'versiia', 'misiats_1551', 'podii_vsi', 'nadislano'])

    def test_nove_bilia_domu(self):
        skh = S.Skhovyshche()
        b = R.Bot(INDEKS, skh, 'a')
        b.natysnuto(7, 's:' + R.kod('/budynok/khreshchatyk/22/'), '2026-11-17')
        self.assertIsNone(b.nove(skh.usi()[0]))                     # одразу після «Стежити» — нового немає
        # новий місяць 1551 і нова подія в наступному покажчику
        i2 = json.loads(json.dumps(INDEKS))
        i2['misiatsi_1551'] = ['2025-12', '2026-11']
        i2['budynky'][1]['pv'] = 1
        b2 = R.Bot(i2, skh, 'a')
        v = b2.nove(skh.usi()[0])
        self.assertIn('Звернень до 1551 за листопад 2026: 3.', v.tekst)     # 2 + 1 у радіусі 300 м
        self.assertIn('Нових подій з рішень судів у даних: 1.', v.tekst)
        nadislani = []
        zvit = S.rozsylka(b2, skh, '2026-11-24', lambda c, v: nadislani.append(c) or True)
        self.assertEqual((zvit['nadislano'], nadislani), (1, [7]))
        self.assertIsNone(b2.nove(skh.usi()[0]))                     # удруге те саме не надсилаємо

    def test_zablokuvav_bota_zapys_vydaleno_i_stari(self):
        skh = S.Skhovyshche()
        skh.stezhyty(1, '/budynok/khreshchatyk/22/', '2026-11-01', 'x', '2025-01', 0)
        skh.stezhyty(2, '/budynok/khreshchatyk/22/', '2024-01-01', 'x', '2025-01', 0)
        zvit = S.rozsylka(R.Bot(INDEKS, skh), skh, '2026-11-24', lambda c, v: False)
        self.assertEqual(zvit['vydaleno'], 2)
        self.assertEqual(skh.usi(), [])

    def test_mezha_zapytiv(self):
        b = R.Bot(INDEKS, None, 'a', zapytiv_na_hodynu=3)
        tt = [b.povidomlennia(5, 'Хрещатик 22', 100.0 + i).tekst for i in range(4)]
        self.assertIn('Забагато', tt[3])
        self.assertNotIn('Забагато', b.povidomlennia(5, 'Хрещатик 22', 100.0 + 3700).tekst)

    def test_dani_knopky_do_64_bait(self):
        for bb in INDEKS['budynky']:
            self.assertLessEqual(len(f's:{R.kod(bb["u"])}'.encode()), 64)

    def test_konsol(self):
        import telegram as TG
        vykhid = io.StringIO()
        TG.konsol(R.Bot(INDEKS, S.Skhovyshche()), io.StringIO('Хрещатик 22\n!3\n'), vykhid)
        self.assertIn('Стежу: вулиця Хрещатик, 22', vykhid.getvalue())

    def test_bez_tokena_ne_zapuskaietsia(self):
        import telegram as TG
        with self.assertRaises(SystemExit):
            TG.Telegram('')


class Kanaly(unittest.TestCase):
    def setUp(self):
        self.h = K.Henerator(INDEKS)
        self.pachka = self.h.pachka(date(2026, 11, 23), 7)

    def test_vidbir_podii(self):
        self.assertEqual(sorted(p['id'] for p in INDEKS['koloda'] if K.prydatna(p)), ['k1', 'k12', 'k13', 'k14', 'k15', 'k16', 'k2'])

    def test_rozklad_i_perevirka(self):
        sh = [d for d in self.pachka if d['rayon'] == 'Шевченківський']
        typy = {date.fromisoformat(d['data']).weekday(): d['typ'] for d in sh}
        self.assertEqual(typy.get(4), 'tsyfry')
        self.assertEqual(typy.get(0), 'istoriia')
        self.assertEqual(typy.get(2), 'vhadai')
        for d in self.pachka:
            self.assertEqual(K.perevirka(d), [], d)

    def test_istoriia_bez_nomera_i_z_rishenniam(self):
        d = next(d for d in self.pachka if d['typ'] == 'istoriia' and d['podiia'] == 'k1')
        self.assertIn('Рішення № 117399819 — лише те, що дійшло до суду.', d['tekst'])
        self.assertNotRegex(d['tekst'], r'Хрещатик,?\s*\d')
        self.assertEqual(d['knopky'][0][0]['url'],
                         'https://moya-vulytsya.pages.dev/vulytsia/khreshchatyk/?dzherelo=tg-shevchenkivskyi')

    def test_vhadai(self):
        d = next(d for d in self.pachka if d['typ'] == 'vhadai')
        self.assertEqual(len(d['varianty']), 3)
        prav = next(v['n'] for v in INDEKS['vulytsi'] if v['s'] == d['vulytsia'])
        self.assertEqual(d['varianty'][d['pravylna']], prav)
        self.assertEqual(len(set(d['varianty'])), 3)
        self.assertLessEqual(len(d['pytannia']), 300)
        self.assertLessEqual(len(d['poiasnennia']), 200)

    def test_tsyfry_z_porivnianniam(self):
        d = next(d for d in self.pachka if d['typ'] == 'tsyfry')
        self.assertIn('зазвичай вулиця району', d['tekst'])
        self.assertIn('/vulytsia/', d['knopky'][0][0]['url'])

    def test_perevirka_lovyt(self):
        pohanyi = {'typ': 'istoriia', 'tekst': 'Небезпечний будинок, вул. Хрещатик, 5', 'knopky': [[{'tekst': 'x', 'url': 'https://a/'}]]}
        zh = K.perevirka(pohanyi)
        self.assertIn('заборонене слово', zh)
        self.assertIn('номер будинку', zh)
        self.assertIn('посилання не на конкретне місце', zh)

    def test_povtornyi_zapusk_i_bez_povtoriv(self):
        self.assertEqual(self.pachka, self.h.pachka(date(2026, 11, 23), 7))
        druha = self.h.pachka(date(2026, 11, 30), 7, {d.get('podiia') for d in self.pachka})
        self.assertFalse({d.get('podiia') for d in druha if d.get('podiia')} & {d.get('podiia') for d in self.pachka if d.get('podiia')})


try:
    import h3  # noqa: F401
    YE_H3 = True
except ImportError:
    YE_H3 = False


@unittest.skipUnless(YE_H3, 'немає бібліотеки h3 (pip install h3)')
class IndeksZiShtuchnoiBazy(unittest.TestCase):
    """Посилання бота — рівно ті, що збирач сайту дає сторінкам будинків і вулиць."""

    def test_posylannia_zbihaiutsia_z_saitom(self):
        import indeks as I
        sys.path.insert(0, str(KORIN / 'tests'))
        from test_sait import BUDYNKY, stvoryty_bazu, stvoryty_pereimenuvannya
        import zibraty_sait
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            stvoryty_bazu(t / 'e.db')
            stvoryty_pereimenuvannya(t / 'p.csv')
            (t / 'b.json').write_text(json.dumps(BUDYNKY, ensure_ascii=False), encoding='utf-8')
            kol = {'podii': [{'id': 'x1', 'vyd': 'ДТП', 'kategoriia': 'dtp', 'rik': 2025, 'opys_korotkyi': 'Водій не пропустив.',
                              'opys_povnyi': 'ОСОБА_1 на вул. Хрещатик, 5', 'adresa': 'вул. Хрещатик, 5', 'lat': 50.447,
                              'lon': 30.522, 'rishennya_nomer': '1', 'rishennya_url': 'https://x'}]}
            (t / 'k.json').write_text(json.dumps(kol, ensure_ascii=False), encoding='utf-8')
            z = I.zibraty(t / 'e.db', t / 'b.json', t / 'p.csv', KORIN / 'data' / 'borders.json', t / 'k.json')
            zibraty_sait.zibraty_sait(t / 'e.db', t / 'sait', t / 'p.csv', KORIN / 'data' / 'borders.json',
                                      budynky=t / 'b.json')
            self.assertTrue(z['budynky'])
            for b in z['budynky']:
                self.assertTrue((t / 'sait' / b['u'].strip('/') / 'index.html').exists(), b['u'])
            for v in z['vulytsi']:
                self.assertTrue((t / 'sait' / 'vulytsia' / v['s'] / 'index.html').exists(), v['s'])
            s = json.dumps(z, ensure_ascii=False)
            self.assertNotIn('ОСОБА', s)                     # повний опис колоди в покажчик не йде
            self.assertNotIn('Хрещатик, 5', s)               # і номер будинку з адреси колоди


if __name__ == '__main__':
    unittest.main()
