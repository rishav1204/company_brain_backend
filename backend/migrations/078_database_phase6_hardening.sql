-- Phase 6 database hardening: constraints, indexes, session security, double-entry, archival prep

-- ---------------------------------------------------------------------------
-- DB-03: Globally unique refresh token hash + SECURITY DEFINER session consume
-- ---------------------------------------------------------------------------
CREATE UNIQUE INDEX IF NOT EXISTS idx_core_sessions_refresh_hash_unique
    ON core.sessions (refresh_token_hash);

CREATE OR REPLACE FUNCTION core.consume_session_by_refresh_hash(p_hash text)
RETURNS TABLE (
    id uuid,
    user_id uuid,
    org_id uuid,
    expires_at timestamptz,
    revoked boolean,
    reuse_detected boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, public
AS $$
DECLARE
    v_row core.sessions%ROWTYPE;
BEGIN
    UPDATE core.sessions s
    SET revoked = TRUE
    WHERE s.refresh_token_hash = p_hash
      AND s.revoked = FALSE
      AND s.expires_at > NOW()
    RETURNING s.* INTO v_row;

    IF FOUND THEN
        id := v_row.id;
        user_id := v_row.user_id;
        org_id := v_row.org_id;
        expires_at := v_row.expires_at;
        revoked := v_row.revoked;
        reuse_detected := FALSE;
        RETURN NEXT;
        RETURN;
    END IF;

    SELECT s.* INTO v_row
    FROM core.sessions s
    WHERE s.refresh_token_hash = p_hash
    LIMIT 1;

    IF FOUND AND v_row.revoked THEN
        id := v_row.id;
        user_id := v_row.user_id;
        org_id := v_row.org_id;
        expires_at := v_row.expires_at;
        revoked := v_row.revoked;
        reuse_detected := TRUE;
        RETURN NEXT;
    END IF;
    RETURN;
END;
$$;

CREATE OR REPLACE FUNCTION core.get_session_by_refresh_hash(p_hash text)
RETURNS TABLE (
    id uuid,
    user_id uuid,
    org_id uuid,
    expires_at timestamptz,
    revoked boolean,
    refresh_token_hash text
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = core, public
AS $$
BEGIN
    RETURN QUERY
    SELECT s.id, s.user_id, s.org_id, s.expires_at, s.revoked, s.refresh_token_hash
    FROM core.sessions s
    WHERE s.refresh_token_hash = p_hash
    LIMIT 1;
END;
$$;

-- ---------------------------------------------------------------------------
-- DB-04: Multi-company data quality audit (flags orgs needing manual review)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.company_id_data_quality (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    table_name text NOT NULL,
    row_id uuid NOT NULL,
    company_id uuid NULL,
    issue_code text NOT NULL,
    detected_at timestamptz NOT NULL DEFAULT now(),
    resolved_at timestamptz NULL,
    UNIQUE (org_id, table_name, row_id, issue_code)
);

ALTER TABLE erp.company_id_data_quality ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS erp_company_id_dq_org ON erp.company_id_data_quality;
CREATE POLICY erp_company_id_dq_org ON erp.company_id_data_quality
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

INSERT INTO erp.company_id_data_quality (org_id, table_name, row_id, company_id, issue_code)
SELECT j.org_id, 'erp.journals', j.id, j.company_id, 'multi_company_ambiguous_backfill'
FROM erp.journals j
JOIN (
    SELECT org_id FROM core.companies GROUP BY org_id HAVING COUNT(*) > 1
) mc ON mc.org_id = j.org_id
WHERE j.company_id = (
    SELECT c.id FROM core.companies c
    WHERE c.org_id = j.org_id
    ORDER BY c.created_at ASC NULLS LAST, c.id ASC
    LIMIT 1
)
ON CONFLICT (org_id, table_name, row_id, issue_code) DO NOTHING;

-- ---------------------------------------------------------------------------
-- DB-06: branch_id on AP/AR headers (journals already have branch_id from 060)
-- ---------------------------------------------------------------------------
ALTER TABLE erp.ap_invoices
    ADD COLUMN IF NOT EXISTS branch_id uuid NULL REFERENCES core.branches(id) ON DELETE SET NULL;
ALTER TABLE erp.ar_invoices
    ADD COLUMN IF NOT EXISTS branch_id uuid NULL REFERENCES core.branches(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_erp_ap_invoices_branch ON erp.ap_invoices(org_id, branch_id) WHERE branch_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_erp_ar_invoices_branch ON erp.ar_invoices(org_id, branch_id) WHERE branch_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- DB-09 / DB-12: Remaining index gaps
-- ---------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_erp_ledger_entries_org_period_account
    ON erp.ledger_entries (org_id, fiscal_period_id, account_id);

CREATE INDEX IF NOT EXISTS idx_platform_event_store_org_created
    ON platform.event_store (org_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- DB-13: Validate company_id NOT NULL constraints when no violating rows remain
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

-- ---------------------------------------------------------------------------
-- DB-14: Prevent DELETE of posted journals (CASCADE on lines would orphan GL)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION erp.prevent_posted_journal_delete()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.journal_status IN ('posted', 'reversed') THEN
        RAISE EXCEPTION 'Cannot delete journal in status %', OLD.journal_status;
    END IF;
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_erp_journals_prevent_delete ON erp.journals;
CREATE TRIGGER trg_erp_journals_prevent_delete
    BEFORE DELETE ON erp.journals
    FOR EACH ROW
    EXECUTE FUNCTION erp.prevent_posted_journal_delete();

-- ---------------------------------------------------------------------------
-- DB-15: Database-level double-entry balance per journal (deferred constraint)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION erp.enforce_journal_double_entry()
RETURNS TRIGGER AS $$
DECLARE
    v_journal_id uuid;
    total_debit numeric(18,2);
    total_credit numeric(18,2);
BEGIN
    v_journal_id := COALESCE(NEW.journal_id, OLD.journal_id);
    SELECT COALESCE(SUM(debit_amount), 0), COALESCE(SUM(credit_amount), 0)
    INTO total_debit, total_credit
    FROM erp.journal_lines
    WHERE journal_id = v_journal_id;

    IF total_debit <> total_credit THEN
        RAISE EXCEPTION 'Journal % is not balanced: debit=% credit=%', v_journal_id, total_debit, total_credit;
    END IF;
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_erp_journal_lines_balance ON erp.journal_lines;
CREATE CONSTRAINT TRIGGER trg_erp_journal_lines_balance
    AFTER INSERT OR UPDATE OR DELETE ON erp.journal_lines
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW
    EXECUTE FUNCTION erp.enforce_journal_double_entry();

-- ---------------------------------------------------------------------------
-- DB-16: Link invoice predictions to posted AP invoices (drift control)
-- ---------------------------------------------------------------------------
ALTER TABLE finance_os.invoice_predictions
    ADD COLUMN IF NOT EXISTS ap_invoice_id uuid NULL REFERENCES erp.ap_invoices(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS synced_at timestamptz NULL;

CREATE INDEX IF NOT EXISTS idx_fin_os_invoice_predictions_ap_invoice
    ON finance_os.invoice_predictions(org_id, ap_invoice_id)
    WHERE ap_invoice_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- DB-17: Archival / partition-readiness (ledger + audit)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.ledger_entries_archive (
    LIKE erp.ledger_entries INCLUDING ALL
);

ALTER TABLE erp.ledger_entries_archive ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS erp_ledger_entries_archive_org ON erp.ledger_entries_archive;
CREATE POLICY erp_ledger_entries_archive_org ON erp.ledger_entries_archive
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());

CREATE OR REPLACE FUNCTION erp.archive_ledger_entries_before(p_cutoff date)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    moved integer;
BEGIN
    WITH moved_rows AS (
        DELETE FROM erp.ledger_entries le
        WHERE le.posting_date < p_cutoff
        RETURNING le.*
    )
    INSERT INTO erp.ledger_entries_archive
    SELECT * FROM moved_rows;
    GET DIAGNOSTICS moved = ROW_COUNT;
    RETURN moved;
END;
$$;

CREATE TABLE IF NOT EXISTS audit.audit_logs_archive (
    LIKE audit.audit_logs INCLUDING ALL
);

CREATE INDEX IF NOT EXISTS idx_audit_logs_org_created
    ON audit.audit_logs (org_id, timestamp DESC);

CREATE OR REPLACE FUNCTION audit.archive_audit_logs_before(p_cutoff timestamptz)
RETURNS integer
LANGUAGE plpgsql
AS $$
DECLARE
    moved integer;
BEGIN
    WITH moved_rows AS (
        DELETE FROM audit.audit_logs al
        WHERE al.timestamp < p_cutoff
          AND COALESCE(al.payload_jsonb->>'archived', 'false') = 'true'
        RETURNING al.*
    )
    INSERT INTO audit.audit_logs_archive
    SELECT * FROM moved_rows
    ON CONFLICT (id) DO NOTHING;
    GET DIAGNOSTICS moved = ROW_COUNT;
    RETURN moved;
END;
$$;

-- ---------------------------------------------------------------------------
-- DB-23/24: Subledger vs GL reconciliation run log
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.subledger_gl_reconciliation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    run_type text NOT NULL,
    status text NOT NULL DEFAULT 'completed',
    variance_amount numeric(18,2) NOT NULL DEFAULT 0,
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_erp_subledger_gl_recon_org_type
    ON erp.subledger_gl_reconciliation_runs (org_id, run_type, created_at DESC);

ALTER TABLE erp.subledger_gl_reconciliation_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS erp_subledger_gl_recon_org ON erp.subledger_gl_reconciliation_runs;
CREATE POLICY erp_subledger_gl_recon_org ON erp.subledger_gl_reconciliation_runs
    USING (org_id = app_current_org_id())
    WITH CHECK (org_id = app_current_org_id());
