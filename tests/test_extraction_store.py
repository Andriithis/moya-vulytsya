import unittest
from pipeline.extraction_store import validate_result
from src import addr


class ResultValidationTests(unittest.TestCase):
    def data(self):
        result = addr.extract('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
        return (['123', 'court', 'ГП', 'code', '2026-09-01', result['street'],
                 result['house'], result['level'], None, None], result['candidates'], 'a'*64, 'b'*64)

    def test_valid_result(self):
        validate_result(*self.data())

    def test_mismatched_selected_address_rejected(self):
        data = self.data()
        data[0][5] = 'вул. Інша'
        with self.assertRaises(ValueError):
            validate_result(*data)

    def test_invalid_source_hash_or_error_rejected(self):
        for index, value in ((2, ''), (3, 'bad')):
            data = list(self.data())
            data[index] = value
            with self.assertRaises(ValueError):
                validate_result(*data)
        data = self.data()
        data[0][9] = 'download_failed'
        with self.assertRaises(ValueError):
            validate_result(*data)

    def test_corrupt_candidates_are_not_empty_success(self):
        for item in (None, {}, [{'role': 'EVENT_LOCATION'}]):
            data = list(self.data())
            data[1] = item
            with self.assertRaises(ValueError):
                validate_result(*data)
