-- Module 25: AI Invoice Intelligence (Finance OS)

CREATE SCHEMA IF NOT EXISTS finance_os;

CREATE TABLE IF NOT EXISTS finance_os.invoice_extractions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  document_id uuid NOT NULL,
  source_extraction_id uuid NULL,
  invoice_number varchar(255) NULL,
  vendor_name varchar(255) NULL,
  vendor_name_normalized varchar(255) NULL,
  vendor_gstin varchar(20) NULL,
  vendor_id uuid NULL,
  invoice_date date NULL,
  due_date date NULL,
  taxable_amount numeric(18,2) NOT NULL DEFAULT 0,
  gst_amount numeric(18,2) NOT NULL DEFAULT 0,
  total_amount numeric(18,2) NOT NULL DEFAULT 0,
  extraction_confidence numeric(5,2) NOT NULL DEFAULT 0,
  confidence_band varchar(32) NOT NULL DEFAULT 'manual_review',
  invoice_type varchar(32) NOT NULL DEFAULT 'purchase',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.invoice_extractions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='invoice_extractions'
      AND policyname='invoice_extractions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY invoice_extractions_org_isolation ON finance_os.invoice_extractions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_inv_ext_doc ON finance_os.invoice_extractions(org_id, document_id);
CREATE INDEX IF NOT EXISTS idx_fin_os_inv_ext_vendor ON finance_os.invoice_extractions(org_id, vendor_gstin);

CREATE TABLE IF NOT EXISTS finance_os.invoice_predictions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  extraction_id uuid NOT NULL REFERENCES finance_os.invoice_extractions(id) ON DELETE CASCADE,
  prediction_type varchar(50) NOT NULL DEFAULT 'ledger',
  suggested_account_id uuid NULL,
  suggested_gst_code varchar(50) NULL,
  suggested_cost_center uuid NULL,
  confidence_score numeric(5,2) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.invoice_predictions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='invoice_predictions'
      AND policyname='invoice_predictions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY invoice_predictions_org_isolation ON finance_os.invoice_predictions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_inv_pred_ext ON finance_os.invoice_predictions(org_id, extraction_id);

CREATE TABLE IF NOT EXISTS finance_os.invoice_anomalies (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  extraction_id uuid NULL REFERENCES finance_os.invoice_extractions(id) ON DELETE CASCADE,
  invoice_id uuid NULL,
  anomaly_type varchar(100) NOT NULL,
  anomaly_score numeric(5,2) NOT NULL DEFAULT 0,
  severity varchar(20) NOT NULL DEFAULT 'medium',
  description text NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'open',
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.invoice_anomalies ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='invoice_anomalies'
      AND policyname='invoice_anomalies_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY invoice_anomalies_org_isolation ON finance_os.invoice_anomalies
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_inv_anom_ext ON finance_os.invoice_anomalies(org_id, extraction_id);

CREATE TABLE IF NOT EXISTS finance_os.invoice_duplicate_scores (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  extraction_id uuid NOT NULL REFERENCES finance_os.invoice_extractions(id) ON DELETE CASCADE,
  matched_invoice_id uuid NULL,
  similarity_score numeric(5,2) NOT NULL DEFAULT 0,
  status varchar(30) NOT NULL DEFAULT 'clean',
  score_breakdown jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE finance_os.invoice_duplicate_scores ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='finance_os' AND tablename='invoice_duplicate_scores'
      AND policyname='invoice_duplicate_scores_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY invoice_duplicate_scores_org_isolation ON finance_os.invoice_duplicate_scores
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_fin_os_inv_dup_ext ON finance_os.invoice_duplicate_scores(org_id, extraction_id);
