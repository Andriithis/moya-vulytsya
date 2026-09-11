import os
import sqlite3
import tempfile
import unittest

from pipeline.postgres_events import iter_legacy_events, location_key


class PostgresEventsBridgeTests(unittest.TestCase):
    def test_location_key_is_stable_for_spacing_and_apostrophe(self):
        self.assertEqual(
            location_key("вул. Героїв Дніпра", " 12 А "),
            "kyiv|вул. героїв дніпра|12А",
        )
        self.assertEqual(
            location_key("вул.  Героїв   Дніпра", "12А"),
            "kyiv|вул. героїв дніпра|12А",
        )

    def test_iter_legacy_events_skips_internal_markers(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "events.db")
            conn = sqlite3.connect(path)
            conn.execute(
                """
                CREATE TABLE events(
                    doc_id TEXT PRIMARY KEY, court TEXT, grp TEXT, cat TEXT,
                    date TEXT, street TEXT, house TEXT, level TEXT, tm TEXT, err TEXT
                )
                """
            )
            conn.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "123456789",
                    "Shevchenkivskyi",
                    "МАЙ",
                    "40576",
                    "2026-09-01",
                    "вул. Хрещатик",
                    "10",
                    "house",
                    "22:30",
                    None,
                ),
            )
            conn.execute(
                "INSERT INTO events VALUES(?,?,?,?,?,?,?,?,?,?)",
                (
                    "__vypravlennia_adres_2026_09__",
                    "",
                    "",
                    "",
                    "",
                    None,
                    None,
                    "marker",
                    None,
                    "marker",
                ),
            )
            conn.commit()
            conn.close()

            rows = list(iter_legacy_events(path))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].doc_id, "123456789")
            self.assertEqual(rows[0].street, "вул. Хрещатик")
            self.assertEqual(rows[0].house, "10")
            self.assertEqual(rows[0].event_time, "22:30")


if __name__ == "__main__":
    unittest.main()
