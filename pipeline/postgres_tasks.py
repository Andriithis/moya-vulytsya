# -*- coding: utf-8 -*-
"""Bridge between the PostgreSQL document queue and legacy step1 processing.

The module is optional. psycopg is imported only when DATABASE_URL is used,
so installations that still run purely on CSV/SQLite keep working unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class PendingDocument:
    doc_id: str
    court_code: str
    category_code: str
    date: str
    doc_url: str


@dataclass(frozen=True)
class PendingWork:
    active: list[PendingDocument]
    inactive_ids: list[str]


def _connect(database_url: str):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - deployment dependency
        raise RuntimeError(
            "DATABASE_URL is configured, but psycopg is not installed. "
            "Install psycopg[binary]>=3.2."
        ) from exc
    return psycopg.connect(database_url)


def load_pending_work(database_url: str, court_codes: Iterable[str]) -> PendingWork:
    """Return pending documents only for the courts handled by this map.

    Active documents are returned for extraction. Explicitly inactive EDRSR
    documents are returned separately so legacy SQLite/public snapshots can
    remove them without treating mere absence from a yearly snapshot as a
    deletion.
    """
    courts = sorted({str(x) for x in court_codes if x})
    if not courts:
        return PendingWork(active=[], inactive_ids=[])

    active: list[PendingDocument] = []
    inactive: list[str] = []

    with _connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            SELECT edrsr_id, court_code, category_code,
                   adjudication_date, doc_url, source_status
            FROM document
            WHERE needs_processing = TRUE
              AND court_code = ANY(%s)
            ORDER BY adjudication_date NULLS LAST, edrsr_id
            """,
            (courts,),
        )
        for doc_id, court_code, category_code, date, doc_url, status in cur:
            if int(status) == 0:
                inactive.append(str(doc_id))
                continue
            if int(status) != 1:
                continue
            active.append(
                PendingDocument(
                    doc_id=str(doc_id),
                    court_code=str(court_code or ""),
                    category_code=str(category_code or ""),
                    date=date.isoformat() if date is not None else "",
                    doc_url=str(doc_url or ""),
                )
            )

    return PendingWork(active=active, inactive_ids=inactive)


def mark_processed(database_url: str, doc_ids: Iterable[str]) -> int:
    """Clear needs_processing for documents safely persisted by step1.

    Calling this only after the local SQLite/snapshot write makes retries safe:
    a crash before this point merely causes the document to be processed again.
    """
    ids = sorted({str(x) for x in doc_ids if x})
    if not ids:
        return 0

    with _connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE document
            SET needs_processing = FALSE, updated_at = now()
            WHERE edrsr_id = ANY(%s)
              AND needs_processing = TRUE
            """,
            (ids,),
        )
        changed = cur.rowcount
        conn.commit()
    return int(changed or 0)
