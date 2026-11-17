"""Перевірки «Нове біля дому» — щотижневий лист і сповіщення (ZAVDANNYA-119).

Запуск: python -m unittest tests.test_lyst -v
Без мережі, без ключів і без справжніх даних: стрічка тижня — штучна (`lyst/lyst_zrazky.py`).
"""
from __future__ import annotations

import copy
import email
import email.policy
import re
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlparse

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'lyst'))

import lyst as L  # noqa: E402
import lyst_kanaly as LK  # noqa: E402
import lyst_skhovyshche as S  # noqa: E402
import lyst_zrazky as Z  # noqa: E402

KLYUCH = b'testovyi-kliuch-lyshe-dlia-testiv-0123456789'
SAIT = 'https://moya-vulytsya.pages.dev'
IMENA = re.compile(r'ОСОБА|[А-ЯІЇЄҐ][а-яіїєґ\']+\s+[А-ЯІЇЄҐ]\.\s?[А-ЯІЇЄҐ]\.')
NOMER_BUDYNKU = re.compile(r',\s*\d+[а-яА-Я]?\b(?!–)|\bбуд\.\s*\d')


def params(url: str) -> dict:
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items()}


class Kanaly:
    def __init__(self):
        self.poshta = LK.PoshtaZahlushka()
        self.telegram = LK.Zahlushka(None, 'telegram')
        self.push = LK.Zahlushka(None, 'push')

    def d(self):
        return {'poshta': self.poshta, 'telegram': self.telegram, 'push': self.push}


class Zbyrannia(unittest.TestCase):
    def setUp(self):
        self.s = Z.strichka()

    def test_lyshe_v_radiusi_svoikh_adres(self):
        l = L.zibraty(self.s, Z.pidpysnyk())
        dim, robota = l.rozdily
        self.assertEqual(len(dim.podii), 4)
        self.assertEqual([p['mistse'] for p in robota.podii], ['провулок Тестовий'])
        self.assertEqual(sum(dim.skarhy.values()), 18)
        self.assertEqual(dim.problema['nazva'], 'перехрестя вулиці Зразкової й провулку Пробного')
        self.assertIsNone(robota.problema)

    def test_chuzhyi_ne_bachyt_chuzhoho(self):
        """Два підписники з різними адресами: у листі кожного — лише його адреси й те, що біля них."""
        a = L.Pidpysnyk('a', 'pidpyska', [L.Adresa('вулиця Зразкова', Z.LA, Z.LO, 'Дім')])
        b = L.Pidpysnyk('b', 'pidpyska', [L.Adresa('провулок Тестовий', Z.LA2, Z.LO2, 'Робота')])
        pos = Z.POS
        ta = ' '.join(L.usi_teksty(L.zibraty(self.s, a), pos))
        tb = ' '.join(L.usi_teksty(L.zibraty(self.s, b), pos))
        self.assertNotIn('провулок Тестовий', ta)
        self.assertNotIn('пляшок олії', ta)
        self.assertNotIn('вулиця Зразкова', tb)
        self.assertNotIn('забрав телефон', tb)
        # розсилка: кожен лист — на свою пошту й лише зі своїм посиланням відписки
        k = Kanaly()
        LK.rozsylka(self.s, [(a, {'poshta': 'a@example.org'}), (b, {'poshta': 'b@example.org'})], k.d(), SAIT, KLYUCH)
        for m in k.poshta.nadislani:
            pid = 'a' if m['To'] == 'a@example.org' else 'b'
            self.assertEqual(params(m['List-Unsubscribe'].strip('<>'))['p'], pid)
            tekst = m.get_body(('plain',)).get_content()
            self.assertNotIn('провулок Тестовий' if pid == 'a' else 'вулиця Зразкова', tekst)

    def test_bez_imen_i_syroi_fabuly(self):
        s = copy.deepcopy(self.s)
        s['podii'][0]['perekaz'] = 'ОСОБА_1 керував авто Іваненко І. І.'       # переказ з вадою — не показується
        s['podii'][1]['fabula'] = 'ОСОБА_2 сира фабула'                         # сира фабула в листі не з'являється ніколи
        l = L.zibraty(s, Z.pidpysnyk())
        for t in L.usi_teksty(l, Z.POS):
            self.assertIsNone(IMENA.search(t), t[:200])
            self.assertNotIn('сира фабула', t)

    def test_tykhyi_tyzhden(self):
        t = Z.strichka(tykha=True)
        l = L.zibraty(t, Z.pidpysnyk())
        self.assertTrue(l.tykhyi)
        self.assertIn('Тихий тиждень', L.tema(l))
        self.assertIsNone(L.zibraty(t, L.Pidpysnyk('x', 'pidpyska', Z.pidpysnyk().adresy, tykhyi_lyst=False)))
        self.assertIsNone(L.zibraty(t, Z.pidpysnyk(platno=False)), 'безкоштовно без нового — нічого')

    def test_slova(self):
        for l in (L.zibraty(self.s, Z.pidpysnyk()), L.zibraty(self.s, Z.pidpysnyk(platno=False)),
                  L.zibraty(Z.strichka(tykha=True), Z.pidpysnyk())):
            for t in L.usi_teksty(l, Z.POS):
                self.assertEqual(L.vady_tekstu(t), [], t[:200])
        self.assertTrue(L.vady_tekstu('Будьте уважні, тут небезпечно'))
        self.assertTrue(L.vady_tekstu('за правилом MV-25'))

    def test_bez_chervonoho(self):
        h = L.html_lysta(L.zibraty(self.s, Z.pidpysnyk()), Z.POS)
        for kolir in re.findall(r'#[0-9A-Fa-f]{6}', h):
            r, g, b = (int(kolir[i:i + 2], 16) for i in (1, 3, 5))
            self.assertFalse(r > 180 and g < 110 and b < 110, f'червоний чи помаранчевий: {kolir}')


