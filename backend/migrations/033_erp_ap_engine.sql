-- Module 11: Accounts Payable Automation Engine

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Vendors
CREATE TABLE IF NOT EXISTS erp.vendors (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  vendor_code varchar(32) NOT NULL,
  vendor_name varchar(256) NOT NULL,
  gstin varchar(15) NULL,
  pan varchar(10) NULL,
  email varchar(256) NULL,
  phone varchar(32) NULL,
  payment_terms_days integer NOT NULL DEFAULT 30,
  status varchar(32) NOT NULL DEFAULT 'active',
  payable_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.vendors ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='vendors' AND policyname='vendors_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY vendors_org_isolation
      ON erp.vendors
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_vendors_org_code ON erp.vendors(org_id, vendor_code);
CREATE INDEX IF NOT EXISTS idx_erp_vendors_org_gstin ON erp.vendors(org_id, gstin) WHERE gstin IS NOT NULL;

-- 2) Vendor bank accounts (encrypted account number at app layer)
CREATE TABLE IF NOT EXISTS erp.vendor_bank_accounts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  vendor_id uuid NOT NULL REFERENCES erp.vendors(id) ON DELETE CASCADE,
  account_number_encrypted text NOT NULL,
  ifsc_code varchar(11) NOT NULL,
  bank_name varchar(128) NULL,
  is_primary boolean NOT NULL DEFAULT false,
  verified boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.vendor_bank_accounts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='vendor_bank_accounts' AND policyname='vendor_bank_accounts_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY vendor_bank_accounts_org_isolation
      ON erp.vendor_bank_accounts
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_erp_vendor_bank_vendor ON erp.vendor_bank_accounts(org_id, vendor_id);

-- 3) AP Invoices
CREATE TABLE IF NOT EXISTS erp.ap_invoices (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  vendor_id uuid NOT NULL REFERENCES erp.vendors(id) ON DELETE RESTRICT,
  invoice_number varchar(64) NOT NULL,
  invoice_date date NOT NULL,
  due_date date NOT NULL,
  invoice_amount numeric(18,2) NOT NULL DEFAULT 0,
  gst_amount numeric(18,2) NOT NULL DEFAULT 0,
  total_amount numeric(18,2) NOT NULL DEFAULT 0,
  paid_amount numeric(18,2) NOT NULL DEFAULT 0,
  status varchar(32) NOT NULL DEFAULT 'draft',
  source_document_id uuid NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  duplicate_checksum varchar(128) NULL,
  ai_confidence jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  approved_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ap_invoices ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ap_invoices' AND policyname='ap_invoices_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ap_invoices_org_isolation
      ON erp.ap_invoices
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.ap_invoices
  ADD CONSTRAINT chk_erp_ap_invoices_status
  CHECK (status IN ('draft','pending_review','pending_approval','approved','partially_paid','paid','cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_ap_invoices_duplicate
  ON erp.ap_invoices(org_id, vendor_id, duplicate_checksum)
  WHERE duplicate_checksum IS NOT NULL AND status NOT IN ('cancelled');
CREATE INDEX IF NOT EXISTS idx_erp_ap_invoices_org_status ON erp.ap_invoices(org_id, status, due_date);
CREATE INDEX IF NOT EXISTS idx_erp_ap_invoices_vendor ON erp.ap_invoices(org_id, vendor_id, invoice_date DESC);

-- 4) AP Invoice lines (expense / GST breakdown)
CREATE TABLE IF NOT EXISTS erp.ap_invoice_lines (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  invoice_id uuid NOT NULL REFERENCES erp.ap_invoices(id) ON DELETE CASCADE,
  account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  line_type varchar(32) NOT NULL DEFAULT 'expense',
  description text,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  tax_code varchar(32) NULL,
  cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ap_invoice_lines ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ap_invoice_lines' AND policyname='ap_invoice_lines_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ap_invoice_lines_org_isolation
      ON erp.ap_invoice_lines
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS idx_erp_ap_invoice_lines_invoice ON erp.ap_invoice_lines(org_id, invoice_id);

-- 5) AP Payments
CREATE TABLE IF NOT EXISTS erp.ap_payments (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  vendor_id uuid NOT NULL REFERENCES erp.vendors(id) ON DELETE RESTRICT,
  payment_reference varchar(64) NOT NULL,
  payment_date date NOT NULL,
  amount numeric(18,2) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'scheduled',
  bank_account_id uuid NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ap_payments ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ap_payments' AND policyname='ap_payments_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ap_payments_org_isolation
      ON erp.ap_payments
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

ALTER TABLE erp.ap_payments
  ADD CONSTRAINT chk_erp_ap_payments_status
  CHECK (status IN ('scheduled','processing','completed','failed','cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_ap_payments_ref ON erp.ap_payments(org_id, payment_reference);
CREATE INDEX IF NOT EXISTS idx_erp_ap_payments_org_status ON erp.ap_payments(org_id, status, payment_date);

-- 6) Payment allocations (payment → invoice)
CREATE TABLE IF NOT EXISTS erp.ap_payment_allocations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  payment_id uuid NOT NULL REFERENCES erp.ap_payments(id) ON DELETE CASCADE,
  invoice_id uuid NOT NULL REFERENCES erp.ap_invoices(id) ON DELETE RESTRICT,
  amount numeric(18,2) NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.ap_payment_allocations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='ap_payment_allocations' AND policyname='ap_payment_allocations_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY ap_payment_allocations_org_isolation
      ON erp.ap_payment_allocations
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

-- 7) Vendor balances (projection)
CREATE TABLE IF NOT EXISTS erp.vendor_balances (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  vendor_id uuid NOT NULL REFERENCES erp.vendors(id) ON DELETE CASCADE,
  outstanding_amount numeric(18,2) NOT NULL DEFAULT 0,
  last_updated timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.vendor_balances ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname='erp' AND tablename='vendor_balances' AND policyname='vendor_balances_org_isolation'
  ) THEN
    EXECUTE $p$
      CREATE POLICY vendor_balances_org_isolation
      ON erp.vendor_balances
      USING (org_id::text = current_setting('app.current_org', true))
    $p$;
  END IF;
END
$$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_vendor_balances_vendor ON erp.vendor_balances(org_id, vendor_id);
