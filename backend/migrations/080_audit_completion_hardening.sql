-- Post-audit completion: FORCE RLS, branch_id, structural modules, constraint validation, legacy migration

-- ---------------------------------------------------------------------------
-- DB-01: FORCE ROW LEVEL SECURITY on core.* and erp.* tables that have RLS
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    r RECORD;
BEGIN
    FOR r IN
        SELECT n.nspname AS schema_name, c.relname AS table_name
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('core', 'erp')
          AND c.relkind = 'r'
          AND c.relrowsecurity = true
    LOOP
        EXECUTE format('ALTER TABLE %I.%I FORCE ROW LEVEL SECURITY', r.schema_name, r.table_name);
    END LOOP;
END $$;

-- ---------------------------------------------------------------------------
-- DB-06/07: branch_id on ap_payments
-- ---------------------------------------------------------------------------
ALTER TABLE erp.ap_payments ADD COLUMN IF NOT EXISTS branch_id uuid NULL REFERENCES core.branches(id);

CREATE INDEX IF NOT EXISTS idx_erp_ap_payments_org_branch
    ON erp.ap_payments (org_id, branch_id)
    WHERE branch_id IS NOT NULL;

-- ---------------------------------------------------------------------------
-- DB-04: metadata on company_id_data_quality for remediation audit
-- ---------------------------------------------------------------------------
ALTER TABLE erp.company_id_data_quality ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb;

-- ---------------------------------------------------------------------------
-- DB-13: Validate company_id constraints when data is clean
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
-- ERP-04 / STR-Public: migrate legacy public.journal_entries into erp.journals
-- ---------------------------------------------------------------------------
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

-- ---------------------------------------------------------------------------
-- STR-FX: exchange rates and revaluation runs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.exchange_rates (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    company_id uuid NULL REFERENCES core.companies(id),
    from_currency text NOT NULL,
    to_currency text NOT NULL DEFAULT 'INR',
    rate numeric(18,8) NOT NULL,
    rate_date date NOT NULL,
    source text NOT NULL DEFAULT 'manual',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, from_currency, to_currency, rate_date)
);

CREATE TABLE IF NOT EXISTS erp.fx_revaluation_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    company_id uuid NULL,
    fiscal_period_id uuid NULL REFERENCES erp.fiscal_periods(id),
    revaluation_date date NOT NULL,
    status text NOT NULL DEFAULT 'completed',
    total_unrealized_gain numeric(18,2) NOT NULL DEFAULT 0,
    total_unrealized_loss numeric(18,2) NOT NULL DEFAULT 0,
    journal_id uuid NULL REFERENCES erp.journals(id),
    details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.exchange_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.fx_revaluation_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.exchange_rates FORCE ROW LEVEL SECURITY;
ALTER TABLE erp.fx_revaluation_runs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS erp_exchange_rates_org ON erp.exchange_rates;
CREATE POLICY erp_exchange_rates_org ON erp.exchange_rates
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
DROP POLICY IF EXISTS erp_fx_reval_org ON erp.fx_revaluation_runs;
CREATE POLICY erp_fx_reval_org ON erp.fx_revaluation_runs
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

-- ---------------------------------------------------------------------------
-- STR-Parallel ledger: secondary ledger books
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.parallel_ledgers (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    company_id uuid NULL REFERENCES core.companies(id),
    ledger_code text NOT NULL,
    ledger_name text NOT NULL,
    accounting_standard text NOT NULL DEFAULT 'IFRS',
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, ledger_code)
);

