# -*- coding: utf-8 -*-
"""Synchronise legacy step1 extraction results into PostgreSQL.

This is a migration bridge, not the final extractor.  The existing step1 still
writes its SQLite/events.csv.gz compatibility state.  After that succeeds, this
module mirrors the extracted event and its candidate event location into the
normalised PostgreSQL model.

Important rules:
- adjudication/decision date is NOT copied to event.event_date;
- only addresses already accepted by addr.py as house/street candidates become
  EVENT_LOCATION links;
- all new events remain is_public=FALSE until later validation/geocoding;
- rerunning the sync is idempotent.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import sqlite3
from pathlib import Path
from typing import Iterable, Optional


EXTRACTION_VERSION = "legacy-step1-v1"
VALID_LOCATION_LEVELS = {"house", "street"}


@dataclass(frozen=True)
class LegacyEventRow:
    doc_id: str
    category: str
    street: Optional[str]
    house: Optional[str]
    level: Optional[str]
    event_time: Optional[str]
    error: Optional[str]


@dataclass(frozen=True)
class SyncResult:
    rows_seen: int
    events_upserted: int
    locations_linked: int
    events_removed_inactive: int
    rows_skipped_missing_document: int


def _connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise RuntimeError(
            "DATABASE_URL is configured, but psycopg is not installed. "
            "Install psycopg[binary]>=3.2."
        ) from exc
    return psycopg.connect(database_url)


def _clean(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def location_key(street: str, house: Optional[str]) -> str:
    """Stable technical key for a pre-geocode address candidate."""
    s = street.lower().replace("’", "'").replace("`", "'")
    s = re.sub(r"\s+", " ", s).strip(" ,.")
    h = (house or "").upper()
    h = re.sub(r"\s+", "", h).strip(" ,.")
    return f"kyiv|{s}|{h}"


def iter_legacy_events(sqlite_path: str | Path) -> Iterable[LegacyEventRow]:
    """Read the compatibility SQLite produced by step1."""
    sqlite_path = Path(sqlite_path)
    conn = sqlite3.connect(str(sqlite_path))
    try:
        for row in conn.execute(
            """
            SELECT doc_id, grp, street, house, level, tm, err
            FROM events
            WHERE doc_id NOT LIKE '__%__'
            ORDER BY doc_id
            """
        ):
            yield LegacyEventRow(
                doc_id=str(row[0]),
                category=str(row[1] or ""),
                street=_clean(row[2]),
                house=_clean(row[3]),
                level=_clean(row[4]),
                event_time=_clean(row[5]),
                error=_clean(row[6]),
            )
    finally:
        conn.close()


def _upsert_one(cur, row: LegacyEventRow) -> tuple[bool, bool, bool]:
    """Return (event_upserted, location_linked, missing_document)."""
    cur.execute(
        "SELECT case_id, source_status FROM document WHERE edrsr_id=%s",
        (row.doc_id,),
    )
    source = cur.fetchone()
    if source is None:
        return False, False, True

    case_id, source_status = source
    if int(source_status) == 0:
        cur.execute("DELETE FROM event WHERE source_document_id=%s", (row.doc_id,))
        return False, False, False

    # step1 currently has no reliable event-date extractor.  Do not copy the
    # court decision date into event_date; unknown stays NULL.
    cur.execute(
        """
        INSERT INTO event (
            case_id, source_document_id, source_event_index, category,
            event_date, event_time, extraction_version, is_public, updated_at
        )
        VALUES (%s, %s, 0, %s, NULL, %s, %s, FALSE, now())
        ON CONFLICT (source_document_id, source_event_index) DO UPDATE SET
            case_id = EXCLUDED.case_id,
            category = EXCLUDED.category,
            event_date = NULL,
            event_time = EXCLUDED.event_time,
            extraction_version = EXCLUDED.extraction_version,
            is_public = FALSE,
            updated_at = now()
        RETURNING id
        """,
        (case_id, row.doc_id, row.category or None, row.event_time, EXTRACTION_VERSION),
    )
    event_id = cur.fetchone()[0]

    # A changed document may yield a different address.  Replace only the
    # extracted EVENT_LOCATION link; future non-event roles remain untouched.
    cur.execute(
        "DELETE FROM event_location WHERE event_id=%s AND role='EVENT_LOCATION'",
        (event_id,),
    )

    if not row.street or row.level not in VALID_LOCATION_LEVELS:
        return True, False, False

    key = location_key(row.street, row.house)
    address_raw = row.street + ((", " + row.house) if row.house else "")
    cur.execute(
        """
        INSERT INTO location (location_key, address_raw, street, house, updated_at)
        VALUES (%s, %s, %s, %s, now())
        ON CONFLICT (location_key) DO UPDATE SET
            address_raw = EXCLUDED.address_raw,
            street = EXCLUDED.street,
            house = EXCLUDED.house,
            updated_at = now()
        RETURNING id
        """,
        (key, address_raw, row.street, row.house),
    )
    location_id = cur.fetchone()[0]
    cur.execute(
        """
        INSERT INTO event_location (event_id, location_id, role, confidence, evidence)
        VALUES (%s, %s, 'EVENT_LOCATION', NULL, %s)
        ON CONFLICT (event_id, location_id, role) DO UPDATE SET
            confidence = EXCLUDED.confidence,
            evidence = EXCLUDED.evidence
        """,
        (event_id, location_id, f"{EXTRACTION_VERSION}:{row.level}"),
    )
    return True, True, False


def sync_legacy_events(database_url: str, sqlite_path: str | Path) -> SyncResult:
    rows_seen = 0
    events_upserted = 0
    locations_linked = 0
    missing = 0

    rows = list(iter_legacy_events(sqlite_path))
    with _connect(database_url) as conn:
        with conn.transaction(), conn.cursor() as cur:
            # Explicit status=0 is authoritative.  Mere absence from a snapshot
            # is never interpreted as deletion.
            cur.execute(
                """
                DELETE FROM event e
                USING document d
                WHERE e.source_document_id=d.edrsr_id
                  AND d.source_status=0
                RETURNING e.id
                """
            )
            removed_inactive = len(cur.fetchall())

            for row in rows:
                rows_seen += 1
                event_ok, location_ok, missing_doc = _upsert_one(cur, row)
                events_upserted += int(event_ok)
                locations_linked += int(location_ok)
                missing += int(missing_doc)

    return SyncResult(
        rows_seen=rows_seen,
        events_upserted=events_upserted,
        locations_linked=locations_linked,
        events_removed_inactive=removed_inactive,
        rows_skipped_missing_document=missing,
    )
