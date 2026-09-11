-- Migration 0002: stable keys for incremental event/location upserts.
-- Safe for a database created from the earlier schema.

ALTER TABLE event
    ADD COLUMN IF NOT EXISTS source_event_index SMALLINT NOT NULL DEFAULT 0;

CREATE UNIQUE INDEX IF NOT EXISTS event_source_document_event_index_uidx
    ON event (source_document_id, source_event_index);

ALTER TABLE location
    ADD COLUMN IF NOT EXISTS location_key TEXT;

CREATE UNIQUE INDEX IF NOT EXISTS location_location_key_uidx
    ON location (location_key)
    WHERE location_key IS NOT NULL;
