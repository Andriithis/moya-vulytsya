"""Конвеєр голосу (ZAVDANNYA-148, MV-156): легка частина без torch — імена файлів, тексти для рушія, межі ліцензій."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'video' / 'holos'))
sys.path.insert(0, str(KORIN / 'video' / 'vau'))

import holos  # noqa: E402


class HolosTests(unittest.TestCase):
    def test_imia_vykhodu(self):
        self.assertEqual(holos.imia_vykhodu(Path('R01 Гачок.m4a')), 'r01-гачок.wav')
        self.assertEqual(holos.imia_vykhodu(Path('...ogg')), 'zapys.wav')

    def test_teksty_i_teka_rushiia(self):
        """Файл для MV_HOLOS=teka має те саме ім'я, яке шукає рушій роликів (holos_servis._teka)."""
        from holos_servis import tekst_dlia_servisu
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / 'teksty.tsv'
            f.write_text('# коментар\nr01.m4a\tЗа 3 роки — 42 справи.\n\nr02\tДругий рядок\n', encoding='utf-8')
            tt = holos.chytaty_teksty(f)
        self.assertEqual(tt, {'r01': 'За 3 роки — 42 справи.', 'r02': 'Другий рядок'})
        ochikuvane = hashlib.sha1(tekst_dlia_servisu(tt['r01']).encode()).hexdigest() + '.wav'
        self.assertEqual(holos.imia_teky(tt['r01']), ochikuvane)

    def test_teksty_bez_tabuliatsii(self):
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / 'teksty.tsv'
            f.write_text('r01 текст без табуляції\n', encoding='utf-8')
            with self.assertRaises(SystemExit):
                holos.chytaty_teksty(f)

    def test_zibraty_vkhid(self):
        with tempfile.TemporaryDirectory() as t:
            for n in ('b.ogg', 'a.m4a', 'notatka.txt'):
                (Path(t) / n).write_bytes(b'')
            self.assertEqual([f.name for f in holos.zibraty_vkhid([t])], ['a.m4a', 'b.ogg'])
            with self.assertRaises(SystemExit):
                holos.zibraty_vkhid([str(Path(t) / 'nemaie')])

    def test_dva_holosy(self):
        self.assertEqual(set(holos.HOLOSY), {'cholovichyi', 'zhinochyi'})
        self.assertEqual(holos.holosy_z_arg('oba'), ['cholovichyi', 'zhinochyi'])
        with self.assertRaises(SystemExit):
            holos.holosy_z_arg('dytiachyi')

    def test_lyshe_dozvoleni_rushii_i_dani(self):
        """Лише моделі з дозволом на комерційне використання (MIT) і закріпленою версією; без Seed-VC (некомерційні дані
        навчання), so-vits-svc (лише для навчання) і без готових «голосів» людей."""
        self.assertEqual(set(holos.RUSHII), {'knn', 'openvoice'})
        for r in holos.RUSHII.values():
            self.assertEqual(r['licenziia'], 'MIT')
            self.assertRegex(r['kod'][1], r'^[0-9a-f]{40}$')
        tekst = (KORIN / 'video' / 'holos' / 'holos.py').read_text(encoding='utf-8').lower()
        for zaboroneno in ('seed-vc', 'so-vits', 'rvc-models', 'weights.gg'):
            self.assertNotIn(zaboroneno + "'", tekst)
        self.assertEqual(holos.NABIR['licenziia'], 'CC BY 4.0')

    def test_dokumenty(self):
        d = KORIN / 'video' / 'holos'
        for f in ('README.md', 'DOSLIDZHENNYA.md', 'YAK-ZAPYSUVATY.md', 'vymohy.txt', 'otsinka.py'):
            self.assertTrue((d / f).is_file(), f)
        zapys = (d / 'YAK-ZAPYSUVATY.md').read_text(encoding='utf-8')
        for slovo in ('телефон', 'кімнат', 'см', 'один файл'):
            self.assertIn(slovo, zapys.lower())

    def test_otsinka_cer(self):
        import otsinka
        self.assertEqual(otsinka.cer('За 42 роки.', 'за сорок два роки'), 0.0)
        self.assertGreater(otsinka.cer('між сьомою', 'між сім'), 0.0)


if __name__ == '__main__':
    unittest.main()
