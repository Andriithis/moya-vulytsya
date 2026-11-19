"""Навчальна гра «Кваліфікуй: кар'єра» (ZAVDANNYA-146, прототип): ядро (через Node.js), генератор справ, межі.

Запуск: python -m unittest tests/test_kariera.py
Справжні дані (випуск і тексти рішень) не потрібні: ядро — на умовних справах, генератор — на штучній базі й текстах.
"""
from __future__ import annotations

import json
import lzma
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
KAR = KORIN / 'site' / 'ihry' / 'kariera'
sys.path.insert(0, str(KAR))
import kariera as K  # noqa: E402

NODE = shutil.which('node')


def sprava(doc, st, ch, sk, vyd='ДОР'):
    return [doc, st, ch, f'Фабула {doc}', f'Суд: {st}', f'https://reyestr.court.gov.ua/Review/{doc}', '2025-05-01', sk, vyd]


DANI = {
    'pole': ['doc', 'stattia', 'chastyna', 'fabula', 'chomu', 'url', 'data', 'skladnist', 'vyd'],
    'statti': {
        'КУпАП 130': {'nazva': 'Сп\'яніння', 'korotko': 'сп\'яніння', 'kodeks': 'КУпАП', 'n': 900, 'riven': 1,
                      'chastyny': ['1', '2', '3'], 'chastky': {'1': 8, '2': 2}},
        'КУпАП 124': {'nazva': 'ДТП', 'korotko': 'ДТП', 'kodeks': 'КУпАП', 'n': 1000, 'riven': 1, 'chastyny': [], 'chastky': {'—': 9}},
        'КУпАП 126': {'nazva': 'Без прав', 'korotko': 'без прав', 'kodeks': 'КУпАП', 'n': 500, 'riven': 2,
                      'chastyny': ['1', '2', '3', '4', '5'], 'chastky': {'5': 3}},
        'КУпАП 51': {'nazva': 'Дрібне викрадення', 'korotko': 'викрадення', 'kodeks': 'КУпАП', 'n': 300, 'riven': 3,
                     'chastyny': ['1', '2'], 'chastky': {'1': 3}},
        'КУпАП 173': {'nazva': 'Хуліганство', 'korotko': 'хуліганство', 'kodeks': 'КУпАП', 'n': 200, 'riven': 4,
                      'chastyny': [], 'chastky': {'—': 3}},
        'КК 185': {'nazva': 'Крадіжка', 'korotko': 'крадіжка', 'kodeks': 'КК', 'n': 100, 'riven': 2,
                   'chastyny': ['1', '2', '3', '4', '5'], 'chastky': {'4': 3}},
        'КК 309': {'nazva': 'Наркотики', 'korotko': 'наркотики', 'kodeks': 'КК', 'n': 90, 'riven': 3,
                   'chastyny': ['1', '2', '3'], 'chastky': {'1': 3}},
    },
    'spravy': [sprava('101', 'КУпАП 130', '1', 1), sprava('102', 'КУпАП 130', '2', 2), sprava('103', 'КУпАП 124', '', 1, 'ДТП'),
               sprava('104', 'КУпАП 126', '5', 2), sprava('105', 'КУпАП 51', '1', 3, 'МАЙ'), sprava('106', 'КУпАП 173', '', 4, 'ГП'),
               sprava('107', 'КК 185', '4', 2, 'МАЙ'), sprava('108', 'КК 309', '1', 3, 'НАР'), sprava('109', 'КК 309', '2', 5, 'НАР'),
               sprava('110', 'КУпАП 124', '', 1, 'ДТП'), sprava('111', 'КУпАП 130', '1', 1)],
}


def node(kod: str):
    """Виконати JS з ядром `Y` і даними `D` (уже підготовленими); повертає те, що скрипт надрукував як JSON."""
    skrypt = (f"const Y=require({json.dumps(str(KAR / 'kariera-yadro.js'))});"
              f"const D=Y.pidhotuvaty({json.dumps(DANI, ensure_ascii=False)});"
              f"const out=(()=>{{{kod}}})();console.log(JSON.stringify(out));")
    r = subprocess.run([NODE, '-e', skrypt], capture_output=True, text=True, timeout=60)
    if r.returncode:
        raise AssertionError(r.stderr)
    return json.loads(r.stdout)


