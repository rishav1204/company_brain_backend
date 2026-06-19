-- Module 13: Banking, Treasury & Cash Management Engine

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Bank accounts (org-owned; account number encrypted at app layer)
CREATE TABLE IF NOT EXISTS erp.bank_accounts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  account_name varchar(256) NOT NULL,
  bank_name varchar(128) NOT NULL,
  account_number_encrypted text NOT NULL,
  ifsc_code varchar(11) NOT NULL,
  currency_code varchar(8) NOT NULL DEFAULT 'INR',
  account_type varchar(32) NOT NULL DEFAULT 'current',
  ledger_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.bank_accounts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='bank_accounts' AND policyname='bank_accounts_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY bank_accounts_org_isolation
      ON erp.bank_accounts
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.bank_accounts
  ADD CONSTRAINT chk_erp_bank_accounts_type
  CHECK (account_type IN ('current','savings','cash_credit','overdraft','escrow','petty_cash'));

CREATE INDEX IF NOT EXISTS idx_erp_bank_accounts_org_active ON erp.bank_accounts(org_id, is_active);
CREATE INDEX IF NOT EXISTS idx_erp_bank_accounts_ledger ON erp.bank_accounts(org_id, ledger_account_id);

-- 2) Bank transactions (canonical cash movements)
CREATE TABLE IF NOT EXISTS erp.bank_transactions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  bank_account_id uuid NOT NULL REFERENCES erp.bank_accounts(id) ON DELETE RESTRICT,
  transaction_reference varchar(128) NOT NULL,
  transaction_date date NOT NULL,
  amount numeric(18,2) NOT NULL,
  transaction_type varchar(16) NOT NULL,
  currency_code varchar(8) NOT NULL DEFAULT 'INR',
  description text NULL,
  source varchar(32) NOT NULL DEFAULT 'manual_import',
  counterparty_ref varchar(256) NULL,
  reconciliation_status varchar(32) NOT NULL DEFAULT 'unreconciled',
  import_idempotency_key varchar(128) NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.bank_transactions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='bank_transactions' AND policyname='bank_transactions_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY bank_transactions_org_isolation
      ON erp.bank_transactions
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.bank_transactions
  ADD CONSTRAINT chk_erp_bank_tx_type CHECK (transaction_type IN ('credit','debit'));
ALTER TABLE erp.bank_transactions
  ADD CONSTRAINT chk_erp_bank_tx_source
  CHECK (source IN ('bank_feed','manual_import','api','payment_gateway'));
ALTER TABLE erp.bank_transactions
  ADD CONSTRAINT chk_erp_bank_tx_recon_status
  CHECK (reconciliation_status IN ('unreconciled','suggested','matched','exception','manual_review'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_bank_tx_import_idem
  ON erp.bank_transactions(org_id, import_idempotency_key) WHERE import_idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_erp_bank_tx_account_date ON erp.bank_transactions(org_id, bank_account_id, transaction_date DESC);
CREATE INDEX IF NOT EXISTS idx_erp_bank_tx_recon ON erp.bank_transactions(org_id, reconciliation_status);

-- 3) Payment requests (treasury payment orchestration)
CREATE TABLE IF NOT EXISTS erp.payment_requests (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  payment_type varchar(32) NOT NULL,
  beneficiary_type varchar(32) NOT NULL,
  beneficiary_ref uuid NULL,
  bank_account_id uuid NOT NULL REFERENCES erp.bank_accounts(id) ON DELETE RESTRICT,
  amount numeric(18,2) NOT NULL,
  currency_code varchar(8) NOT NULL DEFAULT 'INR',
  status varchar(32) NOT NULL DEFAULT 'draft',
  approval_status varchar(32) NOT NULL DEFAULT 'pending',
  scheduled_date date NULL,
  source_type varchar(64) NULL,
  source_id uuid NULL,
  payment_reference varchar(64) NOT NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  approved_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.payment_requests ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='payment_requests' AND policyname='payment_requests_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY payment_requests_org_isolation
      ON erp.payment_requests
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.payment_requests
  ADD CONSTRAINT chk_erp_payment_requests_type
  CHECK (payment_type IN ('vendor_payment','salary','tax_payment','refund','internal_transfer'));
ALTER TABLE erp.payment_requests
  ADD CONSTRAINT chk_erp_payment_requests_beneficiary_type
  CHECK (beneficiary_type IN ('vendor','customer','internal','tax_authority','employee'));
ALTER TABLE erp.payment_requests
  ADD CONSTRAINT chk_erp_payment_requests_status
  CHECK (status IN ('draft','pending_approval','approved','processing','completed','failed','cancelled'));
ALTER TABLE erp.payment_requests
  ADD CONSTRAINT chk_erp_payment_requests_approval
  CHECK (approval_status IN ('pending','approved','rejected'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_payment_requests_ref ON erp.payment_requests(org_id, payment_reference);
CREATE INDEX IF NOT EXISTS idx_erp_payment_requests_status ON erp.payment_requests(org_id, status, scheduled_date);

-- 4) Bank reconciliations
CREATE TABLE IF NOT EXISTS erp.bank_reconciliations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  bank_transaction_id uuid NOT NULL REFERENCES erp.bank_transactions(id) ON DELETE CASCADE,
  ledger_entry_id uuid NULL REFERENCES erp.ledger_entries(id) ON DELETE SET NULL,
  match_type varchar(32) NOT NULL DEFAULT 'suggested',
  confidence_score numeric(5,4) NOT NULL DEFAULT 0,
  status varchar(32) NOT NULL DEFAULT 'suggested',
  approved_by uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.bank_reconciliations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='bank_reconciliations' AND policyname='bank_reconciliations_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY bank_reconciliations_org_isolation
      ON erp.bank_reconciliations
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.bank_reconciliations
  ADD CONSTRAINT chk_erp_bank_recon_match_type
  CHECK (match_type IN ('matched','suggested','exception','manual_review'));
ALTER TABLE erp.bank_reconciliations
  ADD CONSTRAINT chk_erp_bank_recon_status
  CHECK (status IN ('matched','suggested','exception','manual_review'));

CREATE INDEX IF NOT EXISTS idx_erp_bank_recon_tx ON erp.bank_reconciliations(org_id, bank_transaction_id);
CREATE INDEX IF NOT EXISTS idx_erp_bank_recon_status ON erp.bank_reconciliations(org_id, status);

-- Seed treasury workflow definitions (benchmark org)
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
    (
        'd0000001-0001-4001-8001-000000000020'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'TREASURY_PAYMENT_APPROVAL',
        'Treasury Payment Approval',
        'Large treasury payment approval with CFO/dual approval thresholds',
        1,
        '{"steps": [{"key": "treasury_review", "type": "human_approval", "sla_hours": 24}, {"key": "payment_execution", "type": "payment_execution"}], "conditional_approvals": [{"when": {"amount_gte": 500000}, "role": "cfo"}, {"when": {"amount_gte": 2500000}, "role": "dual_approval"}]}'::jsonb
    )
ON CONFLICT DO NOTHING;
