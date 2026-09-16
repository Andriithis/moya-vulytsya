"""Мережа в тестах замінена синтетичними офіційними ресурсами."""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from pipeline.phase2_backfill import allowed_url, fetch_text, OfficialRedirects, run
from pipeline.phase2_qa import hydrate_review
from src.geocode_quality import Resolver
from test_geocode_quality import boundary


class BackfillTests(unittest.TestCase):
    def test_only_official_dump_text_urls_and_redirects(self):
        good = 'https://od.reyestr.court.gov.ua/files/68/' + 'a' * 32 + '.rtf'
        self.assertTrue(allowed_url(good))
        for url in ['https://reyestr.court.gov.ua/Review/123',
                    good.replace('https:', 'http:'), good + '?x=1',
                    good.replace('od.reyestr.court.gov.ua', 'example.invalid')]:
            self.assertFalse(allowed_url(url))
            with self.assertRaises(ValueError):
                fetch_text(url)
            with self.assertRaises(ValueError):
                OfficialRedirects().redirect_request(None, None, 302, '', {}, url)

    def test_repeat_and_changed_source_failure_do_not_reuse_stale_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet = root / 'private/qa'
            packet.mkdir(parents=True)
            plan = [{'doc_id': '123', 'source_row_hash': 'a'*64,
                     'justice_kind': '2', 'judgment_code': '1',
                     'source_url': 'https://od.reyestr.court.gov.ua/files/68/' + 'a'*32 + '.rtf'}]
            path = packet / 'backfill_plan.json'
            path.write_text(json.dumps(plan), encoding='utf-8')
            resolver = Resolver([['вул. Тестова', '16', 50.45, 30.52]], boundary())
            with patch('pipeline.phase2_backfill.PRIVATE', root / 'private'), \
                    patch('pipeline.phase2_backfill.load_resolver', return_value=resolver), \
                    patch('pipeline.phase2_backfill.time.sleep'), \
                    patch('pipeline.phase2_backfill.fetch_text', return_value=(b'{\\rtf synthetic}',
                          'ВСТАНОВИВ:\r\nводій керував по вул. Тестова, 16.\r\n')) as fetch:
                first = run(packet, download=True)
                second = run(packet)
                self.assertEqual(first['geocoded'], 1)
                self.assertEqual(second['stored_outcomes'], 1)
                self.assertEqual(second['reused'], 1)
                self.assertEqual(fetch.call_count, 1)
                (packet / 'review.jsonl').write_text(json.dumps(plan[0])+'\n', encoding='utf-8')
                with patch('pipeline.phase2_qa.PRIVATE', root / 'private'):
                    self.assertEqual(hydrate_review(packet)['ready_for_human_review'], 1)
                    ready = json.loads((packet / 'review-ready.jsonl').read_text(encoding='utf-8'))
                    self.assertIn('\r\n', ready['text'])
                    self.assertNotIn('geocode', ready)
                    with self.assertRaises(FileExistsError):
                        hydrate_review(packet)
                plan[0]['source_row_hash'] = 'b'*64
                path.write_text(json.dumps(plan), encoding='utf-8')
                failed = run(packet)
                self.assertEqual(failed['errors'], 1)
                conn = sqlite3.connect(packet / 'withheld/backfill.sqlite')
                try:
                    self.assertEqual(conn.execute('SELECT count(*) FROM address_evidence').fetchone(), (0,))
                finally:
                    conn.close()

    def test_wrong_or_missing_scope_rejected_before_network_or_database(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            packet = root / 'qa'
            packet.mkdir()
            with patch('pipeline.phase2_backfill.PRIVATE', root), \
                    patch('pipeline.phase2_backfill.fetch_text') as fetch, \
                    patch('pipeline.phase2_backfill.load_resolver') as resolver:
                for item in ({}, {'justice_kind': '2', 'judgment_code': '5'},
                             {'justice_kind': '5', 'judgment_code': '2'},
                             {'justice_kind': '1', 'judgment_code': '1'}):
                    (packet/'backfill_plan.json').write_text(json.dumps([item]))
                    with self.assertRaisesRegex(ValueError, 'кримінальні вироки'):
                        run(packet, download=True)
                fetch.assert_not_called()
                resolver.assert_not_called()
                self.assertFalse((packet/'withheld').exists())
