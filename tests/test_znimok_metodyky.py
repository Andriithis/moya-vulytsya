"""Знімок методики бази (ZAVDANNYA-158): відтворюваний архів з git, перевірка хешу, що входить і що ні."""
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

KOREN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOREN / 'avtorstvo'))
import znimok_metodyky as Z  # noqa: E402

ENV = {**os.environ, 'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@t', 'GIT_COMMITTER_NAME': 't',
       'GIT_COMMITTER_EMAIL': 't@t', 'GIT_AUTHOR_DATE': '2026-11-20T10:00:00+02:00',
       'GIT_COMMITTER_DATE': '2026-11-20T10:00:00+02:00'}


def repo(d: Path, faily: dict) -> Path:
    d.mkdir()
    subprocess.run(['git', 'init', '-q', str(d)], check=True, env=ENV)
    zapysaty(d, faily)
    return d


def zapysaty(d: Path, faily: dict, povidomlennia='k') -> None:
    for shl, t in faily.items():
        (d / shl).parent.mkdir(parents=True, exist_ok=True)
        (d / shl).write_bytes(t if isinstance(t, bytes) else t.encode())
    subprocess.run(['git', '-C', str(d), 'add', '-A'], check=True, env=ENV)
    subprocess.run(['git', '-C', str(d), 'commit', '-q', '-m', povidomlennia], check=True, env=ENV)


class ZnimokTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.mv = repo(t / 'moya-vulytsya', {'AGENTS.md': 'правила', 'RISHENNYA.md': '## MV-1.', 'docs/METODYKA-BAZY.md': 'м',
                                             'docs/STYL.md': 'не методика', 'site/a.py': 'x'})
        self.dani = repo(t / 'dani-edrsr', {
            'SPECYFIKATSIYA.md': 'S-Д.1', 'RISHENNYA.md': 'р', 'config/misto-kyiv.json': '{}', 'src/a.py': 'print(1)',
            'src/zvit/shryfty/f.woff2': b'\0\1', 'src/zvit/leaflet/leaflet.js': 'lib', 'src/kartynka.png': b'\x89PNG',
            'perevirka/zamir.txt': 'замір', 'perevirka/etalon.jsonl': '{"tekst": "рішення"}', 'perevirka/x.csv': 'a',
            'ZVIT-1.md': 'звіт', 'data/velyke.db': 'дані'})
        self.vykhid = t / 'vykhid'

    def tearDown(self):
        self.tmp.cleanup()

    def znimok(self, *dod):
        self.assertEqual(Z.main(['--mv', str(self.mv), '--dani', str(self.dani), '--vykhid', str(self.vykhid),
                                 '--data', '2026-11-20', *dod]), 0)
        return self.vykhid / 'metodyka-2026-11-20.zip'

    def test_shcho_vkhodyt(self):
        with zipfile.ZipFile(self.znimok()) as z:
            imena = set(z.namelist())
        self.assertEqual(imena, {
            'MANIFEST.tsv', 'moya-vulytsya/AGENTS.md', 'moya-vulytsya/RISHENNYA.md', 'moya-vulytsya/docs/METODYKA-BAZY.md',
            'dani-edrsr/SPECYFIKATSIYA.md', 'dani-edrsr/RISHENNYA.md', 'dani-edrsr/config/misto-kyiv.json',
            'dani-edrsr/src/a.py', 'dani-edrsr/perevirka/zamir.txt'})

    def test_vidtvoriuvanyi_i_perevirka(self):
        b1 = self.znimok().read_bytes()
        # робоча тека не впливає: знімок береться з git
        (self.dani / 'SPECYFIKATSIYA.md').write_text('незакомічене')
        b2 = self.znimok().read_bytes()
        self.assertEqual(b1, b2)
        sha = self.vykhid / 'metodyka-2026-11-20.sha256'
        self.assertEqual(sha.read_text().split()[0], Z.sha(b1))
        self.assertEqual(Z.main(['--mv', str(self.mv), '--dani', str(self.dani), '--pereviryty', str(sha)]), 0)
        # нове правило — інший хеш; старий знімок і далі перевіряється з його комітів
        zapysaty(self.dani, {'SPECYFIKATSIYA.md': 'S-Д.1 і S-Д.2'})
        self.assertEqual(Z.main(['--mv', str(self.mv), '--dani', str(self.dani), '--pereviryty', str(sha)]), 0)
        stara = self.vykhid / 'stara'
        stara.mkdir()
        for f in self.vykhid.glob('metodyka-*'):
            (stara / f.name).write_bytes(f.read_bytes())
        b3 = self.znimok().read_bytes()
        self.assertNotEqual(b1, b3)
        # підмінений архів — не збігається
        (stara / 'metodyka-2026-11-20.zip').write_bytes(b3)
        self.assertEqual(Z.main(['--mv', str(self.mv), '--dani', str(self.dani),
                                 '--pereviryty', str(stara / 'metodyka-2026-11-20.sha256')]), 1)

    def test_manifest(self):
        self.znimok()
        t = (self.vykhid / 'metodyka-2026-11-20.MANIFEST.tsv').read_text(encoding='utf-8')
        self.assertIn('# komit\tdani-edrsr\t', t)
        self.assertIn('2026-11-20T10:00:00+02:00', t)
        self.assertNotIn('2026-11-20\t', t.replace('T10', ''))  # дати знімка в описі немає — лише дати комітів
        self.assertIn('dani-edrsr\tsrc/a.py\t' + Z.sha(b'print(1)') + '\t8', t)

    def test_zhurnal(self):
        zh = self.vykhid.parent / 'zhurnal.tsv'
        stary = Z.ZHURNAL
        Z.ZHURNAL = zh
        try:
            self.znimok('--zhurnal')
        finally:
            Z.ZHURNAL = stary
        ryadky = zh.read_text(encoding='utf-8').splitlines()
        self.assertEqual(ryadky[0].split('\t'), Z.ZHURNAL_POLIA)
        self.assertEqual(ryadky[1].split('\t')[:2], ['2026-11-20', 'metodyka-2026-11-20.zip'])

    def test_spravzhnii_zhurnal_formatu(self):
        zh = KOREN / 'avtorstvo' / 'zhurnal.tsv'
        ryadky = zh.read_text(encoding='utf-8').splitlines()
        self.assertEqual(ryadky[0].split('\t'), Z.ZHURNAL_POLIA)
        for r in ryadky[1:]:
            self.assertEqual(len(r.split('\t')), len(Z.ZHURNAL_POLIA), r)


if __name__ == '__main__':
    unittest.main()
