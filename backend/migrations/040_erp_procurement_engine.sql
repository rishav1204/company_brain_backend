-- Module 15: Procurement Engine (Spend Control System)

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Purchase Requisitions
CREATE TABLE IF NOT EXISTS erp.purchase_requisitions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  pr_number varchar(50) NOT NULL,
  requester_id uuid NULL,
  department_id uuid NULL,
  cost_center_id uuid NULL REFERENCES erp.cost_centers(id) ON DELETE SET NULL,
  status varchar(30) NOT NULL DEFAULT 'draft',
  workflow_approved boolean NOT NULL DEFAULT false,
  required_date date NULL,
  total_amount numeric(18,2) NOT NULL DEFAULT 0,
  description text NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  approved_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.purchase_requisitions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='purchase_requisitions' AND policyname='purchase_requisitions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY purchase_requisitions_org_isolation ON erp.purchase_requisitions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.purchase_requisitions
  ADD CONSTRAINT chk_erp_pr_status
  CHECK (status IN ('draft','submitted','approved','rejected','cancelled','converted_to_po'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_pr_org_number ON erp.purchase_requisitions(org_id, pr_number);
CREATE INDEX IF NOT EXISTS idx_erp_pr_org_status ON erp.purchase_requisitions(org_id, status, created_at DESC);

-- 2) PR Items
CREATE TABLE IF NOT EXISTS erp.purchase_requisition_items (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  pr_id uuid NOT NULL REFERENCES erp.purchase_requisitions(id) ON DELETE CASCADE,
  item_name varchar(255) NOT NULL,
  description text NULL,
  quantity numeric(18,4) NOT NULL DEFAULT 1,
  unit_price numeric(18,2) NOT NULL DEFAULT 0,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  expense_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.purchase_requisition_items ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='purchase_requisition_items' AND policyname='purchase_requisition_items_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY purchase_requisition_items_org_isolation ON erp.purchase_requisition_items
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_pr_items_pr ON erp.purchase_requisition_items(org_id, pr_id);

-- 3) Purchase Orders
CREATE TABLE IF NOT EXISTS erp.purchase_orders (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  po_number varchar(50) NOT NULL,
  vendor_id uuid NOT NULL REFERENCES erp.vendors(id) ON DELETE RESTRICT,
  pr_id uuid NULL REFERENCES erp.purchase_requisitions(id) ON DELETE SET NULL,
  status varchar(30) NOT NULL DEFAULT 'draft',
  workflow_approved boolean NOT NULL DEFAULT false,
  po_date date NOT NULL DEFAULT CURRENT_DATE,
  expected_delivery_date date NULL,
  subtotal numeric(18,2) NOT NULL DEFAULT 0,
  gst_amount numeric(18,2) NOT NULL DEFAULT 0,
  total_amount numeric(18,2) NOT NULL DEFAULT 0,
  sent_at timestamptz NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  approved_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.purchase_orders ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='purchase_orders' AND policyname='purchase_orders_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY purchase_orders_org_isolation ON erp.purchase_orders
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.purchase_orders
  ADD CONSTRAINT chk_erp_po_status
  CHECK (status IN ('draft','pending_approval','approved','sent','partially_received','received','closed','cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_po_org_number ON erp.purchase_orders(org_id, po_number);
CREATE INDEX IF NOT EXISTS idx_erp_po_org_vendor ON erp.purchase_orders(org_id, vendor_id, po_date DESC);
CREATE INDEX IF NOT EXISTS idx_erp_po_org_status ON erp.purchase_orders(org_id, status);

-- 4) PO Items
CREATE TABLE IF NOT EXISTS erp.purchase_order_items (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  po_id uuid NOT NULL REFERENCES erp.purchase_orders(id) ON DELETE CASCADE,
  item_name varchar(255) NOT NULL,
  quantity numeric(18,4) NOT NULL DEFAULT 1,
  received_quantity numeric(18,4) NOT NULL DEFAULT 0,
  unit_price numeric(18,2) NOT NULL DEFAULT 0,
  amount numeric(18,2) NOT NULL DEFAULT 0,
  hsn_sac varchar(16) NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.purchase_order_items ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='purchase_order_items' AND policyname='purchase_order_items_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY purchase_order_items_org_isolation ON erp.purchase_order_items
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_po_items_po ON erp.purchase_order_items(org_id, po_id);

-- 5) Goods Receipts (GRN)
CREATE TABLE IF NOT EXISTS erp.goods_receipts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  grn_number varchar(50) NOT NULL,
  po_id uuid NOT NULL REFERENCES erp.purchase_orders(id) ON DELETE RESTRICT,
  received_by uuid NULL,
  received_date date NOT NULL DEFAULT CURRENT_DATE,
  status varchar(30) NOT NULL DEFAULT 'draft',
  workflow_approved boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.goods_receipts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='goods_receipts' AND policyname='goods_receipts_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY goods_receipts_org_isolation ON erp.goods_receipts
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.goods_receipts
  ADD CONSTRAINT chk_erp_grn_status
  CHECK (status IN ('draft','confirmed','cancelled'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_grn_org_number ON erp.goods_receipts(org_id, grn_number);
CREATE INDEX IF NOT EXISTS idx_erp_grn_po ON erp.goods_receipts(org_id, po_id);

-- 6) GRN Items
CREATE TABLE IF NOT EXISTS erp.goods_receipt_items (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  grn_id uuid NOT NULL REFERENCES erp.goods_receipts(id) ON DELETE CASCADE,
  po_item_id uuid NOT NULL REFERENCES erp.purchase_order_items(id) ON DELETE RESTRICT,
  received_quantity numeric(18,4) NOT NULL DEFAULT 0,
  accepted_quantity numeric(18,4) NOT NULL DEFAULT 0,
  rejected_quantity numeric(18,4) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.goods_receipt_items ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='goods_receipt_items' AND policyname='goods_receipt_items_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY goods_receipt_items_org_isolation ON erp.goods_receipt_items
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_grn_items_grn ON erp.goods_receipt_items(org_id, grn_id);

-- 7) Three-way match records
CREATE TABLE IF NOT EXISTS erp.procurement_matches (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  po_id uuid NOT NULL REFERENCES erp.purchase_orders(id) ON DELETE RESTRICT,
  grn_id uuid NULL REFERENCES erp.goods_receipts(id) ON DELETE SET NULL,
  ap_invoice_id uuid NULL REFERENCES erp.ap_invoices(id) ON DELETE SET NULL,
  match_score numeric(8,4) NOT NULL DEFAULT 0,
  match_status varchar(32) NOT NULL DEFAULT 'pending',
  variance_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  override_by uuid NULL,
  override_reason text NULL,
  workflow_approved boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.procurement_matches ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='procurement_matches' AND policyname='procurement_matches_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY procurement_matches_org_isolation ON erp.procurement_matches
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.procurement_matches
  ADD CONSTRAINT chk_erp_match_status
  CHECK (match_status IN ('pending','matched','matched_within_tolerance','exception','rejected'));

CREATE INDEX IF NOT EXISTS idx_erp_matches_po ON erp.procurement_matches(org_id, po_id);
CREATE INDEX IF NOT EXISTS idx_erp_matches_invoice ON erp.procurement_matches(org_id, ap_invoice_id) WHERE ap_invoice_id IS NOT NULL;

-- 8) Procurement policies
CREATE TABLE IF NOT EXISTS erp.procurement_policies (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  policy_name varchar(128) NOT NULL DEFAULT 'default',
  mandatory_po boolean NOT NULL DEFAULT true,
  mandatory_quotations integer NOT NULL DEFAULT 0,
  preferred_vendors_only boolean NOT NULL DEFAULT false,
  budget_enforcement boolean NOT NULL DEFAULT false,
  approval_thresholds jsonb NOT NULL DEFAULT '[]'::jsonb,
  qty_tolerance_pct numeric(8,4) NOT NULL DEFAULT 0,
  price_tolerance_pct numeric(8,4) NOT NULL DEFAULT 2,
  amount_tolerance_pct numeric(8,4) NOT NULL DEFAULT 2,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.procurement_policies ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='procurement_policies' AND policyname='procurement_policies_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY procurement_policies_org_isolation ON erp.procurement_policies
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_proc_policy_org_name ON erp.procurement_policies(org_id, policy_name);

-- 9) Budget envelopes
CREATE TABLE IF NOT EXISTS erp.budget_envelopes (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  cost_center_id uuid NOT NULL REFERENCES erp.cost_centers(id) ON DELETE RESTRICT,
  fiscal_year_id uuid NULL REFERENCES erp.fiscal_years(id) ON DELETE SET NULL,
  allocated numeric(18,2) NOT NULL DEFAULT 0,
  committed numeric(18,2) NOT NULL DEFAULT 0,
  consumed numeric(18,2) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.budget_envelopes ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='budget_envelopes' AND policyname='budget_envelopes_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY budget_envelopes_org_isolation ON erp.budget_envelopes
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_budget_envelope
  ON erp.budget_envelopes(org_id, cost_center_id, COALESCE(fiscal_year_id, '00000000-0000-0000-0000-000000000000'::uuid));

-- 10) AP invoice linkage
ALTER TABLE erp.ap_invoices
  ADD COLUMN IF NOT EXISTS purchase_order_id uuid NULL REFERENCES erp.purchase_orders(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS goods_receipt_id uuid NULL REFERENCES erp.goods_receipts(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_erp_ap_invoices_po ON erp.ap_invoices(org_id, purchase_order_id) WHERE purchase_order_id IS NOT NULL;

-- IAM permissions
INSERT INTO core.permissions (resource, action, description) VALUES
    ('procurement', 'read', 'View procurement documents'),
    ('procurement', 'create', 'Create PR/PO/GRN'),
    ('procurement', 'approve', 'Approve procurement documents'),
    ('procurement', 'receive', 'Confirm goods receipt'),
    ('procurement', 'match', 'Run three-way match'),
    ('procurement', 'override', 'Override match exceptions'),
    ('procurement', 'admin', 'Procurement administration')
ON CONFLICT (resource, action) DO NOTHING;

INSERT INTO core.roles (id, org_id, name, description, policy_context)
VALUES
  ('a0000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'requester', 'Purchase requisition requester', '{}'::jsonb),
  ('a0000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'buyer', 'Procurement buyer', '{}'::jsonb),
  ('a0000001-0001-4001-8001-000000000003'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'procurement_manager', 'Procurement manager', '{"max_approve_amount": 2500000}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'procurement'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('requester', 'buyer', 'procurement_manager', 'cfo', 'controller', 'finance_manager', 'ap_manager', 'tenant_admin')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'procurement' AND p.action = 'read'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('auditor', 'analyst')
ON CONFLICT DO NOTHING;

-- Workflows
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
  (
    'b1000001-0001-4001-8001-000000000001'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'PR_APPROVAL',
    'Purchase Requisition Approval',
    'PR approval with budget check',
    1,
    '{"steps": [{"key": "manager_approval", "type": "human_approval", "sla_hours": 24}, {"key": "validate", "type": "validation"}]}'::jsonb
  ),
  (
    'b1000001-0001-4001-8001-000000000002'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'PO_APPROVAL',
    'Purchase Order Approval',
    'PO approval with threshold routing',
    1,
    '{"steps": [{"key": "procurement_review", "type": "human_approval", "sla_hours": 48}, {"key": "finance_approval", "type": "human_approval", "sla_hours": 24}, {"key": "validate", "type": "validation"}]}'::jsonb
  ),
  (
    'b1000001-0001-4001-8001-000000000003'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'GRN_CONFIRMATION',
    'Goods Receipt Confirmation',
    'GRN quantity and quality confirmation',
    1,
    '{"steps": [{"key": "receive_confirm", "type": "human_approval", "sla_hours": 24}, {"key": "validate", "type": "validation"}]}'::jsonb
  ),
  (
    'b1000001-0001-4001-8001-000000000004'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'PROCUREMENT_EXCEPTION',
    'Procurement Match Exception',
    'Override three-way match variance',
    1,
    '{"steps": [{"key": "controller_review", "type": "human_approval", "sla_hours": 48}, {"key": "override", "type": "validation"}]}'::jsonb
  )
ON CONFLICT DO NOTHING;

-- Default procurement policy
INSERT INTO erp.procurement_policies (
  id, org_id, policy_name, mandatory_po, approval_thresholds,
  price_tolerance_pct, amount_tolerance_pct, qty_tolerance_pct
)
VALUES (
  'b2000001-0001-4001-8001-000000000001'::uuid,
  '11111111-1111-4111-8111-111111111111'::uuid,
  'default',
  true,
  '[{"max_amount": 50000, "role": "manager"}, {"max_amount": 500000, "role": "department_head"}, {"max_amount": 2500000, "role": "controller"}, {"max_amount": null, "role": "cfo"}]'::jsonb,
  2, 2, 0
)
ON CONFLICT DO NOTHING;
