"""Синтетичні адреси та полігони; не вимірюють якість на реальному Києві."""
import sqlite3
from contextlib import closing
import unittest
from unittest.mock import patch
from src.geocode_quality import Boundary, Resolver, street_key, house_key, eligible_geo_ids


def boundary():
    return Boundary({'type': 'Feature', 'properties': {
        'name': 'Київ', 'boundary': 'administrative', 'admin_level': '4',
        'source_url': 'https://example.invalid/synthetic', 'reviewed_at': '2026-09-14'},
        'geometry': {'type': 'Polygon', 'coordinates': [
            [[30.4, 50.4], [30.6, 50.4], [30.6, 50.6], [30.4, 50.6], [30.4, 50.4]],
            [[30.55, 50.55], [30.58, 50.55], [30.58, 50.58], [30.55, 50.58], [30.55, 50.55]],
        ]}})


class GeocodeQualityTests(unittest.TestCase):
    def test_normalization_preserves_type_initials_and_house_parts(self):
        self.assertEqual(street_key('вул.  Тестова'), street_key('Тестова вулиця'))
        self.assertEqual(street_key('вулиці Об’єднання'), street_key("вул. Об'єднання"))
        self.assertNotEqual(street_key('вул. Тестова'), street_key('пров. Тестова'))
        self.assertNotEqual(street_key('вул. І. Тестова'), street_key('вул. Тестова'))
        self.assertEqual(house_key('13 б'), '13Б')
        self.assertEqual(house_key('2 / 32'), '2/32')
        self.assertEqual(house_key('16 корпус 2'), '')
        self.assertEqual(street_key('Тестова'), '')

    def test_boundary_rejects_outside_holes_edges_and_invalid_numbers(self):
        b = boundary()
        self.assertTrue(b.contains(50.45, 30.52))
        for lat, lon in [(50.7, 30.52), (50.56, 30.56), (50.4, 30.5), (float('nan'), 30.5)]:
            self.assertFalse(b.contains(lat, lon))

    def test_invalid_boundary_fails_closed(self):
        props = {'name': 'Київ', 'boundary': 'administrative', 'admin_level': '4',
                 'source_url': 'https://example.invalid/synthetic', 'reviewed_at': '2026-09-14'}
        for ring in [[], [[30.4, 50.4], [30.6, 50.4], [30.6, 50.6]],
                     [[30.4, 50.4], [30.6, 50.6], [30.4, 50.6], [30.6, 50.4], [30.4, 50.4]]]:
            with self.assertRaises(ValueError):
                Boundary({'type': 'Feature', 'properties': props,
                          'geometry': {'type': 'Polygon', 'coordinates': [ring]}})

    def test_only_unique_exact_house_is_eligible(self):
        r = Resolver([['вул. Тестова', '16', 50.45, 30.52]], boundary())
        self.assertEqual(r.resolve('Тестова вулиця', '16'), [50.45, 30.52, 'house', 1.0])
        for st, h in [('вул. Тестова', None), ('вул. Тестова', '17'), ('вул. І. Тестова', '16'),
                      ('пров. Тестова', '16'), ('вул. Тестова', '16А')]:
            self.assertIsNone(r.resolve(st, h))
        for rows in [
            [['вул. Тестова', '16', 50.7, 30.52]],
            [['вул. Тестова', '16', 50.45, 30.52], ['вул. Тестова', '16', 50.46, 30.52]],
        ]:
            self.assertIsNone(Resolver(rows, boundary()).resolve('вул. Тестова', '16'))

    def test_reviewed_rename_and_conflicting_aliases(self):
        alias = {'old': 'вул. Стара', 'new': 'вул. Нова',
                 'source_url': 'https://example.invalid/decision', 'reviewed_at': '2026-09-14'}
        r = Resolver([['вул. Нова', '16', 50.45, 30.52]], boundary(), [alias])
        self.assertIsNotNone(r.resolve('вул. Стара', '16'))
        with self.assertRaises(ValueError):
            Resolver([], boundary(), [dict(alias, source_url='')])
        with self.assertRaises(ValueError):
            Resolver([], boundary(), [alias, dict(alias, new='вул. Інша')])
        with self.assertRaises(ValueError):
            Resolver([], boundary(), [alias, dict(alias, old='вул. Нова', new='вул. Стара')])

    def test_cache_reuses_hits_and_misses_but_invalidates_new_reference(self):
        with closing(sqlite3.connect(':memory:')) as conn:
            r = Resolver([['вул. Тестова', '16', 50.45, 30.52]], boundary())
            for house in ['16', '17']:
                expected = r.cached(conn, 'вул. Тестова', house)
                with patch.object(r, 'resolve', side_effect=AssertionError('повторне зіставлення')):
                    self.assertEqual(r.cached(conn, 'вулиця Тестова', house), expected)
            changed = Resolver([['вул. Тестова', '16', 50.7, 30.52]], boundary())
            self.assertIsNone(changed.cached(conn, 'вул. Тестова', '16'))

    def test_legacy_geo_never_passes_publication_gate(self):
        with closing(sqlite3.connect(':memory:')) as conn:
            conn.execute('CREATE TABLE geo(doc_id TEXT,lat REAL,lon REAL,precision TEXT)')
            conn.execute("INSERT INTO geo VALUES('1',50.45,30.52,'house')")
            self.assertEqual(eligible_geo_ids(conn), set())
