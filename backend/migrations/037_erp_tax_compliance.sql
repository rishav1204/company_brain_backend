-- Module 14: TDS, e-invoice, e-way, compliance calendar, notices

CREATE TABLE IF NOT EXISTS erp.tds_sections (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  section_code varchar(16) NOT NULL,
  description varchar(256) NULL,
  rate numeric(8,4) NOT NULL,
  threshold_amount numeric(18,2) NOT NULL DEFAULT 0,
  is_active boolean NOT NULL DEFAULT true,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, section_code)
);

ALTER TABLE erp.tds_sections ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tds_sections' AND policyname='tds_sections_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_sections_org_isolation ON erp.tds_sections
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.tds_transactions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_type varchar(64) NOT NULL,
  source_id uuid NOT NULL,
  section_code varchar(16) NOT NULL,
  gross_amount numeric(18,2) NOT NULL,
  tds_amount numeric(18,2) NOT NULL,
  net_amount numeric(18,2) NOT NULL,
  status varchar(32) NOT NULL DEFAULT 'calculated',
  return_period varchar(7) NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, source_type, source_id, section_code)
);

ALTER TABLE erp.tds_transactions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tds_transactions' AND policyname='tds_transactions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_transactions_org_isolation ON erp.tds_transactions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.e_invoices (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  ar_invoice_id uuid NOT NULL,
  irn varchar(128) NULL,
  ack_no varchar(64) NULL,
  ack_date timestamptz NULL,
  qr_code text NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  raw_response jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, ar_invoice_id)
);

ALTER TABLE erp.e_invoices ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='e_invoices' AND policyname='e_invoices_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY e_invoices_org_isolation ON erp.e_invoices
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.eway_bills (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_type varchar(64) NOT NULL,
  source_id uuid NOT NULL,
  eway_bill_no varchar(64) NULL,
  valid_upto timestamptz NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  raw_response jsonb NOT NULL DEFAULT '{}'::jsonb,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.eway_bills ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='eway_bills' AND policyname='eway_bills_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY eway_bills_org_isolation ON erp.eway_bills
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS erp.compliance_calendar (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  obligation_type varchar(64) NOT NULL,
  due_date date NOT NULL,
  return_period varchar(7) NULL,
  status varchar(32) NOT NULL DEFAULT 'pending',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.compliance_calendar ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='compliance_calendar' AND policyname='compliance_calendar_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY compliance_calendar_org_isolation ON erp.compliance_calendar
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_compliance_cal_due ON erp.compliance_calendar(org_id, due_date, status);

CREATE TABLE IF NOT EXISTS erp.tax_notices (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  notice_type varchar(64) NOT NULL,
  received_date date NOT NULL,
  document_id uuid NULL,
  status varchar(32) NOT NULL DEFAULT 'open',
  ai_summary text NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.tax_notices ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tax_notices' AND policyname='tax_notices_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tax_notices_org_isolation ON erp.tax_notices
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- Seed default TDS sections for benchmark org
INSERT INTO erp.tds_sections (id, org_id, section_code, description, rate, threshold_amount)
VALUES
  ('a0000001-0001-4001-8001-000000000101'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194C', 'Contractors', 1.0, 30000),
  ('a0000001-0001-4001-8001-000000000102'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194J', 'Professional fees', 10.0, 30000),
  ('a0000001-0001-4001-8001-000000000103'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194H', 'Commission', 5.0, 15000),
  ('a0000001-0001-4001-8001-000000000104'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194I', 'Rent', 10.0, 240000),
  ('a0000001-0001-4001-8001-000000000105'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '194Q', 'Purchase of goods', 0.1, 5000000)
ON CONFLICT DO NOTHING;

INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES
  (
    'd0000001-0001-4001-8001-000000000107'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'TDS_FILING',
    'TDS Filing Approval',
    'TDS return review and filing approval',
    1,
    '{"steps": [{"key": "compliance_review", "type": "human_approval", "sla_hours": 24}, {"key": "file", "type": "validation"}]}'::jsonb
  ),
  (
    'd0000001-0001-4001-8001-000000000108'::uuid,
    '11111111-1111-4111-8111-111111111111'::uuid,
    'EINVOICE_GENERATION',
    'E-Invoice Generation',
    'Review before IRP submission',
    1,
    '{"steps": [{"key": "review", "type": "human_approval", "sla_hours": 12}, {"key": "generate_irn", "type": "validation"}]}'::jsonb
  )
ON CONFLICT DO NOTHING;
