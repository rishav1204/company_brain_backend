-- Module 6: document current version pointers + immutable original reference

ALTER TABLE documents.documents
    ADD COLUMN IF NOT EXISTS original_storage_path TEXT,
    ADD COLUMN IF NOT EXISTS current_storage_path TEXT,
    ADD COLUMN IF NOT EXISTS current_version_number INTEGER NOT NULL DEFAULT 1;

-- Backfill for existing rows
UPDATE documents.documents
SET original_storage_path = COALESCE(original_storage_path, storage_path),
    current_storage_path = COALESCE(current_storage_path, storage_path)
WHERE original_storage_path IS NULL OR current_storage_path IS NULL;

