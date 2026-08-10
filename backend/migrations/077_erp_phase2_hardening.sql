-- Phase 2 ERP hardening: line-level 3-way match + COA versioning

ALTER TABLE erp.ap_invoice_lines
    ADD COLUMN IF NOT EXISTS po_item_id uuid NULL REFERENCES erp.purchase_order_items(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_erp_ap_invoice_lines_po_item
    ON erp.ap_invoice_lines(org_id, po_item_id)
    WHERE po_item_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS erp.coa_versions (
    id uuid PRIMARY KEY,
    org_id uuid NOT NULL,
    fiscal_year varchar(16) NOT NULL,
    version_label varchar(64) NOT NULL DEFAULT 'default',
    effective_from date NOT NULL,
    effective_to date NULL,
    snapshot jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, fiscal_year, version_label)
);

ALTER TABLE erp.coa_versions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS erp_coa_versions_org ON erp.coa_versions;
CREATE POLICY erp_coa_versions_org ON erp.coa_versions
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());
