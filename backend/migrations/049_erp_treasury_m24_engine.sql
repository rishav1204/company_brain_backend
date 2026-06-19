-- Module 24: Treasury Management Engine

CREATE TABLE IF NOT EXISTS erp.cash_positions (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  bank_account_id uuid NOT NULL REFERENCES erp.bank_accounts(id) ON DELETE CASCADE,
  position_date date NOT NULL,
  opening_balance numeric(18,2) NOT NULL DEFAULT 0,
  inflows numeric(18,2) NOT NULL DEFAULT 0,
  outflows numeric(18,2) NOT NULL DEFAULT 0,
  closing_balance numeric(18,2) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.cash_positions ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='cash_positions'
      AND policyname='cash_positions_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY cash_positions_org_isolation ON erp.cash_positions
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_cash_positions_acct_date ON erp.cash_positions(org_id, bank_account_id, position_date);
CREATE INDEX IF NOT EXISTS idx_erp_cash_positions_date ON erp.cash_positions(org_id, position_date DESC);

CREATE TABLE IF NOT EXISTS erp.inter_account_transfers (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  source_account_id uuid NOT NULL REFERENCES erp.bank_accounts(id) ON DELETE RESTRICT,
  destination_account_id uuid NOT NULL REFERENCES erp.bank_accounts(id) ON DELETE RESTRICT,
  transfer_amount numeric(18,2) NOT NULL,
  transfer_date date NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'draft',
  payment_request_id uuid NULL REFERENCES erp.payment_requests(id) ON DELETE SET NULL,
  approved_by uuid NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.inter_account_transfers ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='inter_account_transfers'
      AND policyname='inter_account_transfers_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY inter_account_transfers_org_isolation ON erp.inter_account_transfers
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.inter_account_transfers
  ADD CONSTRAINT chk_erp_inter_account_transfer_status
  CHECK (status IN ('draft','pending_approval','approved','processing','completed','failed','cancelled'));

CREATE INDEX IF NOT EXISTS idx_erp_inter_transfers_status ON erp.inter_account_transfers(org_id, status);

CREATE TABLE IF NOT EXISTS erp.cash_forecasts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  forecast_date date NOT NULL,
  horizon_days int NOT NULL,
  expected_inflows numeric(18,2) NOT NULL DEFAULT 0,
  expected_outflows numeric(18,2) NOT NULL DEFAULT 0,
  forecast_cash_balance numeric(18,2) NOT NULL DEFAULT 0,
  confidence_score numeric(5,2) NOT NULL DEFAULT 0,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.cash_forecasts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='cash_forecasts'
      AND policyname='cash_forecasts_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY cash_forecasts_org_isolation ON erp.cash_forecasts
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_erp_cash_forecasts_org_date ON erp.cash_forecasts(org_id, forecast_date DESC, horizon_days);

CREATE TABLE IF NOT EXISTS erp.liquidity_alerts (
  id uuid PRIMARY KEY,
  org_id uuid NOT NULL,
  alert_type varchar(50) NOT NULL,
  severity varchar(30) NOT NULL DEFAULT 'medium',
  message text NOT NULL,
  status varchar(30) NOT NULL DEFAULT 'open',
  acknowledged_by uuid NULL,
  acknowledged_at timestamptz NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.liquidity_alerts ENABLE ROW LEVEL SECURITY;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='erp' AND tablename='liquidity_alerts'
      AND policyname='liquidity_alerts_org_isolation'
  ) THEN
    EXECUTE $p$ CREATE POLICY liquidity_alerts_org_isolation ON erp.liquidity_alerts
      USING (org_id::text = current_setting('app.current_org', true)) $p$;
  END IF;
END $$;

ALTER TABLE erp.liquidity_alerts
  ADD CONSTRAINT chk_erp_liquidity_alert_status
  CHECK (status IN ('open','acknowledged','dismissed'));

CREATE INDEX IF NOT EXISTS idx_erp_liquidity_alerts_status ON erp.liquidity_alerts(org_id, status);

CREATE INDEX IF NOT EXISTS idx_erp_bank_tx_recon_date ON erp.bank_transactions(org_id, bank_account_id, reconciliation_status, transaction_date);

INSERT INTO workflow.workflow_definitions (id, org_id, workflow_key, name, description, version, definition_json)
VALUES (
  'd0000001-0001-4001-8001-000000000021'::uuid,
  '11111111-1111-4111-8111-111111111111'::uuid,
  'TREASURY_TRANSFER_APPROVAL',
  'Treasury Transfer Approval',
  'Inter-account transfer approval with tiered thresholds',
  1,
  '{"steps":[{"key":"manager_approval","type":"approval","role":"finance_manager"},{"key":"controller_approval","type":"approval","role":"controller","threshold":500000},{"key":"cfo_approval","type":"approval","role":"cfo","threshold":5000000}]}'::jsonb
)
ON CONFLICT DO NOTHING;
