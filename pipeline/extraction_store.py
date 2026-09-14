"""Приватний PostgreSQL checkpoint з перевіркою версії джерела.

Запис результату та завершення черги відбуваються в одній транзакції.
Зміна документа під час завантаження не може підтвердити старий результат.
"""
import json
import re

from src import addr
from src import location_evidence as evidence
from pipeline.postgres_tasks import _connect

HASH = re.compile(r'^[0-9a-f]{64}$')
EVENT_COLUMNS = 'doc_id,court,grp,cat,date,street,house,level,tm,err'


def validate_result(record, candidates, source_hash, text_hash):
    """Перевіряємо структуру та відтворюваність evidence перед записом/відновленням."""
    if (not isinstance(record, (list, tuple)) or len(record) != 10 or
            any(v is not None and not isinstance(v, str) for v in record) or
            not record[0] or not record[0].isdigit() or record[9] is not None or
            record[7] not in ('house', 'street', 'none') or
            not HASH.fullmatch(source_hash or '') or not HASH.fullmatch(text_hash or '') or
            not isinstance(candidates, list)):
        raise ValueError('Непридатний результат витягування')
    # Та сама перевірка, що й у геокодера, включно з нульовим результатом.
    verified = evidence.parse_candidates(candidates)
    if verified is None:
        raise ValueError('Контекст кандидата не проходить перевірку')
    if any(c.role not in ('EVENT_LOCATION', 'COURT', 'RESIDENCE', 'WORKPLACE',
                          'PROPERTY', 'INSTITUTION', 'OTHER', 'UNKNOWN') for c in verified):
        raise ValueError('Невідома роль адреси')
    selected = addr.select_event_candidate(verified)
    expected = (selected.street, selected.house, 'house' if selected.house else 'street') if selected else (None, None, 'none')
    if tuple(record[5:8]) != expected:
        raise ValueError('Адреса рядка не відповідає доказовому контексту')


def persist_result(cur, record, candidates, source_hash, text_hash):
    """Повертає False, якщо джерело вже змінилося/деактивоване/зникло."""
    validate_result(record, candidates, source_hash, text_hash)
    cur.execute('SELECT source_row_hash,source_status FROM document WHERE edrsr_id=%s FOR UPDATE',
                (record[0],))
    current = cur.fetchone()
    if current != (source_hash, 1):
        return False
    cur.execute('''INSERT INTO document_extraction
        (document_id,source_row_hash,extraction_version,text_sha256,record,candidates)
        VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb)
        ON CONFLICT (document_id) DO UPDATE SET
            source_row_hash=EXCLUDED.source_row_hash,
            extraction_version=EXCLUDED.extraction_version,
            text_sha256=EXCLUDED.text_sha256, record=EXCLUDED.record,
            candidates=EXCLUDED.candidates, updated_at=now()''',
        (record[0], source_hash, addr.EXTRACTION_VERSION, text_hash,
         json.dumps(record, ensure_ascii=False), json.dumps(candidates, ensure_ascii=False)))
    cur.execute('UPDATE document SET needs_processing=FALSE WHERE edrsr_id=%s', (record[0],))
    return True


def persist_local_results(database_url, local, doc_ids):
    """Зберігає тільки успішні результати; повертає ID, чия версія джерела застаріла."""
    stale = []
    with _connect(database_url) as conn, conn.transaction(), conn.cursor() as cur:
        for doc in sorted(set(doc_ids)):
            record = local.execute(f'SELECT {EVENT_COLUMNS} FROM events WHERE doc_id=?', (doc,)).fetchone()
            if record is None or record[9] is not None:
                continue
            proof = local.execute('''SELECT candidates,source_row_hash,text_sha256
                                    FROM address_evidence WHERE doc_id=?''', (doc,)).fetchone()
            if proof is None:
                raise ValueError('Немає контексту успішного результату')
            if not persist_result(cur, record, json.loads(proof[0]), proof[1], proof[2]):
                stale.append(doc)
    # Результати з відхиленою версією не повинні потрапити в наступний крок.
    with local:
        for doc in stale:
            local.execute('DELETE FROM address_evidence WHERE doc_id=?', (doc,))
            local.execute("UPDATE events SET street=NULL,house=NULL,level='stale',err='source_changed' WHERE doc_id=?", (doc,))
            if local.execute("SELECT 1 FROM sqlite_master WHERE name='geo'").fetchone():
                local.execute('DELETE FROM geo WHERE doc_id=?', (doc,))
    return stale


def restore_from_cursor(cur, local, court_codes, excluded_groups=()):
    """Відновлює лише поточне джерело. Старі локальні докази перестають діяти."""
    cur.execute('''SELECT x.document_id,x.record,x.candidates,x.source_row_hash,x.text_sha256
        FROM document_extraction x JOIN document d ON d.edrsr_id=x.document_id
        WHERE d.source_status=1 AND d.source_row_hash=x.source_row_hash
          AND x.extraction_version=%s AND d.court_code=ANY(%s)
        ORDER BY x.document_id''', (addr.EXTRACTION_VERSION, sorted(court_codes)))
    count = 0
    with local:
        evidence.init_evidence(local)
        local.execute('DELETE FROM address_evidence')
        if local.execute("SELECT 1 FROM sqlite_master WHERE name='geo'").fetchone():
            local.execute('DELETE FROM geo')
        for doc_id, record, candidates, source_hash, text_hash in cur:
            validate_result(record, candidates, source_hash, text_hash)
            if record[0] != doc_id:
                raise ValueError('Checkpoint належить іншому документу')
            if record[2] in excluded_groups:
                continue
            local.execute(f'INSERT OR REPLACE INTO events ({EVENT_COLUMNS}) VALUES (?,?,?,?,?,?,?,?,?,?)', record)
            evidence.save_evidence(local, doc_id, candidates, source_hash, text_hash)
            count += 1
    return count


def restore_local_results(database_url, local, court_codes, excluded_groups=()):
    with _connect(database_url) as conn, conn.cursor() as cur:
        return restore_from_cursor(cur, local, court_codes, excluded_groups)
