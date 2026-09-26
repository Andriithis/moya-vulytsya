"""Структурна перевірка джерел; не незалежна оцінка точності координат."""
import json
import unittest
from pathlib import Path
from pipeline.osm_boundary import join_rings
from src.geocode_quality import Boundary, Resolver, REFERENCE


class ReferenceDataTests(unittest.TestCase):
    def test_join_reversed_segments_preserves_separate_rings(self):
        self.assertEqual(join_rings([[1, 2], [3, 2], [3, 1], [4, 5, 6, 4]]),
                         [[1, 2, 3, 1], [4, 5, 6, 4]])
        for segments in [[[1, 2], [2, 3]], [[1, 2], [2, 3], [2, 4], [3, 1]], [[1]]]:
            with self.assertRaises(ValueError):
                join_rings(segments)

    def test_kyiv_reference_and_known_ambiguous_names(self):
        feature = json.loads((REFERENCE / 'kyiv_boundary.geojson').read_text(encoding='utf-8'))
        aliases = json.loads((REFERENCE / 'street_aliases.json').read_text(encoding='utf-8'))
        boundary = Boundary(feature)
        self.assertEqual(feature['properties']['osm_relation_id'], 421866)
        self.assertEqual(len(feature['geometry']['coordinates']), 1)
        self.assertEqual(len(feature['geometry']['coordinates'][0]), 3)
        self.assertFalse(feature['properties']['independent_human_review'])
        self.assertTrue(boundary.contains(50.45, 30.52))
        self.assertFalse(boundary.contains(50.45, 31.0))
        r = Resolver([['вулиця Юрія Іллєнка', '3', 50.45, 30.52],
                      ['вулиця Червоноармійська', '1', 50.45, 30.52]],
                     boundary, aliases['aliases'], aliases['blocked'])
        self.assertEqual(r.key('вул. Мельникова', '3'), r.key('вул. Юрія Іллєнка', '3'))
        # Навіть один збіг у неповній OSM-базі не знімає відому неоднозначність.
        self.assertIsNone(r.resolve('вул. Червоноармійська', '1'))
        self.assertEqual(r.key('вул. Горького', '1'), '')
        self.assertEqual(r.key('вул. Максима Горького', '1'), '')
