-- Module 14: GST, Taxation & Compliance Engine (core GST)

CREATE SCHEMA IF NOT EXISTS erp;

CREATE TABLE IF NOT EXISTS erp.gst_registrations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  gstin varchar(15) NOT NULL,
  legal_name varchar(256) NOT NULL,
  trade_name varchar(256) NULL,
  state_code varchar(2) NOT NULL,
  registration_type varchar(32) NOT NULL DEFAULT 'regular',
  status varchar(32) NOT NULL DEFAULT 'active',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, gstin)
);

ALTER TABLE erp.gst_registrations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='gst_registrations' AND policyname='gst_registrations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY gst_registrations_org_isolation ON erp.gst_registrations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.gst_transactions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_type varchar(64) NOT NULL,
  source_id uuid NOT NULL,
  gst_type varchar(32) NOT NULL,
  taxable_value numeric(18,2) NOT NULL DEFAULT 0,
  cgst_amount numeric(18,2) NOT NULL DEFAULT 0,
  sgst_amount numeric(18,2) NOT NULL DEFAULT 0,
  igst_amount numeric(18,2) NOT NULL DEFAULT 0,
  cess_amount numeric(18,2) NOT NULL DEFAULT 0,
  gst_rate numeric(8,4) NULL,
  invoice_date date NOT NULL,
  party_gstin varchar(15) NULL,
  place_of_supply varchar(2) NULL,
  hsn_sac varchar(16) NULL,
  return_period varchar(7) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, source_type, source_id, gst_type)
);

ALTER TABLE erp.gst_transactions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='gst_transactions' AND policyname='gst_transactions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY gst_transactions_org_isolation ON erp.gst_transactions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_gst_tx_org_period ON erp.gst_transactions(org_id, return_period);
CREATE INDEX IF NOT EXISTS idx_erp_gst_tx_org_source ON erp.gst_transactions(org_id, source_type, source_id);

CREATE TABLE IF NOT EXISTS erp.itc_blocked_rules (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  category varchar(64) NOT NULL,
  description text NULL,
  block_percentage numeric(5,2) NOT NULL DEFAULT 100,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.itc_blocked_rules ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='itc_blocked_rules' AND policyname='itc_blocked_rules_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY itc_blocked_rules_org_isolation ON erp.itc_blocked_rules
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.itc_ledger (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  gst_transaction_id uuid NOT NULL REFERENCES erp.gst_transactions(id) ON DELETE CASCADE,
  itc_type varchar(16) NOT NULL,
  eligible_amount numeric(18,2) NOT NULL DEFAULT 0,
  claimed_amount numeric(18,2) NOT NULL DEFAULT 0,
  status varchar(32) NOT NULL DEFAULT 'eligible',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.itc_ledger ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='itc_ledger' AND policyname='itc_ledger_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY itc_ledger_org_isolation ON erp.itc_ledger
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_itc_ledger_tx ON erp.itc_ledger(org_id, gst_transaction_id);

CREATE TABLE IF NOT EXISTS erp.gst_returns (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  return_type varchar(16) NOT NULL,
  return_period varchar(7) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'draft',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  filed_at timestamptz NULL,
  filed_by uuid NULL,
  workflow_approved boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, return_type, return_period)
);

ALTER TABLE erp.gst_returns ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='gst_returns' AND policyname='gst_returns_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY gst_returns_org_isolation ON erp.gst_returns
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.gstr2b_imports (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  return_period varchar(7) NOT NULL,
  vendor_gstin varchar(15) NOT NULL,
  invoice_ref varchar(128) NOT NULL,
  invoice_date date NULL,
  taxable_value numeric(18,2) NOT NULL DEFAULT 0,
  cgst_amount numeric(18,2) NOT NULL DEFAULT 0,
  sgst_amount numeric(18,2) NOT NULL DEFAULT 0,
  igst_amount numeric(18,2) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.gstr2b_imports ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='gstr2b_imports' AND policyname='gstr2b_imports_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY gstr2b_imports_org_isolation ON erp.gstr2b_imports
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_gstr2b_org_period ON erp.gstr2b_imports(org_id, return_period);

CREATE TABLE IF NOT EXISTS erp.gst_reconciliations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  gst_transaction_id uuid NULL REFERENCES erp.gst_transactions(id) ON DELETE SET NULL,
  gstr2b_import_id uuid NULL REFERENCES erp.gstr2b_imports(id) ON DELETE SET NULL,
  return_period varchar(7) NOT NULL,
  match_status varchar(32) NOT NULL DEFAULT 'pending',
  confidence_score numeric(5,4) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.gst_reconciliations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='gst_reconciliations' AND policyname='gst_reconciliations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY gst_reconciliations_org_isolation ON erp.gst_reconciliations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;