class Bezkoshtovno(unittest.TestCase):
    """MV-124: одна адреса, лише числа; MV-25: без місць і номерів будинків подій; MV-102: статеві й щодо дітей — ні."""

    def setUp(self):
        self.s = Z.strichka()
        self.s['podii'].append(dict(Z._p(9, '2026-10-01', 'nas', 'вулиця Зразкова, 7', 0.0002, 0.0002,
                                         'Чоловік ударив жінку на сходах.'), vidkr=0))

    def test_lyshe_chysla(self):
        l = L.zibraty(self.s, Z.pidpysnyk(platno=False))
        self.assertEqual(len(l.rozdily), 1, 'безкоштовно — одна адреса')
        t = L.telegram_bezkoshtovno(l)
        for zaboroneno in ('перехрестя', 'ст. м.', 'сквер', 'Водій', 'Чоловік', 'http', 'Рішення суду', ', 7'):
            self.assertNotIn(zaboroneno, t)
        self.assertIsNone(NOMER_BUDYNKU.search(t.replace('1551', '')), t)
        self.assertIn('Нових подій з рішень судів у даних: 4', t, 'статева (vidkr = 0) не рахується')
        self.assertIn('399', t)

    def test_pidpysnyk_bachyt_nariwni(self):
        l = L.zibraty(self.s, Z.pidpysnyk())
        self.assertEqual(len(l.rozdily[0].podii), 5, 'у підписці чутливі — нарівні (MV-104)')

    def test_bot_lyshe_v_telegram_i_ne_tykhyi(self):
        k = Kanaly()
        p = Z.pidpysnyk(platno=False)
        zv = LK.rozsylka(self.s, [(p, {'telegram': 42, 'poshta': 'x@example.org'})], k.d(), SAIT, KLYUCH)
        self.assertEqual((zv['telegram'], zv['poshta'], zv['push']), (1, 0, 0))
        vmist = k.telegram.nadislani[0][1]
        self.assertEqual(vmist['reply_markup']['inline_keyboard'][1][0]['callback_data'], 'x:')
        zv = LK.rozsylka(Z.strichka(tykha=True), [(p, {'telegram': 42})], k.d(), SAIT, KLYUCH)
        self.assertEqual(zv['bez_novoho'], 1)

    def test_push_bez_nomeriv_i_opysiv(self):
        s = copy.deepcopy(self.s)
        p = L.Pidpysnyk('p', 'pidpyska', [L.Adresa('вулиця Зразкова, 5', Z.LA, Z.LO)])
        for x in L.push(L.zibraty(s, p)):
            self.assertNotIn('5', x['body'].split('—')[0])
            self.assertNotIn('Водій', x['body'])


