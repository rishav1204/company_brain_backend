-- Module 20: TDS production — COA tax accounts seed + Form 16A certificates

CREATE TABLE IF NOT EXISTS erp.tds_certificates (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  vendor_id uuid NOT NULL,
  quarter varchar(4) NOT NULL,
  financial_year varchar(16) NOT NULL,
  document_id uuid NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (org_id, vendor_id, quarter, financial_year)
);

ALTER TABLE erp.tds_certificates ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='tds_certificates' AND policyname='tds_certificates_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY tds_certificates_org_isolation ON erp.tds_certificates
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

-- Benchmark org: tax liability/receivable groups + accounts (idempotent)
INSERT INTO erp.account_groups (id, org_id, group_name, group_code, group_type, nature)
VALUES
  ('f5000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'Tax Liabilities', 'TAX_LIABILITY', 'liability', 'credit'),
  ('f5000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, 'Tax Receivables', 'TAX_RECEIVABLE', 'asset', 'debit')
ON CONFLICT DO NOTHING;

INSERT INTO erp.chart_of_accounts (id, org_id, account_code, account_name, account_type, group_id, is_postable, currency_code)
SELECT v.id, v.org_id, v.account_code, v.account_name, v.account_type, v.group_id, true, 'INR'
FROM (VALUES
  ('f6000001-0001-4001-8001-000000000001'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '2350', 'TDS Payable', 'tds_payable', 'f5000001-0001-4001-8001-000000000001'::uuid),
  ('f6000001-0001-4001-8001-000000000002'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '2351', 'TCS Payable', 'tcs_payable', 'f5000001-0001-4001-8001-000000000001'::uuid),
  ('f6000001-0001-4001-8001-000000000003'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '1350', 'TDS Receivable', 'tds_receivable', 'f5000001-0001-4001-8001-000000000002'::uuid),
  ('f6000001-0001-4001-8001-000000000004'::uuid, '11111111-1111-4111-8111-111111111111'::uuid, '1351', 'TCS Receivable', 'tcs_receivable', 'f5000001-0001-4001-8001-000000000002'::uuid)
) AS v(id, org_id, account_code, account_name, account_type, group_id)
WHERE NOT EXISTS (
  SELECT 1 FROM erp.chart_of_accounts c
  WHERE c.org_id = v.org_id AND c.account_code = v.account_code
);