@unittest.skipUnless(NODE, 'потрібен Node.js')
class Yadro(unittest.TestCase):
    def test_spravy_dnia_odnakovi_dlia_vsikh_i_za_skladnistiu(self):
        r = node("const a=Y.spravyDnia(D,'2026-11-19').map(x=>x.doc),b=Y.spravyDnia(D,'2026-11-19').map(x=>x.doc);"
                 "const c=Y.spravyDnia(D,'2026-11-20').map(x=>x.doc);"
                 "return [a,b,new Set(a).size,Y.spravyDnia(D,'2026-11-19').map(x=>x.skladnist)]")
        self.assertEqual(r[0], r[1], 'та сама дата — ті самі справи')
        self.assertEqual(r[2], 5, 'п\'ять різних справ')
        self.assertEqual(r[3], [1, 1, 2, 3, 4], 'від частої до рідкісної')

    def test_kroky_i_bal(self):
        r = node("const s=Y.novyi('kursant');const x=D.spravy.find(z=>z.doc==='102');"
                 "const a=Y.vidpovisty(s,x,{kodeks:'КУпАП',stattia:'КУпАП 130',chastyna:'2'},'2026-11-19');"
                 "const b=Y.vidpovisty(s,x,{kodeks:'КУпАП',stattia:'КУпАП 130',chastyna:'1'},'2026-11-19');"
                 "const y=D.spravy.find(z=>z.doc==='103');const c=Y.otsinyty(y,{kodeks:'КУпАП',stattia:'КУпАП 124'});"
                 "return [a.otsinka.vse,a.bal,b.otsinka.chastyna,b.bal,c,s.pomylky,Y.riven(s).nazva]")
        self.assertTrue(r[0])
        self.assertEqual(r[1], 12, '(2 + 5 + 3) × 1,2 за складність 2')
        self.assertFalse(r[2])
        self.assertEqual(r[3], 8, '(2 + 5) × 1,2')
        self.assertEqual(r[4], {'kodeks': True, 'stattia': True, 'chastyna': None, 'vse': True}, 'без частини — кроку немає')
        self.assertEqual(r[5], {'ч. 2 ст. 130 КУпАП → ч. 1 ст. 130 КУпАП': 1})
        self.assertEqual(r[6], 'Курсант')

    def test_povtory_1_3_7(self):
        r = node("const s=Y.novyi('pravo');const x=D.spravy.find(z=>z.doc==='105');const k=[];"
                 "Y.vidpovisty(s,x,{kodeks:'КК',stattia:'КК 185'},'2026-11-19');k.push(s.povtory['105'].koly);"
                 "k.push(Y.nastupna(D,s,'2026-11-19').povtor);const n=Y.nastupna(D,s,'2026-11-20');k.push(n.povtor,n.sprava.doc);"
                 "const ok={kodeks:'КУпАП',stattia:'КУпАП 51',chastyna:'1'};"
                 "Y.vidpovisty(s,x,ok,'2026-11-20');k.push(s.povtory['105'].koly);"
                 "Y.vidpovisty(s,x,ok,'2026-11-23');k.push(s.povtory['105'].koly);"
                 "Y.vidpovisty(s,x,ok,'2026-11-30');k.push(s.povtory['105']||null);return [k,s.pomylky]")
        self.assertEqual(r[0], ['2026-11-20', False, True, '105', '2026-11-23', '2026-11-30', None])
        self.assertEqual(r[1], {'КУпАП 51 → КК (кодекс)': 1}, 'помилка кодексу — окремою парою')

    def test_seriia_z_vykhidnym(self):
        r = node("const s=Y.novyi('pravo');const k=[];"
                 "for(const d of ['2026-11-01','2026-11-02','2026-11-04','2026-11-06','2026-11-09']){Y.zakrytyDen(s,d);k.push(s.seriia);}"
                 "return k")
        self.assertEqual(r, [1, 2, 3, 1, 1], 'один пропущений день на 7 — «вихідний»; другий за тиждень чи 2+ дні — заново')

    def test_den_zarakhovuietsia_pislia_piaty(self):
        r = node("const s=Y.novyi('pravo');const d='2026-11-19';const sp=Y.spravyDnia(D,d);"
                 "sp.forEach(x=>Y.vidpovisty(s,x,{kodeks:x.stattia.split(' ')[0],stattia:x.stattia,chastyna:x.chastyna},d,'den'));"
                 "Y.vidpovisty(s,sp[0],{kodeks:'КК'},d,'den');"
                 "return [s.seriia,s.dni[d].pravylno,Y.stanDnia(s,D,d).every(z=>z.zrobleno===1)]")
        self.assertEqual(r, [1, 5, True], 'повторна відповідь на ту саму справу дня не перезаписує день')

    def test_rivni_vidkryvaiut_skladnist(self):
        r = node("const s=Y.novyi('pravo');const a=[];for(const d of [0,59,60,180,400,800,1500,99999]){s.dosvid=d;"
                 "const r=Y.riven(s);a.push([r.indeks,r.maksSkladnist]);}"
                 "s.dosvid=0;const n=[];for(let i=0;i<30;i++)n.push(Y.nastupna(D,s,'2026-11-19',i).sprava.skladnist);"
                 "return [a,Math.max(...n)]")
        self.assertEqual(r[0], [[0, 1], [0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 5], [5, 5]])
        self.assertEqual(r[1], 1, 'на першому рівні — лише найчастіші статті')

    def test_varianty(self):
        r = node("const x=D.spravy.find(z=>z.doc==='108');const v=Y.variantyStatti(D,x);"
                 "return [v,Y.variantyStatti(D,x),Y.variantyChastyny(D,x),Y.variantyChastyny(D,D.spravy.find(z=>z.doc==='103'))]")
        self.assertIn('КК 309', r[0])
        self.assertEqual(len(set(r[0])), len(r[0]))
        self.assertTrue(all(v.startswith('КК ') for v in r[0]), 'варіанти — того самого кодексу')
        self.assertEqual(r[0], r[1], 'варіанти сталі для справи')
        self.assertEqual(r[2], ['1', '2', '3'])
        self.assertEqual(r[3], [])

    def test_odna_chastyna_ne_pytannia(self):
        r = node("D.statti['КУпАП 173'].chastyny=['1'];const x=Object.assign({},D.spravy.find(z=>z.doc==='106'),{chastyna:'1'});"
                 "return [Y.variantyChastyny(D,x),Y.otsinyty(x,{kodeks:'КУпАП',stattia:'КУпАП 173'},D).vse]")
        self.assertEqual(r, [[], True])

    def test_nabir_vykladacha(self):
        r = node("const n=Y.nabir(D,{statti:['КУпАП 130','КК 309'],kilkist:4,zerno:'x'});const k=Y.kodNaboru(n);"
                 "const z=Y.rozibratyKod(D,k).map(x=>x.doc);const c=Y.kodRezultatu(k,[true,false,true,true]);"
                 "return [n.map(x=>x.doc),z,n.map(x=>x.stattia),c,Y.kodRezultatu(k,[true,true,true,false]),Y.rozibratyKod(D,'zzz.!!').length]")
        self.assertEqual(r[0], r[1], 'посилання відкриває той самий набір у тому самому порядку')
        self.assertEqual(sorted(r[2]), ['КК 309', 'КК 309', 'КУпАП 130', 'КУпАП 130'], 'рівно між статтями')
        self.assertRegex(r[3], r'^3/4-[0-9a-z]+$')
        self.assertNotEqual(r[3], r[4], 'код залежить від того, які саме відповіді правильні')
        self.assertEqual(r[5], 0)

    def test_zachatok_kvalifikuy(self):
        skrypt = (f"const Y=require({json.dumps(str(KAR / 'kariera-yadro.js'))});"
                  f"const D=Y.pidhotuvaty(require({json.dumps(str(KAR.parent / 'kvalifikuy.json'))}));"
                  "const x=Y.spravyDnia(D,'2026-11-19');console.log(JSON.stringify([D.zrazok,x.length,!!D.statti[x[0].stattia]]))")
        r = subprocess.run([NODE, '-e', skrypt], capture_output=True, text=True, timeout=60)
        self.assertEqual(json.loads(r.stdout), [True, 5, True], 'без даних випуску гра працює на зачатку')