class Vidpyska(unittest.TestCase):
    def setUp(self):
        self.skh = S.Skhovyshche()
        self.a = self.skh.dodaty('pidpyska', Z.pidpysnyk().adresy, poshta='a@example.org', chat_id=1)
        self.b = self.skh.dodaty('pidpyska', Z.pidpysnyk().adresy, poshta='b@example.org')

    def test_odyn_dotyk(self):
        url = S.posylannia_vidpysky(SAIT, KLYUCH, self.a, 'poshta')
        kod, _ = S.vidpyska(self.skh, KLYUCH, params(url))
        self.assertEqual(kod, 200)
        kanaly = dict((p.id, k) for p, k in self.skh.pidpysnyky())
        self.assertNotIn('poshta', kanaly[self.a])
        self.assertIn('telegram', kanaly[self.a])
        self.assertIn('poshta', kanaly[self.b], 'відписка А не чіпає Б')

    def test_chuzhyi_ne_vidpyshe(self):
        url = S.posylannia_vidpysky(SAIT, KLYUCH, self.a, 'poshta')
        p = params(url)
        for zmina in ({'p': self.b}, {'t': '0' * 32}, {'k': 'telegram'}, {'k': 'pidpysnyk'}):
            kod, _ = S.vidpyska(self.skh, KLYUCH, dict(p, **zmina))
            self.assertEqual(kod, 400, zmina)
        kod, _ = S.vidpyska(self.skh, b'inshyi-kliuch-inshyi-kliuch-inshyi-kliuch', p)
        self.assertEqual(kod, 400)
        self.assertEqual(len([1 for _, k in self.skh.pidpysnyky() if 'poshta' in k]), 2)

    def test_usi_kanaly_vymkneno_zapys_vydaleno(self):
        for k in S.KANALY:
            S.vidpyska(self.skh, KLYUCH, params(S.posylannia_vidpysky(SAIT, KLYUCH, self.a, k)))
        self.assertNotIn(self.a, [p.id for p, _ in self.skh.pidpysnyky()])
        self.assertEqual(self.skh.con.execute('SELECT count(*) FROM adresa WHERE pidpysnyk_id = ?', (self.a,)).fetchone()[0], 0)

    def test_zberihaiemo_minimum(self):
        polia = {r[1] for r in self.skh.con.execute('PRAGMA table_info(pidpysnyk)')}
        self.assertEqual(polia, {'id', 'poshta', 'chat_id', 'taryf', 'poshta_on', 'telegram_on', 'push_on', 'tykhyi',
                                 'stvoreno', 'nadislano'})
        polia_a = {r[1] for r in self.skh.con.execute('PRAGMA table_info(adresa)')}
        self.assertEqual(polia_a, {'pidpysnyk_id', 'poriadok', 'nazva', 'adresa', 'lat', 'lon'})
        self.assertNotIn('@', self.a, 'номер підписника — не пошта')

    def test_lyst_poshty_ma_zaholovky_vidpysky(self):
        k = Kanaly()
        LK.rozsylka(Z.strichka(), self.skh.pidpysnyky(), k.d(), SAIT, KLYUCH, self.skh, '2026-11-16')
        self.assertEqual(len(k.poshta.nadislani), 2)
        m = email.message_from_bytes(bytes(k.poshta.nadislani[0]), policy=email.policy.default)
        self.assertEqual(m['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')
        self.assertTrue(m['List-Unsubscribe'].startswith(f'<{SAIT}/vidpyska/?'))
        self.assertNotRegex(bytes(k.poshta.nadislani[0]).decode('utf-8', 'replace'), r'<img|pixel')
        self.assertEqual({r[0] for r in self.skh.con.execute('SELECT nadislano FROM pidpysnyk')}, {'2026-11-16'})

    def test_bez_kliucha_ne_pratsiuie(self):
        import os
        stare = os.environ.pop(S.ZMINNA_SEKRETU, None)
        try:
            with self.assertRaises(SystemExit):
                S.sekret()
        finally:
            if stare is not None:
                os.environ[S.ZMINNA_SEKRETU] = stare

    def test_poshta_lyshe_zahlushka(self):
        import os
        os.environ[LK.ZMINNA_POSHTY] = 'yakyis-servis'
        try:
            with self.assertRaises(SystemExit):
                LK.poshta()
        finally:
            del os.environ[LK.ZMINNA_POSHTY]
        with tempfile.TemporaryDirectory() as d:
            p = LK.poshta(Path(d))
            LK.rozsylka(Z.strichka(), self.skh.pidpysnyky(), {'poshta': p}, SAIT, KLYUCH)
            self.assertEqual(len(list(Path(d).glob('*.eml'))), 2)


if __name__ == '__main__':
    unittest.main()
