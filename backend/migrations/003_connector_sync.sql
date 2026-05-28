CREATE TABLE connector_sync_states (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    source_id UUID REFERENCES data_sources(id),
    connector TEXT NOT NULL,
    mode TEXT NOT NULL,
    cursor_ref TEXT,
    metadata_jsonb JSONB NOT NULL DEFAULT '{}'::JSONB,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, connector, source_id, mode)
);

CREATE TABLE connector_processed_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    source_id UUID REFERENCES data_sources(id),
    connector TEXT NOT NULL,
    external_record_id TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    normalized_ref TEXT,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, connector, source_id, external_record_id)
);

CREATE INDEX idx_connector_sync_states_org ON connector_sync_states(org_id, connector, updated_at DESC);
CREATE INDEX idx_connector_processed_org ON connector_processed_records(org_id, connector, processed_at DESC);

ALTER TABLE connector_sync_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_sync_states FORCE ROW LEVEL SECURITY;
ALTER TABLE connector_processed_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE connector_processed_records FORCE ROW LEVEL SECURITY;

CREATE POLICY connector_sync_states_org_isolation ON connector_sync_states
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY connector_processed_records_org_isolation ON connector_processed_records
    USING (org_id = current_setting('app.current_org', true)::UUID);
