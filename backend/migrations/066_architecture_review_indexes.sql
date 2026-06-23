-- Architecture review remediation: high-traffic tenant indexes and GL immutability hardening.

CREATE INDEX IF NOT EXISTS idx_erp_journals_org_status_created
  ON erp.journals (org_id, journal_status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_erp_ap_invoices_org_vendor_status
  ON erp.ap_invoices (org_id, vendor_id, status);

CREATE INDEX IF NOT EXISTS idx_erp_ar_invoices_org_customer_status
  ON erp.ar_invoices (org_id, customer_id, status);

CREATE INDEX IF NOT EXISTS idx_erp_ap_payment_allocations_org_payment
  ON erp.ap_payment_allocations (org_id, payment_id);

CREATE INDEX IF NOT EXISTS idx_erp_customer_receipt_allocations_org_receipt
  ON erp.customer_receipt_allocations (org_id, receipt_id);

CREATE INDEX IF NOT EXISTS idx_erp_customer_balances_org_customer
  ON erp.customer_balances (org_id, customer_id);

CREATE INDEX IF NOT EXISTS idx_erp_tds_transactions_org_payment
  ON erp.tds_transactions (org_id, payment_id);

CREATE INDEX IF NOT EXISTS idx_erp_gst_returns_org_period
  ON erp.gst_returns (org_id, return_period);

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_ap_invoices_org_number_active
  ON erp.ap_invoices (org_id, invoice_number)
  WHERE status IS DISTINCT FROM 'cancelled';

CREATE UNIQUE INDEX IF NOT EXISTS uq_erp_ar_invoices_org_number_active
  ON erp.ar_invoices (org_id, invoice_number)
  WHERE status IS DISTINCT FROM 'cancelled';

ALTER TABLE erp.ledger_entries FORCE ROW LEVEL SECURITY;
ALTER TABLE erp.journals FORCE ROW LEVEL SECURITY;
ALTER TABLE erp.account_balances FORCE ROW LEVEL SECURITY;
