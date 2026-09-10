CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS source_snapshot (
    id BIGSERIAL PRIMARY KEY,
    year INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    source_hash TEXT NOT NULL,
    source_modified_at TIMESTAMPTZ,
    downloaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    archive_path TEXT,
    row_count BIGINT,
    status TEXT NOT NULL DEFAULT 'downloaded',
    UNIQUE (year, source_hash)
);

CREATE TABLE IF NOT EXISTS pipeline_run (
    id BIGSERIAL PRIMARY KEY,
    snapshot_id BIGINT REFERENCES source_snapshot(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    documents_seen BIGINT NOT NULL DEFAULT 0,
    documents_new BIGINT NOT NULL DEFAULT 0,
    documents_changed BIGINT NOT NULL DEFAULT 0,
    documents_inactive BIGINT NOT NULL DEFAULT 0,
    events_changed BIGINT NOT NULL DEFAULT 0,
    errors BIGINT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS case_record (
    id BIGSERIAL PRIMARY KEY,
    cause_num TEXT,
    court_code TEXT,
    UNIQUE (cause_num, court_code)
);

CREATE TABLE IF NOT EXISTS document (
    edrsr_id TEXT PRIMARY KEY,
    case_id BIGINT REFERENCES case_record(id),
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
    source_row_hash TEXT NOT NULL,
    first_seen_snapshot_id BIGINT REFERENCES source_snapshot(id),
    last_seen_snapshot_id BIGINT REFERENCES source_snapshot(id),
    needs_processing BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_needs_processing_idx
    ON document (needs_processing)
    WHERE needs_processing = TRUE;
CREATE INDEX IF NOT EXISTS document_case_idx ON document (case_id);
CREATE INDEX IF NOT EXISTS document_date_publ_idx ON document (date_publ);

CREATE TABLE IF NOT EXISTS event (
    id BIGSERIAL PRIMARY KEY,
    case_id BIGINT REFERENCES case_record(id),
    source_document_id TEXT REFERENCES document(edrsr_id),
    category TEXT,
    event_date DATE,
    event_time TIME,
    summary TEXT,
    extraction_version TEXT,
    confidence NUMERIC(4,3),
    is_public BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS event_source_document_idx ON event (source_document_id);
CREATE INDEX IF NOT EXISTS event_date_idx ON event (event_date);

CREATE TABLE IF NOT EXISTS location (
    id BIGSERIAL PRIMARY KEY,
    address_raw TEXT,
    street TEXT,
    house TEXT,
    address_normalized TEXT,
    geom geometry(Point, 4326),
    geocode_source TEXT,
    geocode_confidence NUMERIC(4,3),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS location_geom_idx ON location USING GIST (geom);

CREATE TABLE IF NOT EXISTS event_location (
    event_id BIGINT NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    location_id BIGINT NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN (
        'EVENT_LOCATION', 'COURT', 'RESIDENCE', 'WORKPLACE',
        'PROPERTY', 'INSTITUTION', 'OTHER', 'UNKNOWN'
    )),
    confidence NUMERIC(4,3),
    evidence TEXT,
    PRIMARY KEY (event_id, location_id, role)
);

CREATE INDEX IF NOT EXISTS event_location_role_idx ON event_location (role);
