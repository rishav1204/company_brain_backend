-- Module 18: Inventory & Stock Accounting Engine (Finance-Centric)

CREATE SCHEMA IF NOT EXISTS erp;

-- 1) Inventory items
CREATE TABLE IF NOT EXISTS erp.inventory_items (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  item_code varchar(50) NOT NULL,
  item_name varchar(255) NOT NULL,
  item_type varchar(50) NOT NULL DEFAULT 'trading_goods',
  uom varchar(20) NOT NULL DEFAULT 'EA',
  valuation_method varchar(30) NOT NULL DEFAULT 'weighted_average',
  inventory_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  cogs_account_id uuid NULL REFERENCES erp.chart_of_accounts(id) ON DELETE SET NULL,
  status varchar(30) NOT NULL DEFAULT 'active',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inventory_items ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inventory_items' AND policyname='inventory_items_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inventory_items_org_isolation ON erp.inventory_items
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.inventory_items
  ADD CONSTRAINT chk_erp_inventory_item_type
  CHECK (item_type IN ('raw_material','finished_goods','trading_goods','consumables','service'));

ALTER TABLE erp.inventory_items
  ADD CONSTRAINT chk_erp_inventory_item_status
  CHECK (status IN ('active','inactive'));

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_inventory_item_code ON erp.inventory_items(org_id, item_code);

-- 2) Warehouses
CREATE TABLE IF NOT EXISTS erp.warehouses (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  warehouse_code varchar(50) NOT NULL,
  warehouse_name varchar(255) NOT NULL,
  location varchar(255) NULL,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.warehouses ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='warehouses' AND policyname='warehouses_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY warehouses_org_isolation ON erp.warehouses
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_warehouse_code ON erp.warehouses(org_id, warehouse_code);

-- 3) Inventory policies
CREATE TABLE IF NOT EXISTS erp.inventory_policies (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  policy_name varchar(100) NOT NULL DEFAULT 'default',
  valuation_method varchar(30) NOT NULL DEFAULT 'weighted_average',
  negative_stock_rule varchar(20) NOT NULL DEFAULT 'block',
  default_warehouse_id uuid NULL REFERENCES erp.warehouses(id) ON DELETE SET NULL,
  adjustment_approval_threshold numeric(18,2) NOT NULL DEFAULT 50000,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inventory_policies ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inventory_policies' AND policyname='inventory_policies_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inventory_policies_org_isolation ON erp.inventory_policies
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 4) Inventory movements (canonical ledger)
CREATE TABLE IF NOT EXISTS erp.inventory_movements (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  item_id uuid NOT NULL REFERENCES erp.inventory_items(id) ON DELETE RESTRICT,
  warehouse_id uuid NOT NULL REFERENCES erp.warehouses(id) ON DELETE RESTRICT,
  movement_type varchar(50) NOT NULL,
  quantity numeric(18,4) NOT NULL,
  unit_cost numeric(18,4) NOT NULL DEFAULT 0,
  total_cost numeric(18,2) NOT NULL DEFAULT 0,
  movement_date date NOT NULL DEFAULT CURRENT_DATE,
  reference_type varchar(50) NULL,
  reference_id uuid NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inventory_movements ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inventory_movements' AND policyname='inventory_movements_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inventory_movements_org_isolation ON erp.inventory_movements
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.inventory_movements
  ADD CONSTRAINT chk_erp_inventory_movement_type
  CHECK (movement_type IN ('receipt','issue','transfer','adjustment','sale','return','transfer_in','transfer_out'));

CREATE INDEX IF NOT EXISTS idx_erp_inv_movements_item ON erp.inventory_movements(org_id, item_id, movement_date DESC);
CREATE INDEX IF NOT EXISTS idx_erp_inv_movements_ref ON erp.inventory_movements(org_id, reference_type, reference_id);

-- 5) Balance projection
CREATE TABLE IF NOT EXISTS erp.inventory_balances (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  item_id uuid NOT NULL REFERENCES erp.inventory_items(id) ON DELETE CASCADE,
  warehouse_id uuid NOT NULL REFERENCES erp.warehouses(id) ON DELETE CASCADE,
  quantity_on_hand numeric(18,4) NOT NULL DEFAULT 0,
  inventory_value numeric(18,2) NOT NULL DEFAULT 0,
  weighted_avg_cost numeric(18,4) NOT NULL DEFAULT 0,
  last_updated timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inventory_balances ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inventory_balances' AND policyname='inventory_balances_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inventory_balances_org_isolation ON erp.inventory_balances
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_inv_balance_item_wh ON erp.inventory_balances(org_id, item_id, warehouse_id);

-- 6) FIFO cost layers
CREATE TABLE IF NOT EXISTS erp.inventory_cost_layers (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  item_id uuid NOT NULL REFERENCES erp.inventory_items(id) ON DELETE CASCADE,
  warehouse_id uuid NOT NULL REFERENCES erp.warehouses(id) ON DELETE CASCADE,
  movement_id uuid NULL REFERENCES erp.inventory_movements(id) ON DELETE SET NULL,
  remaining_quantity numeric(18,4) NOT NULL DEFAULT 0,
  unit_cost numeric(18,4) NOT NULL DEFAULT 0,
  receipt_date date NOT NULL DEFAULT CURRENT_DATE,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inventory_cost_layers ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inventory_cost_layers' AND policyname='inventory_cost_layers_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inventory_cost_layers_org_isolation ON erp.inventory_cost_layers
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_inv_layers_item ON erp.inventory_cost_layers(org_id, item_id, warehouse_id, receipt_date);

-- 7) Valuation snapshots
CREATE TABLE IF NOT EXISTS erp.inventory_valuations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  item_id uuid NOT NULL REFERENCES erp.inventory_items(id) ON DELETE CASCADE,
  warehouse_id uuid NULL REFERENCES erp.warehouses(id) ON DELETE SET NULL,
  valuation_date date NOT NULL,
  valuation_method varchar(30) NOT NULL,
  quantity numeric(18,4) NOT NULL DEFAULT 0,
  inventory_value numeric(18,2) NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inventory_valuations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inventory_valuations' AND policyname='inventory_valuations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inventory_valuations_org_isolation ON erp.inventory_valuations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 8) Adjustments audit