CREATE TABLE IF NOT EXISTS erp.parallel_ledger_entries (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    parallel_ledger_id uuid NOT NULL REFERENCES erp.parallel_ledgers(id),
    source_journal_id uuid NOT NULL REFERENCES erp.journals(id),
    account_id uuid NOT NULL REFERENCES erp.chart_of_accounts(id),
    debit_amount numeric(18,2) NOT NULL DEFAULT 0,
    credit_amount numeric(18,2) NOT NULL DEFAULT 0,
    posting_date date NOT NULL,
    fiscal_period_id uuid NULL REFERENCES erp.fiscal_periods(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.parallel_ledgers ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.parallel_ledger_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.parallel_ledgers FORCE ROW LEVEL SECURITY;
ALTER TABLE erp.parallel_ledger_entries FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS erp_parallel_ledgers_org ON erp.parallel_ledgers;
CREATE POLICY erp_parallel_ledgers_org ON erp.parallel_ledgers
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
DROP POLICY IF EXISTS erp_parallel_ledger_entries_org ON erp.parallel_ledger_entries;
CREATE POLICY erp_parallel_ledger_entries_org ON erp.parallel_ledger_entries
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

-- ---------------------------------------------------------------------------
-- STR-BOE: Bill of Entry (import customs)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.bills_of_entry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    company_id uuid NULL REFERENCES core.companies(id),
    branch_id uuid NULL REFERENCES core.branches(id),
    boe_number text NOT NULL,
    boe_date date NOT NULL,
    port_code text NULL,
    vendor_id uuid NULL REFERENCES erp.vendors(id),
    po_id uuid NULL REFERENCES erp.purchase_orders(id),
    assessable_value numeric(18,2) NOT NULL DEFAULT 0,
    customs_duty numeric(18,2) NOT NULL DEFAULT 0,
    igst_import numeric(18,2) NOT NULL DEFAULT 0,
    currency_code text NOT NULL DEFAULT 'INR',
    exchange_rate numeric(18,8) NOT NULL DEFAULT 1,
    status text NOT NULL DEFAULT 'draft',
    journal_id uuid NULL REFERENCES erp.journals(id),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, boe_number)
);

ALTER TABLE erp.bills_of_entry ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.bills_of_entry FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS erp_boe_org ON erp.bills_of_entry;
CREATE POLICY erp_boe_org ON erp.bills_of_entry
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

-- ---------------------------------------------------------------------------
-- ERP-18: Payroll employees for 24Q
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS erp.payroll_employees (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    company_id uuid NULL REFERENCES core.companies(id),
    employee_code text NOT NULL,
    pan text NOT NULL,
    name text NOT NULL,
    date_of_joining date NULL,
    status text NOT NULL DEFAULT 'active',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (org_id, employee_code)
);

CREATE TABLE IF NOT EXISTS erp.payroll_salary_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    company_id uuid NULL REFERENCES core.companies(id),
    employee_id uuid NOT NULL REFERENCES erp.payroll_employees(id),
    return_period text NOT NULL,
    gross_salary numeric(18,2) NOT NULL DEFAULT 0,
    tds_section text NOT NULL DEFAULT '192',
    tds_amount numeric(18,2) NOT NULL DEFAULT 0,
    challan_number text NULL,
    payment_date date NULL,
    status text NOT NULL DEFAULT 'calculated',
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE erp.payroll_employees ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.payroll_salary_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE erp.payroll_employees FORCE ROW LEVEL SECURITY;
ALTER TABLE erp.payroll_salary_runs FORCE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS erp_payroll_employees_org ON erp.payroll_employees;
CREATE POLICY erp_payroll_employees_org ON erp.payroll_employees
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());
DROP POLICY IF EXISTS erp_payroll_salary_runs_org ON erp.payroll_salary_runs;
CREATE POLICY erp_payroll_salary_runs_org ON erp.payroll_salary_runs
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

CREATE INDEX IF NOT EXISTS idx_erp_payroll_salary_runs_period
    ON erp.payroll_salary_runs (org_id, return_period);

-- ---------------------------------------------------------------------------
-- DB-27: Neo4j graph sync outbox
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS finance_os.graph_sync_outbox (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id uuid NOT NULL,
    event_type text NOT NULL,
    payload jsonb NOT NULL,
    status text NOT NULL DEFAULT 'pending',
    attempts int NOT NULL DEFAULT 0,
    last_error text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz NULL
);

ALTER TABLE finance_os.graph_sync_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE finance_os.graph_sync_outbox FORCE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS fin_os_graph_outbox_org ON finance_os.graph_sync_outbox;
CREATE POLICY fin_os_graph_outbox_org ON finance_os.graph_sync_outbox
    USING (org_id = app_current_org_id()) WITH CHECK (org_id = app_current_org_id());

CREATE INDEX IF NOT EXISTS idx_fin_os_graph_outbox_pending
    ON finance_os.graph_sync_outbox (org_id, status, created_at)
    WHERE status = 'pending';