TEKST_130 = ('Справа № 1. ПОСТАНОВА. ВСТАНОВИВ: водій керував у стані сп`яніння. Таким чином, суд вважає доведеним наявність '
             'в діянні ОСОБА_1 складу адміністративного правопорушення, передбаченого ч. 2 ст. 130 КУпАП, тобто повторне '
             'протягом року керування в стані сп`яніння. Керуючись ст.ст. 130 ч.2, 283 КУпАП, суд, - П О С Т А Н О В И В : '
             'ОСОБА_1 визнати винним у вчиненні правопорушення, передбаченого ч. 2 ст. 130 КУпАП та накласти стягнення '
             'відповідно до ч. 1 ст. 307 КУпАП. Суддя.')


class Henerator(unittest.TestCase):
    def test_kvalifikatsiia_z_rezoliutyvnoi(self):
        self.assertEqual(K.znaity_kvalifikatsiiu(TEKST_130), ('КУпАП 130', '2'))
        dvi = TEKST_130.replace('передбаченого ч. 2 ст. 130 КУпАП та', 'передбачених ст. 124, ч. 2 ст. 130 КУпАП та')
        self.assertIsNone(K.znaity_kvalifikatsiiu(dvi), 'дві статті — справа неоднозначна')
        kk = 'Обставини. У Х В А Л И В: ОСОБА_3 визнати винуватим у вчиненні кримінального правопорушення, передбаченого ч.4 ст.185 КК України та призначити покарання; ст. 75 КК України.'
        self.assertEqual(K.znaity_kvalifikatsiiu(kk), ('КК 185', '4'), 'стаття покарання (75 КК) не плутає')
        self.assertEqual(K.znaity_kvalifikatsiiu('ПОСТАНОВИВ: ОСОБА_1 визнати винним за ст. 124 КУпАП.'), ('КУпАП 124', ''))

    def test_poiasnennia_slovamy_sudu(self):
        p = K.poiasnennia(TEKST_130, 'КУпАП 130', '2')
        self.assertIn('тобто повторне', p)
        self.assertIn('Особа А', p)
        self.assertNotIn('ОСОБА_', p)

    def test_znejosobyty(self):
        t = K.znejosobyty('Обвинувачений ОСОБА_3, ІНФОРМАЦІЯ_1, 05.05.2025 за адресою: м. Київ, вул. Хрещатик, 15-А, кв. 7, '
                          'біля будинку 28/15 керував авто д.н.з. НОМЕР_1, повторно протягом року після засудження за ч. 2 '
                          'ст. 309 КК України, що утворює склад адміністративного правопорушення, передбаченого ч. 1 ст. 130 КУпАП.')
        self.assertIn('Особа В', t)
        self.assertNotRegex(t, r'ОСОБА_|ІНФОРМАЦІЯ|НОМЕР_|309|130|15-А|28/15|кв\. 7|КУпАП|КК')
        self.assertIn('вул. Хрещатик', t)
        self.assertIn('повторно протягом року', t, 'ознака частини лишається — це і є навичка')
        self.assertIn('[стаття]', t)

    def test_poza_hroiu(self):
        for st in ('ст.173-2 КУпАП · домашнє насильство', 'ст.152 КК · зґвалтування', 'ст.390-1 КК · приписи', 'ст.156 КК · розбещення'):
            self.assertTrue(K.POZA.search(st), st)
        for st in ('ст.156 КУпАП · торгівля алкоголем', 'ст.185 КК · крадіжка', 'ст.115 КК · умисне вбивство'):
            self.assertFalse(K.POZA.search(st), st)
        self.assertTrue(K.DITY.search('продав пиво неповнолітньому'))

    def test_zibraty_naskriz(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            con = sqlite3.connect(tmp / 'events.db')
            con.executescript(
                'CREATE TABLE release(versiia TEXT, podii INT, khesh_vkhodu TEXT);'
                "INSERT INTO release VALUES('events-2026-11-08',3,'x');"
                'CREATE TABLE document(doc_id TEXT, data_rishennia TEXT, url TEXT);'
                'CREATE TABLE event(event_id TEXT, doc_id TEXT, stattia TEXT, fabula TEXT, vyd TEXT, chutlyva INT);')
            fab = ('Особа ОСОБА_1 керувала автомобілем у стані алкогольного сп`яніння по вул. Хрещатик, 22 у м. Києві, '
                   'повторно протягом року, від огляду не відмовлялась, результат огляду — 1,2 проміле.')
            rows = [('1', 'ст.130 КУпАП · керування у стані сп\'яніння', fab, 'ДОР', 0),
                    ('2', 'ст.173-2 КУпАП · домашнє насильство', fab, 'НАС', 0),
                    ('3', 'ст.130 КУпАП · керування у стані сп\'яніння', fab.replace('Особа', 'Неповнолітня особа'), 'ДОР', 0)]
            for doc, st, f, v, ch in rows:
                con.execute('INSERT INTO document VALUES(?,?,?)', (doc, '2025-05-01', f'https://reyestr.court.gov.ua/Review/{doc}'))
                con.execute('INSERT INTO event VALUES(?,?,?,?,?,?)', (doc + '-1', doc, st, f, v, ch))
            con.commit()
            con.close()
            (tmp / 't').mkdir()
            with lzma.open(tmp / 't' / '2025-05.jsonl.xz', 'wt', encoding='utf-8') as fh:
                for doc in ('1', '2', '3'):
                    fh.write(json.dumps({'doc_id': doc, 'tekst': TEKST_130}, ensure_ascii=False) + '\n')
            d = K.zibraty(tmp / 'events.db', [tmp / 't' / '2025-05.jsonl.xz'])
        self.assertEqual(d['vypusk'], 'events-2026-11-08')
        self.assertEqual([s[0] for s in d['spravy']], ['1'], 'домашнє насильство й справа з неповнолітнім — поза грою')
        s = dict(zip(d['pole'], d['spravy'][0]))
        self.assertEqual((s['stattia'], s['chastyna']), ('КУпАП 130', '2'))
        self.assertNotRegex(s['fabula'], r'ОСОБА_|22')
        self.assertIn('тобто', s['chomu'])
        self.assertEqual(d['statti']['КУпАП 130']['riven'], 1)


class Mezhi(unittest.TestCase):
    FAILY = ('index.html', 'kariera.js', 'kariera-yadro.js')

    def test_bez_vypadkovosti_i_bez_hroshei(self):
        for f in ('kariera-yadro.js', 'kariera.js'):
            t = (KAR / f).read_text(encoding='utf-8')
            self.assertNotIn('Math.random', t, f'{f}: справи дня однакові для всіх')
            self.assertNotRegex(t, r'fetch\([^)]*(oplata|kupyty|api|http)', f'{f}: прототип нічого не продає й не надсилає')

    def test_bez_zaboronenykh_sliv(self):
        zab = re.compile(r'небезпечн|безпечн|рейтинг|будьте уважн|уникайте|станеться знову|макет|конвеєр|MV-\d', re.I)
        for f in self.FAILY:
            t = (KAR / f).read_text(encoding='utf-8')
            vydyme = re.sub(r'//[^\n]*|<!--.*?-->', '', t, flags=re.S)   # коментарі коду люди не бачать
            self.assertIsNone(zab.search(vydyme), f)

    def test_ne_yurydychna_dopomoha(self):
        self.assertIn('Навчання, не юридична допомога', (KAR / 'index.html').read_text(encoding='utf-8'))

    def test_bez_vbudovanykh_styliv(self):
        for f in ('index.html', 'kariera.js'):
            self.assertNotIn('style="', (KAR / f).read_text(encoding='utf-8'), f'{f}: політика безпеки сторінки')

    def test_zminni_dyzainu_yak_u_hri(self):
        hra = (KORIN / 'site' / 'hra' / 'hra.css').read_text(encoding='utf-8')
        kar = (KAR / 'kariera.css').read_text(encoding='utf-8')
        z = lambda t: dict(re.findall(r'(--[\w-]+):\s*(#[0-9A-Fa-f]{6})', t.split('* {')[0]))
        self.assertEqual(z(kar), z(hra))

    def test_dani_poza_git(self):
        r = subprocess.run(['git', 'check-ignore', '-q', 'site/ihry/kariera/kariera.json'], cwd=KORIN)
        self.assertEqual(r.returncode, 0, 'фабули з випуску — поза git')


if __name__ == '__main__':
    unittest.main()
