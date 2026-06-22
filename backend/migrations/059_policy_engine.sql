-- Module 34: Policy Engine — master policies, decisions audit, approval matrix

CREATE TABLE IF NOT EXISTS governance.policies (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  policy_code varchar(100) NOT NULL,
  policy_name varchar(255) NOT NULL,
  policy_type varchar(100) NOT NULL,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, policy_code)
);

ALTER TABLE governance.policies ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='governance' AND tablename='policies'
      AND policyname='governance_policies_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY governance_policies_org ON governance.policies
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_governance_policies_org_type
  ON governance.policies (org_id, policy_type, is_active);

-- Backfill master policies from existing policy_rules
INSERT INTO governance.policies (org_id, policy_code, policy_name, policy_type, is_active)
SELECT DISTINCT org_id, policy_key, policy_key, policy_type, is_active
FROM governance.policy_rules
ON CONFLICT (org_id, policy_code) DO NOTHING;

ALTER TABLE governance.policy_rules
  ADD COLUMN IF NOT EXISTS policy_id uuid REFERENCES governance.policies(id),
  ADD COLUMN IF NOT EXISTS policy_code varchar(100);

UPDATE governance.policy_rules pr
SET policy_id = p.id, policy_code = pr.policy_key
FROM governance.policies p
WHERE p.org_id = pr.org_id AND p.policy_code = pr.policy_key
  AND pr.policy_id IS NULL;

CREATE TABLE IF NOT EXISTS governance.policy_decisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  object_type varchar(100),
  object_id uuid,
  action varchar(128) NOT NULL,
  decision varchar(50) NOT NULL,
  policy_code varchar(100),
  risk_level varchar(32),
  approval_chain jsonb NOT NULL DEFAULT '[]'::jsonb,
  input_context jsonb NOT NULL DEFAULT '{}'::jsonb,
  reason text,
  actor_id uuid,
  evaluated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE governance.policy_decisions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='governance' AND tablename='policy_decisions'
      AND policyname='governance_policy_decisions_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY governance_policy_decisions_org ON governance.policy_decisions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_policy_decisions_org_eval
  ON governance.policy_decisions (org_id, evaluated_at DESC);

CREATE INDEX IF NOT EXISTS idx_policy_decisions_object
  ON governance.policy_decisions (org_id, object_type, object_id, evaluated_at DESC)
  WHERE object_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS governance.approval_matrix (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  action_code varchar(100) NOT NULL,
  department varchar(100),
  business_unit varchar(100),
  min_amount numeric(18,2) NOT NULL DEFAULT 0,
  max_amount numeric(18,2),
  approver_role varchar(100) NOT NULL,
  level int NOT NULL DEFAULT 1,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE governance.approval_matrix ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='governance' AND tablename='approval_matrix'
      AND policyname='governance_approval_matrix_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY governance_approval_matrix_org ON governance.approval_matrix
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_approval_matrix_org_action
  ON governance.approval_matrix (org_id, action_code, min_amount, level);

CREATE TABLE IF NOT EXISTS governance.policy_exceptions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id uuid NOT NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
  policy_code varchar(100) NOT NULL,
  object_type varchar(100),
  object_id uuid,
  action varchar(128) NOT NULL,
  reason text NOT NULL,
  approved_by uuid,
  workflow_instance_id uuid,
  expires_at timestamptz,
  status varchar(32) NOT NULL DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE governance.policy_exceptions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='governance' AND tablename='policy_exceptions'
      AND policyname='governance_policy_exceptions_org'
  ) THEN
    EXECUTE $p$ CREATE POLICY governance_policy_exceptions_org ON governance.policy_exceptions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- Append-only policy_decisions
CREATE OR REPLACE FUNCTION governance.prevent_policy_decision_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'governance.policy_decisions is append-only';
END;
$$;

DROP TRIGGER IF EXISTS policy_decisions_no_update ON governance.policy_decisions;
CREATE TRIGGER policy_decisions_no_update
BEFORE UPDATE OR DELETE ON governance.policy_decisions
FOR EACH ROW EXECUTE FUNCTION governance.prevent_policy_decision_mutation();

-- Seed default approval matrix per org (INR tiers — matches legacy banking behavior)
INSERT INTO governance.approval_matrix (org_id, action_code, min_amount, max_amount, approver_role, level)
SELECT o.id, m.action_code, m.min_amount, m.max_amount, m.approver_role, m.level
FROM core.organizations o
CROSS JOIN (
  VALUES
    ('vendor_payment', 0, 50000, 'finance_manager', 1),
    ('vendor_payment', 50000, 500000, 'controller', 2),
    ('vendor_payment', 500000, 2500000, 'cfo', 3),
    ('vendor_payment', 2500000, NULL, 'dual_approval', 4),
    ('payment.execute', 0, 50000, 'finance_manager', 1),
    ('payment.execute', 50000, 500000, 'controller', 2),
    ('payment.execute', 500000, 2500000, 'cfo', 3),
    ('payment.execute', 2500000, NULL, 'dual_approval', 4),
    ('journal.post', 0, 500000, 'finance_manager', 1),
    ('journal.post', 500000, NULL, 'controller', 2),
    ('treasury.transfer', 0, 5000000, 'treasury_manager', 1),
    ('treasury.transfer', 5000000, NULL, 'cfo', 2)
) AS m(action_code, min_amount, max_amount, approver_role, level)
ON CONFLICT DO NOTHING;
