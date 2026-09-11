# -*- coding: utf-8 -*-
"""Крок 1b. Синхронізує результати step1 у PostgreSQL/PostGIS.

Крок навмисно опційний: без DATABASE_URL чинний CSV/SQLite pipeline працює
як раніше. Це міст для поступової міграції, а не заміна карти одним релізом.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from pipeline.postgres_events import sync_legacy_events

DATA = os.path.join(ROOT, "data")
SQLITE = os.path.join(DATA, "events.db")


def main():
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        print("DATABASE_URL не задано — PostgreSQL sync пропущено.")
        return
    if not os.path.exists(SQLITE):
        print("Немає data/events.db — спочатку виконайте step1_download.py")
        sys.exit(1)

    result = sync_legacy_events(database_url, SQLITE)
    print("=== PostgreSQL: події та кандидатні локації ===")
    print(f"прочитано зі старої бази: {result.rows_seen:,}")
    print(f"подій записано/оновлено: {result.events_upserted:,}")
    print(f"локацій прив'язано:      {result.locations_linked:,}")
    print(f"неактивних видалено:     {result.events_removed_inactive:,}")
    if result.rows_skipped_missing_document:
        print(
            "без документа у PostgreSQL пропущено: "
            f"{result.rows_skipped_missing_document:,}"
        )


if __name__ == "__main__":
    main()
