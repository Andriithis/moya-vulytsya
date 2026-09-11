"""Штучні регресійні приклади; це не ручний QA реальних рішень."""
import unittest
from src import addr


class LocationRoleTests(unittest.TestCase):
    def test_explicit_event(self):
        result = addr.extract('ВСТАНОВИВ: о 22:30 водій керував автомобілем по вул. Лугова, 16.')
        self.assertEqual((result['street'], result['house']), ('вул. Лугова', '16'))
        self.assertEqual(result['time'], '22:30')

    def test_negative_roles_with_event_word_do_not_become_event(self):
        cases = {
            'COURT': 'Суд розташований за адресою',
            'RESIDENCE': 'Особа проживає за адресою',
            'WORKPLACE': 'Особа працює за адресою',
            'PROPERTY': 'Обʼєкт належить особі за адресою',
            'INSTITUTION': 'Відділ поліції розташований за адресою',
        }
        for role, prefix in cases.items():
            with self.subTest(role=role):
                text = f'ВСТАНОВИВ: {prefix} вул. Лугова, 16, а раніше вчинив крадіжку.'
                cs = addr.extract_candidates(text)
                self.assertEqual(cs[0].role, role)
                self.assertIsNone(addr.extract(text)['street'])

    def test_all_occurrences_have_exact_source_offsets(self):
        text = ('Суд за адресою вул. Судова, 10.\nВСТАНОВИВ:\n'
                'Особа мешкає за адресою вул. Домашня, 12; '
                'водій керував автомобілем по вул. Лугова, 16.')
        cs = addr.extract_candidates(text)
        self.assertEqual([c.role for c in cs], ['COURT', 'RESIDENCE', 'EVENT_LOCATION'])
        for c in cs:
            self.assertEqual(text[c.start:c.end], c.raw)
            self.assertEqual(text[c.context_start:c.context_start+len(c.context)], c.context)
        self.assertEqual(addr.extract(text)['street'], 'вул. Лугова')

    def test_no_header_fallback_when_body_has_no_address(self):
        text = 'Водій керував по вул. Лугова, 16.\nВСТАНОВИВ: місце не встановлено.'
        self.assertIsNone(addr.extract(text)['street'])

    def test_clean_mention_is_not_event_evidence(self):
        self.assertIsNone(addr.extract('ВСТАНОВИВ: за адресою вул. Лугова, 16.')['street'])

    def test_procedural_and_negated_contexts(self):
        for text in (
            'Особа не керувала автомобілем по вул. Лугова, 16.',
            'Особа не вчинила крадіжку за адресою вул. Лугова, 16.',
            'Клопотання про обшук за адресою вул. Лугова, 16, де особа вчинила крадіжку.',
            'Можливо, особа вчинила крадіжку за адресою вул. Лугова, 16.',
            'Особа вчинила крадіжку, її доставили за адресою вул. Лугова, 16.',
            'Особа вчинила крадіжку, потім зустріла знайомого біля вул. Лугова, 16.',
            'Особа вчинила крадіжку і була затримана біля вул. Лугова, 16.',
        ):
            with self.subTest(text=text):
                self.assertIsNone(addr.extract('ВСТАНОВИВ: ' + text)['street'])

    def test_multiple_addresses_are_not_assigned_nearby_event_word(self):
        text = ('ВСТАНОВИВ: водій керував по вул. Лугова, 16, '
                'особу виявлено за адресою вул. Лісова, 10.')
        self.assertEqual(len(addr.extract_candidates(text)), 2)
        self.assertIsNone(addr.extract(text)['street'])

    def test_multiple_events_do_not_pick_first(self):
        text = ('ВСТАНОВИВ: водій керував по вул. Лугова, 16; '
                'водій керував по вул. Лісова, 10.')
        self.assertIsNone(addr.extract(text)['street'])

    def test_conflicting_roles_at_same_address(self):
        text = ('ВСТАНОВИВ: мешкає за адресою вул. Лугова, 16; '
                'водій керував по вул. Лугова, 16.')
        self.assertIsNone(addr.extract(text)['street'])

    def test_street_name_is_not_institution_keyword(self):
        self.assertEqual(addr.extract('ВСТАНОВИВ: водій керував по вул. Судова, 16.')['street'],
                         'вул. Судова')

    def test_street_only_keeps_multiword_name(self):
        result = addr.extract('ВСТАНОВИВ: водій керував по вул. Героїв Дніпра.')
        self.assertEqual((result['street'], result['house'], result['level']),
                         ('вул. Героїв Дніпра', None, 'street'))

    def test_street_only_does_not_rescue_rejected_house(self):
        self.assertIsNone(addr.extract('ВСТАНОВИВ: суд за адресою вул. Героїв Дніпра, 16.')['street'])

    def test_repeated_mentions_preserved(self):
        text = 'Водій керував по вул. Лугова, 16; водій керував по вул. Лугова, 16.'
        self.assertEqual(len(addr.extract_candidates(text)), 2)
        self.assertEqual(addr.extract(text)['house'], '16')


if __name__ == '__main__':
    unittest.main()
