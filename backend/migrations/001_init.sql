CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'starter',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    email TEXT NOT NULL,
    display_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL
);

CREATE TABLE user_roles (
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    role_id UUID NOT NULL REFERENCES roles(id),
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE data_sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    config_ref TEXT NOT NULL,
    last_sync_at TIMESTAMPTZ
);

CREATE TABLE ingestion_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    source_id UUID NOT NULL REFERENCES data_sources(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status TEXT NOT NULL,
    error_summary TEXT
);

CREATE TABLE identity_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    canonical_type TEXT NOT NULL,
    canonical_key TEXT NOT NULL,
    confidence FLOAT NOT NULL
);

CREATE TABLE identity_aliases (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    identity_profile_id UUID NOT NULL REFERENCES identity_profiles(id),
    source TEXT NOT NULL,
    source_key TEXT NOT NULL,
    raw_value TEXT NOT NULL
);

CREATE TABLE finance_entities (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL,
    external_ref TEXT
);

CREATE TABLE vendors (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    finance_entity_id UUID REFERENCES finance_entities(id),
    payment_terms TEXT,
    risk_tier TEXT
);

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    finance_entity_id UUID REFERENCES finance_entities(id),
    segment TEXT,
    risk_tier TEXT
);

CREATE TABLE invoices (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    invoice_type TEXT NOT NULL,
    vendor_id UUID REFERENCES vendors(id),
    customer_id UUID REFERENCES customers(id),
    amount NUMERIC NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    due_date DATE,
    status TEXT NOT NULL
);

CREATE TABLE journal_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    period TEXT NOT NULL,
    entry_date DATE NOT NULL,
    account_code TEXT NOT NULL,
    debit NUMERIC NOT NULL DEFAULT 0,
    credit NUMERIC NOT NULL DEFAULT 0,
    status TEXT NOT NULL
);

CREATE TABLE approvals (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    object_type TEXT NOT NULL,
    object_id UUID NOT NULL,
    step_no INT NOT NULL,
    approver_user_id UUID REFERENCES users(id),
    status TEXT NOT NULL,
    decided_at TIMESTAMPTZ
);

CREATE TABLE workflows (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    workflow_type TEXT NOT NULL,
    state TEXT NOT NULL,
    owner_user_id UUID REFERENCES users(id),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE TABLE workflow_steps (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    workflow_id UUID NOT NULL REFERENCES workflows(id),
    step_type TEXT NOT NULL,
    state TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    decision_type TEXT NOT NULL,
    title TEXT NOT NULL,
    rationale TEXT NOT NULL,
    made_by UUID REFERENCES users(id),
    decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE incidents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    incident_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE memory_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    memory_type TEXT NOT NULL,
    subject_ref TEXT NOT NULL,
    payload_jsonb JSONB NOT NULL,
    relevance_score FLOAT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    source_id UUID REFERENCES data_sources(id),
    external_id TEXT,
    title TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    permission_ref TEXT,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    document_id UUID NOT NULL REFERENCES documents(id),
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    metadata_jsonb JSONB NOT NULL DEFAULT '{}'::JSONB,
    token_count INT NOT NULL,
    embedding VECTOR(1536)
);

CREATE TABLE citations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    response_id UUID NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    span_start INT,
    span_end INT,
    confidence FLOAT NOT NULL
);

CREATE TABLE agent_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    agent_type TEXT NOT NULL,
    trigger_type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ
);

CREATE TABLE agent_actions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    agent_run_id UUID NOT NULL REFERENCES agent_runs(id),
    action_type TEXT NOT NULL,
    target_system TEXT NOT NULL,
    payload_jsonb JSONB NOT NULL,
    outcome TEXT,
    idempotency_key TEXT NOT NULL UNIQUE
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    actor_type TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    object_ref TEXT NOT NULL,
    payload_jsonb JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_org ON users(org_id);
