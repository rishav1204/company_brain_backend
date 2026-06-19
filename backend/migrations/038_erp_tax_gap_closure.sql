-- Module 14 gap closure: tax rate master, TDS returns, IAM permissions, roles

CREATE TABLE IF NOT EXISTS erp.tax_rate_master (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  hsn_sac varchar(16) NULL,
  description varchar(256) NULL,
  gst_rate numeric(8,4) NOT NULL,
  cess_rate numeric(8,4) NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_erp_tax_rate_master_org_hsn_rate
  ON erp.tax_rate_master (org_id, COALESCE(hsn_sac, ''), gst_rate);

ALTER TABLE erp.tax_rate_master ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tax_rate_master' AND policyname='tax_rate_master_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tax_rate_master_org_isolation ON erp.tax_rate_master
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.tds_returns (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  return_period varchar(7) NOT NULL,
  form_type varchar(16) NOT NULL DEFAULT '26Q',
  status varchar(32) NOT NULL DEFAULT 'draft',
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  filed_at timestamptz NULL,
  filed_by uuid NULL,
  workflow_approved boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, return_period, form_type)
);

ALTER TABLE erp.tds_returns ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tds_returns' AND policyname='tds_returns_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_returns_org_isolation ON erp.tds_returns
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- IAM: tax permissions aligned with route guards
INSERT INTO core.permissions (resource, action, description) VALUES
    ('tax', 'read', 'View tax and compliance data'),
    ('tax', 'file', 'File tax returns and e-invoices'),
    ('tax', 'modify', 'Modify tax data and claim ITC'),
    ('erp.tax', 'admin', 'Full tax module administration')
ON CONFLICT (resource, action) DO NOTHING;

INSERT INTO core.roles (id, org_id, name, description, system_role, policy_context)
VALUES
    ('b0000001-0001-4001-8001-00000000000b'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'tax_manager', 'Tax and GST manager', TRUE, '{"max_approve_amount": null}'::jsonb),
    ('b0000001-0001-4001-8001-00000000000c'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'compliance_officer', 'Compliance and filings officer', TRUE, '{}'::jsonb)
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource IN ('tax', 'gst', 'erp.tax')
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('tax_manager', 'compliance_officer', 'cfo', 'controller', 'tenant_admin')
ON CONFLICT DO NOTHING;

-- Default GST rates for benchmark org
INSERT INTO erp.tax_rate_master (id, org_id, hsn_sac, description, gst_rate)
VALUES
  ('b0000001-0001-4001-8001-000000000201'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, NULL, 'Zero rated', 0),
  ('b0000001-0001-4001-8001-000000000202'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, NULL, 'GST 5%', 5),
  ('b0000001-0001-4001-8001-000000000203'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, NULL, 'GST 12%', 12),
  ('b0000001-0001-4001-8001-000000000204'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, NULL, 'GST 18%', 18),
  ('b0000001-0001-4001-8001-000000000205'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, NULL, 'GST 28%', 28)
ON CONFLICT DO NOTHING;

INSERT INTO erp.itc_blocked_rules (id, org_id, category, description, block_percentage)
SELECT * FROM (VALUES
  ('b0000001-0001-4001-8001-000000000301'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'motor_vehicle', 'Motor vehicles (blocked ITC)', 100::numeric),
  ('b0000001-0001-4001-8001-000000000302'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'personal_consumption', 'Personal consumption', 100::numeric),
  ('b0000001-0001-4001-8001-000000000303'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'employee_benefit', 'Employee benefits (specific cases)', 100::numeric)
) AS v(id, org_id, category, description, block_percentage)
WHERE NOT EXISTS (SELECT 1 FROM erp.itc_blocked_rules r WHERE r.org_id = v.org_id AND r.category = v.category);
