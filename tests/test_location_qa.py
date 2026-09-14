from pathlib import Path
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

    def test_cached_development_sample_has_no_false_public_locations(self):
        root = Path(__file__).resolve().parents[1]
        result = evaluate(root, root / 'data/fixtures/location_qa.json')
        self.assertEqual(result['false_positive'], 0)
        self.assertGreater(result['true_positive'], 0)
        self.assertFalse(result['production_precision_established'])
