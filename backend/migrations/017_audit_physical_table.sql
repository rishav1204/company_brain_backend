-- Physical audit.audit_logs table (synced from public.audit_logs on insert)

DROP VIEW IF EXISTS audit.audit_logs;

CREATE TABLE IF NOT EXISTS audit.audit_logs (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    actor_id TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    action VARCHAR(128),
    entity_type VARCHAR(64),
    entity_id UUID,
    event_type TEXT NOT NULL,
    object_ref TEXT NOT NULL,
    before_state JSONB,
    after_state JSONB,
    payload_jsonb JSONB NOT NULL DEFAULT '{}'::jsonb,
    request_id UUID,
    trace_id UUID,
    ip_address INET,
    user_agent TEXT,
    source_service VARCHAR(128),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS audit_logs_org_time_idx ON audit.audit_logs (org_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS audit_logs_entity_idx ON audit.audit_logs (org_id, entity_type, entity_id, timestamp DESC);

INSERT INTO audit.audit_logs (
    id, org_id, actor_id, actor_type, action, entity_type, entity_id,
    event_type, object_ref, before_state, after_state, payload_jsonb,
    request_id, trace_id, ip_address, user_agent, source_service, timestamp
)
SELECT
    id, org_id, actor_id, actor_type,
    COALESCE(action, event_type), entity_type, entity_id,
    event_type, object_ref, before_state, after_state, payload_jsonb,
    request_id, trace_id, ip_address, user_agent, source_service, created_at
FROM public.audit_logs
ON CONFLICT (id) DO NOTHING;

CREATE OR REPLACE FUNCTION audit.sync_public_audit_log()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit.audit_logs (
        id, org_id, actor_id, actor_type, action, entity_type, entity_id,
        event_type, object_ref, before_state, after_state, payload_jsonb,
        request_id, trace_id, ip_address, user_agent, source_service, timestamp
    )
    VALUES (
        NEW.id, NEW.org_id, NEW.actor_id, NEW.actor_type,
        COALESCE(NEW.action, NEW.event_type), NEW.entity_type, NEW.entity_id,
        NEW.event_type, NEW.object_ref, NEW.before_state, NEW.after_state, NEW.payload_jsonb,
        NEW.request_id, NEW.trace_id, NEW.ip_address, NEW.user_agent, NEW.source_service, NEW.created_at
    )
    ON CONFLICT (id) DO NOTHING;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_logs_sync_to_audit_schema ON public.audit_logs;
CREATE TRIGGER audit_logs_sync_to_audit_schema
AFTER INSERT ON public.audit_logs
FOR EACH ROW EXECUTE FUNCTION audit.sync_public_audit_log();

-- Backward-compatible read alias
CREATE OR REPLACE VIEW audit.audit_logs_legacy AS SELECT * FROM audit.audit_logs;

ALTER TABLE audit.audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit.audit_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY audit_logs_physical_org ON audit.audit_logs
    USING (org_id = current_setting('app.current_org', true)::UUID);
