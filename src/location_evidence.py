"""Внутрішній контекст адрес. Не включати в публічний CSV-знімок."""
import json

try:
    from . import addr
except ImportError:  # запуск src/step*.py
    import addr


def init_evidence(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS address_evidence (
        doc_id TEXT PRIMARY KEY, version TEXT NOT NULL, candidates TEXT NOT NULL
    )''')


def save_evidence(conn, doc_id, candidates):
    conn.execute('INSERT OR REPLACE INTO address_evidence VALUES (?, ?, ?)',
                 (doc_id, addr.EXTRACTION_VERSION,
                  json.dumps(candidates, ensure_ascii=False)))
    # Стара координата перестає бути чинною одразу після повторного витягування.
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name='geo'").fetchone():
        conn.execute('DELETE FROM geo WHERE doc_id=?', (doc_id,))


def load_candidates(conn, doc_id):
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='address_evidence'").fetchone():
        return []
    row = conn.execute('SELECT version,candidates FROM address_evidence WHERE doc_id=?',
                       (doc_id,)).fetchone()
    if not row or row[0] != addr.EXTRACTION_VERSION:
        return []
    try:
        candidates = [addr.AddressCandidate(**item) for item in json.loads(row[1])]
        for c in candidates:
            offset = c.start - c.context_start
            if (c.version != addr.EXTRACTION_VERSION or offset < 0 or
                    c.end - c.start != len(c.raw) or
                    c.context[offset:offset + len(c.raw)] != c.raw):
                return []
            if c.role == 'EVENT_LOCATION':
                verified = addr.extract_candidates(c.context)
                if not any(v.start == offset and v.raw == c.raw and
                           v.street == c.street and v.house == c.house and
                           v.role == 'EVENT_LOCATION' for v in verified):
                    return []
        return candidates
    except (TypeError, ValueError, KeyError, AttributeError):
        return []


def confirmed_rows(conn):
    """Єдиний допуск до старого геокодера й карти; старі CSV не є доказом."""
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name='address_evidence'").fetchone():
        return []
    rows = []
    for doc, street, house, level, error in conn.execute(
            '''SELECT e.doc_id,e.street,e.house,e.level,e.err FROM events e
               JOIN address_evidence a ON a.doc_id=e.doc_id
               WHERE e.street IS NOT NULL AND a.version=?''', (addr.EXTRACTION_VERSION,)):
        if error or level not in ('house', 'street'):
            continue
        selected = addr.select_event_candidate(load_candidates(conn, doc))
        if selected and (selected.street, selected.house) == (street, house):
            rows.append((doc, street, house))
    return rows
