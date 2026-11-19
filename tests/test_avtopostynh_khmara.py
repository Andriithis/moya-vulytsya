"""Автопостинг без сервера — обгортка для GitHub Actions і файл робочого процесу (ZAVDANNYA-131, MV-153)."""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

KORIN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KORIN / 'avtopostynh'))

import khmara as K  # noqa: E402
import zahlushka as Z  # noqa: E402

ROBOCHYI = KORIN / 'avtopostynh' / 'github' / 'avtopostynh.yml'
PN_18 = datetime(2026, 11, 23, 16, 20, tzinfo=timezone.utc)      # понеділок 18:20 за Києвом


def arg(**k):
    a = dict(id='', prychyna='', mistse=False, usi_merezhi=False, merezha='')
    a.update(k)
    return argparse.Namespace(**a)


class Obhortka(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.t = Path(self._t.name)
        Z.zrobyty(self.t / 'vkhid' / 'media')
        self.addCleanup(self._t.cleanup)

    def test_typovo_probnyi(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('MV_PROBNYI', None)
            self.assertTrue(K.probnyi())
            os.environ['MV_PROBNYI'] = '0'
            self.assertFalse(K.probnyi())
            os.environ['MV_PROBNYI'] = ''
            self.assertTrue(K.probnyi())

    def test_tiktok_ne_v_khmari(self):
        with mock.patch.dict(os.environ, {'MV_MEREZHI': 'telegram, youtube,tiktok'}):
            self.assertEqual(K.merezhi_dlia_khmary(), ('telegram,youtube', ['tiktok']))

    def test_kanaly_zi_zminnoi(self):
        with mock.patch.dict(os.environ, {'MV_KANALY_JSON': '{"Печерський": "@mv_pecherskyi"}'}):
            self.assertEqual(K.kanaly(None), {'Печерський': '@mv_pecherskyi'})

    def test_hodyna_perehliad_i_prybraty(self):
        pidsumok = self.t / 'summary.md'
        with mock.patch.dict(os.environ, {'MV_PROBNYI': '1', 'MV_MEREZHI': 'telegram,youtube,tiktok',
                                          'GITHUB_STEP_SUMMARY': str(pidsumok), 'MV_KANALY_JSON': ''}):
            zv = K.zapustyty(self.t / 'stan', self.t / 'vkhid', 'hodyna', arg(), PN_18)
            self.assertTrue(any('tiktok' in x for x in zv))
            self.assertTrue(any('indeks.json' in x for x in zv))
            self.assertTrue(any(x.startswith('youtube') and 'опубліковано' in x for x in zv))
            self.assertFalse(any(x.startswith('tiktok') and 'опубліковано' in x for x in zv))
            md = (self.t / 'stan' / K.PEREHLIAD).read_text(encoding='utf-8')
            self.assertIn('Пробний режим', md)
            self.assertIn('## YouTube', md)
            self.assertIn('Run workflow', md)
            self.assertIn(md.splitlines()[0], pidsumok.read_text(encoding='utf-8'))
            ids = re.findall(r'\| `([0-9a-f]+)` \| \S', md)        # опубліковане має посилання
            self.assertTrue(ids)
            zv = K.zapustyty(self.t / 'stan', self.t / 'vkhid', 'prybraty', arg(id=ids[0], prychyna='перевірка'), PN_18)
            self.assertTrue(any('видалено' in x for x in zv), zv)
            self.assertIn('прибрано', (self.t / 'stan' / K.PEREHLIAD).read_text(encoding='utf-8'))
            for f in K.ZBERIHATY:
                self.assertTrue((self.t / 'stan' / f).exists(), f)

    def test_prybraty_bez_prychyny(self):
        with self.assertRaises(SystemExit):
            K.zapustyty(self.t / 'stan', None, 'prybraty', arg(id='x'), PN_18)


class RobochyiProtses(unittest.TestCase):
    """Файл для GitHub Actions: пробний режим за замовчуванням, ключі лише з секретів, введення — не в тексті команд."""

    @classmethod
    def setUpClass(cls):
        cls.t = ROBOCHYI.read_text(encoding='utf-8')

    def test_rozklad_i_ruchnyi_zapusk(self):
        self.assertRegex(self.t, r"cron: '\d+ [\d,-]+ \* \* \*'")
        self.assertNotRegex(self.t, r"cron: '0 ")                  # не о :00 — GitHub найбільше затримує
        self.assertIn('workflow_dispatch:', self.t)
        for k in ('hodyna', 'prybraty', 'vidnovyty', 'zhurnal'):
            self.assertIn(k, self.t)

    def test_probnyi_typovo(self):
        self.assertIn("MV_PROBNYI: ${{ vars.MV_PROBNYI || '1' }}", self.t)

    def test_kliuchi_lyshe_z_sekretiv(self):
        for imia in ('MV_TELEGRAM_TOKEN', 'MV_YOUTUBE_REFRESH_TOKEN', 'MV_META_PAGE_TOKEN', 'MV_DANI_TOKEN'):
            self.assertIn(f'secrets.{imia}', self.t)
        self.assertNotIn('TIKTOK', self.t)
        self.assertNotRegex(self.t, r'\d{6,}:[A-Za-z0-9_-]{30,}')       # схоже на токен Telegram
        self.assertNotRegex(self.t, r'gh[pousr]_[A-Za-z0-9]{20,}')        # схоже на ключ GitHub

    def test_vvedennia_ne_v_komandakh(self):
        """Що людина вписала в поля запуску, не підставляється в текст команди (захист від підстановки коду)."""
        run = re.findall(r'run: \|\n((?:          .*\n|\n)+)', self.t)
        self.assertTrue(run)
        for blok in run:
            self.assertNotIn('${{', blok)

    def test_stan_i_konkurentnist(self):
        self.assertIn('avtopostynh-stan', self.t)
        self.assertIn('group: avtopostynh', self.t)
        self.assertIn('contents: write', self.t)
        self.assertIn('for f in ' + ' '.join(K.ZBERIHATY) + ';', self.t)
        self.assertIn('kod/avtopostynh/khmara.py', self.t)
        self.assertIn('repository: Andriithis/moya-vulytsya', self.t)


if __name__ == '__main__':
    unittest.main()
