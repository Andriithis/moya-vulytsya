import json
import sqlite3
import unittest
from unittest.mock import patch

from src import addr, location_evidence as evidence
from src import step2_geocode as geocode
from pipeline.postgres_events import LegacyEventRow, _upsert_one


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.execute('''CREATE TABLE events(doc_id TEXT PRIMARY KEY,
            street TEXT,house TEXT,level TEXT,err TEXT)''')
        self.conn.execute('CREATE TABLE geo(doc_id TEXT PRIMARY KEY,lat REAL,lon REAL,precision TEXT)')
        evidence.init_evidence(self.conn)

    def store(self, text, doc='123456789'):
        result = addr.extract(text)
        self.conn.execute('INSERT OR REPLACE INTO events VALUES(?,?,?,?,NULL)',
                          (doc, result['street'], result['house'], result['level']))
        evidence.save_evidence(self.conn, doc, result['candidates'])
        return result

    def test_text_to_persisted_gate(self):
        self.store('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
        self.assertEqual(evidence.confirmed_rows(self.conn), [('123456789', 'вул. Лугова', '16')])

    def test_legacy_addresses_and_stale_coordinates_are_not_evidence(self):
        self.conn.execute("INSERT INTO events VALUES('123','вул. Лугова','16','house',NULL)")
        self.conn.execute("INSERT INTO geo VALUES('123',50.45,30.52,'house')")
        self.assertEqual(evidence.confirmed_rows(self.conn), [])

    def test_new_extraction_invalidates_old_coordinate(self):
        self.conn.execute("INSERT INTO geo VALUES('123456789',50.45,30.52,'house')")
        self.store('ВСТАНОВИВ: суд за адресою вул. Лугова, 16.')
        self.assertEqual(self.conn.execute('SELECT * FROM geo').fetchall(), [])
        self.assertEqual(evidence.confirmed_rows(self.conn), [])

    def test_mismatched_address_or_error_fails_closed(self):
        for column, value in [('street', 'вул. Лісова'), ('house', '18'), ('err', 'failed')]:
            with self.subTest(column=column):
                self.store('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
                self.conn.execute(f'UPDATE events SET {column}=?', (value,))
                self.assertEqual(evidence.confirmed_rows(self.conn), [])

    def test_stale_corrupt_or_forged_evidence_fails_closed(self):
        for payload in ('null', '{}', '[1]', 'invalid', '[{"role":"EVENT_LOCATION"}]'):
            with self.subTest(payload=payload):
                self.store('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
                self.conn.execute('UPDATE address_evidence SET candidates=?', (payload,))
                self.assertEqual(evidence.confirmed_rows(self.conn), [])
        result = self.store('ВСТАНОВИВ: суд за адресою вул. Лугова, 16.')
        result['candidates'][0]['role'] = 'EVENT_LOCATION'
        evidence.save_evidence(self.conn, '123456789', result['candidates'])
        self.assertEqual(evidence.load_candidates(self.conn, '123456789'), [])
        self.store('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
        self.conn.execute("UPDATE address_evidence SET version='old'")
        self.assertEqual(evidence.confirmed_rows(self.conn), [])

    def test_empty_gate_stops_before_network(self):
        with patch.object(geocode.os.path, 'exists', return_value=True), \
                patch.object(geocode.sqlite3, 'connect', return_value=self.conn), \
                patch.object(geocode, 'fetch') as fetch:
            with self.assertRaisesRegex(RuntimeError, 'Немає підтверджених'):
                geocode.main()
            fetch.assert_not_called()

    def test_geocoder_uses_only_confirmed_rows(self):
        self.store('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
        self.conn.execute("INSERT INTO events VALUES('old','вул. Лугова','16','house',NULL)")
        self.conn.execute("INSERT INTO geo VALUES('old',50.45,30.52,'house')")
        with patch.object(geocode.os.path, 'exists', return_value=True), \
                patch.object(geocode.sqlite3, 'connect', return_value=self.conn), \
                patch.object(geocode, 'fetch', return_value=[['Лугова', '16', 50.45, 30.52]]):
            geocode.main()
        self.assertEqual(self.conn.execute('SELECT doc_id FROM geo').fetchall(), [('123456789',)])


class RecordingCursor:
    def __init__(self, status=1):
        self.calls = []
        self.results = iter([(1, status), (2,)] + [(3,)] * 20)

    def execute(self, sql, params):
        self.calls.append((sql, params))

    def fetchone(self):
        return next(self.results)


class PostgresLocationGateTests(unittest.TestCase):
    def row(self, text=None, error=None):
        result = addr.extract(text) if text else {'street': 'вул. Лугова', 'house': '16', 'level': 'house'}
        return LegacyEventRow('123456789', 'ГП', result['street'], result['house'],
                              result['level'], None, error,
                              tuple(addr.extract_candidates(text)) if text else ())

    def roles(self, cur):
        return [params[2] for sql, params in cur.calls if 'INSERT INTO event_location' in sql]

    def test_legacy_address_is_unknown(self):
        cur = RecordingCursor()
        _upsert_one(cur, self.row())
        self.assertEqual(self.roles(cur), ['UNKNOWN'])
        self.assertTrue(any('is_public = FALSE' in sql for sql, _ in cur.calls))

    def test_all_roles_are_synced_with_context(self):
        cur = RecordingCursor()
        _upsert_one(cur, self.row('Суд за адресою вул. Судова, 10.\nВСТАНОВИВ: '
                                 'мешкає за адресою вул. Домашня, 12; '
                                 'водій керував по вул. Лугова, 16.'))
        self.assertEqual(self.roles(cur), ['COURT', 'RESIDENCE', 'EVENT_LOCATION'])
        for sql, params in cur.calls:
            if 'INSERT INTO event_location' in sql:
                saved = json.loads(params[3].split(':', 1)[1])
                self.assertIn('context', saved[0])

    def test_error_does_not_restore_old_address(self):
        cur = RecordingCursor()
        _upsert_one(cur, self.row(error='download_failed'))
        self.assertEqual(self.roles(cur), [])
        self.assertTrue(any('DELETE FROM event_location' in sql for sql, _ in cur.calls))

    def test_ambiguous_events_are_only_candidates(self):
        cur = RecordingCursor()
        _upsert_one(cur, self.row('Водій керував по вул. Лугова, 16; водій керував по вул. Лісова, 10.'))
        self.assertEqual(self.roles(cur), ['UNKNOWN', 'UNKNOWN'])

    def test_inactive_status_has_no_event(self):
        for status in (0,):
            cur = RecordingCursor(status)
            _upsert_one(cur, self.row())
            self.assertEqual(self.roles(cur), [])
            self.assertTrue(any('DELETE FROM event WHERE' in sql for sql, _ in cur.calls))


if __name__ == '__main__':
    unittest.main()
