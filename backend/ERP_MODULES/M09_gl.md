# M09 — General Ledger (GL) Engine

## Purpose
The GL is the **immutable accounting truth core**. Operational entities (documents, invoices, payments, workflows, AI outputs) are **not** accounting truth; only posted ledger entries are.

## Database (schema: `erp.*`)
Migration: `backend/migrations/030_erp_gl_engine.sql`

### Core tables
- **`erp.ledger_entries`**: immutable accounting truth records (no updates/deletes; corrections via reversals/new postings)
- **`erp.ledger_batches`**: atomic posting group identifier
- **`erp.account_balances`**: projection table (materialized totals and closing balance per account+period)
- **`erp.fiscal_periods`**: period control for posting eligibility
- **`erp.closing_entries`**: recorded closing batches (year-end close scaffolding)

### Invariants (enforced)
- **Non-negative amounts**: `debit_amount >= 0`, `credit_amount >= 0`
- **Exactly one side populated**: debit xor credit (no both-side lines)
- **Org isolation**: RLS policies scoped by `app.current_org`

## Posting rules (non-negotiable)
- **Double-entry**: total debits == total credits (rounded to 2 decimals)
- **Fiscal locking**: posting date must resolve to an **open and unlocked** `erp.fiscal_periods` row
- **Account validation**: account exists, `is_active = true`, `is_postable = true`
- **Atomicity**: batch + entries + balance projection are written in one DB transaction

## APIs (prefix: `/api/v1/erp/*`)

### Fiscal periods
- **POST** `/erp/fiscal-periods`
- **GET** `/erp/fiscal-periods`
- **POST** `/erp/fiscal-periods/{fiscal_period_id}/lock`
- **POST** `/erp/fiscal-periods/{fiscal_period_id}/close`

All mutations require GL finance admin guard (`erp.gl.admin` / `gl.admin` / finance-admin role).

### Posting to GL
- **POST** `/erp/gl/post`

Payload:
```json
{
  "posting_date": "2026-05-28",
  "company_id": null,
  "lines": [
    {"account_id":"...","debit_amount":1000,"credit_amount":0,"currency_code":"INR","exchange_rate":1,"entry_type":"journal"},
    {"account_id":"...","debit_amount":0,"credit_amount":1000,"currency_code":"INR","exchange_rate":1,"entry_type":"journal"}
  ]
}
```

Emits: `erp.ledger.posted` (best-effort)
Audits: `erp.ledger.posted` (best-effort)

### Balances (projection)
- **GET** `/erp/gl/balances?fiscal_period_id=...`
- **POST** `/erp/gl/balances/{fiscal_period_id}/recompute`

### Trial balance
- **GET** `/erp/trial-balance?fiscal_period_id=...`

Emits: `erp.trial_balance.generated` (best-effort)

### Ledger drilldown
- **GET** `/erp/ledger/entries?account_id=...&batch_id=...&reference_type=...&reference_id=...&limit=...&offset=...`

### Reversal (immutable correction)
- **POST** `/erp/gl/batches/{batch_id}/reverse`

Creates a new posted batch with swapped debit/credit lines and `reference_type="ledger_batch"` pointing to the reversed batch.
Emits: `erp.ledger.reversed` (best-effort)

## Events
Registered in `app/modules/platform/events/bus/event_registry.py`:
- `erp.ledger.posted`
- `erp.ledger.reversed`
- `erp.fiscal_period.closed`
- `erp.trial_balance.generated`

## Tests
Unit tests added under `app/modules/erp/gl/tests/` for:
- double-entry validation
- balance normal-side formula
- fiscal lock enforcement behavior

## Notes / follow-ups for next hardening pass
- Add cost-center “mandatory” enforcement once COA supports it as an explicit flag.
- Add multi-currency base-currency amounts (store base amounts alongside foreign amounts) when treasury module is wired.
- Add partitioning strategy for `erp.ledger_entries` once volumes justify it (e.g., by month/year).

