"""Ігри в карті (ZAVDANNYA-117; MV-129, MV-130, MV-26): справи детектива, ядро, бали, запрошення, «Кваліфікуй», збирання.

Запуск: python -m unittest tests/test_ihry.py
Ядро (site/ihry/ihry-yadro.js) перевіряється через Node.js; без Node ці перевірки пропускаються з поясненням.
"""
from __future__ import annotations

import copy
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
IHRY = KORIN / 'site' / 'ihry'
sys.path.insert(0, str(IHRY))
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import detektyv as DT  # noqa: E402

SPRAVY = sorted((IHRY / 'spravy').glob('*.json'))
NODE = shutil.which('node')


def js(kod: str):
    """Виконати код у Node з ядром ігор (Y) і повернути JSON-результат."""
    p = subprocess.run([NODE, '-e', f'const Y = require({json.dumps(str(IHRY / "ihry-yadro.js"))});'
                        f'const K = require({json.dumps(str(IHRY / "nalashtuvannia.json"))});'
                        f'console.log(JSON.stringify((() => {{ {kod} }})()));'],
                       capture_output=True, text=True, check=True)
    return json.loads(p.stdout)


class Spravy(unittest.TestCase):
    """«Детектив тижня»: справи-зразки проходять перевірку; кожен запобіжник MV-129 і правило 2.4 справді ловить порушення."""

    def setUp(self):
        self.s = DT.prochytaty(SPRAVY[0])

    def ne_hodytsia(self, s, slovo):
        with self.assertRaises(DT.PomylkaSpravy) as e:
            DT.perevirka(s)
        self.assertIn(slovo, str(e.exception))

    def test_zrazky(self):
        self.assertGreaterEqual(len(SPRAVY), 2)
        for f in SPRAVY:
            s = DT.prochytaty(f)
            z = DT.perevirka(s)
            self.assertLessEqual(z['kholms'], 5, f.name)               # Холмс розкриває до суботи
            self.assertGreaterEqual(z['kroky'][3]['de'], 3, f.name)
            self.assertTrue(re.fullmatch(r'\d+', s['rishennia']['nomer']))
            self.assertEqual(s['poznachka'], DT.POZNACHKA)

    def test_z1_poznachka(self):
        self.s['poznachka'] = 'Справжня історія'
        self.ne_hodytsia(self.s, 'З1')

    def test_z2_zaklad_bez_adresy(self):
        self.s['zaklady'][0]['nazva'] = "кав'ярня «Сірий кіт», вул. Якась, 5"
        self.ne_hodytsia(self.s, 'З2')

    def test_z2_zaklad_vyhadanyi(self):
        self.s['zaklady'][0]['vyhadanyi'] = False
        self.ne_hodytsia(self.s, 'З2')

    def test_z2_spravzhnia_nazva(self):
        self.s['slidy'][2]['rechennia'][0]['tekst'] += ' Гаманець «Patek».'
        self.ne_hodytsia(self.s, 'Patek')

    def test_z2_nevidoma_nazva(self):
        self.s['vyklyk'] += ' Поруч — магазин «АТБ».'
        self.ne_hodytsia(self.s, 'АТБ')

    def test_z2_vulytsia_zi_spysku(self):
        with self.assertRaises(DT.PomylkaSpravy):
            DT.perevirka(self.s, {'вулиця хрещатик'})
        DT.perevirka(self.s, {self.s['vulytsia'].lower()})

    def test_z3_prykmety(self):
        for t in ('людина років 30', 'чоловік у капюшоні', 'висока на зріст жінка з татуюванням', 'з бородою'):
            s = copy.deepcopy(self.s)
            s['personazhi'][0]['rol'] = t
            self.ne_hodytsia(s, 'прикмета')

    def test_ne_shukaty_liudynu(self):
        self.s['vyklyk'] += ' Хто це зробив?'
        self.ne_hodytsia(self.s, 'шукати людину')

    def test_zaboroneni_slova_i_nomery(self):
        for t, slovo in (('Тут небезпечно.', 'заборонене'), ('проспект Берестейський, 136', 'номер будинку'),
                         ('ОСОБА_3 вийшов', 'знеособлення'), ('стрибнув з мосту', 'кризи')):
            s = copy.deepcopy(self.s)
            s['slidy'][3]['rechennia'][0]['tekst'] = t
            self.ne_hodytsia(s, slovo)

    def test_chutlyva_stattia(self):
        self.s['rishennia']['stattia'] = 'ч. 1 ст. 152 КК'
        self.ne_hodytsia(self.s, 'чутлива')

    def test_p9_vyhadka_ne_zvuzhuie(self):
        r = self.s['slidy'][4]['rechennia'][1]
        r['dzherelo'] = 'vyhadka'
        self.ne_hodytsia(self.s, 'П9')

    def test_p7_tsytata(self):
        self.s['slidy'][0]['rechennia'][0]['tsytata'] = 'такого в рішенні немає'
        self.ne_hodytsia(self.s, 'П7')

    def test_p2_odna_vidpovid(self):
        self.s['slidy'][4]['rechennia'] = [r for r in self.s['slidy'][4]['rechennia'] if r['dzherelo'] != 'pidkazka']
        self.ne_hodytsia(self.s, 'П2')

    def test_p3_ne_zarano(self):
        self.s['slidy'][1]['rechennia'][2]['umovy'].append({'pole': 'de', 'oznaka': 'nazva_vid_mista', 'znachennia': True})
        self.ne_hodytsia(self.s, 'П3')

    def test_p5_ne_nazvaty_vidpovid(self):
        self.s['slidy'][0]['zahadka'] += ' Це було ввечері.'
        self.ne_hodytsia(self.s, 'П5')

    def test_p6_skhovanka_ne_bilia_vidpovidi(self):
        self.s['slidy'][1]['tsil'].update(lat=50.4562, lon=30.3657)
        self.ne_hodytsia(self.s, 'П6')

    def test_p8_spravzhnia_vidpovid(self):
        self.s['rishennia']['chas'] = '09:00'
        self.ne_hodytsia(self.s, 'П8')

    def test_dlia_saitu_bez_uryvkiv(self):
        d = DT.dlia_saitu(self.s)
        t = json.dumps(d, ensure_ascii=False)
        self.assertNotIn('uryvky', t)
        self.assertNotIn('tsytata', t)
        self.assertNotIn('ОСОБА_', t)
        self.assertNotIn('Patek', t)
        self.assertIn('rozkryto_pislia', d)