CREATE TABLE IF NOT EXISTS erp.inventory_adjustments (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  item_id uuid NOT NULL REFERENCES erp.inventory_items(id) ON DELETE RESTRICT,
  warehouse_id uuid NOT NULL REFERENCES erp.warehouses(id) ON DELETE RESTRICT,
  adjustment_date date NOT NULL DEFAULT CURRENT_DATE,
  quantity_variance numeric(18,4) NOT NULL DEFAULT 0,
  value_variance numeric(18,2) NOT NULL DEFAULT 0,
  reason text NULL,
  status varchar(30) NOT NULL DEFAULT 'posted',
  workflow_approved boolean NOT NULL DEFAULT false,
  movement_id uuid NULL REFERENCES erp.inventory_movements(id) ON DELETE SET NULL,
  journal_id uuid NULL REFERENCES erp.journals(id) ON DELETE SET NULL,
  created_by uuid NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inventory_adjustments ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inventory_adjustments' AND policyname='inventory_adjustments_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inventory_adjustments_org_isolation ON erp.inventory_adjustments
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- 9) GRN inventory links (idempotency)
CREATE TABLE IF NOT EXISTS erp.grn_inventory_links (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  goods_receipt_id uuid NOT NULL,
  grn_item_id uuid NOT NULL,
  inventory_movement_id uuid NOT NULL REFERENCES erp.inventory_movements(id) ON DELETE RESTRICT,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.grn_inventory_links ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='grn_inventory_links' AND policyname='grn_inventory_links_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY grn_inventory_links_org_isolation ON erp.grn_inventory_links
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_grn_inv_link ON erp.grn_inventory_links(org_id, grn_item_id);

-- Bridge columns on GRN items
ALTER TABLE erp.goods_receipt_items
  ADD COLUMN IF NOT EXISTS inventory_item_id uuid NULL REFERENCES erp.inventory_items(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS warehouse_id uuid NULL REFERENCES erp.warehouses(id) ON DELETE SET NULL;

-- IAM permissions
INSERT INTO core.permissions (resource, action, description) VALUES
    ('inventory', 'read', 'View inventory'),
    ('inventory', 'create', 'Create inventory items and warehouses'),
    ('inventory', 'receive', 'Record inventory receipts'),
    ('inventory', 'issue', 'Issue inventory and COGS'),
    ('inventory', 'transfer', 'Transfer stock between warehouses'),
    ('inventory', 'adjust', 'Inventory adjustments'),
    ('inventory', 'value', 'Run inventory valuations'),
    ('inventory', 'admin', 'Inventory administration')
ON CONFLICT (resource, action) DO NOTHING;

INSERT INTO core.roles (id, org_id, name, description, policy_context)
VALUES
  ('e1000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'warehouse_manager', 'Warehouse and stock manager', '{}'::jsonb),
  ('e1000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'inventory_controller', 'Inventory financial controller', '{}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'inventory'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('warehouse_manager', 'inventory_controller', 'finance_controller', 'finance_manager', 'controller', 'cfo', 'tenant_admin')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'inventory' AND p.action = 'read'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('auditor', 'analyst')
ON CONFLICT DO NOTHING;

-- Workflow
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
  (
    'e2000001-0001-4001-8001-000000000001'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'INVENTORY_ADJUSTMENT_APPROVAL',
    'Inventory Adjustment Approval',
    'Approve large inventory adjustments',
    1,
    '{"steps": [{"key": "controller_review", "type": "human_approval", "sla_hours": 48}, {"key": "validate", "type": "validation"}]}'::jsonb
  )
ON CONFLICT DO NOTHING;

-- Default warehouse + policy
INSERT INTO erp.warehouses (id, org_id, warehouse_code, warehouse_name, location)
VALUES
  ('e3000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'MAIN', 'Main Warehouse', 'HQ')
ON CONFLICT DO NOTHING;

INSERT INTO erp.inventory_policies (id, org_id, policy_name, valuation_method, negative_stock_rule, default_warehouse_id)
VALUES
  ('e4000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'default', 'weighted_average', 'block', 'e3000001-0001-4001-8001-000000000001'::uuid)
ON CONFLICT DO NOTHING;
