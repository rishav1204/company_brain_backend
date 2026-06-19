-- Module 23: Reconciliation Engine

ALTER TABLE erp.bank_reconciliations
  ADD COLUMN IF NOT EXISTS matched_entity_type varchar(50) NULL,
  ADD COLUMN IF NOT EXISTS matched_entity_id uuid NULL,
  ADD COLUMN IF NOT EXISTS approved_at timestamptz NULL;

ALTER TABLE erp.bank_reconciliations DROP CONSTRAINT IF EXISTS chk_erp_bank_recon_match_type;
ALTER TABLE erp.bank_reconciliations DROP CONSTRAINT IF EXISTS chk_erp_bank_recon_status;

ALTER TABLE erp.bank_reconciliations
  ADD CONSTRAINT chk_erp_bank_recon_match_type
  CHECK (match_type IN ('matched','suggested','exception','manual_review','partial'));

ALTER TABLE erp.bank_reconciliations
  ADD CONSTRAINT chk_erp_bank_recon_status
  CHECK (status IN (
    'unmatched','suggested','pending_approval','matched',
    'partially_matched','rejected','exception','manual_review'
  ));

ALTER TABLE erp.bank_transactions DROP CONSTRAINT IF EXISTS chk_erp_bank_tx_recon_status;
ALTER TABLE erp.bank_transactions
  ADD CONSTRAINT chk_erp_bank_tx_recon_status
  CHECK (reconciliation_status IN (
    'unreconciled','suggested','pending_approval','matched',
    'partially_matched','rejected','exception','manual_review'
  ));

CREATE TABLE IF NOT EXISTS erp.reconciliation_match_lines (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  reconciliation_id uuid NOT NULL REFERENCES erp.bank_reconciliations(id) ON DELETE CASCADE,
  bank_transaction_id uuid NULL REFERENCES erp.bank_transactions(id) ON DELETE SET NULL,
  entity_type varchar(50) NOT NULL,
  entity_id uuid NOT NULL,
  allocated_amount numeric(18,2) NOT NULL DEFAULT 0,
  remaining_amount numeric(18,2) NOT NULL DEFAULT 0,
  match_group_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.reconciliation_match_lines ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='reconciliation_match_lines'
      AND policyname='reconciliation_match_lines_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY reconciliation_match_lines_org_isolation ON erp.reconciliation_match_lines
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_recon_match_lines_recon ON erp.reconciliation_match_lines(org_id, reconciliation_id);
CREATE INDEX IF NOT EXISTS idx_erp_recon_match_lines_entity ON erp.reconciliation_match_lines(org_id, entity_type, entity_id);

CREATE TABLE IF NOT EXISTS erp.reconciliation_exceptions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  bank_transaction_id uuid NULL REFERENCES erp.bank_transactions(id) ON DELETE SET NULL,
  reconciliation_id uuid NULL REFERENCES erp.bank_reconciliations(id) ON DELETE SET NULL,
  exception_type varchar(50) NOT NULL,
  description text NULL,
  status varchar(30) NOT NULL DEFAULT 'open',
  assigned_to uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.reconciliation_exceptions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='reconciliation_exceptions'
      AND policyname='reconciliation_exceptions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY reconciliation_exceptions_org_isolation ON erp.reconciliation_exceptions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.reconciliation_exceptions
  ADD CONSTRAINT chk_erp_recon_exception_status
  CHECK (status IN ('open','assigned','resolved','dismissed'));

CREATE INDEX IF NOT EXISTS idx_erp_recon_exceptions_status ON erp.reconciliation_exceptions(org_id, status);

CREATE TABLE IF NOT EXISTS erp.reconciliation_rules (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  rule_name varchar(255) NOT NULL,
  rule_type varchar(50) NOT NULL,
  weight numeric(5,2) NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.reconciliation_rules ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='reconciliation_rules'
      AND policyname='reconciliation_rules_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY reconciliation_rules_org_isolation ON erp.reconciliation_rules
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_recon_rules_org_type ON erp.reconciliation_rules(org_id, rule_type);

CREATE TABLE IF NOT EXISTS erp.reconciliation_adjustments (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  bank_transaction_id uuid NULL REFERENCES erp.bank_transactions(id) ON DELETE SET NULL,
  reconciliation_id uuid NULL REFERENCES erp.bank_reconciliations(id) ON DELETE SET NULL,
  adjustment_type varchar(50) NOT NULL,
  amount numeric(18,2) NOT NULL,
  expense_account_id uuid NULL,
  bank_account_id uuid NULL,
  status varchar(30) NOT NULL DEFAULT 'draft',
  journal_id uuid NULL,
  approved_by uuid NULL,
  approved_at timestamptz NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.reconciliation_adjustments ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='reconciliation_adjustments'
      AND policyname='reconciliation_adjustments_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY reconciliation_adjustments_org_isolation ON erp.reconciliation_adjustments
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.reconciliation_adjustments
  ADD CONSTRAINT chk_erp_recon_adjustment_status
  CHECK (status IN ('draft','pending_approval','approved','posted','rejected'));

CREATE INDEX IF NOT EXISTS idx_erp_recon_adjustments_status ON erp.reconciliation_adjustments(org_id, status);

-- Backfill matched_entity from metadata where present
UPDATE erp.bank_reconciliations
SET
  matched_entity_type = COALESCE(matched_entity_type, metadata->>'match_target_type'),
  matched_entity_id = COALESCE(
    matched_entity_id,
    NULLIF(metadata->>'match_target_id', '')::uuid
  )
WHERE metadata ? 'match_target_type';
