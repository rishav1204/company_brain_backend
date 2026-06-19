-- Module 21: Compliance Calendar & Regulatory Obligation Engine

CREATE TABLE IF NOT EXISTS erp.compliance_types (
  id uuid PRIMARY KEY,
  compliance_code varchar(50) NOT NULL UNIQUE,
  compliance_name varchar(255) NOT NULL,
  regulator varchar(255) NULL,
  frequency varchar(50) NOT NULL DEFAULT 'monthly',
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS erp.compliance_rules (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  compliance_type_id uuid NOT NULL REFERENCES erp.compliance_types(id),
  due_day integer NOT NULL DEFAULT 1,
  month_offset integer NOT NULL DEFAULT 1,
  frequency varchar(50) NOT NULL DEFAULT 'monthly',
  reminder_offsets_days jsonb NOT NULL DEFAULT '[30,15,7,3,1]'::jsonb,
  escalation_levels jsonb NOT NULL DEFAULT '["assignee","manager","finance_head","cfo"]'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, compliance_type_id)
);

ALTER TABLE erp.compliance_rules ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='compliance_rules' AND policyname='compliance_rules_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY compliance_rules_org_isolation ON erp.compliance_rules
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.compliance_obligations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  compliance_type_id uuid NOT NULL REFERENCES erp.compliance_types(id),
  title varchar(255) NOT NULL,
  due_date date NOT NULL,
  return_period varchar(16) NULL,
  status varchar(30) NOT NULL DEFAULT 'upcoming',
  priority varchar(30) NOT NULL DEFAULT 'medium',
  assigned_to uuid NULL,
  completed_at timestamptz NULL,
  waived_at timestamptz NULL,
  waive_reason text NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, compliance_type_id, return_period)
);

ALTER TABLE erp.compliance_obligations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='compliance_obligations' AND policyname='compliance_obligations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY compliance_obligations_org_isolation ON erp.compliance_obligations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_compliance_obligations_due ON erp.compliance_obligations(org_id, due_date, status);
CREATE INDEX IF NOT EXISTS idx_compliance_obligations_period ON erp.compliance_obligations(org_id, return_period);

CREATE TABLE IF NOT EXISTS erp.compliance_reminders (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  obligation_id uuid NOT NULL REFERENCES erp.compliance_obligations(id) ON DELETE CASCADE,
  reminder_date date NOT NULL,
  notification_sent boolean NOT NULL DEFAULT false,
  sent_at timestamptz NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, obligation_id, reminder_date)
);

