-- Module 16: Expense Management Engine (Employee Spend Governance)

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Expense claims
CREATE TABLE IF NOT EXISTS erp.expense_claims (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  employee_id uuid NOT NULL,
  claim_number varchar(50) NOT NULL,
  claim_date date NOT NULL DEFAULT CURRENT_DATE,
  expense_category varchar(50) NULL,
  total_amount numeric(18,2) NOT NULL DEFAULT 0,
  status varchar(30) NOT NULL DEFAULT 'draft',
  workflow_approved boolean NOT NULL DEFAULT false,
  submitted_at timestamptz NULL,
  approved_at timestamptz NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  reimbursement_payment_id uuid NULL,
  cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  department_id uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  approved_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.expense_claims ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='expense_claims' AND policyname='expense_claims_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY expense_claims_org_isolation ON erp.expense_claims
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.expense_claims
  ADD CONSTRAINT chk_erp_expense_claim_status
  CHECK (status IN ('draft','submitted','under_review','approved','rejected','paid','cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_expense_claim_number ON erp.expense_claims(org_id, claim_number);
CREATE INDEX IF NOT EXISTS idx_erp_expense_claims_employee ON erp.expense_claims(org_id, employee_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_erp_expense_claims_status ON erp.expense_claims(org_id, status);

-- 2) Claim items
CREATE TABLE IF NOT EXISTS erp.expense_claim_items (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  claim_id uuid NOT NULL REFERENCES erp.expense_claims(id) ON DELETE CASCADE,
  expense_date date NOT NULL,
  expense_type varchar(50) NOT NULL DEFAULT 'miscellaneous',
  merchant_name varchar(255) NULL,
  description text NULL,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  gst_amount numeric(18,2) NOT NULL DEFAULT 0,
  receipt_id uuid NULL,
  expense_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.expense_claim_items ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='expense_claim_items' AND policyname='expense_claim_items_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY expense_claim_items_org_isolation ON erp.expense_claim_items
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.expense_claim_items
  ADD CONSTRAINT chk_erp_expense_item_type
  CHECK (expense_type IN ('travel','hotel','meal','fuel','internet','mobile','office_supplies','training','miscellaneous'));

CREATE INDEX IF NOT EXISTS idx_erp_expense_items_claim ON erp.expense_claim_items(org_id, claim_id);

-- 3) Expense receipts (OCR-linked)
CREATE TABLE IF NOT EXISTS erp.expense_receipts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  claim_item_id uuid NULL REFERENCES erp.expense_claim_items(id) ON DELETE SET NULL,
  document_id uuid NULL,
  ocr_status varchar(30) NOT NULL DEFAULT 'pending',
  merchant_name varchar(255) NULL,
  receipt_date date NULL,
  receipt_amount numeric(18,2) NULL,
  confidence_score numeric(5,2) NULL,
  receipt_hash varchar(128) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.expense_receipts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='expense_receipts' AND policyname='expense_receipts_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY expense_receipts_org_isolation ON erp.expense_receipts
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_expense_receipts_hash ON erp.expense_receipts(org_id, receipt_hash) WHERE receipt_hash IS NOT NULL;

-- Link claim items to receipts
ALTER TABLE erp.expense_claim_items
  DROP CONSTRAINT IF EXISTS expense_claim_items_receipt_id_fkey;
ALTER TABLE erp.expense_claim_items
  ADD CONSTRAINT expense_claim_items_receipt_id_fkey
  FOREIGN KEY (receipt_id) REFERENCES erp.expense_receipts(id) ON DELETE SET NULL;

-- 4) Expense policies
CREATE TABLE IF NOT EXISTS erp.expense_policies (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  policy_name varchar(255) NOT NULL DEFAULT 'default',
  expense_type varchar(50) NOT NULL,
  max_amount numeric(18,2) NULL,
  max_per_day numeric(18,2) NULL,
  per_diem_rate numeric(18,2) NULL,
  requires_receipt boolean NOT NULL DEFAULT true,
  receipt_mandatory_above numeric(18,2) NOT NULL DEFAULT 500,
  requires_manager_approval boolean NOT NULL DEFAULT true,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.expense_policies ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='expense_policies' AND policyname='expense_policies_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY expense_policies_org_isolation ON erp.expense_policies
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_expense_policy_type ON erp.expense_policies(org_id, policy_name, expense_type);

-- 5) Policy violations audit
CREATE TABLE IF NOT EXISTS erp.expense_policy_violations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  claim_id uuid NOT NULL REFERENCES erp.expense_claims(id) ON DELETE CASCADE,
  policy_id uuid NULL REFERENCES erp.expense_policies(id) ON DELETE SET NULL,
  violation_type varchar(64) NOT NULL,
  severity varchar(32) NOT NULL DEFAULT 'warning',
  message text NULL,
  override_by uuid NULL,
  workflow_approved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.expense_policy_violations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='expense_policy_violations' AND policyname='expense_policy_violations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY expense_policy_violations_org_isolation ON erp.expense_policy_violations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 6) Employee advances
CREATE TABLE IF NOT EXISTS erp.employee_advances (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  employee_id uuid NOT NULL,
  advance_amount numeric(18,2) NOT NULL DEFAULT 0,
  settled_amount numeric(18,2) NOT NULL DEFAULT 0,
  issued_date date NOT NULL DEFAULT CURRENT_DATE,
  settlement_due_date date NULL,
  status varchar(30) NOT NULL DEFAULT 'issued',
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.employee_advances ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='employee_advances' AND policyname='employee_advances_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY employee_advances_org_isolation ON erp.employee_advances
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.employee_advances
  ADD CONSTRAINT chk_erp_employee_advance_status
  CHECK (status IN ('issued','partially_adjusted','adjusted','expired'));

-- 7) Employee bank accounts
CREATE TABLE IF NOT EXISTS erp.employee_bank_accounts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  employee_id uuid NOT NULL,
  account_number_encrypted text NOT NULL,
  ifsc_code varchar(11) NOT NULL,
  bank_name varchar(128) NULL,
  is_primary boolean NOT NULL DEFAULT false,
  verified boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.employee_bank_accounts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='employee_bank_accounts' AND policyname='employee_bank_accounts_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY employee_bank_accounts_org_isolation ON erp.employee_bank_accounts
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_employee_bank ON erp.employee_bank_accounts(org_id, employee_id);

-- 8) Corporate card transactions (future-proof)
CREATE TABLE IF NOT EXISTS erp.corporate_card_transactions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  employee_id uuid NULL,
  card_last4 varchar(4) NULL,
  transaction_date date NOT NULL,
  amount numeric(18,2) NOT NULL,
  merchant_name varchar(255) NULL,
  allocation_status varchar(32) NOT NULL DEFAULT 'unallocated',
  claim_item_id uuid NULL REFERENCES erp.expense_claim_items(id) ON DELETE SET NULL,
  bank_feed_ref varchar(128) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.corporate_card_transactions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='corporate_card_transactions' AND policyname='corporate_card_transactions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY corporate_card_transactions_org_isolation ON erp.corporate_card_transactions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.corporate_card_transactions
  ADD CONSTRAINT chk_erp_card_allocation
  CHECK (allocation_status IN ('unallocated','allocated','personal'));

-- Treasury: add reimbursement payment type
ALTER TABLE erp.payment_requests DROP CONSTRAINT IF EXISTS payment_requests_payment_type_check;
ALTER TABLE erp.payment_requests
  ADD CONSTRAINT payment_requests_payment_type_check
  CHECK (payment_type IN ('vendor_payment','salary','tax_payment','refund','internal_transfer','reimbursement'));

-- IAM permissions
INSERT INTO core.permissions (resource, action, description) VALUES
    ('expense', 'read', 'View expense claims'),
    ('expense', 'create', 'Create and submit expense claims'),
    ('expense', 'approve', 'Approve expense claims'),
    ('expense', 'reimburse', 'Schedule and execute reimbursements'),
    ('expense', 'policy', 'Manage expense policies'),
    ('expense', 'override', 'Override policy violations'),
    ('expense', 'admin', 'Expense administration')
ON CONFLICT (resource, action) DO NOTHING;

INSERT INTO core.roles (id, org_id, name, description, policy_context)
VALUES
  ('c1000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'employee', 'Expense claim submitter', '{}'::jsonb),
  ('c1000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'expense_manager', 'Expense and reimbursement manager', '{"max_approve_amount": 500000}'::jsonb),
  ('c1000001-0001-4001-8001-000000000003'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'finance_reviewer', 'Finance expense reviewer', '{}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'expense'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('employee', 'expense_manager', 'finance_reviewer', 'finance_manager', 'controller', 'cfo', 'tenant_admin')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'expense' AND p.action = 'read'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('auditor', 'analyst', 'manager')
ON CONFLICT DO NOTHING;

-- Workflows
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
  (
    'c2000001-0001-4001-8001-000000000001'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'EXPENSE_CLAIM_APPROVAL',
    'Expense Claim Approval',
    'Employee expense claim approval with threshold routing',
    1,
    '{"steps": [{"key": "manager_review", "type": "human_approval", "sla_hours": 48}, {"key": "finance_review", "type": "human_approval", "sla_hours": 24}, {"key": "validate", "type": "validation"}]}'::jsonb
  ),
  (
    'c2000001-0001-4001-8001-000000000002'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'EXPENSE_POLICY_EXCEPTION',
    'Expense Policy Exception',
    'Override expense policy violation',
    1,
    '{"steps": [{"key": "controller_review", "type": "human_approval", "sla_hours": 48}, {"key": "override", "type": "validation"}]}'::jsonb
  ),
  (
    'c2000001-0001-4001-8001-000000000003'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'EXPENSE_REIMBURSEMENT',
    'Expense Reimbursement Payment',
    'Reimbursement payout approval',
    1,
    '{"steps": [{"key": "finance_approval", "type": "human_approval", "sla_hours": 24}, {"key": "payment", "type": "validation"}]}'::jsonb
  )
ON CONFLICT DO NOTHING;

-- Default expense policies
INSERT INTO erp.expense_policies (id, org_id, policy_name, expense_type, max_amount, max_per_day, per_diem_rate, receipt_mandatory_above)
VALUES
  ('c3000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'default', 'meal', 1000, 1000, NULL, 500),
  ('c3000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'default', 'hotel', 5000, NULL, 5000, 500),
  ('c3000001-0001-4001-8001-000000000003'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'default', 'travel', 2500, 2500, NULL, 500),
  ('c3000001-0001-4001-8001-000000000004'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'default', 'miscellaneous', NULL, NULL, NULL, 500)
ON CONFLICT DO NOTHING;
