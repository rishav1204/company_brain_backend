-- ERP-04: Deprecate public.journal_entries; reads should use erp.journals

COMMENT ON TABLE public.journal_entries IS
  'DEPRECATED — use erp.journals and erp.journal_lines. Writes blocked by trg_block_legacy_journal_entries_writes.';

-- Idempotent header backfill for any rows added before migration 080
INSERT INTO erp.journals (
    id, org_id, company_id, journal_number, journal_type, journal_status,
    posting_date, description, source_type, currency_code, exchange_rate, created_at
)
SELECT
    je.id,
    je.org_id,
    (SELECT c.id FROM core.companies c WHERE c.org_id = je.org_id ORDER BY c.created_at ASC NULLS LAST LIMIT 1),
    'LEG-' || LEFT(je.id::text, 8),
    'legacy',
    CASE
        WHEN lower(COALESCE(je.status, '')) IN ('posted', 'approved', 'reversed', 'cancelled')
            THEN lower(je.status)
        ELSE 'posted'
    END,
    COALESCE(je.entry_date, CURRENT_DATE),
    'Migrated from public.journal_entries (period ' || COALESCE(je.period, 'unknown') || ')',
    'legacy_migration',
    'INR',
    1,
    now()
FROM public.journal_entries je
WHERE NOT EXISTS (SELECT 1 FROM erp.journals j WHERE j.id = je.id)
ON CONFLICT DO NOTHING;
