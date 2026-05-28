-- Module 6: security + retention metadata

ALTER TABLE documents.documents
    ADD COLUMN IF NOT EXISTS malware_scan_status VARCHAR(32) NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS malware_scan_provider VARCHAR(64),
    ADD COLUMN IF NOT EXISTS malware_scan_detail TEXT,
    ADD COLUMN IF NOT EXISTS malware_scanned_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS retention_until TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS documents_retention_until_idx
    ON documents.documents (org_id, retention_until)
    WHERE retention_until IS NOT NULL;
