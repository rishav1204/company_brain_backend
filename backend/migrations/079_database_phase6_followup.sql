-- Phase 6 follow-up: expand company_id data quality flags to AP/AR/vouchers

INSERT INTO erp.company_id_data_quality (org_id, table_name, row_id, company_id, issue_code)
SELECT j.org_id, 'erp.ap_invoices', j.id, j.company_id, 'multi_company_ambiguous_backfill'
FROM erp.ap_invoices j
JOIN (SELECT org_id FROM core.companies GROUP BY org_id HAVING COUNT(*) > 1) mc ON mc.org_id = j.org_id
WHERE j.company_id = (
    SELECT c.id FROM core.companies c
    WHERE c.org_id = j.org_id
    ORDER BY c.created_at ASC NULLS LAST, c.id ASC
    LIMIT 1
)
ON CONFLICT (org_id, table_name, row_id, issue_code) DO NOTHING;

INSERT INTO erp.company_id_data_quality (org_id, table_name, row_id, company_id, issue_code)
SELECT j.org_id, 'erp.ar_invoices', j.id, j.company_id, 'multi_company_ambiguous_backfill'
FROM erp.ar_invoices j
JOIN (SELECT org_id FROM core.companies GROUP BY org_id HAVING COUNT(*) > 1) mc ON mc.org_id = j.org_id
WHERE j.company_id = (
    SELECT c.id FROM core.companies c
    WHERE c.org_id = j.org_id
    ORDER BY c.created_at ASC NULLS LAST, c.id ASC
    LIMIT 1
)
ON CONFLICT (org_id, table_name, row_id, issue_code) DO NOTHING;

INSERT INTO erp.company_id_data_quality (org_id, table_name, row_id, company_id, issue_code)
SELECT j.org_id, 'erp.vouchers', j.id, j.company_id, 'multi_company_ambiguous_backfill'
FROM erp.vouchers j
JOIN (SELECT org_id FROM core.companies GROUP BY org_id HAVING COUNT(*) > 1) mc ON mc.org_id = j.org_id
WHERE j.company_id = (
    SELECT c.id FROM core.companies c
    WHERE c.org_id = j.org_id
    ORDER BY c.created_at ASC NULLS LAST, c.id ASC
    LIMIT 1
)
ON CONFLICT (org_id, table_name, row_id, issue_code) DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM erp.journals WHERE company_id IS NULL) THEN
        ALTER TABLE erp.journals VALIDATE CONSTRAINT chk_erp_journals_company_id_not_null;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM erp.ap_invoices WHERE company_id IS NULL) THEN
        ALTER TABLE erp.ap_invoices VALIDATE CONSTRAINT chk_erp_ap_invoices_company_id_not_null;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM erp.ar_invoices WHERE company_id IS NULL) THEN
        ALTER TABLE erp.ar_invoices VALIDATE CONSTRAINT chk_erp_ar_invoices_company_id_not_null;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM erp.vouchers WHERE company_id IS NULL) THEN
        ALTER TABLE erp.vouchers VALIDATE CONSTRAINT chk_erp_vouchers_company_id_not_null;
    END IF;
END $$;
