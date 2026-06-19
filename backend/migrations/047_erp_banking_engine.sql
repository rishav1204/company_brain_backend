-- Module 22: Banking Engine (canonical bank operations)

ALTER TABLE erp.bank_accounts
  ADD COLUMN IF NOT EXISTS opening_balance numeric(18,2) NOT NULL DEFAULT 0;

ALTER TABLE erp.bank_transactions
  ADD COLUMN IF NOT EXISTS value_date date NULL,
  ADD COLUMN IF NOT EXISTS status varchar(30) NOT NULL DEFAULT 'imported',
  ADD COLUMN IF NOT EXISTS source_type varchar(64) NULL,
  ADD COLUMN IF NOT EXISTS source_id uuid NULL;

CREATE INDEX IF NOT EXISTS idx_erp_bank_tx_source ON erp.bank_transactions(org_id, source_type, source_id);

CREATE TABLE IF NOT EXISTS erp.bank_beneficiaries (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  beneficiary_name varchar(255) NOT NULL,
  account_number_encrypted text NOT NULL,
  ifsc_code varchar(20) NOT NULL,
  bank_name varchar(128) NULL,
  vendor_id uuid NULL REFERENCES erp.vendors(id) ON DELETE SET NULL,
  customer_id uuid NULL,
  verified boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.bank_beneficiaries ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='bank_beneficiaries' AND policyname='bank_beneficiaries_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY bank_beneficiaries_org_isolation ON erp.bank_beneficiaries
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_bank_beneficiaries_vendor ON erp.bank_beneficiaries(org_id, vendor_id);
CREATE INDEX IF NOT EXISTS idx_erp_bank_beneficiaries_customer ON erp.bank_beneficiaries(org_id, customer_id);

ALTER TABLE erp.payment_requests
  ADD COLUMN IF NOT EXISTS beneficiary_id uuid NULL REFERENCES erp.bank_beneficiaries(id) ON DELETE SET NULL;

CREATE TABLE IF NOT EXISTS erp.bank_statement_imports (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  bank_account_id uuid NOT NULL REFERENCES erp.bank_accounts(id) ON DELETE RESTRICT,
  file_format varchar(20) NOT NULL,
  file_hash varchar(64) NULL,
  row_count integer NOT NULL DEFAULT 0,
  imported_count integer NOT NULL DEFAULT 0,
  skipped_count integer NOT NULL DEFAULT 0,
  imported_by uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.bank_statement_imports ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='bank_statement_imports' AND policyname='bank_statement_imports_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY bank_statement_imports_org_isolation ON erp.bank_statement_imports
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- Migrate verified vendor bank accounts into canonical beneficiaries
INSERT INTO erp.bank_beneficiaries (id, org_id, beneficiary_name, account_number_encrypted, ifsc_code, bank_name, vendor_id, verified, metadata)
SELECT
  v.id,
  v.org_id,
  COALESCE(v.bank_name, 'Vendor Beneficiary'),
  v.account_number_encrypted,
  v.ifsc_code,
  v.bank_name,
  v.vendor_id,
  v.verified,
  jsonb_build_object('migrated_from', 'vendor_bank_accounts', 'is_primary', v.is_primary)
FROM erp.vendor_bank_accounts v
ON CONFLICT (id) DO NOTHING;
