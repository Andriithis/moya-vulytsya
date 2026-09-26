# -*- coding: utf-8 -*-
"""PostgreSQL ingestion for official EDRSR yearly snapshots.

The module is deliberately optional: importing it does not require psycopg.
A database connection is opened only when ``ingest_snapshot`` is called, so the
legacy CSV/SQLite pipeline keeps working when DATABASE_URL is not configured.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from pipeline.edrsr_snapshot import iter_documents, sha256_file


@dataclass(frozen=True)
class IngestResult:
    snapshot_id: int
    run_id: Optional[int]
    archive_sha256: str
    rows_seen: int
    documents_new: int
    documents_changed: int
    documents_inactive: int
    no_op: bool


_CREATE_STAGE_SQL = """
CREATE TEMP TABLE edrsr_document_stage (
    edrsr_id TEXT PRIMARY KEY,
    court_code TEXT,
    judgment_code TEXT,
    justice_kind TEXT,
    category_code TEXT,
    cause_num TEXT,
    adjudication_date DATE,
    receipt_date DATE,
    judge TEXT,
    doc_url TEXT,
    source_status SMALLINT NOT NULL,
    date_publ TIMESTAMPTZ,
    source_row_hash TEXT NOT NULL
) ON COMMIT DROP
"""

_COPY_STAGE_SQL = """
COPY edrsr_document_stage (
    edrsr_id, court_code, judgment_code, justice_kind, category_code,
    cause_num, adjudication_date, receipt_date, judge, doc_url,
    source_status, date_publ, source_row_hash
) FROM STDIN
"""


def _none(value: str) -> Optional[str]:
    value = value.strip()
    return value or None


def _date(value: str) -> Optional[str]:
    value = value.strip()
    return value[:10] if value else None


def _timestamp(value: str) -> Optional[str]:
    value = value.strip()
    return value or None


def _stage_row(row):
    return (
        row.doc_id,
        _none(row.court_code),
        _none(row.judgment_code),
        _none(row.justice_kind),
        _none(row.category_code),
        _none(row.cause_num),
        _date(row.adjudication_date),
        _date(row.receipt_date),
        _none(row.judge),
        _none(row.doc_url),
        row.status,
        _timestamp(row.date_publ),
        row.source_row_hash,
    )


def ingest_snapshot(
    database_url: str,
    archive_path: str | Path,
    *,
    year: int,
    source_url: str,
    archive_path_for_db: Optional[str] = None,
) -> IngestResult:
    """Register a snapshot and set-wise upsert its EDRSR documents.

    A repeated ``(year, sha256)`` snapshot is a true no-op. Absence from a
    cumulative snapshot is never interpreted as deletion; ``source_status`` is
    changed only from an explicit row in EDRSR.
    """
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - depends on deployment image
        raise RuntimeError(
            "DATABASE_URL is configured, but psycopg is not installed. "
            "Install psycopg[binary]>=3.2."
        ) from exc

    archive_path = Path(archive_path)
    archive_sha256 = sha256_file(archive_path)
    stored_path = archive_path_for_db or str(archive_path)

    with psycopg.connect(database_url) as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, row_count FROM source_snapshot WHERE year=%s AND source_hash=%s",
                    (year, archive_sha256),
                )
                existing = cur.fetchone()
                if existing:
                    return IngestResult(
                        snapshot_id=existing[0],
                        run_id=None,
                        archive_sha256=archive_sha256,
                        rows_seen=int(existing[1] or 0),
                        documents_new=0,
                        documents_changed=0,
                        documents_inactive=0,
                        no_op=True,
                    )

                cur.execute(
                    """
                    INSERT INTO source_snapshot
                        (year, source_url, source_hash, archive_path, status)
                    VALUES (%s, %s, %s, %s, 'processing')
                    RETURNING id
                    """,
                    (year, source_url, archive_sha256, stored_path),
                )
                snapshot_id = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO pipeline_run (snapshot_id) VALUES (%s) RETURNING id",
                    (snapshot_id,),
                )
                run_id = cur.fetchone()[0]
                cur.execute(_CREATE_STAGE_SQL)

                rows_seen = 0
                inactive = 0
                with cur.copy(_COPY_STAGE_SQL) as copy:
                    for row in iter_documents(archive_path):
                        copy.write_row(_stage_row(row))
                        rows_seen += 1
                        if row.status == 0:
                            inactive += 1

                # Cases are normalized before documents so FK assignment is set-wise.
                cur.execute(
                    """
                    INSERT INTO case_record (cause_num, court_code)
                    SELECT DISTINCT cause_num, court_code
                    FROM edrsr_document_stage
                    WHERE cause_num IS NOT NULL AND cause_num <> ''
                    ON CONFLICT (cause_num, court_code) DO NOTHING
                    """
                )

                # Count changes against the pre-upsert state. A status/date_publ
                # change matters even if another source field happens to hash alike.
                cur.execute(
                    """
                    SELECT
                        count(*) FILTER (WHERE d.edrsr_id IS NULL) AS new_count,
                        count(*) FILTER (
                            WHERE d.edrsr_id IS NOT NULL AND (
                                d.source_row_hash IS DISTINCT FROM s.source_row_hash OR
                                d.source_status IS DISTINCT FROM s.source_status OR
                                d.date_publ IS DISTINCT FROM s.date_publ
                            )
                        ) AS changed_count
                    FROM edrsr_document_stage s
                    LEFT JOIN document d ON d.edrsr_id = s.edrsr_id
                    """
                )
                documents_new, documents_changed = cur.fetchone()
                documents_new = int(documents_new or 0)
                documents_changed = int(documents_changed or 0)

                cur.execute(
                    """
                    INSERT INTO document (
                        edrsr_id, case_id, court_code, judgment_code, justice_kind,
                        category_code, cause_num, adjudication_date, receipt_date,
                        judge, doc_url, source_status, date_publ, source_row_hash,
                        first_seen_snapshot_id, last_seen_snapshot_id, needs_processing
                    )
                    SELECT
                        s.edrsr_id,
                        c.id,
                        s.court_code,
                        s.judgment_code,
                        s.justice_kind,
                        s.category_code,
                        s.cause_num,
                        s.adjudication_date,
                        s.receipt_date,
                        s.judge,
                        s.doc_url,
                        s.source_status,
                        s.date_publ,
                        s.source_row_hash,
                        %s,
                        %s,
                        TRUE
                    FROM edrsr_document_stage s
                    LEFT JOIN case_record c
                      ON c.cause_num = s.cause_num
                     AND c.court_code IS NOT DISTINCT FROM s.court_code
                    ON CONFLICT (edrsr_id) DO UPDATE SET
                        case_id = EXCLUDED.case_id,
                        court_code = EXCLUDED.court_code,
                        judgment_code = EXCLUDED.judgment_code,
                        justice_kind = EXCLUDED.justice_kind,
                        category_code = EXCLUDED.category_code,
                        cause_num = EXCLUDED.cause_num,
                        adjudication_date = EXCLUDED.adjudication_date,
                        receipt_date = EXCLUDED.receipt_date,
                        judge = EXCLUDED.judge,
                        doc_url = EXCLUDED.doc_url,
                        source_status = EXCLUDED.source_status,
                        date_publ = EXCLUDED.date_publ,
                        source_row_hash = EXCLUDED.source_row_hash,
                        last_seen_snapshot_id = EXCLUDED.last_seen_snapshot_id,
                        needs_processing = document.needs_processing OR (
                            document.source_row_hash IS DISTINCT FROM EXCLUDED.source_row_hash OR
                            document.source_status IS DISTINCT FROM EXCLUDED.source_status OR
                            document.date_publ IS DISTINCT FROM EXCLUDED.date_publ
                        ),
                        updated_at = CASE WHEN
                            document.source_row_hash IS DISTINCT FROM EXCLUDED.source_row_hash OR
                            document.source_status IS DISTINCT FROM EXCLUDED.source_status OR
                            document.date_publ IS DISTINCT FROM EXCLUDED.date_publ
                        THEN now() ELSE document.updated_at END
                    """,
                    (snapshot_id, snapshot_id),
                )

                cur.execute(
                    """
                    UPDATE source_snapshot
                    SET row_count=%s, status='processed'
                    WHERE id=%s
                    """,
                    (rows_seen, snapshot_id),
                )
                cur.execute(
                    """
                    UPDATE pipeline_run
                    SET finished_at=now(), status='success', documents_seen=%s,
                        documents_new=%s, documents_changed=%s,
                        documents_inactive=%s
                    WHERE id=%s
                    """,
                    (rows_seen, documents_new, documents_changed, inactive, run_id),
                )

    return IngestResult(
        snapshot_id=snapshot_id,
        run_id=run_id,
        archive_sha256=archive_sha256,
        rows_seen=rows_seen,
        documents_new=documents_new,
        documents_changed=documents_changed,
        documents_inactive=inactive,
        no_op=False,
    )
