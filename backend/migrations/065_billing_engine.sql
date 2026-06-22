-- Module 37: Billing, Subscription & Usage Governance

CREATE SCHEMA IF NOT EXISTS billing;

CREATE TABLE IF NOT EXISTS billing.plans (
  plan_key varchar(64) PRIMARY KEY,
  name varchar(255) NOT NULL,
  tier int NOT NULL DEFAULT 1,
  monthly_price_inr numeric(12,2) NOT NULL DEFAULT 0,
  included_ai_credits int NOT NULL DEFAULT 0,
  status varchar(32) NOT NULL DEFAULT 'active',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing.plan_features (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_key varchar(64) NOT NULL REFERENCES billing.plans(plan_key) ON DELETE CASCADE,
  feature_code varchar(64) NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  UNIQUE (plan_key, feature_code)
);

CREATE TABLE IF NOT EXISTS billing.plan_limits (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  plan_key varchar(64) NOT NULL REFERENCES billing.plans(plan_key) ON DELETE CASCADE,
  limit_code varchar(64) NOT NULL,
  limit_value bigint NULL,
  UNIQUE (plan_key, limit_code)
);

CREATE TABLE IF NOT EXISTS billing.org_subscriptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  plan_key varchar(64) NOT NULL REFERENCES billing.plans(plan_key),
  status varchar(32) NOT NULL DEFAULT 'active',
  started_at timestamptz NOT NULL DEFAULT now(),
  renews_at timestamptz NULL,
  trial_ends_at timestamptz NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id)
);

CREATE TABLE IF NOT EXISTS billing.org_entitlements (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  feature_code varchar(64) NOT NULL,
  enabled boolean NOT NULL DEFAULT true,
  expires_at timestamptz NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, feature_code)
);

CREATE TABLE IF NOT EXISTS billing.org_credit_wallets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  balance numeric(12,2) NOT NULL DEFAULT 0,
  included_monthly numeric(12,2) NOT NULL DEFAULT 0,
  purchased_balance numeric(12,2) NOT NULL DEFAULT 0,
  period_start date NOT NULL DEFAULT date_trunc('month', now())::date,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id)
);

CREATE TABLE IF NOT EXISTS billing.credit_transactions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  delta numeric(12,2) NOT NULL,
  balance_after numeric(12,2) NOT NULL,
  reason varchar(128) NOT NULL,
  operation_code varchar(64) NULL,
  reference_type varchar(64) NULL,
  reference_id uuid NULL,
  idempotency_key varchar(128) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_billing_credit_tx_idem
  ON billing.credit_transactions(org_id, idempotency_key) WHERE idempotency_key IS NOT NULL;

CREATE TABLE IF NOT EXISTS billing.ai_usage (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  provider varchar(32) NOT NULL,
  model varchar(128) NOT NULL,
  operation_code varchar(64) NULL,
  prompt_tokens int NOT NULL DEFAULT 0,
  completion_tokens int NOT NULL DEFAULT 0,
  total_tokens int NOT NULL DEFAULT 0,
  cost_usd numeric(12,6) NOT NULL DEFAULT 0,
  credits_charged numeric(12,2) NOT NULL DEFAULT 0,
  reference_type varchar(64) NULL,
  reference_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS billing.usage_metrics (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  metric_code varchar(64) NOT NULL,
  period_start date NOT NULL,
  value bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, metric_code, period_start)
);

