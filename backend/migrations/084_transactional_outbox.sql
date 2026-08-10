-- RQ-18: Transactional outbox for crash-safe event publishing

CREATE TABLE IF NOT EXISTS platform.event_outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    event_id uuid NOT NULL,
    queue_name varchar(128) NOT NULL,
    envelope jsonb NOT NULL,
    status varchar(32) NOT NULL DEFAULT 'pending', -- pending|publishing|published|failed
    attempt_count int NOT NULL DEFAULT 0,
    next_attempt_at timestamptz NULL,
    last_error text NULL,
    locked_by varchar(128) NULL,
    locked_until timestamptz NULL,
    published_at timestamptz NULL,
    redis_stream_id varchar(64) NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, event_id)
);

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_pending
    ON platform.event_outbox (status, next_attempt_at, created_at);

CREATE INDEX IF NOT EXISTS idx_platform_event_outbox_org_status
    ON platform.event_outbox (org_id, status, created_at DESC);

ALTER TABLE platform.event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.event_outbox FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS platform_event_outbox_tenant ON platform.event_outbox;
CREATE POLICY platform_event_outbox_tenant ON platform.event_outbox
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

