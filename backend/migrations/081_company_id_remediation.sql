-- DB-04: Automated company_id remediation for multi-company orgs

ALTER TABLE erp.journals ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

-- ---------------------------------------------------------------------------
-- Phase 1: Single-company orgs — assign sole company and resolve all flags
-- ---------------------------------------------------------------------------
WITH sole AS (
    SELECT org_id, (array_agg(id ORDER BY created_at ASC NULLS LAST, id ASC))[1] AS company_id
    FROM core.companies
    GROUP BY org_id
    HAVING COUNT(*) = 1
)
UPDATE erp.journals j
SET company_id = s.company_id, updated_at = COALESCE(j.updated_at, now())
FROM sole s
WHERE j.org_id = s.org_id AND j.company_id IS DISTINCT FROM s.company_id;

WITH sole AS (
    SELECT org_id, (array_agg(id ORDER BY created_at ASC NULLS LAST, id ASC))[1] AS company_id
    FROM core.companies
    GROUP BY org_id
    HAVING COUNT(*) = 1
)
UPDATE erp.ap_invoices i
SET company_id = s.company_id, updated_at = COALESCE(i.updated_at, now())
FROM sole s
WHERE i.org_id = s.org_id AND i.company_id IS DISTINCT FROM s.company_id;

WITH sole AS (
    SELECT org_id, (array_agg(id ORDER BY created_at ASC NULLS LAST, id ASC))[1] AS company_id
    FROM core.companies
    GROUP BY org_id
    HAVING COUNT(*) = 1
)
UPDATE erp.ar_invoices i
SET company_id = s.company_id, updated_at = COALESCE(i.updated_at, now())
FROM sole s
WHERE i.org_id = s.org_id AND i.company_id IS DISTINCT FROM s.company_id;

WITH sole AS (
    SELECT org_id, (array_agg(id ORDER BY created_at ASC NULLS LAST, id ASC))[1] AS company_id
    FROM core.companies
    GROUP BY org_id
    HAVING COUNT(*) = 1
)
UPDATE erp.vouchers v
SET company_id = s.company_id, updated_at = COALESCE(v.updated_at, now())
FROM sole s
WHERE v.org_id = s.org_id AND v.company_id IS DISTINCT FROM s.company_id;

UPDATE erp.company_id_data_quality dq
SET resolved_at = now(),
    metadata = COALESCE(dq.metadata, '{}'::jsonb) || '{"remediation":"single_company_org"}'::jsonb
WHERE dq.resolved_at IS NULL
  AND dq.org_id IN (
      SELECT org_id FROM core.companies GROUP BY org_id HAVING COUNT(*) = 1
  );

-- ---------------------------------------------------------------------------
-- Phase 2: Multi-company — infer company_id from branch_id
-- ---------------------------------------------------------------------------
UPDATE erp.journals j
SET company_id = b.company_id, updated_at = COALESCE(j.updated_at, now())
FROM core.branches b
WHERE j.branch_id = b.id
  AND j.org_id = b.org_id
  AND j.company_id IS DISTINCT FROM b.company_id;

UPDATE erp.ap_invoices i
SET company_id = b.company_id, updated_at = COALESCE(i.updated_at, now())
FROM core.branches b
WHERE i.branch_id = b.id
  AND i.org_id = b.org_id
  AND i.company_id IS DISTINCT FROM b.company_id;

UPDATE erp.ar_invoices i
SET company_id = b.company_id, updated_at = COALESCE(i.updated_at, now())
FROM core.branches b
WHERE i.branch_id = b.id
  AND i.org_id = b.org_id
  AND i.company_id IS DISTINCT FROM b.company_id;

UPDATE erp.vouchers v
SET company_id = b.company_id, updated_at = COALESCE(v.updated_at, now())
FROM core.branches b
WHERE v.branch_id = b.id
  AND v.org_id = b.org_id
  AND v.company_id IS DISTINCT FROM b.company_id;

-- ---------------------------------------------------------------------------
-- Phase 3: Journals from source documents (AP/AR invoices)
-- ---------------------------------------------------------------------------
UPDATE erp.journals j
SET company_id = ap.company_id, updated_at = COALESCE(j.updated_at, now())
FROM erp.ap_invoices ap
WHERE j.org_id = ap.org_id
  AND j.source_id = ap.id
  AND lower(COALESCE(j.source_type, '')) IN ('ap_invoice', 'ap.payment', 'accounts_payable')
  AND j.company_id IS DISTINCT FROM ap.company_id
  AND ap.company_id IS NOT NULL;

UPDATE erp.journals j
SET company_id = ar.company_id, updated_at = COALESCE(j.updated_at, now())
FROM erp.ar_invoices ar
WHERE j.org_id = ar.org_id
  AND j.source_id = ar.id
  AND lower(COALESCE(j.source_type, '')) IN ('ar_invoice', 'ar.payment', 'accounts_receivable', 'sales_invoice')
  AND j.company_id IS DISTINCT FROM ar.company_id
  AND ar.company_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Phase 4: Vouchers from posted journal company_id
-- ---------------------------------------------------------------------------
UPDATE erp.vouchers v
SET company_id = j.company_id, updated_at = COALESCE(v.updated_at, now())
FROM erp.journals j
WHERE v.org_id = j.org_id
  AND v.journal_id = j.id
  AND j.company_id IS NOT NULL
  AND v.company_id IS DISTINCT FROM j.company_id;

