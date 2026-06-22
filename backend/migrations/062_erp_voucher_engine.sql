-- Module 11: Voucher Engine (document entry layer; GL truth remains in journals)

CREATE SCHEMA IF NOT EXISTS erp;

CREATE TABLE IF NOT EXISTS erp.voucher_sequences (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  voucher_type varchar(50) NOT NULL,
  financial_year varchar(20) NOT NULL,
  current_sequence bigint NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.voucher_sequences ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'erp' AND tablename = 'voucher_sequences' AND policyname = 'voucher_sequences_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY voucher_sequences_org_isolation ON erp.voucher_sequences
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_voucher_sequences_org_type_fy
  ON erp.voucher_sequences(org_id, COALESCE(company_id, '00000000-0000-0000-0000-000000000000'::uuid), voucher_type, financial_year);

CREATE TABLE IF NOT EXISTS erp.vouchers (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  branch_id uuid NULL,
  fiscal_year_id uuid NULL REFERENCES erp.fiscal_years(id) ON DELETE SET NULL,
  voucher_number varchar(100) NOT NULL,
  voucher_type varchar(50) NOT NULL,
  voucher_date date NOT NULL,
  status varchar(50) NOT NULL DEFAULT 'draft',
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  workflow_id uuid NULL,
  total_amount numeric(18,2) NOT NULL DEFAULT 0,
  narration text,
  reference_type varchar(50) NULL,
  reference_id uuid NULL,
  source_module varchar(32) NULL,
  reversal_of_voucher_id uuid NULL REFERENCES erp.vouchers(id) ON DELETE SET NULL,
  reversed_by_voucher_id uuid NULL,
  idempotency_key varchar(128) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  approved_by uuid NULL,
  posted_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  approved_at timestamptz NULL,
  posted_at timestamptz NULL,
  CONSTRAINT chk_erp_vouchers_status CHECK (
    status IN ('draft', 'validated', 'pending_approval', 'approved', 'journal_generated', 'posted', 'reversed', 'cancelled')
  )
);

ALTER TABLE erp.vouchers ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'erp' AND tablename = 'vouchers' AND policyname = 'vouchers_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY vouchers_org_isolation ON erp.vouchers
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_vouchers_org_number ON erp.vouchers(org_id, voucher_number);
CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_vouchers_org_idempotency
  ON erp.vouchers(org_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_erp_vouchers_org_type_date ON erp.vouchers(org_id, voucher_type, voucher_date DESC);
CREATE INDEX IF NOT EXISTS idx_erp_vouchers_journal ON erp.vouchers(org_id, journal_id);
CREATE INDEX IF NOT EXISTS idx_erp_vouchers_reference ON erp.vouchers(org_id, reference_type, reference_id);

CREATE TABLE IF NOT EXISTS erp.voucher_lines (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  voucher_id uuid NOT NULL REFERENCES erp.vouchers(id) ON DELETE CASCADE,
  line_number integer NOT NULL DEFAULT 1,
  account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id) ON DELETE RESTRICT,
  debit_amount numeric(18,2) NOT NULL DEFAULT 0,
  credit_amount numeric(18,2) NOT NULL DEFAULT 0,
  narration text,
  cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  tax_code varchar(32) NULL,
  party_type varchar(32) NULL,
  party_id uuid NULL,
  reference_type varchar(64) NULL,
  reference_id uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT chk_erp_voucher_line_xor CHECK (
    (debit_amount > 0 AND credit_amount = 0) OR (credit_amount > 0 AND debit_amount = 0)
  )
);

ALTER TABLE erp.voucher_lines ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'erp' AND tablename = 'voucher_lines' AND policyname = 'voucher_lines_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY voucher_lines_org_isolation ON erp.voucher_lines
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_erp_voucher_lines_voucher ON erp.voucher_lines(org_id, voucher_id);

ALTER TABLE erp.journals ADD COLUMN IF NOT EXISTS voucher_id uuid NULL REFERENCES erp.vouchers(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_erp_journals_voucher ON erp.journals(org_id, voucher_id) WHERE voucher_id IS NOT NULL;

ALTER TABLE erp.ap_invoices ADD COLUMN IF NOT EXISTS voucher_id uuid NULL REFERENCES erp.vouchers(id) ON DELETE SET NULL;
ALTER TABLE erp.ar_invoices ADD COLUMN IF NOT EXISTS voucher_id uuid NULL REFERENCES erp.vouchers(id) ON DELETE SET NULL;
