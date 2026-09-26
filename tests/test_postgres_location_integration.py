"""Реальна БД у CI; кожен тест використовує окрему тимчасову схему."""
import os
from pathlib import Path
import unittest
import uuid
import sqlite3
from pipeline.extraction_store import persist_result, restore_from_cursor
from src import location_evidence as evidence

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
                             VALUES ('123456789',1,%s)""", ('a' * 64,))

    def row(self, text=None):
        result = addr.extract(text) if text else {'street': 'вул. Лугова', 'house': '16', 'level': 'house'}
        return LegacyEventRow(
            '123456789', 'ГП', result['street'], result['house'], result['level'],
            None, None, tuple(addr.extract_candidates(text)) if text else (),
            'a' * 64 if text else None,
        )

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

    def test_forbidden_roles_never_become_event_locations(self):
        for phrase in ['суд за адресою', 'лікарня за адресою', 'проживає за адресою',
                       'працює за адресою', 'належить квартира за адресою']:
            with self.subTest(phrase=phrase):
                self.sync(self.row(f'ВСТАНОВИВ: {phrase} вул. Лугова, 16. Водій керував автомобілем.'))
                self.assertNotIn(('EVENT_LOCATION',), self.roles())
                self.assertEqual(self.conn.execute('SELECT is_public FROM event').fetchone(), (False,))

    def test_transaction_rollback_preserves_previous_links(self):
        self.sync(self.row())
        with self.assertRaises(RuntimeError):
            with self.conn.transaction(), self.conn.cursor() as cur:
                _upsert_one(cur, self.row('Водій керував по вул. Лугова, 16.'))
                raise RuntimeError('імітований збій до commit')
        self.assertEqual(self.roles(), [('UNKNOWN',)])

    def test_changed_source_revokes_stale_event_location_during_sync(self):
        self.sync(self.row('ВСТАНОВИВ: водій керував по вул. Лугова, 16.'))
        self.assertEqual(self.roles(), [('EVENT_LOCATION',)])
        self.conn.execute(
            'UPDATE document SET source_row_hash=%s,needs_processing=TRUE',
            ('c' * 64,),
        )

        self.sync(self.row('ВСТАНОВИВ: водій керував по вул. Лугова, 16.'))

        self.assertEqual(self.roles(), [])
        self.assertEqual(self.conn.execute('SELECT is_public FROM event').fetchone(), (False,))

    def test_candidates_without_source_hash_fail_closed(self):
        row = self.row('ВСТАНОВИВ: водій керував по вул. Лугова, 16.')
        unsafe = LegacyEventRow(
            row.doc_id, row.category, row.street, row.house, row.level,
            row.event_time, row.error, row.candidates, None,
        )
        self.sync(unsafe)
        self.assertEqual(self.roles(), [])
        self.assertEqual(self.conn.execute('SELECT count(*) FROM event').fetchone(), (0,))

    def test_migration_0003_is_repeatable_on_existing_database(self):
        self.conn.execute('DROP TABLE document_extraction')
        migration = Path('db/migrations/0003_document_extraction.sql').read_text(encoding='utf-8')
        self.conn.execute(migration)
        self.conn.execute(migration)
        self.conn.execute(
            """INSERT INTO document_extraction
               (document_id,source_row_hash,extraction_version,text_sha256,record,candidates)
               VALUES ('123456789',%s,'test',%s,
                       '["123456789",null,null,null,null,null,null,"none",null,null]','[]')""",
            ('a' * 64, 'b' * 64),
        )
        self.assertEqual(
            self.conn.execute('SELECT count(*) FROM document_extraction').fetchone(),
            (1,),
        )

    def checkpoint_data(self, text='ВСТАНОВИВ: водій керував по вул. Лугова, 16.'):
        result = addr.extract(text)
        record = ['123456789', 'Shevchenkivskyi', 'ГП', '41235', '2026-09-01',
                  result['street'], result['house'], result['level'], result['time'], None]
        self.conn.execute("UPDATE document SET source_row_hash=%s,court_code='2610'", ('a'*64,))
        return record, result['candidates'], 'a'*64, 'b'*64

    def new_local(self):
        local = sqlite3.connect(':memory:')
        self.addCleanup(local.close)
        local.execute('''CREATE TABLE events(doc_id TEXT PRIMARY KEY,court TEXT,grp TEXT,
                         cat TEXT,date TEXT,street TEXT,house TEXT,level TEXT,tm TEXT,err TEXT)''')
        evidence.init_evidence(local)
        local.commit()
        return local

    def test_checkpoint_survives_fresh_local_database(self):
        data = self.checkpoint_data()
        with self.conn.transaction(), self.conn.cursor() as cur:
            self.assertTrue(persist_result(cur, *data))
            self.assertTrue(persist_result(cur, *data))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM document_extraction').fetchone(), (1,))
        self.assertEqual(self.conn.execute('SELECT needs_processing FROM document').fetchone(), (False,))
        local = self.new_local()
        with self.conn.cursor() as cur:
            self.assertEqual(restore_from_cursor(cur, local, ['2610']), 1)
        self.assertEqual(evidence.confirmed_rows(local), [('123456789', 'вул. Лугова', '16')])

    def test_checkpoint_and_queue_rollback_together(self):
        data = self.checkpoint_data()
        with self.assertRaises(RuntimeError):
            with self.conn.transaction(), self.conn.cursor() as cur:
                persist_result(cur, *data)
                raise RuntimeError('збій до commit')
        self.assertEqual(self.conn.execute('SELECT count(*) FROM document_extraction').fetchone(), (0,))
        self.assertEqual(self.conn.execute('SELECT needs_processing FROM document').fetchone(), (True,))

    def test_changed_source_cannot_be_acknowledged(self):
        data = self.checkpoint_data()
        self.conn.execute('UPDATE document SET source_row_hash=%s', ('c'*64,))
        with self.conn.transaction(), self.conn.cursor() as cur:
            self.assertFalse(persist_result(cur, *data))
        self.assertEqual(self.conn.execute('SELECT needs_processing FROM document').fetchone(), (True,))
        self.assertEqual(self.conn.execute('SELECT count(*) FROM document_extraction').fetchone(), (0,))

    def test_restore_revokes_changed_inactive_and_old_version(self):
        data = self.checkpoint_data()
        for mutation in ('UPDATE document SET source_status=0',
                         "UPDATE document SET source_row_hash=repeat('c',64)",
                         "UPDATE document_extraction SET extraction_version='old'"):
            with self.subTest(mutation=mutation):
                self.conn.execute('UPDATE document SET source_status=1,source_row_hash=%s', ('a'*64,))
                with self.conn.transaction(), self.conn.cursor() as cur:
                    persist_result(cur, *data)
                local = self.new_local()
                with self.conn.cursor() as cur:
                    restore_from_cursor(cur, local, ['2610'])
                self.conn.execute(mutation)
                with self.conn.cursor() as cur:
                    self.assertEqual(restore_from_cursor(cur, local, ['2610']), 0)
                self.assertEqual(evidence.confirmed_rows(local), [])

    def test_empty_extraction_is_durable_and_not_public(self):
        data = self.checkpoint_data('ВСТАНОВИВ: адреса невідома.')
        with self.conn.transaction(), self.conn.cursor() as cur:
            persist_result(cur, *data)
        local = self.new_local()
        with self.conn.cursor() as cur:
            self.assertEqual(restore_from_cursor(cur, local, ['2610']), 1)
        self.assertEqual(evidence.confirmed_rows(local), [])

    def test_mismatched_checkpoint_document_fails_atomically(self):
        data = self.checkpoint_data()
        with self.conn.transaction(), self.conn.cursor() as cur:
            persist_result(cur, *data)
        self.conn.execute("UPDATE document_extraction SET record=jsonb_set(record,'{0}','\"999\"')")
        local = self.new_local()
        with self.conn.cursor() as cur, self.assertRaises(ValueError):
            restore_from_cursor(cur, local, ['2610'])
        self.assertEqual(local.execute('SELECT count(*) FROM events').fetchone(), (0,))


if __name__ == '__main__':
    unittest.main()