-- ---------------------------------------------------------------------------
-- Phase 5: Metadata authoritative company_id on flagged rows
-- ---------------------------------------------------------------------------
UPDATE erp.journals j
SET company_id = (j.metadata->>'authoritative_company_id')::uuid, updated_at = COALESCE(j.updated_at, now())
WHERE j.metadata ? 'authoritative_company_id'
  AND (j.metadata->>'authoritative_company_id') ~* '^[0-9a-f-]{36}$'
  AND j.company_id::text IS DISTINCT FROM j.metadata->>'authoritative_company_id';

UPDATE erp.ap_invoices i
SET company_id = (i.metadata->>'authoritative_company_id')::uuid, updated_at = COALESCE(i.updated_at, now())
WHERE i.metadata ? 'authoritative_company_id'
  AND (i.metadata->>'authoritative_company_id') ~* '^[0-9a-f-]{36}$'
  AND i.company_id::text IS DISTINCT FROM i.metadata->>'authoritative_company_id';

UPDATE erp.ar_invoices i
SET company_id = (i.metadata->>'authoritative_company_id')::uuid, updated_at = COALESCE(i.updated_at, now())
WHERE i.metadata ? 'authoritative_company_id'
  AND (i.metadata->>'authoritative_company_id') ~* '^[0-9a-f-]{36}$'
  AND i.company_id::text IS DISTINCT FROM i.metadata->>'authoritative_company_id';

UPDATE erp.vouchers v
SET company_id = (v.metadata->>'authoritative_company_id')::uuid, updated_at = COALESCE(v.updated_at, now())
WHERE v.metadata ? 'authoritative_company_id'
  AND (v.metadata->>'authoritative_company_id') ~* '^[0-9a-f-]{36}$'
  AND v.company_id::text IS DISTINCT FROM v.metadata->>'authoritative_company_id';

-- ---------------------------------------------------------------------------
-- Phase 6: Resolve flags where row no longer uses ambiguous first-company backfill
-- ---------------------------------------------------------------------------
UPDATE erp.company_id_data_quality dq
SET resolved_at = now(),
    metadata = COALESCE(dq.metadata, '{}'::jsonb) || '{"remediation":"auto_corrected"}'::jsonb
WHERE dq.resolved_at IS NULL
  AND dq.issue_code = 'multi_company_ambiguous_backfill'
  AND dq.table_name = 'erp.journals'
  AND EXISTS (
      SELECT 1 FROM erp.journals j
      WHERE j.id = dq.row_id AND j.org_id = dq.org_id
        AND j.company_id IS NOT NULL
        AND j.company_id <> (
            SELECT c.id FROM core.companies c
            WHERE c.org_id = j.org_id
            ORDER BY c.created_at ASC NULLS LAST, c.id ASC
            LIMIT 1
        )
  );

UPDATE erp.company_id_data_quality dq
SET resolved_at = now(),
    metadata = COALESCE(dq.metadata, '{}'::jsonb) || '{"remediation":"auto_corrected"}'::jsonb
WHERE dq.resolved_at IS NULL
  AND dq.issue_code = 'multi_company_ambiguous_backfill'
  AND dq.table_name = 'erp.ap_invoices'
  AND EXISTS (
      SELECT 1 FROM erp.ap_invoices i
      WHERE i.id = dq.row_id AND i.org_id = dq.org_id
        AND i.company_id IS NOT NULL
        AND i.company_id <> (
            SELECT c.id FROM core.companies c
            WHERE c.org_id = i.org_id
            ORDER BY c.created_at ASC NULLS LAST, c.id ASC
            LIMIT 1
        )
  );

UPDATE erp.company_id_data_quality dq
SET resolved_at = now(),
    metadata = COALESCE(dq.metadata, '{}'::jsonb) || '{"remediation":"auto_corrected"}'::jsonb
WHERE dq.resolved_at IS NULL
  AND dq.issue_code = 'multi_company_ambiguous_backfill'
  AND dq.table_name = 'erp.ar_invoices'
  AND EXISTS (
      SELECT 1 FROM erp.ar_invoices i
      WHERE i.id = dq.row_id AND i.org_id = dq.org_id
        AND i.company_id IS NOT NULL
        AND i.company_id <> (
            SELECT c.id FROM core.companies c
            WHERE c.org_id = i.org_id
            ORDER BY c.created_at ASC NULLS LAST, c.id ASC
            LIMIT 1
        )
  );

UPDATE erp.company_id_data_quality dq
SET resolved_at = now(),
    metadata = COALESCE(dq.metadata, '{}'::jsonb) || '{"remediation":"auto_corrected"}'::jsonb
WHERE dq.resolved_at IS NULL
  AND dq.issue_code = 'multi_company_ambiguous_backfill'
  AND dq.table_name = 'erp.vouchers'
  AND EXISTS (
      SELECT 1 FROM erp.vouchers v
      WHERE v.id = dq.row_id AND v.org_id = dq.org_id
        AND v.company_id IS NOT NULL
        AND v.company_id <> (
            SELECT c.id FROM core.companies c
            WHERE c.org_id = v.org_id
            ORDER BY c.created_at ASC NULLS LAST, c.id ASC
            LIMIT 1
        )
  );

-- ---------------------------------------------------------------------------
-- DB-13: Re-validate constraints after remediation
-- ---------------------------------------------------------------------------
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