@unittest.skipUnless(NODE, 'немає Node.js — ядро ігор не перевірити')
class Yadro(unittest.TestCase):

    def test_zvuzhennia_yak_u_python(self):
        for f in SPRAVY:
            s = DT.prochytaty(f)
            py = DT.zvuzhennia(s)
            j = js(f'const s = require({json.dumps(str(f))}); return Y.zvuzhennia(s);')
            self.assertEqual(py, j, f.name)

    def test_tyzhden(self):
        r = js('''return [Y.ponedilok('2026-11-17'), Y.ponedilok('2026-11-22'), Y.ponedilok('2026-11-23'),
                  Y.stanTyzhnia({den: 7, hodyna: 19}), Y.stanTyzhnia({den: 7, hodyna: 20}), Y.stanTyzhnia({den: 3, hodyna: 9})];''')
        self.assertEqual(r[:3], ['2026-11-16', '2026-11-16', '2026-11-23'])
        self.assertFalse(r[3]['rozkryttia'])
        self.assertTrue(r[4]['rozkryttia'])
        self.assertEqual(r[5]['slidiv'], 3)

    def test_sprava_tyzhnia(self):
        r = js(f'''const s = [require({json.dumps(str(SPRAVY[0]))}), require({json.dumps(str(SPRAVY[1]))})];
                  return [Y.spravaTyzhnia(s, '2026-11-18'), Y.spravaTyzhnia(s, '2026-11-25'), Y.spravaTyzhnia(s, '2027-03-03').demo];''')
        self.assertEqual(r[0]['sprava']['tyzhden'], '2026-11-16')
        self.assertFalse(r[0]['demo'])
        self.assertEqual(r[1]['sprava']['tyzhden'], '2026-11-23')
        self.assertTrue(r[2])

    def test_vidhuk_bez_pereboru(self):
        """Відгук лише про поля, чий розкривальний слід уже відкрито: у понеділок про «поле справи» — нічого."""
        s = DT.dlia_saitu(DT.prochytaty(SPRAVY[0]))
        f = Path(tempfile.mkdtemp()) / 's.json'
        f.write_text(json.dumps(s, ensure_ascii=False), encoding='utf-8')
        r = js(f'''const s = require({json.dumps(str(f))});
                  const v = {{shcho: s.polia.shcho.vidpovid, koly: s.polia.koly.vidpovid, pole: s.polia.pole.vidpovid}};
                  return [Y.vidhuk(s, v, 0), Y.vidhuk(s, v, 1), Y.vidhuk(s, v, 6)];''')
        self.assertEqual(r[0], {'tak': 0, 'z': 0})
        self.assertEqual(r[1]['z'], 1)                 # після сліду 1 — лише «коли»
        self.assertEqual(r[2], {'tak': 3, 'z': 3})
        shutil.rmtree(f.parent)

    def test_ochky_detektyva(self):
        s = DT.dlia_saitu(DT.prochytaty(SPRAVY[0]))
        f = Path(tempfile.mkdtemp()) / 's.json'
        f.write_text(json.dumps(s, ensure_ascii=False), encoding='utf-8')
        r = js(f'''const s = require({json.dumps(str(f))}); const v = {{}};
                  ['de','shcho','koly','pole'].forEach(p => v[p] = s.polia[p].vidpovid);
                  const rano = Object.assign({{den: 1}}, v), piznio = Object.assign({{den: 6}}, v);
                  const nevirno = Object.assign({{}}, v, {{den: 6, de: 'nyvky'}});
                  return [Y.ochkyDetektyva(s, [rano]).razom, Y.ochkyDetektyva(s, [piznio]).razom,
                          Y.ochkyDetektyva(s, [rano, nevirno]).polia.de.ochky, Y.ochkyDetektyva(s, []).razom];''')
        self.assertEqual(r[1], 2000)          # без бонусу — сума полів
        self.assertGreater(r[0], r[1])        # правильно до розкривального сліду — більше
        self.assertLessEqual(r[0], 3000)
        self.assertEqual(r[2], 0)
        self.assertEqual(r[3], 0)
        shutil.rmtree(f.parent)

    def test_odnakovi_dlia_vsikh(self):
        """MV-130: справи й події спроби однакові для всіх у межах дня (без «пощастило»)."""
        r = js('''const p = []; for (let i = 0; i < 40; i++) p.push({id: 'p' + i});
                  const a = Y.sprobaVgadai(p, '2026-11-18', 2, 5).map(x => x.id), b = Y.sprobaVgadai(p, '2026-11-18', 2, 5).map(x => x.id),
                        c = Y.sprobaVgadai(p, '2026-11-19', 2, 5).map(x => x.id);
                  return [a, b, c, Y.spravyKvalifikuy(p, '2026-11-18').map(x => x.id).join(), Y.spravyKvalifikuy(p, '2026-11-18').map(x => x.id).join()];''')
        self.assertEqual(r[0], r[1])
        self.assertNotEqual(r[0], r[2])
        self.assertEqual(r[3], r[4])

    def test_bali(self):
        r = js('''const s = Y.novyiStan(), d = '2026-11-18'; const v = [];
                  for (let i = 0; i < 4; i++) v.push(Y.vytratyty(s, 'kvalifikuy', K, d));
                  Y.dodatyKupleni(s, K.pakety[0]); v.push(Y.vytratyty(s, 'kvalifikuy', K, d));
                  const det = [Y.vytratyty(s, 'detektyv', K, d), Y.vytratyty(s, 'detektyv', K, d)];
                  const b1 = Y.zarakhuvaty(s, 5000, K, d); for (let i = 0; i < 20; i++) Y.zarakhuvaty(s, 5000, K, d);
                  const sohodni = s.baliSohodni; Y.naDen(s, '2026-11-19');
                  return {v, det, b1, sohodni, novyiDen: s.baliSohodni, kupleni: s.kupleni,
                          obmin: Y.obminMozhlyvyi(s, K.obmin[0], K, '2026-11-19'), pakety: Y.perevirkaPaketiv(K)};''')
        self.assertEqual(r['v'], ['bezkoshtovna'] * 3 + [None, 'kuplena'])   # спершу безкоштовні, далі куплені
        self.assertEqual(r['det'], ['bezkoshtovna', None])                    # детектив не докуповується
        self.assertEqual(r['b1'], 50)                                          # 100 очок = 1 бал
        self.assertEqual(r['sohodni'], 300)                                    # денна стеля
        self.assertEqual(r['novyiDen'], 0)
        self.assertEqual(r['kupleni'], 4)
        self.assertFalse(r['obmin']['mozhna'])                                 # обмін — лише з кабінетом
        self.assertEqual(r['pakety'], [])                                      # пакет не дає балів на суму, більшу за ціну

    def test_paket_shcho_porushuie_zapobizhnyk(self):
        r = js('const k = JSON.parse(JSON.stringify(K)); k.pakety.push({id: "x", sprob: 100, tsina: 99}); return Y.perevirkaPaketiv(k);')
        self.assertEqual(len(r), 1)

    def test_zaproshennia(self):
        r = js('''const d = '2026-11-18', s = {pokazano: false};
                  const k = (sek, dot, vidk) => ({sekund: sek, dotykiv: dot, vidkryto: !!vidk, data: d});
                  const z = {};
                  const a = [Y.chasZaproshuvaty(z, s, k(10, 1)), Y.chasZaproshuvaty(z, s, k(41, 0)), Y.chasZaproshuvaty(z, s, k(5, 3)),
                             Y.chasZaproshuvaty(z, s, k(60, 5, true)), Y.chasZaproshuvaty(z, {pokazano: true}, k(60, 5))];
                  Y.zakrylyZaproshennia(z, d); a.push(Y.chasZaproshuvaty(z, s, k(60, 5)));
                  a.push(Y.chasZaproshuvaty(z, s, {sekund: 60, dotykiv: 5, data: '2026-11-19'}));
                  Y.zakrylyZaproshennia(z, '2026-11-19'); Y.zakrylyZaproshennia(z, '2026-11-20');
                  a.push(z.pauza_do, Y.chasZaproshuvaty(z, s, {sekund: 60, data: '2026-11-25'}), Y.chasZaproshuvaty(z, s, {sekund: 60, data: '2026-11-27'}));
                  a.push(Y.chasZaproshuvaty({ne_proponuvaty: true}, s, k(60, 5)));
                  a.push(Y.yakaGra({kvalifikuyPoruch: true, detektyvNovyiSlid: true}), Y.yakaGra({detektyvNovyiSlid: true, vulytsiaYe: true}),
                         Y.yakaGra({vulytsiaYe: true, vulytsiaZihrano: true, podiiaYe: true}), Y.yakaGra({}));
                  return a;''')
        self.assertEqual(r[:5], [False, True, True, False, False])
        self.assertEqual(r[5:7], [False, True])                    # «×» — до кінця дня
        self.assertEqual(r[7], '2026-11-27')                       # тричі поспіль — пауза 7 днів
        self.assertEqual(r[8:10], [False, True])
        self.assertFalse(r[10])                                    # «Не пропонувати ігри»
        self.assertEqual(r[11:], ['kvalifikuy-tut', 'detektyv', 'vgadai', None])

    def test_ochky_kvalifikuy(self):
        r = js('''const s = {vidpovid: {stattia: 'КК 309', chastyna: '1'}}, b = {vidpovid: {stattia: 'КУпАП 124', chastyna: null}};
                  return [Y.ochkyKvalifikuy(s, {}, {stattia: 'КК 309', chastyna: '1'}).ochky, Y.ochkyKvalifikuy(s, {}, {stattia: 'КК 309', chastyna: '2'}).ochky,
                          Y.ochkyKvalifikuy(s, {}, {stattia: 'КК 307', chastyna: '1'}).ochky, Y.ochkyKvalifikuy(b, {}, {stattia: 'КУпАП 124'}).ochky];''')
        self.assertEqual(r, [1000, 600, 0, 1000])