CREATE INDEX idx_user_roles_org ON user_roles(org_id);
CREATE INDEX idx_sources_org_status ON data_sources(org_id, status);
CREATE INDEX idx_ingestion_runs_status_time ON ingestion_runs(status, started_at);
CREATE INDEX idx_ingestion_runs_org ON ingestion_runs(org_id, started_at);
CREATE INDEX idx_aliases_org ON identity_aliases(org_id);
CREATE INDEX idx_invoices_org_status_due ON invoices(org_id, status, due_date);
CREATE INDEX idx_workflows_org_state ON workflows(org_id, state);
CREATE INDEX idx_workflow_steps_org ON workflow_steps(org_id, started_at);
CREATE INDEX idx_decisions_org_time ON decisions(org_id, decided_at);
CREATE INDEX idx_memory_org_type ON memory_records(org_id, memory_type, created_at);
CREATE INDEX idx_doc_chunks_org_doc ON document_chunks(org_id, document_id, chunk_index);
CREATE INDEX idx_doc_chunks_metadata ON document_chunks USING GIN (metadata_jsonb);
CREATE INDEX idx_doc_chunks_embedding ON document_chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_agent_runs_org_status ON agent_runs(org_id, status, started_at);
CREATE INDEX idx_agent_actions_org ON agent_actions(org_id);
CREATE INDEX idx_audit_org_event_time ON audit_logs(org_id, event_type, created_at);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE users FORCE ROW LEVEL SECURITY;
ALTER TABLE user_roles ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_roles FORCE ROW LEVEL SECURITY;
ALTER TABLE data_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE data_sources FORCE ROW LEVEL SECURITY;
ALTER TABLE ingestion_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ingestion_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE identity_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE identity_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE identity_aliases FORCE ROW LEVEL SECURITY;
ALTER TABLE finance_entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_entities FORCE ROW LEVEL SECURITY;
ALTER TABLE vendors ENABLE ROW LEVEL SECURITY;
ALTER TABLE vendors FORCE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers FORCE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices FORCE ROW LEVEL SECURITY;
ALTER TABLE journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE approvals ENABLE ROW LEVEL SECURITY;
ALTER TABLE approvals FORCE ROW LEVEL SECURITY;
ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflows FORCE ROW LEVEL SECURITY;
ALTER TABLE workflow_steps ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_steps FORCE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions FORCE ROW LEVEL SECURITY;
ALTER TABLE incidents ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidents FORCE ROW LEVEL SECURITY;
ALTER TABLE memory_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE memory_records FORCE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;
ALTER TABLE citations ENABLE ROW LEVEL SECURITY;
ALTER TABLE citations FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_runs FORCE ROW LEVEL SECURITY;
ALTER TABLE agent_actions ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_actions FORCE ROW LEVEL SECURITY;
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;

CREATE POLICY users_org_isolation ON users
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY user_roles_org_isolation ON user_roles
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY sources_org_isolation ON data_sources
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY ingestion_runs_org_isolation ON ingestion_runs
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY profiles_org_isolation ON identity_profiles
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY aliases_org_isolation ON identity_aliases
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY entities_org_isolation ON finance_entities
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY vendors_org_isolation ON vendors
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY customers_org_isolation ON customers
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY invoices_org_isolation ON invoices
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY journals_org_isolation ON journal_entries
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY approvals_org_isolation ON approvals
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY workflows_org_isolation ON workflows
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY workflow_steps_org_isolation ON workflow_steps
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY decisions_org_isolation ON decisions
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY incidents_org_isolation ON incidents
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY memory_org_isolation ON memory_records
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY documents_org_isolation ON documents
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY chunks_org_isolation ON document_chunks
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY citations_org_isolation ON citations
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY agent_runs_org_isolation ON agent_runs
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY agent_actions_org_isolation ON agent_actions
    USING (org_id = current_setting('app.current_org', true)::UUID);
CREATE POLICY audit_org_isolation ON audit_logs
    USING (org_id = current_setting('app.current_org', true)::UUID);

CREATE OR REPLACE FUNCTION prevent_audit_log_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs is append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_logs_no_update
BEFORE UPDATE ON audit_logs
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_log_mutation();

CREATE TRIGGER audit_logs_no_delete
BEFORE DELETE ON audit_logs
FOR EACH ROW
EXECUTE FUNCTION prevent_audit_log_mutation();
