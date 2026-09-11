"""Реальна БД у CI; кожен тест використовує окрему тимчасову схему."""
import os
from pathlib import Path
import unittest
import uuid

from pipeline.postgres_events import LegacyEventRow, _upsert_one
from src import addr


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'Потрібен TEST_DATABASE_URL')
class PostgresIntegrationTests(unittest.TestCase):
    def setUp(self):
        import psycopg
        from psycopg import sql
        self.conn = psycopg.connect(os.environ['TEST_DATABASE_URL'], autocommit=True)
        self.addCleanup(self.conn.close)
        self.schema = 'test_locations_' + uuid.uuid4().hex
        self.conn.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(self.schema)))
        self.addCleanup(lambda: self.conn.execute(
            sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(self.schema))))
        self.conn.execute(sql.SQL('SET search_path TO {},public').format(sql.Identifier(self.schema)))
        self.conn.execute(Path('db/schema.sql').read_text(encoding='utf-8'))
        self.conn.execute("""INSERT INTO document(edrsr_id,source_status,source_row_hash)
                             VALUES ('123456789',1,'test')""")

    def row(self, text=None):
        result = addr.extract(text) if text else {'street': 'вул. Лугова', 'house': '16', 'level': 'house'}
        return LegacyEventRow('123456789', 'ГП', result['street'], result['house'], result['level'],
                              None, None, tuple(addr.extract_candidates(text)) if text else ())

    def sync(self, row):
        with self.conn.transaction(), self.conn.cursor() as cur:
            _upsert_one(cur, row)

    def roles(self):
        return self.conn.execute('SELECT role FROM event_location ORDER BY role').fetchall()

    def test_idempotency_and_reclassification_remove_stale_event_link(self):
        row = self.row('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
        self.sync(row)
        self.sync(row)
        self.assertEqual(self.roles(), [('EVENT_LOCATION',)])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM event').fetchone(), (1,))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM location').fetchone(), (1,))
        self.sync(self.row('ВСТАНОВИВ: суд за адресою вул. Лугова, 16.'))
        self.assertEqual(self.roles(), [('COURT',)])
        self.sync(self.row('ВСТАНОВИВ: місце невідоме.'))
        self.assertEqual(self.roles(), [])
        self.assertEqual(self.conn.execute('SELECT is_public,event_date FROM event').fetchone(),
                         (False, None))

    def test_legacy_and_inactive_source(self):
        self.sync(self.row())
        self.assertEqual(self.roles(), [('UNKNOWN',)])
        self.conn.execute('UPDATE document SET source_status=0')
        self.sync(self.row())
        self.assertEqual(self.roles(), [])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM event').fetchone(), (0,))

    def test_transaction_rollback_preserves_previous_links(self):
        self.sync(self.row())
        with self.assertRaises(RuntimeError):
            with self.conn.transaction(), self.conn.cursor() as cur:
                _upsert_one(cur, self.row('Водій керував по вул. Лугова, 16.'))
                raise RuntimeError('імітований збій до commit')
        self.assertEqual(self.roles(), [('UNKNOWN',)])


if __name__ == '__main__':
    unittest.main()
