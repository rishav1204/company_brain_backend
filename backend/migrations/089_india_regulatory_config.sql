-- 089: India regulatory config — versioned global params + org overrides
-- Platform dashboard can update statute without code releases.

CREATE SCHEMA IF NOT EXISTS platform;

-- Scalar parameters (rates, floors, deductions)
CREATE TABLE IF NOT EXISTS platform.regulatory_param (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code TEXT NOT NULL DEFAULT 'IN',
    domain TEXT NOT NULL,
    param_key TEXT NOT NULL,
    org_id UUID NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    value_numeric NUMERIC(18,6) NULL,
    value_text TEXT NULL,
    value_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    unit TEXT NULL,
    description TEXT NULL,
    effective_from DATE NOT NULL DEFAULT DATE '2000-01-01',
    effective_to DATE NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS platform_regulatory_param_uniq
    ON platform.regulatory_param (
        country_code, domain, param_key,
        COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid),
        effective_from
    );

CREATE INDEX IF NOT EXISTS platform_regulatory_param_lookup_idx
    ON platform.regulatory_param (country_code, param_key, org_id, status, effective_from);

-- Progressive slabs
CREATE TABLE IF NOT EXISTS platform.regulatory_slab_set (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code TEXT NOT NULL DEFAULT 'IN',
    set_code TEXT NOT NULL,
    name TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT 'income_tax',
    org_id UUID NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    effective_from DATE NOT NULL DEFAULT DATE '2000-01-01',
    effective_to DATE NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS platform_regulatory_slab_set_uniq
    ON platform.regulatory_slab_set (
        country_code, set_code,
        COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid),
        effective_from
    );

