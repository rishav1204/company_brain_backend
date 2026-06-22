-- Module 30: Forecasting Engine (Finance OS) — read-only predictions & audit

CREATE SCHEMA IF NOT EXISTS finance_os;

CREATE TABLE IF NOT EXISTS finance_os.forecasts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  forecast_type varchar(50) NOT NULL,
  horizon_days int NOT NULL,
  as_of_date date NOT NULL,
  forecast_date date NOT NULL,
  forecast_value numeric(18,2) NOT NULL,
  confidence_score numeric(5,2) NOT NULL DEFAULT 0,
  confidence_band varchar(16) NOT NULL DEFAULT 'low',
  model_version varchar(50) NOT NULL DEFAULT 'rule_v1',
  inputs jsonb NOT NULL DEFAULT '{}'::jsonb,
  generated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.forecasts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='forecasts'
      AND policyname='forecasts_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY forecasts_org_isolation ON finance_os.forecasts
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_forecasts_org_type_date
  ON finance_os.forecasts(org_id, forecast_type, as_of_date DESC, horizon_days, forecast_date);
CREATE INDEX IF NOT EXISTS idx_fin_os_forecasts_org_generated
  ON finance_os.forecasts(org_id, generated_at DESC);

CREATE TABLE IF NOT EXISTS finance_os.forecast_explanations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  forecast_id uuid NOT NULL REFERENCES finance_os.forecasts(id) ON DELETE CASCADE,
  explanation text NOT NULL,
  evidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.forecast_explanations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='forecast_explanations'
      AND policyname='forecast_explanations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY forecast_explanations_org_isolation ON finance_os.forecast_explanations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_forecast_expl_org_forecast
  ON finance_os.forecast_explanations(org_id, forecast_id);

CREATE TABLE IF NOT EXISTS finance_os.forecast_accuracy (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  forecast_id uuid NOT NULL REFERENCES finance_os.forecasts(id) ON DELETE CASCADE,
  actual_value numeric(18,2) NOT NULL,
  forecast_value numeric(18,2) NOT NULL,
  variance_percent numeric(10,2) NOT NULL,
  calculated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.forecast_accuracy ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='forecast_accuracy'
      AND policyname='forecast_accuracy_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY forecast_accuracy_org_isolation ON finance_os.forecast_accuracy
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_forecast_accuracy_org_forecast
  ON finance_os.forecast_accuracy(org_id, forecast_id);
