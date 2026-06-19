-- Module 12: Fiscal Period Management (Accounting Control Engine)

CREATE TABLE IF NOT EXISTS erp.fiscal_years (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  company_id uuid NULL,
  fiscal_year_code varchar(20) NOT NULL,
  start_date date NOT NULL,
  end_date date NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'open',
  is_current boolean NOT NULL DEFAULT false,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, fiscal_year_code)
);

ALTER TABLE erp.fiscal_years ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='fiscal_years' AND policyname='fiscal_years_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY fiscal_years_org_isolation ON erp.fiscal_years
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.fiscal_periods
  ADD COLUMN IF NOT EXISTS fiscal_year_id uuid NULL REFERENCES erp.fiscal_years(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS period_number integer NULL,
  ADD COLUMN IF NOT EXISTS lock_status varchar(30) NOT NULL DEFAULT 'open',
  ADD COLUMN IF NOT EXISTS closed_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS closed_by uuid NULL;

UPDATE erp.fiscal_periods
SET lock_status = CASE
  WHEN status = 'closed' THEN 'closed'
  WHEN status = 'locked' OR is_locked = true THEN 'hard_locked'
  WHEN status = 'soft_locked' THEN 'soft_locked'
  ELSE 'open'
END
WHERE lock_status = 'open' AND (status != 'open' OR is_locked = true);

CREATE TABLE IF NOT EXISTS erp.period_close_checklists (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  period_id uuid NOT NULL REFERENCES erp.fiscal_periods(id) ON DELETE CASCADE,
  check_name varchar(128) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  completed_by uuid NULL,
  completed_at timestamptz NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, period_id, check_name)
);

ALTER TABLE erp.period_close_checklists ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='period_close_checklists' AND policyname='period_close_checklists_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY period_close_checklists_org_isolation ON erp.period_close_checklists
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.period_reopen_requests (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  period_id uuid NOT NULL REFERENCES erp.fiscal_periods(id) ON DELETE CASCADE,
  reason text NOT NULL,
  requested_by uuid NOT NULL,
  approved_by uuid NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.period_reopen_requests ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='period_reopen_requests' AND policyname='period_reopen_requests_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY period_reopen_requests_org_isolation ON erp.period_reopen_requests
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.year_end_runs (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  fiscal_year_id uuid NOT NULL REFERENCES erp.fiscal_years(id) ON DELETE RESTRICT,
  status varchar(32) NOT NULL DEFAULT 'pending',
  closing_journal_id uuid NULL,
  closing_batch_id uuid NULL,
  next_fiscal_year_id uuid NULL REFERENCES erp.fiscal_years(id) ON DELETE SET NULL,
  run_by uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz NULL
);

ALTER TABLE erp.year_end_runs ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='year_end_runs' AND policyname='year_end_runs_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY year_end_runs_org_isolation ON erp.year_end_runs
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- IAM permissions
INSERT INTO core.permissions (resource, action, description) VALUES
    ('fiscal', 'read', 'View fiscal years and periods'),
    ('fiscal', 'close', 'Close fiscal periods'),
    ('fiscal', 'reopen', 'Reopen closed periods'),
    ('fiscal', 'soft_post', 'Post during soft-locked periods'),
    ('fiscal', 'year_end', 'Run year-end close')
ON CONFLICT (resource, action) DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'fiscal'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('cfo', 'controller', 'tenant_admin', 'tax_manager', 'compliance_officer')
ON CONFLICT DO NOTHING;

INSERT INTO core.role_permissions (role_id, permission_id)
SELECT r.id, p.id
FROM core.roles r
JOIN core.permissions p ON p.resource = 'fiscal' AND p.action = 'read'
WHERE r.org_id = '11111111-1111-4111-8111-111111111111'::uuid
  AND r.name IN ('auditor', 'analyst', 'ap_manager', 'ar_manager')
ON CONFLICT DO NOTHING;

-- Workflows
INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
  (
    'e0000001-0001-4001-8001-000000000001'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'PERIOD_CLOSE',
    'Fiscal Period Close',
    'Month-end close approval and lock',
    1,
    '{"steps": [{"key": "controller_review", "type": "human_approval", "sla_hours": 48}, {"key": "finalize_close", "type": "validation"}]}'::jsonb
  ),
  (
    'e0000001-0001-4001-8001-000000000002'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'PERIOD_REOPEN',
    'Fiscal Period Reopen',
    'Reopen closed period with audit trail',
    1,
    '{"steps": [{"key": "cfo_approval", "type": "human_approval", "sla_hours": 24}, {"key": "reopen", "type": "validation"}]}'::jsonb
  )
ON CONFLICT DO NOTHING;

-- Benchmark org FY2026-27 with monthly periods
INSERT INTO erp.fiscal_years (id, org_id, fiscal_year_code, start_date, end_date, status, is_current)
VALUES (
  'f0000001-0001-4001-8001-000000000001'::uuid,
  '11111111-1111-4111-8111-111111111111'::uuid,
  'FY2026-27',
  '2026-04-01'::date,
  '2027-03-31'::date,
  'open',
  true
)
ON CONFLICT DO NOTHING;

INSERT INTO erp.fiscal_periods (id, org_id, fiscal_year_id, period_name, period_number, start_date, end_date, status, is_locked, lock_status)
SELECT
  ('f1000001-0001-4001-8001-' || lpad(m::text, 12, '0'))::uuid,
  '11111111-1111-4111-8111-111111111111'::uuid,
  'f0000001-0001-4001-8001-000000000001'::uuid,
  to_char(d, 'Mon YYYY'),
  m,
  d,
  (d + interval '1 month' - interval '1 day')::date,
  'open',
  false,
  'open'
FROM generate_series(1, 12) AS m
CROSS JOIN LATERAL (
  SELECT ('2026-04-01'::date + ((m - 1) || ' months')::interval)::date AS d
) AS dates
WHERE NOT EXISTS (
  SELECT 1 FROM erp.fiscal_periods fp
  WHERE fp.org_id = '11111111-1111-4111-8111-111111111111'::uuid
    AND fp.fiscal_year_id = 'f0000001-0001-4001-8001-000000000001'::uuid
);