class Kvalifikuy(unittest.TestCase):
    def test_spravy(self):
        d = json.loads((IHRY / 'kvalifikuy.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(d['spravy']), 5)
        for s in d['spravy']:
            v = s['vidpovid']
            self.assertIn(v['stattia'], s['varianty'], s['id'])
            self.assertEqual(len(s['varianty']), 4)
            for x in s['varianty']:
                self.assertIn(x, d['statti'], s['id'])
            if v['chastyna']:
                self.assertIn(v['chastyna'], d['statti'][v['stattia']]['chastyny'], s['id'])
            else:
                self.assertEqual(d['statti'][v['stattia']]['chastyny'], [], s['id'])
            self.assertRegex(s['rishennia']['url'], r'^https://reyestr\.court\.gov\.ua/Review/\d+$')
            self.assertTrue(s['uryvky'], s['id'])
            t = s['fabula'] + s['chomu']
            self.assertNotRegex(t, r'ОСОБА_|НОМЕР_|АДРЕСА_|небезпечн|безпечн|рейтинг')
            self.assertNotRegex(t, DT.NOMER_BUDYNKU.pattern)
            self.assertNotRegex(t, DT.CHUTLYVI_STATTI.pattern)
            # статті з номером у вироку — лише нечутливі (MV-69: чутливі в ігри не йдуть)
            self.assertNotIn(v['stattia'], ('КУпАП 173-2', 'КК 152', 'КК 153', 'КК 126-1'))
            if 'tochka' in s:
                self.assertTrue(50.2 < s['tochka']['lat'] < 50.6 and 30.2 < s['tochka']['lon'] < 30.9)
        for st, ch in d['chastky'].items():
            self.assertIn(st, d['statti'])
            self.assertLessEqual(sum(x[1] for x in ch['chastky']), 100)


class Sait(unittest.TestCase):
    """Збирання: дані ігор у /ihry/, кнопка й панель на карті, стара гра — переадресація, без уривків рішень."""

    @classmethod
    def setUpClass(cls):
        try:
            import h3  # noqa: F401
        except ImportError:
            raise unittest.SkipTest('немає бібліотеки h3')
        import zibraty_sait as Z
        from test_sait import stvoryty_bazu
        cls.tmp = Path(tempfile.mkdtemp())
        stvoryty_bazu(cls.tmp / 'events.db')
        cls.sait = cls.tmp / 'sait'
        Z.zibraty_sait(cls.tmp / 'events.db', cls.sait, None, KORIN / 'data' / 'borders.json')

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_dani(self):
        for f in ('detektyv.json', 'kvalifikuy.json', 'nalashtuvannia.json', 'koloda.json'):
            self.assertTrue((self.sait / 'ihry' / f).is_file(), f)
        for f in ('detektyv.json', 'kvalifikuy.json'):
            t = (self.sait / 'ihry' / f).read_text(encoding='utf-8')
            self.assertNotIn('uryvky', t)
            self.assertNotIn('tsytata', t)
            self.assertNotIn('ОСОБА_', t)
            self.assertNotIn('MOYO', t)

    def test_karta(self):
        for f in ('karta/index.html', 'index.html'):
            t = (self.sait / f).read_text(encoding='utf-8')
            self.assertIn('id="fihry"', t)
            self.assertIn('id="ihry"', t)
            self.assertIn('id="ihry-zaproshennia"', t)
            self.assertIn('/sait/ihry.js', t)
            self.assertNotIn(' style=', t)
        css = (self.sait / 'sait' / 'sait.css').read_text(encoding='utf-8')
        self.assertIn('.panel-ihor', css)
        self.assertNotRegex((IHRY / 'ihry.css').read_text(encoding='utf-8'), r'#[0-9a-fA-F]{3,6}\b|red|orange')

    def test_stara_hra_pereadresatsiia(self):
        t = (self.sait / 'zahlushka' / 'hra' / 'index.html').read_text(encoding='utf-8')
        self.assertIn('url=/karta/?hra=vgadai', t)
        self.assertNotIn('/zahlushka/hra/', (self.sait / 'karta' / 'index.html').read_text(encoding='utf-8'))


class Osm(unittest.TestCase):
    """ZAVDANNYA-123: координати станцій і схованок — з еталона OpenStreetMap (site/ihry/osm-tochky.json), не з пам'яті."""

    def test_zrazky_prokhodiat(self):
        for f in SPRAVY:
            DT.zvirka_osm(DT.prochytaty(f))

    def test_zsunutyi_variant_ne_prokhodyt(self):
        s = DT.prochytaty(SPRAVY[0])
        s['polia']['de']['kandydaty'][0]['lat'] += 0.003          # ≈ 330 м
        with self.assertRaisesRegex(DT.PomylkaSpravy, 'OSM: варіант'):
            DT.zvirka_osm(s)

    def test_skhovanka_daleko_vid_oriientyra(self):
        s = DT.prochytaty(SPRAVY[0])
        s['slidy'][3]['tsil'].update(lat=50.4497, lon=30.485)      # стара точка «площі» — ≈ 620 м від Галицької площі
        with self.assertRaisesRegex(DT.PomylkaSpravy, 'схованка сліду 4'):
            DT.zvirka_osm(s)

    def test_bez_osm_ne_prokhodyt(self):
        s = DT.prochytaty(SPRAVY[1])
        s['slidy'][0]['tsil'].pop('osm')
        with self.assertRaisesRegex(DT.PomylkaSpravy, 'без точки еталона'):
            DT.zvirka_osm(s)

    def test_etalon(self):
        e = json.loads((IHRY / 'osm-tochky.json').read_text(encoding='utf-8'))
        self.assertIn('OpenStreetMap', e['pro'])
        for k, t in e['tochky'].items():
            self.assertRegex(t['osm'], r'^(node|way|relation)/\d+$', k)
            self.assertTrue(50.2 < t['lat'] < 50.6 and 30.2 < t['lon'] < 30.9, k)

    def test_kvalifikuy_tochky(self):
        e = DT.osm_tochky()
        for s in json.loads((IHRY / 'kvalifikuy.json').read_text(encoding='utf-8'))['spravy']:
            if s.get('tochka'):
                self.assertLess(DT.vidstan_m(s['tochka'], e[s['tochka']['osm']]), DT.OSM_STANTSIIA_M, s['id'])


class Porih(unittest.TestCase):
    """ZAVDANNYA-123: межа дрібного викрадення — з джерелом (закон № 3886-IX, чинний з 09.08.2024), не з пам'яті."""

    def test_k1_za_novoiu_redaktsiieiu(self):
        d = json.loads((IHRY / 'kvalifikuy.json').read_text(encoding='utf-8'))
        t = ' '.join(s['chomu'] for s in d['spravy'])
        self.assertNotIn('0,2 неоподатк', t)
        self.assertNotIn('близько 300 грн', t)
        self.assertIn('3 028 грн', t)
        self.assertIn('3886-IX', d['dzherelo_poroha']['tekst'])
        self.assertTrue(all(u.startswith('https://') for u in d['dzherelo_poroha']['posylannia']))


class VulytsiaVKarti(unittest.TestCase):
    """ZAVDANNYA-123: «Вулиця дня» в карті — робоча версія ZAVDANNYA-114, без заглушки."""

    @classmethod
    def setUpClass(cls):
        cls.t = (IHRY / 'ihry.js').read_text(encoding='utf-8')

    def test_bez_zahlushky(self):
        self.assertNotIn('з\'явиться з повним випуском', self.t)
        self.assertNotIn("'скоро', !DZH.vulytsia", self.t)

    def test_robocha_versiia(self):
        for shcho in ('V.pidkazkyDlia(zah)', 'V.vidkryti(nevd, zah)', "zah.chastyna", 'zvuzhennia',
                      "?dzherelo=hra-vulytsia", '/oplata/?tovar=pidpyska&amp;dzherelo=hra-vulytsia', 'navigator.share',
                      'Наступна вулиця — завтра', "'/karta/?hra=vulytsia'"):
            self.assertIn(shcho, self.t)

    def test_podilytysia_bez_nazvy(self):
        # Текст «Поділитися» — з ядра (без назви вулиці); посилання — гра без ?data=
        self.assertIn('V.tekstPodilytysia(VD.data, por, vRozghadano(), VD.d.sprob, location.origin + \'/karta/?hra=vulytsia\')', self.t)


if __name__ == '__main__':
    unittest.main()
