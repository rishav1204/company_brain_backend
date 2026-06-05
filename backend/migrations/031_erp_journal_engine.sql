-- Module 10: Journal Engine + Accounting Transaction Orchestration

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Journals (mutable until posted)
CREATE TABLE IF NOT EXISTS erp.journals (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  journal_number varchar(64) NOT NULL,
  journal_type varchar(32) NOT NULL DEFAULT 'general',
  journal_status varchar(32) NOT NULL DEFAULT 'draft',
  posting_date date NOT NULL,
  description text,
  source_type varchar(64) NULL,
  source_id uuid NULL,
  currency_code varchar(8) NOT NULL DEFAULT 'INR',
  exchange_rate numeric(18,6) NOT NULL DEFAULT 1,
  created_by uuid NULL,
  approved_by uuid NULL,
  posted_by uuid NULL,
  ledger_batch_id uuid NULL REFERENCES erp.ledger_batches(id) ON DELETE SET NULL,
  idempotency_key varchar(128) NULL,
  ai_confidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  posted_at timestamptz NULL
);

ALTER TABLE erp.journals ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='journals' AND policyname='journals_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY journals_org_isolation
      ON erp.journals
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_journals_org_number ON erp.journals(org_id, journal_number);
CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_journals_org_idempotency
  ON erp.journals(org_id, idempotency_key) WHERE idempotency_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_erp_journals_org_status ON erp.journals(org_id, journal_status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_erp_journals_source ON erp.journals(org_id, source_type, source_id);

-- 2) Journal lines
CREATE TABLE IF NOT EXISTS erp.journal_lines (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  journal_id uuid NOT NULL REFERENCES erp.journals(id) ON DELETE CASCADE,
  account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id) ON DELETE RESTRICT,
  line_description text,
  debit_amount numeric(18,2) NOT NULL DEFAULT 0,
  credit_amount numeric(18,2) NOT NULL DEFAULT 0,
  cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  tax_code varchar(32) NULL,
  reference_type varchar(64) NULL,
  reference_id uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.journal_lines ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='journal_lines' AND policyname='journal_lines_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY journal_lines_org_isolation
      ON erp.journal_lines
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.journal_lines
  ADD CONSTRAINT chk_erp_journal_lines_non_negative
  CHECK (debit_amount >= 0 AND credit_amount >= 0);

ALTER TABLE erp.journal_lines
  ADD CONSTRAINT chk_erp_journal_lines_xor_sides
  CHECK ((debit_amount = 0 AND credit_amount > 0) OR (credit_amount = 0 AND debit_amount > 0));

CREATE INDEX IF NOT EXISTS idx_erp_journal_lines_journal ON erp.journal_lines(org_id, journal_id);

-- 3) Recurring journal templates
CREATE TABLE IF NOT EXISTS erp.recurring_journals (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  template_name varchar(128) NOT NULL,
  frequency varchar(32) NOT NULL,
  next_run_date date NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  journal_template jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.recurring_journals ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='recurring_journals' AND policyname='recurring_journals_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY recurring_journals_org_isolation
      ON erp.recurring_journals
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_erp_recurring_journals_org_next ON erp.recurring_journals(org_id, next_run_date, is_active);

-- 4) Journal reversals (tracking)
CREATE TABLE IF NOT EXISTS erp.journal_reversals (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  original_journal_id uuid NOT NULL REFERENCES erp.journals(id) ON DELETE RESTRICT,
  reversal_journal_id uuid NOT NULL REFERENCES erp.journals(id) ON DELETE RESTRICT,
  reversal_reason text,
  reversed_by uuid NULL,
  reversed_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.journal_reversals ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='journal_reversals' AND policyname='journal_reversals_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY journal_reversals_org_isolation
      ON erp.journal_reversals
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_journal_reversals_original ON erp.journal_reversals(org_id, original_journal_id);

-- 5) Accrual entries
CREATE TABLE IF NOT EXISTS erp.accrual_entries (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  accrual_type varchar(64) NOT NULL,
  source_reference uuid NULL,
  accrual_date date NOT NULL,
  reversal_date date NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.accrual_entries ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='accrual_entries' AND policyname='accrual_entries_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY accrual_entries_org_isolation
      ON erp.accrual_entries
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_erp_accrual_entries_org_date ON erp.accrual_entries(org_id, accrual_date DESC);
