# -*- coding: utf-8 -*-
"""Перенесення результатів step1 та контексту адрес у PostgreSQL.

Дата рішення не підміняє дату події. Старі адреси без контексту мають роль
UNKNOWN. EVENT_LOCATION потребує явного зв'язку з подією та однозначного
вибору. Усі події залишаються is_public=FALSE до наступних перевірок.
Повторний sync замінює витягнуті зв'язки, не створюючи дублів.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import re
import json
import sqlite3
from pathlib import Path
from typing import Iterable, Optional
from src.addr import AddressCandidate, EXTRACTION_VERSION, select_event_candidate
from src.location_evidence import load_candidates


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
    candidates: tuple[AddressCandidate, ...] = ()


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
            WHERE doc_id NOT GLOB '__*__'
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
                candidates=tuple(load_candidates(conn, str(row[0]))),
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

    # При повторному витягуванні прибираємо старі результати нашого extractor-а.
    # Інші не-подієві зв'язки, наприклад ручна класифікація, залишаються.
    cur.execute(
        """DELETE FROM event_location WHERE event_id=%s AND
           (role='EVENT_LOCATION' OR evidence LIKE 'location-roles-v1:%%'
            OR evidence LIKE 'legacy-step1-v1:%%')""",
        (event_id,),
    )

    if row.error:
        return True, False, False

    selected = select_event_candidate(row.candidates)
    if selected and ((selected.street, selected.house) != (row.street, row.house)
                     or row.level not in VALID_LOCATION_LEVELS):
        selected = None
    # Знімок старого step1 не містить контексту: це лише UNKNOWN, не подія.
    grouped = {}
    for candidate in row.candidates:
        role = candidate.role
        if role == 'EVENT_LOCATION' and selected is None:
            role = 'UNKNOWN'
        key = (candidate.street, candidate.house, role)
        grouped.setdefault(key, []).append(asdict(candidate))
    if not grouped and row.street and row.level in VALID_LOCATION_LEVELS:
        grouped[(row.street, row.house, 'UNKNOWN')] = [{'reason': 'legacy_without_context'}]
    for (street, house, role), evidence in grouped.items():
        key = location_key(street, house)
        address_raw = street + ((", " + house) if house else "")
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
            (key, address_raw, street, house),
        )
        location_id = cur.fetchone()[0]
        cur.execute(
            """
            INSERT INTO event_location (event_id, location_id, role, confidence, evidence)
            VALUES (%s, %s, %s, NULL, %s)
            ON CONFLICT (event_id, location_id, role) DO UPDATE SET
                confidence = EXCLUDED.confidence,
                evidence = EXCLUDED.evidence
            """,
            (event_id, location_id, role,
             EXTRACTION_VERSION + ':' + json.dumps(evidence, ensure_ascii=False)),
        )
    return True, bool(grouped), False


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