CREATE TABLE IF NOT EXISTS billing.usage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  metric_code varchar(64) NOT NULL,
  delta bigint NOT NULL DEFAULT 1,
  reference_type varchar(64) NULL,
  reference_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE billing.org_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing.org_entitlements ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing.org_credit_wallets ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing.credit_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing.ai_usage ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing.usage_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE billing.usage_events ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='billing' AND tablename='org_subscriptions' AND policyname='billing_org_subscriptions_org') THEN
    EXECUTE $p$ CREATE POLICY billing_org_subscriptions_org ON billing.org_subscriptions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='billing' AND tablename='org_entitlements' AND policyname='billing_org_entitlements_org') THEN
    EXECUTE $p$ CREATE POLICY billing_org_entitlements_org ON billing.org_entitlements
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='billing' AND tablename='org_credit_wallets' AND policyname='billing_org_credit_wallets_org') THEN
    EXECUTE $p$ CREATE POLICY billing_org_credit_wallets_org ON billing.org_credit_wallets
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='billing' AND tablename='credit_transactions' AND policyname='billing_credit_transactions_org') THEN
    EXECUTE $p$ CREATE POLICY billing_credit_transactions_org ON billing.credit_transactions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='billing' AND tablename='ai_usage' AND policyname='billing_ai_usage_org') THEN
    EXECUTE $p$ CREATE POLICY billing_ai_usage_org ON billing.ai_usage
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='billing' AND tablename='usage_metrics' AND policyname='billing_usage_metrics_org') THEN
    EXECUTE $p$ CREATE POLICY billing_usage_metrics_org ON billing.usage_metrics
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='billing' AND tablename='usage_events' AND policyname='billing_usage_events_org') THEN
    EXECUTE $p$ CREATE POLICY billing_usage_events_org ON billing.usage_events
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_billing_ai_usage_org_created ON billing.ai_usage(org_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_billing_usage_events_org_metric ON billing.usage_events(org_id, metric_code, created_at DESC);

-- Seed plans
INSERT INTO billing.plans (plan_key, name, tier, monthly_price_inr, included_ai_credits) VALUES
  ('finance_starter', 'Finance Starter', 1, 3999, 0),
  ('finance_growth', 'Finance Growth', 2, 12999, 500),
  ('finance_os_pro', 'Finance OS Pro', 3, 29999, 2000),
  ('enterprise', 'Enterprise', 4, 0, 0)
ON CONFLICT (plan_key) DO NOTHING;

-- Starter features
INSERT INTO billing.plan_features (plan_key, feature_code) VALUES
  ('finance_starter', 'coa'), ('finance_starter', 'gl'), ('finance_starter', 'journals'),
  ('finance_starter', 'vouchers'), ('finance_starter', 'ap'), ('finance_starter', 'ar'),
  ('finance_starter', 'gst'), ('finance_starter', 'tds'), ('finance_starter', 'compliance'),
  ('finance_starter', 'banking'), ('finance_starter', 'reporting')
ON CONFLICT DO NOTHING;

-- Growth adds
INSERT INTO billing.plan_features (plan_key, feature_code)
SELECT 'finance_growth', feature_code FROM billing.plan_features WHERE plan_key = 'finance_starter'
ON CONFLICT DO NOTHING;
INSERT INTO billing.plan_features (plan_key, feature_code) VALUES
  ('finance_growth', 'procurement'), ('finance_growth', 'expense'), ('finance_growth', 'assets'),
  ('finance_growth', 'reconciliation'), ('finance_growth', 'treasury'),
  ('finance_growth', 'analytics'), ('finance_growth', 'audit_explorer')
ON CONFLICT DO NOTHING;

-- Pro adds
INSERT INTO billing.plan_features (plan_key, feature_code)
SELECT 'finance_os_pro', feature_code FROM billing.plan_features WHERE plan_key = 'finance_growth'
ON CONFLICT DO NOTHING;
INSERT INTO billing.plan_features (plan_key, feature_code) VALUES
  ('finance_os_pro', 'invoice_ai'), ('finance_os_pro', 'workflow_intelligence'),
  ('finance_os_pro', 'memory'), ('finance_os_pro', 'graph_engine'), ('finance_os_pro', 'agents'),
  ('finance_os_pro', 'forecasting'), ('finance_os_pro', 'api_platform')
ON CONFLICT DO NOTHING;

-- Enterprise adds
INSERT INTO billing.plan_features (plan_key, feature_code)
SELECT 'enterprise', feature_code FROM billing.plan_features WHERE plan_key = 'finance_os_pro'
ON CONFLICT DO NOTHING;
INSERT INTO billing.plan_features (plan_key, feature_code) VALUES
  ('enterprise', 'consolidation'), ('enterprise', 'multi_entity')
ON CONFLICT DO NOTHING;

-- Plan limits
INSERT INTO billing.plan_limits (plan_key, limit_code, limit_value) VALUES
  ('finance_starter', 'max_users', 5), ('finance_starter', 'max_entities', 1), ('finance_starter', 'max_gstins', 1), ('finance_starter', 'api_calls_monthly', 10000),
  ('finance_growth', 'max_users', 25), ('finance_growth', 'max_entities', 3), ('finance_growth', 'max_gstins', 3), ('finance_growth', 'api_calls_monthly', 50000),
  ('finance_os_pro', 'max_users', 100), ('finance_os_pro', 'max_entities', 10), ('finance_os_pro', 'max_gstins', 10), ('finance_os_pro', 'api_calls_monthly', 200000)
ON CONFLICT DO NOTHING;
