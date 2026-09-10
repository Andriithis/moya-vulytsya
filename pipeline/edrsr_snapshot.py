# -*- coding: utf-8 -*-
"""Deterministic parser for official EDRSR yearly snapshot archives.

This module intentionally has no database dependency. It is the stable boundary
between the external ZIP/TSV format and the rest of the project. Database upsert
is added on top of the records yielded here; the temporary Kyiv TSV export can
remain during migration of the old pipeline.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

EXPECTED_COLUMNS = (
    "doc_id",
    "court_code",
    "judgment_code",
    "justice_kind",
    "category_code",
    "cause_num",
    "adjudication_date",
    "receipt_date",
    "judge",
    "doc_url",
    "status",
    "date_publ",
)


@dataclass(frozen=True)
class DocumentRow:
    doc_id: str
    court_code: str
    judgment_code: str
    justice_kind: str
    category_code: str
    cause_num: str
    adjudication_date: str
    receipt_date: str
    judge: str
    doc_url: str
    status: int
    date_publ: str
    source_row_hash: str


@dataclass(frozen=True)
class SnapshotManifest:
    archive_sha256: str
    rows_seen: int
    documents_csv: str
    parsed_at: str


def sha256_file(path: os.PathLike[str] | str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _normalize(value: str) -> str:
    return value.strip().strip('"')


def _row_hash(values: list[str]) -> str:
    canonical = "\t".join(_normalize(v) for v in values[:12]).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _documents_member(zf: zipfile.ZipFile) -> str:
    matches = [name for name in zf.namelist() if name.lower().endswith("documents.csv")]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one documents.csv, found {len(matches)}")
    return matches[0]


def iter_documents(archive_path: os.PathLike[str] | str) -> Iterator[DocumentRow]:
    """Yield normalized metadata rows from the official EDRSR ZIP.

    The reader is streaming; it does not unpack the full archive or load the
    yearly documents table into memory.
    """
    with zipfile.ZipFile(archive_path) as zf:
        member = _documents_member(zf)
        with zf.open(member) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
            reader = csv.reader(text, delimiter="\t")
            header = next(reader, None)
            if not header:
                raise ValueError("documents.csv is empty")
            normalized_header = tuple(_normalize(v) for v in header[:12])
            if len(header) < 12:
                raise ValueError(f"documents.csv header has only {len(header)} columns")
            if normalized_header != EXPECTED_COLUMNS:
                raise ValueError(
                    "documents.csv header/order changed: "
                    f"expected {EXPECTED_COLUMNS!r}, got {normalized_header!r}"
                )

            for line_no, values in enumerate(reader, start=2):
                if not values or all(not v.strip() for v in values):
                    continue
                if len(values) < 12:
                    raise ValueError(f"documents.csv line {line_no} has {len(values)} columns; expected >=12")
                v = [_normalize(x) for x in values[:12]]
                if not v[0]:
                    raise ValueError(f"documents.csv line {line_no} has empty doc_id")
                try:
                    status = int(v[10])
                except ValueError as exc:
                    raise ValueError(f"documents.csv line {line_no}: invalid status {v[10]!r}") from exc
                if status not in (0, 1):
                    raise ValueError(f"documents.csv line {line_no}: unexpected status {status}")
                yield DocumentRow(
                    doc_id=v[0],
                    court_code=v[1],
                    judgment_code=v[2],
                    justice_kind=v[3],
                    category_code=v[4],
                    cause_num=v[5],
                    adjudication_date=v[6][:10],
                    receipt_date=v[7][:10],
                    judge=v[8],
                    doc_url=v[9],
                    status=status,
                    date_publ=v[11],
                    source_row_hash=_row_hash(values),
                )


def inspect_snapshot(archive_path: os.PathLike[str] | str) -> SnapshotManifest:
    rows = 0
    with zipfile.ZipFile(archive_path) as zf:
        member = _documents_member(zf)
    for _ in iter_documents(archive_path):
        rows += 1
    return SnapshotManifest(
        archive_sha256=sha256_file(archive_path),
        rows_seen=rows,
        documents_csv=member,
        parsed_at=datetime.now(timezone.utc).isoformat(),
    )


def write_manifest(archive_path: os.PathLike[str] | str, output_path: os.PathLike[str] | str) -> SnapshotManifest:
    manifest = inspect_snapshot(archive_path)
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(json.dumps(asdict(manifest), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Validate an EDRSR yearly ZIP and write a manifest")
    parser.add_argument("archive")
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args()

    manifest_path = args.manifest or f"{args.archive}.manifest.json"
    result = write_manifest(args.archive, manifest_path)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
