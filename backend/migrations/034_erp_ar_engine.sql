-- Module 12: Accounts Receivable Automation Engine

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Customers
CREATE TABLE IF NOT EXISTS erp.customers (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  customer_code varchar(32) NOT NULL,
  customer_name varchar(256) NOT NULL,
  customer_type varchar(32) NOT NULL DEFAULT 'corporate',
  gstin varchar(15) NULL,
  pan varchar(10) NULL,
  email varchar(256) NULL,
  phone varchar(32) NULL,
  credit_limit numeric(18,2) NOT NULL DEFAULT 0,
  payment_terms_days integer NOT NULL DEFAULT 30,
  receivable_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  revenue_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  status varchar(32) NOT NULL DEFAULT 'active',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.customers ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='customers' AND policyname='customers_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY customers_org_isolation
      ON erp.customers
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.customers
  ADD CONSTRAINT chk_erp_customers_type
  CHECK (customer_type IN ('retail','corporate','government','export','internal'));

ALTER TABLE erp.customers
  ADD CONSTRAINT chk_erp_customers_status
  CHECK (status IN ('active','inactive','blocked'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_customers_org_code ON erp.customers(org_id, customer_code);
CREATE INDEX IF NOT EXISTS idx_erp_customers_org_gstin ON erp.customers(org_id, gstin) WHERE gstin IS NOT NULL;

-- 2) Customer addresses (billing, shipping, place of supply)
CREATE TABLE IF NOT EXISTS erp.customer_addresses (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  customer_id uuid NOT NULL REFERENCES erp.customers(id) ON DELETE CASCADE,
  address_type varchar(32) NOT NULL DEFAULT 'billing',
  line1 varchar(256) NOT NULL,
  line2 varchar(256) NULL,
  city varchar(128) NULL,
  state_code varchar(8) NULL,
  postal_code varchar(16) NULL,
  country_code varchar(4) NOT NULL DEFAULT 'IN',
  place_of_supply varchar(64) NULL,
  is_primary boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.customer_addresses ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='customer_addresses' AND policyname='customer_addresses_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY customer_addresses_org_isolation
      ON erp.customer_addresses
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.customer_addresses
  ADD CONSTRAINT chk_erp_customer_addresses_type
  CHECK (address_type IN ('billing','shipping','place_of_supply'));

CREATE INDEX IF NOT EXISTS idx_erp_customer_addresses_customer ON erp.customer_addresses(org_id, customer_id);

-- 3) AR Invoices (sales invoices)
CREATE TABLE IF NOT EXISTS erp.ar_invoices (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  customer_id uuid NOT NULL REFERENCES erp.customers(id) ON DELETE RESTRICT,
  invoice_number varchar(64) NOT NULL,
  invoice_date date NOT NULL,
  due_date date NOT NULL,
  subtotal numeric(18,2) NOT NULL DEFAULT 0,
  gst_amount numeric(18,2) NOT NULL DEFAULT 0,
  total_amount numeric(18,2) NOT NULL DEFAULT 0,
  paid_amount numeric(18,2) NOT NULL DEFAULT 0,
  status varchar(32) NOT NULL DEFAULT 'draft',
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  revenue_recognition jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  issued_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ar_invoices ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ar_invoices' AND policyname='ar_invoices_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ar_invoices_org_isolation
      ON erp.ar_invoices
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.ar_invoices
  ADD CONSTRAINT chk_erp_ar_invoices_status
  CHECK (status IN ('draft','issued','partially_paid','paid','overdue','cancelled','written_off'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_ar_invoices_number ON erp.ar_invoices(org_id, customer_id, invoice_number);
CREATE INDEX IF NOT EXISTS idx_erp_ar_invoices_org_status ON erp.ar_invoices(org_id, status, due_date);

-- 4) AR Invoice lines
CREATE TABLE IF NOT EXISTS erp.ar_invoice_lines (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  invoice_id uuid NOT NULL REFERENCES erp.ar_invoices(id) ON DELETE CASCADE,
  line_type varchar(32) NOT NULL DEFAULT 'revenue',
  account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  description varchar(512) NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  tax_code varchar(32) NULL,
  cost_center_id uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ar_invoice_lines ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ar_invoice_lines' AND policyname='ar_invoice_lines_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ar_invoice_lines_org_isolation
      ON erp.ar_invoice_lines
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_erp_ar_invoice_lines_invoice ON erp.ar_invoice_lines(org_id, invoice_id);

-- 5) Customer receipts
CREATE TABLE IF NOT EXISTS erp.customer_receipts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  customer_id uuid NOT NULL REFERENCES erp.customers(id) ON DELETE RESTRICT,
  receipt_number varchar(64) NOT NULL,
  receipt_date date NOT NULL,
  amount numeric(18,2) NOT NULL,
  payment_mode varchar(32) NOT NULL DEFAULT 'bank_transfer',
  bank_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  status varchar(32) NOT NULL DEFAULT 'recorded',
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.customer_receipts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='customer_receipts' AND policyname='customer_receipts_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY customer_receipts_org_isolation
      ON erp.customer_receipts
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.customer_receipts
  ADD CONSTRAINT chk_erp_customer_receipts_mode
  CHECK (payment_mode IN ('bank_transfer','upi','cash','cheque','card','gateway'));

ALTER TABLE erp.customer_receipts
  ADD CONSTRAINT chk_erp_customer_receipts_status
  CHECK (status IN ('recorded','processing','completed','failed','cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_customer_receipts_number ON erp.customer_receipts(org_id, receipt_number);
CREATE INDEX IF NOT EXISTS idx_erp_customer_receipts_customer ON erp.customer_receipts(org_id, customer_id, receipt_date);

-- 6) Receipt allocations
CREATE TABLE IF NOT EXISTS erp.customer_receipt_allocations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  receipt_id uuid NOT NULL REFERENCES erp.customer_receipts(id) ON DELETE CASCADE,
  invoice_id uuid NOT NULL REFERENCES erp.ar_invoices(id) ON DELETE RESTRICT,
  amount numeric(18,2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.customer_receipt_allocations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='customer_receipt_allocations' AND policyname='customer_receipt_allocations_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY customer_receipt_allocations_org_isolation
      ON erp.customer_receipt_allocations
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

-- 7) Customer balance projection
CREATE TABLE IF NOT EXISTS erp.customer_balances (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  customer_id uuid NOT NULL REFERENCES erp.customers(id) ON DELETE CASCADE,
  outstanding_amount numeric(18,2) NOT NULL DEFAULT 0,
  credit_used numeric(18,2) NOT NULL DEFAULT 0,
  last_updated timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, customer_id)
);

ALTER TABLE erp.customer_balances ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='customer_balances' AND policyname='customer_balances_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY customer_balances_org_isolation
      ON erp.customer_balances
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

-- Seed AR workflow definitions (benchmark org)
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
    (
        'd0000001-0001-4001-8001-000000000010'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'AR_INVOICE_APPROVAL',
        'AR Sales Invoice Approval',
        'Credit-exceeded or high-value sales invoice approval',
        1,
        '{"steps": [{"key": "credit_review", "type": "human_approval", "sla_hours": 24}, {"key": "issue", "type": "validation"}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000011'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'AR_CREDIT_LIMIT_APPROVAL',
        'AR Credit Limit Approval',
        'Customer credit limit increase approval',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 48}]}'::jsonb
    ),
    (
        'd0000001-0001-4001-8001-000000000012'::uuid,
        '11111111-1111-4111-8111-111111111111'::uuid,
        'AR_WRITE_OFF_APPROVAL',
        'AR Write-off Approval',
        'Bad debt write-off maker-checker approval',
        1,
        '{"steps": [{"key": "approval", "type": "human_approval", "sla_hours": 72}, {"key": "post", "type": "validation"}]}'::jsonb
    )
ON CONFLICT DO NOTHING;
