-- Module 3: Platform event bus — event store, idempotency, webhooks, queue jobs

CREATE SCHEMA IF NOT EXISTS platform;

-- Canonical event persistence for replay and audit
CREATE TABLE IF NOT EXISTS platform.event_store (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    event_id UUID NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    event_version VARCHAR(16) NOT NULL DEFAULT 'v1',
    entity_type VARCHAR(64),
    entity_id UUID,
    source VARCHAR(128) NOT NULL,
    trace_id UUID,
    actor_id UUID,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'published',
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (org_id, event_id)
);

CREATE INDEX IF NOT EXISTS platform_event_store_org_type_idx
    ON platform.event_store (org_id, event_type, created_at DESC);

CREATE INDEX IF NOT EXISTS platform_event_store_status_idx
    ON platform.event_store (org_id, status) WHERE status != 'processed';

-- Finance-grade idempotency (ERP writes, event processing)
CREATE TABLE IF NOT EXISTS platform.idempotency_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    idempotency_key VARCHAR(256) NOT NULL,
    scope VARCHAR(64) NOT NULL DEFAULT 'event',
    request_hash TEXT,
    response_payload JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days'),
    UNIQUE (org_id, scope, idempotency_key)
);

CREATE INDEX IF NOT EXISTS platform_idempotency_expires_idx
    ON platform.idempotency_keys (expires_at);

-- Outbound webhook subscriptions
CREATE TABLE IF NOT EXISTS platform.webhook_subscriptions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    target_url TEXT NOT NULL,
    secret VARCHAR(256) NOT NULL,
    event_types TEXT[] NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    rate_limit_per_minute INTEGER NOT NULL DEFAULT 60,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS platform_webhook_subs_org_active_idx
    ON platform.webhook_subscriptions (org_id) WHERE is_active = TRUE;

-- Webhook delivery log
CREATE TABLE IF NOT EXISTS platform.webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    subscription_id UUID NOT NULL REFERENCES platform.webhook_subscriptions(id) ON DELETE CASCADE,
    event_id UUID NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    signature VARCHAR(512),
    delivered_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS platform_webhook_deliveries_retry_idx
    ON platform.webhook_deliveries (org_id, status, next_retry_at)
    WHERE status IN ('pending', 'retrying');

-- Async job tracking (queue observability)
CREATE TABLE IF NOT EXISTS platform.queue_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    org_id UUID NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    queue_name VARCHAR(128) NOT NULL,
    event_id UUID,
    job_type VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'queued',
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 5,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_detail TEXT,
    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS platform_queue_jobs_org_queue_idx
    ON platform.queue_jobs (org_id, queue_name, status, scheduled_at);

ALTER TABLE platform.event_store ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.idempotency_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.webhook_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.webhook_deliveries ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.queue_jobs ENABLE ROW LEVEL SECURITY;

CREATE POLICY platform_event_store_tenant ON platform.event_store
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

CREATE POLICY platform_idempotency_tenant ON platform.idempotency_keys
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

CREATE POLICY platform_webhook_subs_tenant ON platform.webhook_subscriptions
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

CREATE POLICY platform_webhook_deliveries_tenant ON platform.webhook_deliveries
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

CREATE POLICY platform_queue_jobs_tenant ON platform.queue_jobs
    FOR ALL USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
