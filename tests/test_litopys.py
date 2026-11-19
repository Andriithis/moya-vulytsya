"""Довга гра «Літопис міста» (ZAVDANNYA-140, прототип): ядро гри (через Node.js), генератор даних, межі.

Запуск: python -m unittest tests/test_litopys.py
Справжні дані (випуск і колода) не потрібні: ядро — на умовних вулицях, генератор — на підмінених профілях.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

KORIN = Path(__file__).resolve().parents[1]
LIT = KORIN / 'site' / 'ihry' / 'litopys'
sys.path.insert(0, str(LIT))
import litopys as L  # noqa: E402

NODE = shutil.which('node')

DANI = {
    'vydy': {'dtp': {'nazva': 'ДТП', 'n': 500, 'chastka': 50.0, 'ridkist': 'zvychaina'},
             'kurinnia': {'nazva': 'Куріння', 'n': 9, 'chastka': 0.9, 'ridkist': 'ridkisna'},
             'shum': {'nazva': 'Тиша', 'n': 1, 'chastka': 0.05, 'ridkist': 'duzhe'}},
    'rayony': {'Подільський': {}, 'Печерський': {}},
    'podii': {'1-1': ['dtp', 2025, 'опис', 'вул. А, 1', 50.4, 30.5, 'https://x', '1'],
              '2-1': ['kurinnia', 2024, 'опис', 'вул. Б, 2', 50.4, 30.5, 'https://x', '2'],
              '3-1': ['shum', 2024, 'опис', 'вул. В, 3', 50.4, 30.5, 'https://x', '3']},
    'vulytsi': [{'slug': 'a', 'rayon': 'Подільський', 'podii': ['1-1', '2-1']},
                {'slug': 'b', 'rayon': 'Подільський', 'podii': ['3-1']},
                {'slug': 'c', 'rayon': 'Печерський', 'podii': []}],
}


def node(kod: str):
    """Виконати JS з ядром `Y` і даними `D`; повертає те, що скрипт надрукував як JSON."""
    skrypt = (f"const Y=require({json.dumps(str(LIT / 'litopys-yadro.js'))});const D={json.dumps(DANI, ensure_ascii=False)};"
              f"const out=(()=>{{{kod}}})();console.log(JSON.stringify(out));")
    r = subprocess.run([NODE, '-e', skrypt], capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


@unittest.skipUnless(NODE, 'потрібен Node.js')
class Yadro(unittest.TestCase):
    T0 = "const t0=Date.parse('2026-11-19T10:00:00Z');"

    def test_dotyk_i_naim(self):
        r = node(self.T0 + "const s=Y.novyi(t0,'Подільський');for(let i=0;i<15;i++)Y.dotyk(s,D.vydy,t0);"
                 "const ok=Y.naiaty(s,'chytach');return [ok,s.pomichnyky.chytach,Math.round(s.storinky),Y.tsinaPomichnyka(s,Y.N.pomichnyky[0])]")
        self.assertEqual(r[:3], [True, 1, 0])
        self.assertEqual(r[3], 18)   # 15 × 1,15

    def test_vulytsia_lyshe_u_vidkrytomu_raioni_i_kartky_navperedvidomi(self):
        r = node(self.T0 + "const s=Y.novyi(t0,'Подільський');s.storinky=1e9;"
                 "const c=Y.vidkrytyVulytsiu(s,D.vulytsi[2],D.podii);const a=Y.vidkrytyVulytsiu(s,D.vulytsi[0],D.podii);"
                 "const a2=Y.vidkrytyVulytsiu(s,D.vulytsi[0],D.podii);return [c.chomu,a.ok,a.novi_karty,a2.chomu,s.karty]")
        self.assertEqual(r[0], 'rayon')
        self.assertTrue(r[1])
        self.assertEqual(sorted(r[2]), ['dtp', 'kurinnia'], 'вулиця дає саме ті картки, що показано наперед')
        self.assertEqual(r[3], 'uzhe')
        self.assertEqual(r[4], {'dtp': 1, 'kurinnia': 1})

    def test_offlain_mezha_i_polovyna(self):
        r = node(self.T0 + "const s=Y.novyi(t0,'Подільський');s.pomichnyky.chytach=10;"
                 "const r=Y.plyn(s,D.vydy,t0+24*3600e3);return [r.obrizano,Math.round(r.storinok)]")
        self.assertTrue(r[0])
        self.assertEqual(r[1], round(10 * 0.2 * 0.15 * 8 * 3600))   # 8 годин, у 0,15 швидкості (ZAVDANNYA-141)

    def test_vydannia_zberihaie_kolektsiiu(self):
        r = node(self.T0 + "const s=Y.novyi(t0,'Подільський');s.storinky=1e9;Y.vidkrytyVulytsiu(s,D.vulytsi[0],D.podii);"
                 "s.za_vydannia=2e6;s.pomichnyky.chytach=5;const a=Y.noveVydannia(s);"
                 "return [a,s.avtorytet,s.storinky,s.pomichnyky,s.vulytsi,Object.keys(s.karty).length,Y.porihVydannia(s)]")
        self.assertEqual(r[0], 3)                 # 2 млн / 20 тис. = 100 → 1 + log10(100)
        self.assertEqual(r[2], 0)
        self.assertEqual(r[3], {})
        self.assertEqual(r[4], ['a'])
        self.assertEqual(r[5], 2)
        self.assertEqual(r[6], 200000)            # наступний поріг — удесятеро вищий

    def test_sprava_dnia_odnakova_dlia_vsikh_i_pravylna_sered_variantiv(self):
        r = node("const a=Y.spravaDnia('2026-11-19',D),b=Y.spravaDnia('2026-11-19',D);"
                 "return [JSON.stringify(a)===JSON.stringify(b),a.varianty_vydu.includes(a.vyd),a.varianty_vydu.length,"
                 "new Set(a.varianty_vydu).size]")
        self.assertEqual(r, [True, True, 3, 3])

    def test_seriia_z_vykhidnym(self):
        kod = self.T0 + """const s=Y.novyi(t0,'Подільський');s.storinky=1e12;
          function zrobyty(t){const d=Y.den(s,t);d.zrobleno={sprava:true,rayon:true};d.vulyts=3;Y.perevirytyVulytsi(s,t);}
          const res=[];
          zrobyty(t0);res.push(s.seriia.dniv);
          zrobyty(t0+864e5);res.push(s.seriia.dniv);
          zrobyty(t0+3*864e5);res.push(s.seriia.dniv);      // пропущено один день — вихідний
          zrobyty(t0+5*864e5);res.push(s.seriia.dniv);      // ще пропуск у той самий тиждень — серія з початку
          return res;"""
        self.assertEqual(node(kod), [1, 2, 3, 1])

    def test_vidpovid_odna_na_den(self):
        r = node(self.T0 + "const s=Y.novyi(t0,'Подільський');const a=Y.vidpovisty(s,t0,'sprava','dtp','dtp');"
                 "const b=Y.vidpovisty(s,t0,'sprava','shum','dtp');return [a,b,s.natkhnennia_do-t0]")
        self.assertEqual(r, [True, None, 3600000])

    def test_povazhni_bez_bonusu_i_ne_v_spravi_dnia(self):
        dani = "const P=JSON.parse(JSON.stringify(D));P.vydy.tilesni={nazva:'Тілесні',n:5,chastka:0.5,ridkist:'ridkisna',povazhna:true};" \
               "P.podii['4-1']=['tilesni',2025,'',' вул. Г, 4',50.4,30.5,'https://x','4'];P.vulytsi[1].podii.push('4-1');"
        r = node(self.T0 + dani + "const s=Y.novyi(t0,'Подільський');s.karty={tilesni:16};const b=Y.bonusKart(s,P.vydy);"
                 "const ids=new Set();for(let i=0;i<400;i++){const d=new Date(t0+i*864e5).toISOString().slice(0,10);"
                 "const sp=Y.spravaDnia(d,P);ids.add(sp.id);if(sp.varianty_vydu.includes('tilesni'))ids.add('VARIANT');}"
                 "return [b,[...ids].sort()]")
        self.assertEqual(r[0], 0, 'без балів «за шкоду»')
        self.assertNotIn('4-1', r[1])
        self.assertNotIn('VARIANT', r[1])

    def test_poshta_arkhivu_raz_na_den(self):
        r = node(self.T0 + "const s=Y.novyi(t0,'Подільський');const a=Y.poshta(s,t0);const b=Y.poshta(s,t0+3600e3);"
                 "const tr=Y.skilkyNaVulytsi(s,3);const c=Y.poshta(s,t0+864e5);const d=Y.poshta(s,t0+864e5+60e3);"
                 "return [a,b,c===tr,d,tr===Y.tsinaVulytsi(s)+Y.tsinaVulytsi({vulytsi:['x']})+Y.tsinaVulytsi({vulytsi:['x','y']})]")
        self.assertEqual(r, [0, 0, True, 0, True], 'перший день без пошти; далі — раз на день, рівно на 3 наступні вулиці')

    def test_zlamanyi_stan_ne_valyt_hru(self):
        self.assertEqual(node("return [Y.pryniaty(null,1),Y.pryniaty({v:99},1),Y.pryniaty('x',1)]"), [None, None, None])


@unittest.skipUnless(NODE and (LIT / 'litopys.json').exists(), 'потрібні Node.js і зібраний litopys.json (з колоди, поза git)')
class Temp(unittest.TestCase):
    """ZAVDANNYA-141, крок 3: місто не закінчується за тиждень, щодня є що відкрити (симулятор, 60 днів)."""

    def test_60_dniv(self):
        r = subprocess.run([NODE, str(LIT / 'symuliatsiia.js'), str(LIT / 'litopys.json'), '--json'],
                           capture_output=True, text=True, timeout=300)
        d = json.loads(r.stdout)
        dni = {x['den']: x for x in d['dni'] if 'mitka' not in x}
        self.assertLess(dni[7]['vulyts'], d['vsogo_vulyts'] * 0.15, 'за тиждень — менше 15 % вулиць')
        self.assertLess(dni[60]['vulyts'], d['vsogo_vulyts'] * 0.5)
        self.assertGreaterEqual(min(dni[n]['novykh'] for n in range(2, 61)), 3, 'щодня щонайменше 3 нові вулиці')


class Mezhi(unittest.TestCase):
    def test_bez_vypadkovosti_i_bez_hroshei(self):
        for f in ('litopys-yadro.js', 'litopys.js'):
            t = (LIT / f).read_text(encoding='utf-8')
            self.assertNotIn('Math.random', t, f'{f}: нагороди без випадку (MV-155 П8)')
            self.assertNotRegex(t, r'fetch\([^)]*(oplata|kupyty|api)', f'{f}: прототип нічого не продає й не надсилає')

    def test_bez_zaboronenykh_sliv(self):
        zab = re.compile(r'небезпечн|безпечн|рейтинг|будьте уважн|уникайте|станеться знову', re.I)
        for f in ('index.html', 'litopys.js', 'litopys-yadro.js'):
            self.assertIsNone(zab.search((LIT / f).read_text(encoding='utf-8')), f)

    def test_bez_vbudovanykh_styliv(self):
        for f in ('index.html', 'litopys.js'):
            self.assertNotIn('style="', (LIT / f).read_text(encoding='utf-8'), f'{f}: політика безпеки сторінки')

    def test_zminni_dyzainu_yak_u_hri(self):
        hra = (KORIN / 'site' / 'hra' / 'hra.css').read_text(encoding='utf-8')
        lit = (LIT / 'litopys.css').read_text(encoding='utf-8')
        z = lambda t: dict(re.findall(r'(--[\w-]+):\s*(#[0-9A-Fa-f]{6})', t.split('* {')[0]))
        self.assertEqual(z(lit), z(hra))

    def test_ridkist(self):
        self.assertEqual([L.ridkist(x) for x in (51, 5, 1.6, 0.4, 0.05)],
                         ['zvychaina', 'zvychaina', 'nechasta', 'ridkisna', 'duzhe'])


class Henerator(unittest.TestCase):
    def test_poterpili_povazhno_mv4_ni(self):
        koloda = {'zibrano': '2026-11-08', 'podii': [
            {'id': '1-1', 'kategoriia': 'dtp', 'vyd': 'ДТП', 'rik': 2025, 'opys_korotkyi': 'зіткнення', 'adresa': 'вул. А, 1',
             'lat': 50.4, 'lon': 30.5, 'rishennya_url': 'https://x', 'rishennya_nomer': '1'},
            {'id': '2-1', 'kategoriia': 'tilesni', 'vyd': 'Тілесні', 'rik': 2025, 'opys_korotkyi': 'вдарив', 'adresa': 'вул. А, 2',
             'lat': 50.4, 'lon': 30.5, 'rishennya_url': 'https://x', 'rishennya_nomer': '2'},
            {'id': '3-1', 'kategoriia': 'domashnie_nasylstvo', 'vyd': 'Д', 'rik': 2025, 'opys_korotkyi': 'x', 'adresa': 'вул. А, 3',
             'lat': 50.4, 'lon': 30.5, 'rishennya_url': 'https://x', 'rishennya_nomer': '3'}]}

        class V:
            slug = 'a'

        class Dn:
            versiia = 'proba'
            vulytsi = {'a': V()}
        chastoty = {'dtp': ('ДТП', 900), 'tilesni': ('Тілесні', 50), 'domashnie_nasylstvo': ('Д', 50)}
        prof = {'slug': 'a', 'nazva': 'вулиця А', 'rayon': 'Подільський', 'n': 40, 'hrupa': 'dtp', 'lat': 50.4, 'lon': 30.5}
        with mock.patch.object(L.VD, 'podii_kolody', return_value={'a': koloda['podii']}), \
                mock.patch.object(L.VD, 'profil', return_value=prof):
            d = L.zibraty_z_dani(Dn(), koloda, chastoty, {'Подільський': [[50.4, 30.5], [50.5, 30.5], [50.5, 30.6]]})
        # MV-165: події з потерпілими — є (без опису, позначка «поважна»); статеві, щодо дітей, домашнє насильство — ні.
        self.assertEqual(sorted(d['vydy']), ['dtp', 'tilesni'])
        self.assertTrue(d['vydy']['tilesni']['povazhna'])
        self.assertNotIn('povazhna', d['vydy']['dtp'])
        self.assertEqual(sorted(d['podii']), ['1-1', '2-1'])
        self.assertEqual(d['podii']['2-1'][2], '', 'без опису — без деталей про потерпілого')
        self.assertEqual(d['podii']['2-1'][6], 'https://x', 'посилання на рішення лишається')
        self.assertEqual(d['podii']['1-1'][2], 'зіткнення')
        self.assertEqual(d['vydy']['dtp']['chastka'], 90.0, 'частка — від усіх подій, разом із прибраними видами')


if __name__ == '__main__':
    unittest.main()
