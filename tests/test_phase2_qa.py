"""Перевірки сліпого відбору без реальних текстів рішень."""
import unittest
import csv
import io
import json
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
from pipeline.phase2_qa import select_sample, prepare
from pipeline.edrsr_snapshot import EXPECTED_COLUMNS


class Phase2QaTests(unittest.TestCase):
    def test_sample_is_deterministic_active_kyiv_and_excludes_development(self):
        rows = [SimpleNamespace(doc_id=str(i), court_code='2601', status=1, cause_num=str(i))
                for i in range(20)]
        rows += [SimpleNamespace(doc_id='inactive', court_code='2601', status=0, cause_num='x'),
                 SimpleNamespace(doc_id='outside', court_code='9999', status=1, cause_num='y')]
        a = select_sample(rows, 10, 'seed', {'0', '1'})
        b = select_sample(reversed(rows), 10, 'seed', {'0', '1'})
        self.assertEqual([r.doc_id for r in a], [r.doc_id for r in b])
        self.assertEqual(len(a), 10)
        self.assertTrue(all(r.doc_id not in {'0', '1', 'inactive', 'outside'} for r in a))
        with self.assertRaises(ValueError):
            select_sample(rows, 0, 'seed')

    def test_public_output_and_nonofficial_dataset_are_rejected_before_reading(self):
        with self.assertRaises(ValueError):
            prepare('missing.zip', 'https://data.gov.ua/dataset/test', '.', 'data/fixtures/qa')
        with self.assertRaises(ValueError):
            prepare('missing.zip', 'https://example.invalid/dataset/test', '.', 'private/qa')

    def test_prepare_blind_packet_missing_texts_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tsv = io.StringIO()
            writer = csv.writer(tsv, delimiter='\t')
            writer.writerow(EXPECTED_COLUMNS)
            for doc in ['123', '124']:
                writer.writerow([doc, '2601', '1', '2', 'test', f'synthetic-{doc}',
                                 '2026-09-01', '2026-09-01', '',
                                 'https://example.invalid/synthetic', '1', '2026-09-01'])
            archive = root / 'synthetic.zip'
            with zipfile.ZipFile(archive, 'w') as zf:
                zf.writestr('documents.csv', tsv.getvalue())
            (root / '123.txt').write_text('Синтетичний текст.', encoding='utf-8')
            output = root / 'private/qa'
            with patch('pipeline.phase2_qa.PRIVATE', root / 'private'):
                summary = prepare(archive, 'https://data.gov.ua/dataset/synthetic', root, output)
                self.assertEqual((summary['selected'], summary['texts_missing']), (2, 1))
                review = [json.loads(line) for line in (output / 'review.jsonl').read_text(encoding='utf-8').splitlines()]
                self.assertTrue(all(row['expected_event_location'] is None for row in review))
                self.assertFalse(summary['backfill_executed'])
                with self.assertRaises(FileExistsError):
                    prepare(archive, 'https://data.gov.ua/dataset/synthetic', root, output)
