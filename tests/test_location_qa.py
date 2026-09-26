from pathlib import Path
import hashlib
import json
import tempfile
import unittest
from pipeline.location_qa import evaluate, summarize


class LocationQaTests(unittest.TestCase):
    def test_zero_predictions_do_not_claim_perfect_precision(self):
        result = summarize([(['вул. Лугова', '16'], None), (None, None)])
        self.assertIsNone(result['precision'])
        self.assertEqual(result['recall'], 0)

    def test_wrong_location_is_both_false_positive_and_miss(self):
        result = summarize([(['correct', '1'], ['wrong', '2'])])
        self.assertEqual((result['false_positive'], result['false_negative']), (1, 1))

    def test_evaluation_uses_verified_private_source(self):
        text = 'ВСТАНОВИВ: водій керував по вул. Тестова, 16.'
        url = 'https://od.reyestr.court.gov.ua/files/synthetic.rtf'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'excerpt.txt').write_text(
                f'\n--- тест · справа synthetic\n{url}\n\n    {text}\n', encoding='utf-8')
            manifest = root / 'manifest.json'
            manifest.write_text(json.dumps({'source_artifact': 'excerpt.txt', 'cases': [{
                'case_number': 'synthetic', 'source_url': url,
                'text_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'expected_location': ['вул. Тестова', '16'],
            }]}), encoding='utf-8')
            result = evaluate(root, manifest)
            (root / 'excerpt.txt').write_text(
                f'\n--- тест · справа synthetic\n{url}\n\n    {text} змінено\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                evaluate(root, manifest)
        self.assertEqual(result['false_positive'], 0)
        self.assertGreater(result['true_positive'], 0)
        self.assertFalse(result['production_precision_established'])
