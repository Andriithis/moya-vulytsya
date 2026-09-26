-- Внутрішній результат витягування. Не надавати доступ публічній API-ролі.
CREATE TABLE IF NOT EXISTS document_extraction (
    document_id TEXT PRIMARY KEY REFERENCES document(edrsr_id) ON DELETE CASCADE,
    source_row_hash TEXT NOT NULL CHECK (source_row_hash ~ '^[0-9a-f]{64}$'),
    extraction_version TEXT NOT NULL,
    text_sha256 TEXT NOT NULL CHECK (text_sha256 ~ '^[0-9a-f]{64}$'),
    record JSONB NOT NULL CHECK (jsonb_typeof(record) = 'array' AND jsonb_array_length(record) = 10),
    candidates JSONB NOT NULL CHECK (jsonb_typeof(candidates) = 'array'),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
REVOKE ALL ON document_extraction FROM PUBLIC;
