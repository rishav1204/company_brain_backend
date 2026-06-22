-- Module 32: Finance Analytics & BI Engine — executive KPI snapshots (never scan ERP at request time)

CREATE SCHEMA IF NOT EXISTS finance_analytics;

CREATE TABLE IF NOT EXISTS finance_analytics.kpi_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  kpi_code varchar(100) NOT NULL,
  kpi_value numeric(18,4) NOT NULL DEFAULT 0,
  snapshot_date date NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, kpi_code, snapshot_date)
);

ALTER TABLE finance_analytics.kpi_snapshots ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_analytics' AND tablename='kpi_snapshots'
      AND policyname='kpi_snapshots_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY kpi_snapshots_org_isolation ON finance_analytics.kpi_snapshots
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_analytics_kpi_org_code_date
  ON finance_analytics.kpi_snapshots(org_id, kpi_code, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS finance_analytics.kpi_trends (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  kpi_code varchar(100) NOT NULL,
  trend_direction varchar(20) NOT NULL,
  trend_percent numeric(10,2) NOT NULL DEFAULT 0,
  period_key varchar(32) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, kpi_code, period_key)
);

ALTER TABLE finance_analytics.kpi_trends ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_analytics' AND tablename='kpi_trends'
      AND policyname='kpi_trends_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY kpi_trends_org_isolation ON finance_analytics.kpi_trends
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_analytics_trends_org_code_created
  ON finance_analytics.kpi_trends(org_id, kpi_code, created_at DESC);

CREATE TABLE IF NOT EXISTS finance_analytics.executive_insights (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  insight_type varchar(100) NOT NULL,
  title text NOT NULL,
  description text NOT NULL,
  severity varchar(20) NOT NULL DEFAULT 'info',
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  generated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_analytics.executive_insights ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_analytics' AND tablename='executive_insights'
      AND policyname='executive_insights_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY executive_insights_org_isolation ON finance_analytics.executive_insights
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_analytics_insights_org_sev_gen
  ON finance_analytics.executive_insights(org_id, severity, generated_at DESC);

CREATE TABLE IF NOT EXISTS finance_analytics.dashboard_snapshots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  snapshot_date date NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, snapshot_date)
);

ALTER TABLE finance_analytics.dashboard_snapshots ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_analytics' AND tablename='dashboard_snapshots'
      AND policyname='dashboard_snapshots_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY dashboard_snapshots_org_isolation ON finance_analytics.dashboard_snapshots
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_analytics_dashboard_org_date
  ON finance_analytics.dashboard_snapshots(org_id, snapshot_date DESC);

CREATE TABLE IF NOT EXISTS finance_analytics.anomaly_flags (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  anomaly_type varchar(100) NOT NULL,
  severity varchar(20) NOT NULL DEFAULT 'medium',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  detected_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_analytics.anomaly_flags ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_analytics' AND tablename='anomaly_flags'
      AND policyname='anomaly_flags_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY anomaly_flags_org_isolation ON finance_analytics.anomaly_flags
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_analytics_anomaly_org_detected
  ON finance_analytics.anomaly_flags(org_id, detected_at DESC);