ALTER TABLE erp.compliance_reminders ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='compliance_reminders' AND policyname='compliance_reminders_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY compliance_reminders_org_isolation ON erp.compliance_reminders
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.compliance_escalations (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  obligation_id uuid NOT NULL REFERENCES erp.compliance_obligations(id) ON DELETE CASCADE,
  escalation_level integer NOT NULL DEFAULT 1,
  escalated_to_role varchar(64) NULL,
  escalated_at timestamptz NOT NULL DEFAULT now(),
  resolved boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE erp.compliance_escalations ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='compliance_escalations' AND policyname='compliance_escalations_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY compliance_escalations_org_isolation ON erp.compliance_escalations
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.compliance_penalties (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  obligation_id uuid NOT NULL REFERENCES erp.compliance_obligations(id) ON DELETE CASCADE,
  penalty_amount numeric(18,2) NOT NULL DEFAULT 0,
  interest_amount numeric(18,2) NOT NULL DEFAULT 0,
  calculated_at timestamptz NOT NULL DEFAULT now(),
  is_manual_override boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb
);

ALTER TABLE erp.compliance_penalties ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='compliance_penalties' AND policyname='compliance_penalties_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY compliance_penalties_org_isolation ON erp.compliance_penalties
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- Global compliance types
INSERT INTO erp.compliance_types (id, compliance_code, compliance_name, regulator, frequency, metadata)
VALUES
  ('a1000001-0001-4001-8001-000000000001'::uuid, 'GST_GSTR1', 'GSTR-1 Filing', 'GSTN', 'monthly', '{"source_module":"M19"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000002'::uuid, 'GST_GSTR3B', 'GSTR-3B Filing', 'GSTN', 'monthly', '{"source_module":"M19"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000003'::uuid, 'GST_PAYMENT', 'GST Payment', 'GSTN', 'monthly', '{"source_module":"M19"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000004'::uuid, 'TDS_26Q', 'TDS 26Q Return', 'NSDL', 'quarterly', '{"source_module":"M20"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000005'::uuid, 'TDS_27Q', 'TDS 27Q Return', 'NSDL', 'quarterly', '{"source_module":"M20"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000006'::uuid, 'TDS_CHALLAN', 'TDS Challan Deposit', 'NSDL', 'monthly', '{"source_module":"M20"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000007'::uuid, 'PF_RETURN', 'PF Return', 'EPFO', 'monthly', '{"source_module":"stub"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000008'::uuid, 'ESI_RETURN', 'ESI Return', 'ESIC', 'monthly', '{"source_module":"stub"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000009'::uuid, 'ROC_AOC4', 'ROC AOC-4', 'MCA', 'annual', '{"source_module":"stub"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000010'::uuid, 'ROC_MGT7', 'ROC MGT-7', 'MCA', 'annual', '{"source_module":"stub"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000011'::uuid, 'INCOME_TAX', 'Income Tax Filing', 'CBDT', 'annual', '{"source_module":"stub"}'::jsonb),
  ('a1000001-0001-4001-8001-000000000012'::uuid, 'AUDIT_INTERNAL', 'Internal Audit', 'Internal', 'annual', '{"source_module":"custom"}'::jsonb)
ON CONFLICT (compliance_code) DO NOTHING;

-- Benchmark org rules (replaces hardcoded DEFAULT_OBLIGATIONS)
INSERT INTO erp.compliance_rules (id, org_id, compliance_type_id, due_day, month_offset, frequency)
SELECT gen_random_uuid(), '11111111-1111-4111-8111-111111111111'::uuid, t.id, r.due_day, r.month_offset, r.frequency
FROM (VALUES
  ('GST_GSTR1', 11, 1, 'monthly'),
  ('GST_GSTR3B', 20, 1, 'monthly'),
  ('GST_PAYMENT', 20, 1, 'monthly'),
  ('TDS_CHALLAN', 7, 1, 'monthly'),
  ('TDS_26Q', 31, 3, 'quarterly'),
  ('AUDIT_INTERNAL', 30, 9, 'annual')
) AS r(code, due_day, month_offset, frequency)
JOIN erp.compliance_types t ON t.compliance_code = r.code
ON CONFLICT DO NOTHING;

-- Migrate legacy compliance_calendar rows
INSERT INTO erp.compliance_obligations (id, org_id, compliance_type_id, title, due_date, return_period, status, metadata)
SELECT
  c.id,
  c.org_id,
  COALESCE(t.id, (SELECT id FROM erp.compliance_types WHERE compliance_code = 'GST_GSTR1' LIMIT 1)),
  COALESCE(t.compliance_name, c.obligation_type),
  c.due_date,
  c.return_period,
  CASE WHEN c.status = 'completed' THEN 'completed' WHEN c.status = 'pending' THEN 'upcoming' ELSE c.status END,
  c.metadata
FROM erp.compliance_calendar c
LEFT JOIN erp.compliance_types t ON t.compliance_code = CASE c.obligation_type
  WHEN 'GSTR-1' THEN 'GST_GSTR1'
  WHEN 'GSTR-3B' THEN 'GST_GSTR3B'
  WHEN 'TDS' THEN 'TDS_CHALLAN'
  WHEN 'TAX_PAYMENT' THEN 'GST_PAYMENT'
  WHEN 'ANNUAL_GST' THEN 'GST_GSTR3B'
  WHEN 'AUDIT' THEN 'AUDIT_INTERNAL'
  ELSE 'GST_GSTR1'
END
ON CONFLICT (org_id, compliance_type_id, return_period) DO NOTHING;

INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES (
  'a2000001-0001-4001-8001-000000000001'::uuid,
  '11111111-1111-4111-8111-111111111111'::uuid,
  'COMPLIANCE_ESCALATION',
  'Compliance Escalation',
  'Escalate overdue regulatory obligations',
  1,
  '{"steps": [{"key": "compliance_review", "type": "human_approval", "sla_hours": 24}]}'::jsonb
),
(
  'a2000001-0001-4001-8001-000000000002'::uuid,
  '11111111-1111-4111-8111-111111111111'::uuid,
  'COMPLIANCE_WAIVE',
  'Compliance Waive Approval',
  'Approve waiving a regulatory obligation',
  1,
  '{"steps": [{"key": "cfo_approval", "type": "human_approval", "sla_hours": 48}]}'::jsonb
)
ON CONFLICT DO NOTHING;
