"""Безпека сервера продажу (ZAVDANNYA-156): налаштування Workers, що їх пише site/khostynh.py.

Самі перевірки зловмисником — у site/worker/testy/bezpeka.test.mjs (запускає tests/test_prodazh.py).
Запуск: python -m unittest tests.test_bezpeka_prodazhu -v
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site'))

import khostynh as KH  # noqa: E402


def konfig(**kw) -> dict:
    with tempfile.TemporaryDirectory() as t:
        vykhid = Path(t) / 'sait'
        vykhid.mkdir()
        teka = KH.pidhotuvaty_worker(vykhid, 1, **kw)
        return json.loads((teka / 'wrangler.jsonc').read_text(encoding='utf-8').split('\n', 1)[1])


class TestNalashtuvannia(unittest.TestCase):
    def test_limit_zapytiv_z_prodazhem(self):
        for oplata in ('tak', 'skoro'):
            k = konfig(prodazh={'d1': 'd1-id', 'servis': 'liqpay', 'adresa': 'https://mv.test'}, oplata=oplata)
            self.assertEqual(k['ratelimits'], [{'name': 'OBMEZHENNIA', 'namespace_id': '1561', 'simple': KH.OBMEZHENNIA}], oplata)
            self.assertIn(KH.OBMEZHENNIA['period'], (10, 60), 'Cloudflare приймає лише 10 або 60 с')

    def test_bez_prodazhu_bez_limitu(self):
        self.assertNotIn('ratelimits', konfig())

    def test_testova_oplata_lyshe_z_testovym_servisom(self):
        self.assertNotIn('TESTOVA_OPLATA', konfig(prodazh={'d1': 'x', 'servis': 'liqpay', 'adresa': 'https://mv.test'})['vars'])

    def test_kliuchi_ne_u_failakh(self):
        k = konfig(prodazh={'d1': 'x', 'servis': 'liqpay', 'adresa': 'https://mv.test'})
        self.assertNotRegex(json.dumps(k['vars']), r'(?i)private|token|secret|kliuch|sekret')

    def test_obmezheni_marshruty_ne_chipaiut_oplatu(self):
        """Сповіщення платіжного сервісу й видавача — ніколи не під лімітом (index.js, OBMEZHENI)."""
        js = (KORIN / 'site' / 'worker' / 'prodazh' / 'index.js').read_text(encoding='utf-8')
        blok = re.search(r'const OBMEZHENI = \[(.*?)\];', js, re.S).group(1)
        self.assertNotIn('spovishchennia', blok)
        self.assertNotIn('vnutr', blok)


if __name__ == '__main__':
    unittest.main()