CREATE TABLE IF NOT EXISTS platform.regulatory_slab_band (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slab_set_id UUID NOT NULL REFERENCES platform.regulatory_slab_set(id) ON DELETE CASCADE,
    sort_order INT NOT NULL DEFAULT 0,
    upper_limit NUMERIC(18,2) NULL,
    rate_pct NUMERIC(8,4) NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS platform_regulatory_slab_band_set_idx
    ON platform.regulatory_slab_band (slab_set_id, sort_order);

-- Filing / operational thresholds
CREATE TABLE IF NOT EXISTS platform.regulatory_threshold (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code TEXT NOT NULL DEFAULT 'IN',
    threshold_code TEXT NOT NULL,
    org_id UUID NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    amount NUMERIC(18,2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    description TEXT NULL,
    effective_from DATE NOT NULL DEFAULT DATE '2000-01-01',
    effective_to DATE NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS platform_regulatory_threshold_uniq
    ON platform.regulatory_threshold (
        country_code, threshold_code,
        COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid),
        effective_from
    );

-- Penalty / late-fee formulas
CREATE TABLE IF NOT EXISTS platform.regulatory_penalty_formula (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code TEXT NOT NULL DEFAULT 'IN',
    formula_code TEXT NOT NULL,
    compliance_code_pattern TEXT NOT NULL,
    org_id UUID NULL REFERENCES core.organizations(id) ON DELETE CASCADE,
    daily_fee NUMERIC(18,2) NOT NULL DEFAULT 0,
    nil_daily_fee NUMERIC(18,2) NULL,
    fee_cap NUMERIC(18,2) NULL,
    interest_annual_pct NUMERIC(8,4) NULL,
    interest_monthly_pct NUMERIC(8,4) NULL,
    cap_by_turnover_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_from DATE NOT NULL DEFAULT DATE '2000-01-01',
    effective_to DATE NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS platform_regulatory_penalty_uniq
    ON platform.regulatory_penalty_formula (
        country_code, formula_code,
        COALESCE(org_id, '00000000-0000-0000-0000-000000000000'::uuid),
        effective_from
    );

-- Global TDS section templates
CREATE TABLE IF NOT EXISTS platform.regulatory_tds_section_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code TEXT NOT NULL DEFAULT 'IN',
    section_code TEXT NOT NULL,
    section_name TEXT NOT NULL,
    description TEXT NULL,
    rate_pan NUMERIC(8,4) NOT NULL DEFAULT 0,
    rate_no_pan NUMERIC(8,4) NOT NULL DEFAULT 20,
    threshold_amount NUMERIC(18,2) NOT NULL DEFAULT 0,
    payment_type TEXT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_from DATE NOT NULL DEFAULT DATE '2000-01-01',
    effective_to DATE NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS platform_regulatory_tds_tmpl_uniq
    ON platform.regulatory_tds_section_template (country_code, section_code, effective_from);

-- Compliance due-day templates (global)
CREATE TABLE IF NOT EXISTS platform.regulatory_compliance_template (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code TEXT NOT NULL DEFAULT 'IN',
    compliance_code TEXT NOT NULL,
    due_day INT NOT NULL,
    month_offset INT NOT NULL DEFAULT 1,
    frequency TEXT NOT NULL DEFAULT 'monthly',
    reminder_offsets JSONB NOT NULL DEFAULT '[30,15,7,3,1]'::jsonb,
    escalation_levels JSONB NOT NULL DEFAULT '["assignee","manager","finance_head","cfo"]'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    effective_from DATE NOT NULL DEFAULT DATE '2000-01-01',
    effective_to DATE NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS platform_regulatory_compliance_tmpl_uniq
    ON platform.regulatory_compliance_template (country_code, compliance_code, effective_from);

CREATE TABLE IF NOT EXISTS platform.regulatory_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_user_id UUID NULL,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    org_id UUID NULL,
    before_json JSONB NULL,
    after_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Extend tax rate / tds effective dating when tables exist
DO $$
BEGIN
  IF to_regclass('erp.tax_rate_master') IS NOT NULL THEN
    ALTER TABLE erp.tax_rate_master ADD COLUMN IF NOT EXISTS effective_from DATE NOT NULL DEFAULT DATE '2000-01-01';
    ALTER TABLE erp.tax_rate_master ADD COLUMN IF NOT EXISTS effective_to DATE NULL;
  END IF;
  IF to_regclass('erp.tds_sections') IS NOT NULL THEN
    ALTER TABLE erp.tds_sections ADD COLUMN IF NOT EXISTS effective_from DATE NOT NULL DEFAULT DATE '2000-01-01';
    ALTER TABLE erp.tds_sections ADD COLUMN IF NOT EXISTS effective_to DATE NULL;
  END IF;
  IF to_regclass('erp.tds_rules') IS NOT NULL THEN
    ALTER TABLE erp.tds_rules ADD COLUMN IF NOT EXISTS effective_from DATE NOT NULL DEFAULT DATE '2000-01-01';
    ALTER TABLE erp.tds_rules ADD COLUMN IF NOT EXISTS effective_to DATE NULL;
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Seeds: global IN statutes (mirror former code hardcodes)
-- ---------------------------------------------------------------------------

INSERT INTO platform.regulatory_param (
    country_code, domain, param_key, value_numeric, unit, description, effective_from
) VALUES
    ('IN', 'tds', 'tds.no_pan_floor_pct', 20, 'percent', 'u/s 206AA-style no-PAN floor rate %', DATE '2000-01-01'),
    ('IN', 'tds', 'tds.no_pan_multiplier', 2, 'x', 'Fallback multiplier when rate_no_pan missing', DATE '2000-01-01'),
    ('IN', 'gst', 'gst.interest_delay_pct', 18, 'percent', 'Interest on delayed GST payment', DATE '2000-01-01'),
    ('IN', 'gst', 'gst.interest_excess_itc_pct', 24, 'percent', 'Interest on excess ITC / wrongful reduction', DATE '2000-01-01'),
    ('IN', 'income_tax', 'income_tax.standard_deduction_annual', 75000, 'INR', 'Standard deduction (new regime salaried)', DATE '2024-04-01'),
    ('IN', 'income_tax', 'income_tax.rebate_87a_amount', 60000, 'INR', 'Section 87A rebate amount', DATE '2025-04-01'),
    ('IN', 'income_tax', 'income_tax.health_education_cess_pct', 4, 'percent', 'Health and education cess on tax', DATE '2000-01-01'),
    ('IN', 'income_tax', 'income_tax.default_slab_set', NULL, NULL, 'Default slab set code', DATE '2000-01-01'),
    ('IN', 'calendar', 'calendar.fy_start_month', 4, 'month', 'Financial year start month (India Apr)', DATE '2000-01-01'),
    ('IN', 'compliance', 'compliance.escalation_levels', NULL, NULL, 'Default escalation chain JSON', DATE '2000-01-01'),
    ('IN', 'pf', 'pf.employee_contrib_pct', 12, 'percent', 'PF employee contribution (stub)', DATE '2000-01-01'),
    ('IN', 'pf', 'pf.employer_contrib_pct', 12, 'percent', 'PF employer contribution (stub)', DATE '2000-01-01'),
    ('IN', 'pf', 'pf.wage_ceiling', 15000, 'INR', 'PF wage ceiling (stub)', DATE '2000-01-01'),
    ('IN', 'esi', 'esi.employee_contrib_pct', 0.75, 'percent', 'ESI employee contribution (stub)', DATE '2000-01-01'),
    ('IN', 'esi', 'esi.employer_contrib_pct', 3.25, 'percent', 'ESI employer contribution (stub)', DATE '2000-01-01'),
    ('IN', 'esi', 'esi.wage_ceiling', 21000, 'INR', 'ESI wage ceiling (stub)', DATE '2000-01-01'),
    ('IN', 'roc', 'roc.aoc4_due_day', 30, 'day', 'AOC-4 due day default (stub)', DATE '2000-01-01'),
    ('IN', 'roc', 'roc.mgt7_due_day', 30, 'day', 'MGT-7 due day default (stub)', DATE '2000-01-01'),
    ('IN', 'governance', 'governance.ap_invoice_approve_amount_gt', 50000, 'INR', 'Bootstrap seed for AP approval threshold', DATE '2000-01-01'),
    ('IN', 'governance', 'governance.journal_post_amount_gt', 500000, 'INR', 'Bootstrap seed for journal post amount_gt', DATE '2000-01-01'),
    ('IN', 'governance', 'governance.treasury_transfer_amount_gt', 5000000, 'INR', 'Bootstrap seed for treasury transfer amount_gt', DATE '2000-01-01')
ON CONFLICT DO NOTHING;

UPDATE platform.regulatory_param
SET value_text = 'income_tax_new_regime',
    value_json = '{"set_code":"income_tax_new_regime"}'::jsonb
WHERE param_key = 'income_tax.default_slab_set' AND org_id IS NULL;

UPDATE platform.regulatory_param
SET value_json = '["assignee","manager","finance_head","cfo"]'::jsonb
WHERE param_key = 'compliance.escalation_levels' AND org_id IS NULL;

-- Income tax new regime slabs (match former INDIA_FY_SLABS)
INSERT INTO platform.regulatory_slab_set (
    country_code, set_code, name, domain, effective_from, metadata
)
SELECT 'IN', 'income_tax_new_regime', 'India new income tax regime', 'income_tax', DATE '2025-04-01',
       '{"regime":"new","section":"115BAC"}'::jsonb
WHERE NOT EXISTS (
    SELECT 1 FROM platform.regulatory_slab_set
    WHERE set_code = 'income_tax_new_regime' AND org_id IS NULL AND effective_from = DATE '2025-04-01'
);

INSERT INTO platform.regulatory_slab_band (slab_set_id, sort_order, upper_limit, rate_pct)
SELECT s.id, b.sort_order, b.upper_limit, b.rate_pct
FROM platform.regulatory_slab_set s
CROSS JOIN (VALUES
    (1, 400000::numeric, 0::numeric),
    (2, 800000, 5),
    (3, 1200000, 10),
    (4, 1600000, 15),
    (5, 2000000, 20),
    (6, 2400000, 25),
    (7, NULL, 30)
) AS b(sort_order, upper_limit, rate_pct)
WHERE s.set_code = 'income_tax_new_regime' AND s.org_id IS NULL AND s.effective_from = DATE '2025-04-01'
  AND NOT EXISTS (SELECT 1 FROM platform.regulatory_slab_band x WHERE x.slab_set_id = s.id);

-- Thresholds
INSERT INTO platform.regulatory_threshold (
    country_code, threshold_code, amount, description, effective_from
) VALUES
    ('IN', 'gst.b2c_large_invoice', 250000, 'GSTR-1 B2C large invoice threshold (seed; adjust via dashboard)', DATE '2000-01-01'),
    ('IN', 'gst.eway_bill_min', 50000, 'E-way bill auto generation minimum taxable value', DATE '2000-01-01'),
    ('IN', 'gst.einvoice_default', 0, 'Default e-invoice amount threshold when registration metadata empty', DATE '2000-01-01'),
    ('IN', 'tds.194q_amount_hint', 5000000, 'Recommender: amounts >= this may map to 194Q', DATE '2000-01-01')
ON CONFLICT DO NOTHING;

-- Penalty formulas (structured; editable)
INSERT INTO platform.regulatory_penalty_formula (
    country_code, formula_code, compliance_code_pattern,
    daily_fee, nil_daily_fee, fee_cap, interest_annual_pct, interest_monthly_pct,
    cap_by_turnover_json, metadata, effective_from
) VALUES
    ('IN', 'gst_late_fee', 'GST%', 100, 20, 5000, 18, NULL,
     '[{"max_turnover":15000000,"fee_cap":2000},{"max_turnover":50000000,"fee_cap":5000},{"max_turnover":null,"fee_cap":10000}]'::jsonb,
     '{"notes":"simplified combined CGST+SGST daily fee"}'::jsonb, DATE '2000-01-01'),
    ('IN', 'gstr_late_fee', 'GSTR%', 100, 20, 5000, 18, NULL,
     '[]'::jsonb, '{}'::jsonb, DATE '2000-01-01'),
    ('IN', 'tds_late_fee', 'TDS%', 200, NULL, NULL, NULL, 1.5,
     '[]'::jsonb, '{"basis":"per_day"}'::jsonb, DATE '2000-01-01'),
    ('IN', 'generic_late_fee', '*', 50, NULL, NULL, 12, NULL,
     '[]'::jsonb, '{}'::jsonb, DATE '2000-01-01')
ON CONFLICT DO NOTHING;

-- TDS section templates
INSERT INTO platform.regulatory_tds_section_template (
    country_code, section_code, section_name, description, rate_pan, rate_no_pan, threshold_amount, payment_type, effective_from
) VALUES
    ('IN', '194C', 'Contractor', 'Payments to contractors', 1, 20, 30000, 'contractor', DATE '2000-01-01'),
    ('IN', '194J', 'Professional', 'Fees for professional/technical services', 10, 20, 30000, 'professional', DATE '2000-01-01'),
    ('IN', '194H', 'Commission', 'Commission or brokerage', 5, 20, 15000, 'commission', DATE '2000-01-01'),
    ('IN', '194I', 'Rent', 'Rent', 10, 20, 240000, 'rent', DATE '2000-01-01'),
    ('IN', '194Q', 'Purchase of goods', 'TDS on purchase of goods', 0.1, 5, 5000000, 'goods', DATE '2000-01-01'),
    ('IN', '194A', 'Interest', 'Interest other than securities', 10, 20, 40000, 'interest', DATE '2000-01-01'),
    ('IN', '192', 'Salary', 'Salary TDS', 0, 0, 0, 'salary', DATE '2000-01-01'),
    ('IN', '206C', 'TCS', 'Tax collection at source', 0.1, 1, 5000000, 'tcs', DATE '2000-01-01')
ON CONFLICT DO NOTHING;

-- Compliance calendar templates
INSERT INTO platform.regulatory_compliance_template (
    country_code, compliance_code, due_day, month_offset, frequency, effective_from
) VALUES
    ('IN', 'GSTR1', 11, 1, 'monthly', DATE '2000-01-01'),
    ('IN', 'GSTR3B', 20, 1, 'monthly', DATE '2000-01-01'),
    ('IN', 'GST_PAYMENT', 20, 1, 'monthly', DATE '2000-01-01'),
    ('IN', 'TDS_CHALLAN', 7, 1, 'monthly', DATE '2000-01-01'),
    ('IN', 'TDS_26Q', 31, 3, 'quarterly', DATE '2000-01-01'),
    ('IN', 'TDS_27Q', 31, 3, 'quarterly', DATE '2000-01-01'),
    ('IN', 'INTERNAL_AUDIT', 30, 9, 'annual', DATE '2000-01-01'),
    ('IN', 'PF_RETURN', 15, 1, 'monthly', DATE '2000-01-01'),
    ('IN', 'ESI_RETURN', 15, 1, 'monthly', DATE '2000-01-01'),
    ('IN', 'ROC_AOC4', 30, 9, 'annual', DATE '2000-01-01'),
    ('IN', 'ROC_MGT7', 30, 9, 'annual', DATE '2000-01-01'),
    ('IN', 'INCOME_TAX', 31, 3, 'annual', DATE '2000-01-01')
ON CONFLICT DO NOTHING;

-- Seed allowed GST rates as global params JSON for catalog validation
INSERT INTO platform.regulatory_param (
    country_code, domain, param_key, value_json, description, effective_from
) VALUES (
    'IN', 'gst', 'gst.allowed_rates',
    '[0, 0.25, 3, 5, 12, 18, 28]'::jsonb,
    'Allowed GST rate percentages when org rate master empty',
    DATE '2000-01-01'
) ON CONFLICT DO NOTHING;
