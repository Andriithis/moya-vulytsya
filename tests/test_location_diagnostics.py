"""Регресії з розробницького дослідження; усі тексти вигадані."""
import unittest
from src.addr import extract, extract_candidates


class DiagnosticRegressionTests(unittest.TestCase):
    def test_city_preposition_is_not_house_suffix(self):
        for suffix in ('в м. Києві', 'у місті Києві'):
            cs = extract_candidates('За адресою вул. Тестова, 42 '+suffix+'.')
            self.assertEqual(cs[0].house, '42')
            self.assertEqual(cs[0].raw, 'вул. Тестова, 42')
        for house in ('42В', '42 В', '42/2Б'):
            self.assertEqual(extract_candidates('вул. Тестова, '+house+'.')[0].house,
                             house.replace(' ', ''))

    def test_kilometre_marker_is_not_house(self):
        for unit in ('км', 'кілометр'):
            cs = extract_candidates('ОСОБА_1 керував по шосе Тестове, 17 '+unit+'.')
            self.assertFalse(any(c.house for c in cs))

    def test_driver_subject_and_forbidden_roles(self):
        text = 'ВСТАНОВИВ: За адресою вул. Тестова, 42 водій ОСОБА_1 керував автомобілем.'
        self.assertEqual(extract(text)['house'], '42')
        for phrase in ('суд', 'установа', 'проживає', 'працює', 'належить', 'не', 'нібито', 'обшук'):
            self.assertIsNone(extract(text[:-1]+' '+phrase+'.')['street'])
        self.assertIsNone(extract(text.replace('керував', 'заперечує, що керував'))['street'])
