-- AP/AR credit & debit note document types (canonical CN/DN entities on invoice tables)

ALTER TABLE erp.ap_invoices
  ADD COLUMN IF NOT EXISTS document_type varchar(32) NOT NULL DEFAULT 'invoice',
  ADD COLUMN IF NOT EXISTS reference_invoice_id uuid NULL REFERENCES erp.ap_invoices(id) ON DELETE SET NULL;

ALTER TABLE erp.ar_invoices
  ADD COLUMN IF NOT EXISTS document_type varchar(32) NOT NULL DEFAULT 'invoice',
  ADD COLUMN IF NOT EXISTS reference_invoice_id uuid NULL REFERENCES erp.ar_invoices(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_erp_ap_invoices_document_type
  ON erp.ap_invoices(org_id, document_type, invoice_date DESC);
CREATE INDEX IF NOT EXISTS idx_erp_ar_invoices_document_type
  ON erp.ar_invoices(org_id, document_type, invoice_date DESC);
