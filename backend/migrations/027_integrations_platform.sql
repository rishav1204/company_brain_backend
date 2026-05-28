-- Module 7: Integration Platform (connectors, webhooks, sync, ingestion, api keys)

CREATE SCHEMA IF NOT EXISTS integrations;

-- 1) Connectors
CREATE TABLE IF NOT EXISTS integrations.connectors (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  connector_type varchar(32) NOT NULL,   -- erp|bank|gst|email|communication|payment_gateway|ocr|ai|storage
  provider_name varchar(64) NOT NULL,    -- tally|zoho|sap|gstn|icici|razorpayx|ses|twilio|slack|openai|textract|documentai|cloudinary
  status varchar(32) NOT NULL DEFAULT 'active',
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  encrypted_credentials text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE integrations.connectors ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='integrations' AND tablename='connectors' AND policyname='connectors_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY connectors_org_isolation
      ON integrations.connectors
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_integrations_connectors_org ON integrations.connectors(org_id);
CREATE INDEX IF NOT EXISTS idx_integrations_connectors_type ON integrations.connectors(org_id, connector_type, provider_name);

-- 2) Webhook subscriptions
CREATE TABLE IF NOT EXISTS integrations.webhook_subscriptions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  endpoint_url text NOT NULL,
  secret_hash text NOT NULL,
  secret_encrypted text,
  event_types jsonb NOT NULL DEFAULT '[]'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE integrations.webhook_subscriptions ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='integrations' AND tablename='webhook_subscriptions' AND policyname='webhook_subscriptions_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY webhook_subscriptions_org_isolation
      ON integrations.webhook_subscriptions
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_integrations_webhook_subs_org ON integrations.webhook_subscriptions(org_id);
CREATE INDEX IF NOT EXISTS idx_integrations_webhook_subs_active ON integrations.webhook_subscriptions(org_id, is_active);

-- 3) Webhook deliveries
CREATE TABLE IF NOT EXISTS integrations.webhook_deliveries (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  subscription_id uuid NOT NULL REFERENCES integrations.webhook_subscriptions(id) ON DELETE CASCADE,
  event_id uuid,
  event_type varchar(128) NOT NULL,
  payload jsonb NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'pending', -- pending|delivered|retrying|failed|rate_limited
  attempt_count int NOT NULL DEFAULT 0,
  last_error text,
  signature text,
  delivered_at timestamptz,
  next_retry_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  last_attempt_at timestamptz
);

ALTER TABLE integrations.webhook_deliveries ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='integrations' AND tablename='webhook_deliveries' AND policyname='webhook_deliveries_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY webhook_deliveries_org_isolation
      ON integrations.webhook_deliveries
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_integrations_webhook_deliveries_org ON integrations.webhook_deliveries(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_integrations_webhook_deliveries_status ON integrations.webhook_deliveries(org_id, status, next_retry_at);

-- 4) Sync jobs
CREATE TABLE IF NOT EXISTS integrations.sync_jobs (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  connector_id uuid NOT NULL REFERENCES integrations.connectors(id) ON DELETE CASCADE,
  sync_type varchar(64) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'queued', -- queued|running|completed|failed
  started_at timestamptz,
  completed_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE integrations.sync_jobs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='integrations' AND tablename='sync_jobs' AND policyname='sync_jobs_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY sync_jobs_org_isolation
      ON integrations.sync_jobs
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_integrations_sync_jobs_org ON integrations.sync_jobs(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_integrations_sync_jobs_status ON integrations.sync_jobs(org_id, status);

-- 5) Ingestion records
CREATE TABLE IF NOT EXISTS integrations.ingestion_records (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_type varchar(64) NOT NULL, -- email|webhook|erp|bank|gst|manual
  source_reference text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  status varchar(32) NOT NULL DEFAULT 'received', -- received|processed|failed
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE integrations.ingestion_records ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='integrations' AND tablename='ingestion_records' AND policyname='ingestion_records_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ingestion_records_org_isolation
      ON integrations.ingestion_records
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_integrations_ingestion_org ON integrations.ingestion_records(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_integrations_ingestion_source ON integrations.ingestion_records(org_id, source_type);

-- 6) API Keys (hashed; never store raw key)
CREATE TABLE IF NOT EXISTS integrations.api_keys (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  name varchar(128) NOT NULL,
  key_hash text NOT NULL,
  scopes jsonb NOT NULL DEFAULT '[]'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  last_used_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz
);

ALTER TABLE integrations.api_keys ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='integrations' AND tablename='api_keys' AND policyname='api_keys_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY api_keys_org_isolation
      ON integrations.api_keys
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_integrations_api_keys_hash ON integrations.api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_integrations_api_keys_org ON integrations.api_keys(org_id, created_at DESC);

