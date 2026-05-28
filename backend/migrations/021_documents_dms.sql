-- Module 6: Document Management System + OCR + Financial Document Intelligence

CREATE SCHEMA IF NOT EXISTS documents;

CREATE TABLE IF NOT EXISTS documents.documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    document_type VARCHAR(64) NOT NULL,
    file_name VARCHAR(512) NOT NULL,
    mime_type VARCHAR(128) NOT NULL,
    storage_path TEXT NOT NULL,
    checksum_hash TEXT NOT NULL,
    uploaded_by UUID,
    status VARCHAR(32) NOT NULL DEFAULT 'uploaded',
    file_size BIGINT NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, checksum_hash, document_type)
);

CREATE INDEX IF NOT EXISTS documents_org_type_created_idx
    ON documents.documents (org_id, document_type, created_at DESC);

CREATE INDEX IF NOT EXISTS documents_org_status_created_idx
    ON documents.documents (org_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS documents.document_versions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    storage_path TEXT NOT NULL,
    uploaded_by UUID,
    change_reason TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, version_number)
);

CREATE TABLE IF NOT EXISTS documents.extractions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    extraction_type VARCHAR(64) NOT NULL,
    extracted_data JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    extraction_status VARCHAR(32) NOT NULL DEFAULT 'queued',
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS documents_extractions_doc_created_idx
    ON documents.extractions (document_id, created_at DESC);

CREATE TABLE IF NOT EXISTS documents.classifications (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    classification VARCHAR(64) NOT NULL,
    confidence_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    classified_by VARCHAR(64) NOT NULL DEFAULT 'system',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS documents_classifications_doc_created_idx
    ON documents.classifications (document_id, created_at DESC);

CREATE TABLE IF NOT EXISTS documents.evidence_links (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    entity_type VARCHAR(64) NOT NULL,
    entity_id UUID NOT NULL,
    workflow_id UUID,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS documents_evidence_entity_idx
    ON documents.evidence_links (org_id, entity_type, entity_id, created_at DESC);

CREATE TABLE IF NOT EXISTS documents.semantic_embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    embedding VECTOR(1536),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS documents_embeddings_doc_created_idx
    ON documents.semantic_embeddings (document_id, created_at DESC);

CREATE TABLE IF NOT EXISTS documents.duplicate_candidates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    matched_document_id UUID NOT NULL REFERENCES documents.documents(id) ON DELETE CASCADE,
    duplicate_reason VARCHAR(128) NOT NULL,
    similarity_score NUMERIC(5,4) NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'open',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE documents.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents.documents FORCE ROW LEVEL SECURITY;
ALTER TABLE documents.document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents.document_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE documents.extractions ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents.extractions FORCE ROW LEVEL SECURITY;
ALTER TABLE documents.classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents.classifications FORCE ROW LEVEL SECURITY;
ALTER TABLE documents.evidence_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents.evidence_links FORCE ROW LEVEL SECURITY;
ALTER TABLE documents.semantic_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents.semantic_embeddings FORCE ROW LEVEL SECURITY;
ALTER TABLE documents.duplicate_candidates ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents.duplicate_candidates FORCE ROW LEVEL SECURITY;

CREATE POLICY documents_rows_org ON documents.documents
    USING (org_id = current_setting('app.current_org', true)::UUID);

CREATE POLICY document_versions_rows_org ON documents.document_versions
    USING (org_id = current_setting('app.current_org', true)::UUID);

CREATE POLICY extractions_rows_org ON documents.extractions
    USING (org_id = current_setting('app.current_org', true)::UUID);

CREATE POLICY classifications_rows_org ON documents.classifications
    USING (org_id = current_setting('app.current_org', true)::UUID);

CREATE POLICY evidence_links_rows_org ON documents.evidence_links
    USING (org_id = current_setting('app.current_org', true)::UUID);

CREATE POLICY semantic_embeddings_rows_org ON documents.semantic_embeddings
    USING (org_id = current_setting('app.current_org', true)::UUID);

CREATE POLICY duplicate_candidates_rows_org ON documents.duplicate_candidates
    USING (org_id = current_setting('app.current_org', true)::UUID);
