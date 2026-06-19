-- Module 20: TDS/TCS gap closure — rules, challans, enriched transactions

ALTER TABLE erp.tds_sections
  ADD COLUMN IF NOT EXISTS section_name varchar(256) NULL,
  ADD COLUMN IF NOT EXISTS rate_pan numeric(8,4) NULL,
  ADD COLUMN IF NOT EXISTS rate_no_pan numeric(8,4) NULL;

UPDATE erp.tds_sections
SET
  section_name = COALESCE(section_name, description),
  rate_pan = COALESCE(rate_pan, rate),
  rate_no_pan = COALESCE(rate_no_pan, GREATEST(rate * 2, 20))
WHERE rate_pan IS NULL OR rate_no_pan IS NULL;

CREATE TABLE IF NOT EXISTS erp.tds_rules (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  section_code varchar(16) NOT NULL,
  threshold_amount numeric(18,2) NOT NULL DEFAULT 0,
  rate_pan numeric(8,4) NOT NULL,
  rate_no_pan numeric(8,4) NOT NULL,
  applicable_entity varchar(64) NOT NULL DEFAULT 'vendor',
  payment_type varchar(64) NULL,
  expense_category varchar(64) NULL,
  pan_required boolean NOT NULL DEFAULT false,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, section_code, payment_type, expense_category)
);

ALTER TABLE erp.tds_rules ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tds_rules' AND policyname='tds_rules_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_rules_org_isolation ON erp.tds_rules
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.tds_transactions
  ADD COLUMN IF NOT EXISTS vendor_id uuid NULL,
  ADD COLUMN IF NOT EXISTS invoice_id uuid NULL,
  ADD COLUMN IF NOT EXISTS payment_id uuid NULL,
  ADD COLUMN IF NOT EXISTS challan_id uuid NULL,
  ADD COLUMN IF NOT EXISTS financial_year varchar(16) NULL,
  ADD COLUMN IF NOT EXISTS quarter varchar(4) NULL,
  ADD COLUMN IF NOT EXISTS deduction_date date NULL;

CREATE TABLE IF NOT EXISTS erp.tds_challans (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  tax_type varchar(16) NOT NULL DEFAULT 'TDS',
  challan_no varchar(64) NULL,
  bsr_code varchar(32) NULL,
  cin varchar(64) NULL,
  deposit_date date NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  quarter varchar(4) NULL,
  financial_year varchar(16) NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.tds_challans ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tds_challans' AND policyname='tds_challans_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_challans_org_isolation ON erp.tds_challans
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.tcs_transactions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_type varchar(64) NOT NULL,
  source_id uuid NOT NULL,
  customer_id uuid NULL,
  section_code varchar(16) NOT NULL DEFAULT '206C',
  gross_amount numeric(18,2) NOT NULL,
  tcs_amount numeric(18,2) NOT NULL,
  total_collected numeric(18,2) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'calculated',
  return_period varchar(7) NULL,
  financial_year varchar(16) NULL,
  quarter varchar(4) NULL,
  challan_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, source_type, source_id, section_code)
);

ALTER TABLE erp.tcs_transactions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tcs_transactions' AND policyname='tcs_transactions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tcs_transactions_org_isolation ON erp.tcs_transactions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.tds_reconciliations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_type varchar(32) NOT NULL DEFAULT '26AS',
  financial_year varchar(16) NOT NULL,
  quarter varchar(4) NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  result jsonb NOT NULL DEFAULT '{}'::jsonb,
  status varchar(32) NOT NULL DEFAULT 'completed',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.tds_reconciliations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tds_reconciliations' AND policyname='tds_reconciliations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_reconciliations_org_isolation ON erp.tds_reconciliations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- Seed additional sections for benchmark org
INSERT INTO erp.tds_sections (id, org_id, section_code, section_name, description, rate, rate_pan, rate_no_pan, threshold_amount)
VALUES
  ('a0000001-0001-4001-8001-000000000106'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194A', 'Interest', 'Interest other than securities', 10.0, 10.0, 20.0, 40000),
  ('a0000001-0001-4001-8001-000000000107'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194IB', 'Rent Individual', 'Rent paid to individual/HUF', 5.0, 5.0, 20.0, 600000),
  ('a0000001-0001-4001-8001-000000000108'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194M', 'Professional Payment', 'Contract/professional to individual', 5.0, 5.0, 20.0, 5000000),
  ('a0000001-0001-4001-8001-000000000109'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '206C', 'TCS Sale of Goods', 'Tax collected at source on sale', 0.1, 0.1, 1.0, 5000000)
ON CONFLICT DO NOTHING;

UPDATE erp.tds_sections SET section_name = description WHERE section_name IS NULL;

-- Seed TDS rules from sections for benchmark org
INSERT INTO erp.tds_rules (id, org_id, section_code, threshold_amount, rate_pan, rate_no_pan, applicable_entity, payment_type)
SELECT
  gen_random_uuid(),
  s.org_id,
  s.section_code,
  s.threshold_amount,
  COALESCE(s.rate_pan, s.rate),
  COALESCE(s.rate_no_pan, GREATEST(s.rate * 2, 20)),
  'vendor',
  CASE s.section_code
    WHEN '194C' THEN 'contract'
    WHEN '194J' THEN 'professional'
    WHEN '194H' THEN 'commission'
    WHEN '194I' THEN 'rent'
    WHEN '194Q' THEN 'goods'
    WHEN '194A' THEN 'interest'
    WHEN '194IB' THEN 'rent_individual'
    WHEN '194M' THEN 'professional_individual'
    ELSE NULL
  END
FROM erp.tds_sections s
WHERE s.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND s.section_code <> '206C'
ON CONFLICT DO NOTHING;

INSERT INTO erp.tds_rules (id, org_id, section_code, threshold_amount, rate_pan, rate_no_pan, applicable_entity, payment_type)
VALUES
  ('b0000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '206C', 5000000, 0.1, 1.0, 'customer', 'sale')
ON CONFLICT DO NOTHING;
