-- Module 36: API + Webhook Platform — gateway extensions (reuse integrations.* + platform.*)

-- A) Extend integrations.api_keys
ALTER TABLE integrations.api_keys
  ADD COLUMN IF NOT EXISTS ip_allowlist jsonb NOT NULL DEFAULT '[]'::jsonb,
  ADD COLUMN IF NOT EXISTS rate_limit_per_minute int NOT NULL DEFAULT 100,
  ADD COLUMN IF NOT EXISTS rate_limit_per_hour int NOT NULL DEFAULT 1000,
  ADD COLUMN IF NOT EXISTS key_tier varchar(32) NOT NULL DEFAULT 'partner';

-- B) Extend integrations.webhook_subscriptions
ALTER TABLE integrations.webhook_subscriptions
  ADD COLUMN IF NOT EXISTS name varchar(255),
  ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

-- C) Extend integrations.webhook_deliveries
ALTER TABLE integrations.webhook_deliveries
  ADD COLUMN IF NOT EXISTS response_code int,
  ADD COLUMN IF NOT EXISTS response_body text;

-- D) API request audit log (feeds M33 via audit_service)
CREATE TABLE IF NOT EXISTS platform.api_request_log (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  api_key_id uuid,
  method varchar(16),
  path text,
  status_code int,
  scope_used jsonb NOT NULL DEFAULT '[]'::jsonb,
  idempotency_key varchar(256),
  ip_address inet,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE platform.api_request_log ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='platform' AND tablename='api_request_log' AND policyname='api_request_log_org'
  ) THEN
    EXECUTE $p$
      CREATE POLICY api_request_log_org ON platform.api_request_log
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_platform_api_request_log_org
  ON platform.api_request_log (org_id, created_at DESC);

-- E) Event stream adapter registry (v1 stub for Kafka/EventBridge/SQS/RabbitMQ)
CREATE TABLE IF NOT EXISTS platform.event_stream_adapters (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  adapter_type varchar(32) NOT NULL,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE platform.event_stream_adapters ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='platform' AND tablename='event_stream_adapters' AND policyname='event_stream_adapters_org'
  ) THEN
    EXECUTE $p$
      CREATE POLICY event_stream_adapters_org ON platform.event_stream_adapters
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_platform_event_stream_adapters_org
  ON platform.event_stream_adapters (org_id, adapter_type);

-- F) Legacy webhook deprecation note:
-- platform.webhook_subscriptions / platform.webhook_deliveries (migration 015) are deprecated.
-- New subscriptions MUST use integrations.webhook_subscriptions (migration 027).
