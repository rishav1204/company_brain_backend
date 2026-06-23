-- P1 tenancy & integrity: canonical fiscal periods, block legacy accounting writes.

-- 1) Migrate core.fiscal_periods rows into erp.fiscal_periods where missing (canonical = erp.*)
INSERT INTO erp.fiscal_periods (id, org_id, company_id, period_name, start_date, end_date, status, is_locked)
SELECT
    cfp.id,
    cfp.org_id,
    cfp.company_id,
    cfp.period_key,
    cfp.starts_on,
    cfp.ends_on,
    CASE WHEN cfp.status = 'open' THEN 'open' ELSE cfp.status END,
    cfp.status IN ('locked', 'closed')
FROM core.fiscal_periods cfp
WHERE NOT EXISTS (
    SELECT 1 FROM erp.fiscal_periods efp
    WHERE efp.org_id = cfp.org_id
      AND COALESCE(efp.company_id, '00000000-0000-0000-0000-000000000000'::uuid)
        = COALESCE(cfp.company_id, '00000000-0000-0000-0000-000000000000'::uuid)
      AND efp.period_name = cfp.period_key
)
ON CONFLICT DO NOTHING;

COMMENT ON TABLE core.fiscal_periods IS 'DEPRECATED: canonical fiscal periods live in erp.fiscal_periods (M12).';

CREATE OR REPLACE FUNCTION app_block_core_fiscal_period_writes()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'core.fiscal_periods is deprecated; use erp.fiscal_periods via fiscal module APIs';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_core_fiscal_period_writes ON core.fiscal_periods;
CREATE TRIGGER trg_block_core_fiscal_period_writes
    BEFORE INSERT OR UPDATE OR DELETE ON core.fiscal_periods
    FOR EACH ROW EXECUTE FUNCTION app_block_core_fiscal_period_writes();

-- 2) Block legacy public accounting table writes (use erp.ap_invoices / erp.journals)
CREATE OR REPLACE FUNCTION app_block_legacy_public_invoices_writes()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'public.invoices is deprecated; use erp.ap_invoices / erp.ar_invoices';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_legacy_invoices_writes ON public.invoices;
CREATE TRIGGER trg_block_legacy_invoices_writes
    BEFORE INSERT OR UPDATE OR DELETE ON public.invoices
    FOR EACH ROW EXECUTE FUNCTION app_block_legacy_public_invoices_writes();

CREATE OR REPLACE FUNCTION app_block_legacy_journal_entries_writes()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'public.journal_entries is deprecated; use erp.journals and posting_orchestrator';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_block_legacy_journal_entries_writes ON public.journal_entries;
CREATE TRIGGER trg_block_legacy_journal_entries_writes
    BEFORE INSERT OR UPDATE OR DELETE ON public.journal_entries
    FOR EACH ROW EXECUTE FUNCTION app_block_legacy_journal_entries_writes();
