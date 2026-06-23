-- P2 scalability + P1 company scope: remaining tenant indexes and ERP company_id hardening.

-- Backfill company_id on ERP transactional rows from org's first company
UPDATE erp.journals j
SET company_id = c.id
FROM (
    SELECT DISTINCT ON (org_id) org_id, id
    FROM core.companies
    ORDER BY org_id, created_at ASC
) c
WHERE j.company_id IS NULL AND j.org_id = c.org_id;

UPDATE erp.ap_invoices i
SET company_id = c.id
FROM (
    SELECT DISTINCT ON (org_id) org_id, id
    FROM core.companies
    ORDER BY org_id, created_at ASC
) c
WHERE i.company_id IS NULL AND i.org_id = c.org_id;

UPDATE erp.ar_invoices i
SET company_id = c.id
FROM (
    SELECT DISTINCT ON (org_id) org_id, id
    FROM core.companies
    ORDER BY org_id, created_at ASC
) c
WHERE i.company_id IS NULL AND i.org_id = c.org_id;

UPDATE erp.vouchers v
SET company_id = c.id
FROM (
    SELECT DISTINCT ON (org_id) org_id, id
    FROM core.companies
    ORDER BY org_id, created_at ASC
) c
WHERE v.company_id IS NULL AND v.org_id = c.org_id;

ALTER TABLE erp.journals
  ADD CONSTRAINT chk_erp_journals_company_id_not_null CHECK (company_id IS NOT NULL) NOT VALID;
ALTER TABLE erp.ap_invoices
  ADD CONSTRAINT chk_erp_ap_invoices_company_id_not_null CHECK (company_id IS NOT NULL) NOT VALID;
ALTER TABLE erp.ar_invoices
  ADD CONSTRAINT chk_erp_ar_invoices_company_id_not_null CHECK (company_id IS NOT NULL) NOT VALID;
ALTER TABLE erp.vouchers
  ADD CONSTRAINT chk_erp_vouchers_company_id_not_null CHECK (company_id IS NOT NULL) NOT VALID;

-- High-traffic / audit-flagged tenant indexes
CREATE INDEX IF NOT EXISTS idx_workflow_escalations_org_status
  ON workflow.escalations (org_id, status);

CREATE INDEX IF NOT EXISTS idx_workflow_org_holidays_org
  ON workflow.org_holidays (org_id, holiday_date);

CREATE INDEX IF NOT EXISTS idx_workflow_scheduled_workflows_org
  ON workflow.scheduled_workflows (org_id, next_run_at);

CREATE INDEX IF NOT EXISTS idx_documents_versions_org_doc
  ON documents.document_versions (org_id, document_id);

CREATE INDEX IF NOT EXISTS idx_documents_duplicate_candidates_org
  ON documents.duplicate_candidates (org_id, document_id);

CREATE INDEX IF NOT EXISTS idx_erp_gst_reconciliations_org_period
  ON erp.gst_reconciliations (org_id, return_period);

CREATE INDEX IF NOT EXISTS idx_erp_fiscal_years_org_start
  ON erp.fiscal_years (org_id, year_start);

CREATE INDEX IF NOT EXISTS idx_erp_inventory_adjustments_org_item
  ON erp.inventory_adjustments (org_id, item_id);

CREATE INDEX IF NOT EXISTS idx_erp_compliance_rules_org
  ON erp.compliance_rules (org_id, rule_code);

CREATE INDEX IF NOT EXISTS idx_erp_compliance_reminders_org_due
  ON erp.compliance_reminders (org_id, due_date);

CREATE INDEX IF NOT EXISTS idx_erp_tds_rules_org_section
  ON erp.tds_rules (org_id, section_code);

CREATE INDEX IF NOT EXISTS idx_erp_tds_challans_org_period
  ON erp.tds_challans (org_id, financial_year, quarter);

CREATE INDEX IF NOT EXISTS idx_erp_tds_returns_org_period
  ON erp.tds_returns (org_id, financial_year, quarter);

CREATE INDEX IF NOT EXISTS idx_erp_expense_policy_violations_org
  ON erp.expense_policy_violations (org_id, claim_id);

CREATE INDEX IF NOT EXISTS idx_governance_retention_policies_org
  ON governance.retention_policies (org_id);

CREATE INDEX IF NOT EXISTS idx_notifications_preferences_org_user
  ON notifications.preferences (org_id, user_id);

CREATE INDEX IF NOT EXISTS idx_public_journal_entries_org
  ON public.journal_entries (org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_public_roles_org
  ON public.roles (org_id);
