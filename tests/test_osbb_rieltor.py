"""ZAVDANNYA-143: ОСББ і рієлтор — видавач передає генератору правильний режим.

Наскрізні перевірки сервера (оплата → кабінет → щомісячна довідка ОСББ → лист; рієлтор: «Мої об'єкти», 5 на місяць) —
site/worker/testy/osbb_rieltor.test.mjs (їх запускає tests/test_prodazh.py, test_node).
Запуск: python -m unittest tests.test_osbb_rieltor -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'site' / 'prodazh'))
import vydavach  # noqa: E402

GENERATOR = ('import sys, json\na = sys.argv[1:]\nv = a[a.index("--vyhid") + 1]\n'
             'open(v, "w", encoding="utf-8").write("<!doctype html>" + json.dumps(a, ensure_ascii=False))\n')


class Vydavach(unittest.TestCase):
    def prapory(self, rezhym):
        with tempfile.TemporaryDirectory() as t:
            g = Path(t) / 'zibraty.py'
            g.write_text(GENERATOR, encoding='utf-8')
            f = vydavach.zibraty(g, {'id': 'dabc', 'rezhym': rezhym, 'adresa': 'проспект Оболонський, 16'}, Path(t), shi=False)
            self.assertIsNotNone(f)
            return json.loads(f.read_text(encoding='utf-8')[len('<!doctype html>'):])

    def test_rezhymy(self):
        self.assertIn('--osbb', self.prapory('osbb'), 'щомісячна довідка ОСББ — генератор --osbb (dani-edrsr S-Зв.5)')
        self.assertNotIn('--povnyi', self.prapory('osbb'))
        self.assertEqual([x for x in self.prapory('dovidka') if x.startswith('--') and x != '--vyhid'], ['--dovidka', '--chysto'])
        self.assertIn('--povnyi', self.prapory('povnyi'))
        self.assertEqual(self.prapory('osbb')[0], 'проспект Оболонський, 16')


if __name__ == '__main__':
    unittest.main()
