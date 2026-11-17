"""ZAVDANNYA-105: місяці по сотах для смуги «роки · місяці» й «вау» — лише числа, сума = число за 3 роки."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))
sys.path.insert(0, str(KORIN / 'site' / 'sait'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    import h3  # noqa: F401
except ImportError:  # pragma: no cover
    h3 = None


@unittest.skipIf(h3 is None, 'немає h3')
class Misiatsi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import zibraty_sait
        from test_sait import stvoryty_bazu, stvoryty_pereimenuvannya
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        stvoryty_bazu(t / 'events.db')
        stvoryty_pereimenuvannya(t / 'pereim.csv')
        zibraty_sait.zibraty_sait(t / 'events.db', t / 'sait', t / 'pereim.csv', KORIN / 'data' / 'borders.json')
        cls.soty = {r: json.loads((t / 'sait' / 'karta' / f'soty-{r}.json').read_text(encoding='utf-8')) for r in (7, 8, 9)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_suma_misiatsiv_dorivniuie_chyslu_za_try_roky(self):
        bulo = 0
        for r, d in self.soty.items():
            for f in d['soty']['features']:
                p = f['properties']
                for h, ryad in p.get('m', {}).items():
                    bulo += 1
                    self.assertLessEqual(sum(n for _, n in ryad), p.get(h + '3', 0), (r, p['id'], h))
                    self.assertTrue(all(isinstance(i, int) and 0 <= i < 36 and isinstance(n, int) and n > 0 for i, n in ryad))
                if r == 9 and 'm' in p and 'all' in p['m']:
                    # на рівні 9 статевих і щодо дітей немає, а дата в штучній базі є всюди — сума рівна
                    self.assertEqual(sum(n for _, n in p['m']['all']), p['all3'])
        self.assertGreater(bulo, 0)

    def test_chutlyvi_bez_misiatsia(self):
        # у штучній базі статева справа й справа щодо дитини — 2025-05 на Васильківській (лише великі соти, «nas»)
        menshe = 0
        for r in (7, 8):
            for f in self.soty[r]['soty']['features']:
                p = f['properties']
                if p.get('nas3'):
                    v_misiatsiakh = sum(n for _, n in p.get('m', {}).get('nas', []))
                    self.assertLessEqual(v_misiatsiakh, p['nas3'], (r, p['id']))
                    menshe += v_misiatsiakh < p['nas3']
        self.assertGreaterEqual(menshe, 2)   # сота з Васильківською на рівнях 7 і 8

    def test_u_misiatsiakh_lyshe_chysla(self):
        for d in self.soty.values():
            for f in d['soty']['features']:
                tekst = json.dumps(f['properties'].get('m', {}), ensure_ascii=False)
                self.assertRegex(tekst, r'^[\{\}\[\]\d,: "a-z]*$')


if __name__ == '__main__':
    unittest.main()
