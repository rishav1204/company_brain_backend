-- Module 31: ERP Reporting Engine — pre-aggregated snapshots (never scan transactional tables at request time)

CREATE SCHEMA IF NOT EXISTS erp_reporting;

CREATE TABLE IF NOT EXISTS erp_reporting.trial_balance_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  fiscal_period_id uuid NOT NULL,
  account_id uuid NOT NULL,
  account_code varchar(64),
  account_name varchar(256),
  debit_total numeric(18,2) NOT NULL DEFAULT 0,
  credit_total numeric(18,2) NOT NULL DEFAULT 0,
  balance numeric(18,2) NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, fiscal_period_id, account_id)
);

ALTER TABLE erp_reporting.trial_balance_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='trial_balance_mv'
      AND policyname='trial_balance_mv_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY trial_balance_mv_org_isolation ON erp_reporting.trial_balance_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_tb_org_period
  ON erp_reporting.trial_balance_mv(org_id, fiscal_period_id);

CREATE TABLE IF NOT EXISTS erp_reporting.pnl_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  fiscal_period_id uuid NOT NULL,
  reporting_category varchar(128) NOT NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, fiscal_period_id, reporting_category)
);

ALTER TABLE erp_reporting.pnl_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='pnl_mv'
      AND policyname='pnl_mv_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY pnl_mv_org_isolation ON erp_reporting.pnl_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_pnl_org_period
  ON erp_reporting.pnl_mv(org_id, fiscal_period_id);

CREATE TABLE IF NOT EXISTS erp_reporting.balance_sheet_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  fiscal_period_id uuid NOT NULL,
  reporting_category varchar(128) NOT NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, fiscal_period_id, reporting_category)
);

ALTER TABLE erp_reporting.balance_sheet_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='balance_sheet_mv'
      AND policyname='balance_sheet_mv_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY balance_sheet_mv_org_isolation ON erp_reporting.balance_sheet_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_bs_org_period
  ON erp_reporting.balance_sheet_mv(org_id, fiscal_period_id);

CREATE TABLE IF NOT EXISTS erp_reporting.ap_aging_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  as_of_date date NOT NULL,
  vendor_id uuid NOT NULL,
  vendor_name varchar(256),
  bucket_current numeric(18,2) NOT NULL DEFAULT 0,
  bucket_1_30 numeric(18,2) NOT NULL DEFAULT 0,
  bucket_31_60 numeric(18,2) NOT NULL DEFAULT 0,
  bucket_61_90 numeric(18,2) NOT NULL DEFAULT 0,
  bucket_90_plus numeric(18,2) NOT NULL DEFAULT 0,
  total_outstanding numeric(18,2) NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, as_of_date, vendor_id)
);

ALTER TABLE erp_reporting.ap_aging_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='ap_aging_mv'
      AND policyname='ap_aging_mv_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY ap_aging_mv_org_isolation ON erp_reporting.ap_aging_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_ap_aging_org_date
  ON erp_reporting.ap_aging_mv(org_id, as_of_date);

CREATE TABLE IF NOT EXISTS erp_reporting.ar_aging_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  as_of_date date NOT NULL,
  customer_id uuid NOT NULL,
  customer_name varchar(256),
  bucket_current numeric(18,2) NOT NULL DEFAULT 0,
  bucket_1_30 numeric(18,2) NOT NULL DEFAULT 0,
  bucket_31_60 numeric(18,2) NOT NULL DEFAULT 0,
  bucket_61_90 numeric(18,2) NOT NULL DEFAULT 0,
  bucket_90_plus numeric(18,2) NOT NULL DEFAULT 0,
  total_outstanding numeric(18,2) NOT NULL DEFAULT 0,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, as_of_date, customer_id)
);

ALTER TABLE erp_reporting.ar_aging_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='ar_aging_mv'
      AND policyname='ar_aging_mv_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY ar_aging_mv_org_isolation ON erp_reporting.ar_aging_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_ar_aging_org_date
  ON erp_reporting.ar_aging_mv(org_id, as_of_date);

CREATE TABLE IF NOT EXISTS erp_reporting.gst_summary_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  return_period varchar(16) NOT NULL,
  return_type varchar(32) NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, return_period, return_type)
);

ALTER TABLE erp_reporting.gst_summary_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='gst_summary_mv'
      AND policyname='gst_summary_mv_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY gst_summary_mv_org_isolation ON erp_reporting.gst_summary_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_gst_org_period
  ON erp_reporting.gst_summary_mv(org_id, return_period);

CREATE TABLE IF NOT EXISTS erp_reporting.tds_summary_mv (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL,
  return_period varchar(16) NOT NULL,
  form_type varchar(32) NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  refreshed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, return_period, form_type)
);

ALTER TABLE erp_reporting.tds_summary_mv ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='tds_summary_mv'
      AND policyname='tds_summary_mv_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_summary_mv_org_isolation ON erp_reporting.tds_summary_mv
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_tds_org_period
  ON erp_reporting.tds_summary_mv(org_id, return_period);

CREATE TABLE IF NOT EXISTS erp_reporting.report_runs (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  report_type varchar(64) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'queued',
  filters jsonb NOT NULL DEFAULT '{}'::jsonb,
  file_ref text,
  error_message text,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

ALTER TABLE erp_reporting.report_runs ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='report_runs'
      AND policyname='report_runs_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY report_runs_org_isolation ON erp_reporting.report_runs
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_runs_org_type_created
  ON erp_reporting.report_runs(org_id, report_type, created_at DESC);

CREATE TABLE IF NOT EXISTS erp_reporting.report_snapshots (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  report_type varchar(64) NOT NULL,
  period_key varchar(64) NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp_reporting.report_snapshots ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp_reporting' AND tablename='report_snapshots'
      AND policyname='report_snapshots_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY report_snapshots_org_isolation ON erp_reporting.report_snapshots
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_rpt_snapshots_org_type_created
  ON erp_reporting.report_snapshots(org_id, report_type, created_at DESC);
