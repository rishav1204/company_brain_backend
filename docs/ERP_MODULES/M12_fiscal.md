# Module 12 — Fiscal Period Management (Accounting Control Engine)

## Purpose
Canonical accounting control layer for fiscal years, period locks, month-end close, reopen, and year-end. Every journal/GL posting validates against period status before posting.

**Migration:** `039_erp_fiscal_engine.sql`

## APIs (`/api/v1/erp/ledger`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/fiscal-years` | List fiscal years |
| POST | `/fiscal-years` | Create FY + 12 monthly periods (India Apr–Mar default) |
| GET | `/periods` | List periods |
| POST | `/periods` | Create period |
| GET | `/periods/{id}` | Get period |
| POST | `/periods/{id}/close/init` | Seed close checklist |
| GET | `/periods/{id}/close/checklist` | List checklist |
| POST | `/periods/{id}/close/checklist` | Complete checklist item |
| POST | `/periods/{id}/close/submit` | Submit PERIOD_CLOSE workflow |
| POST | `/periods/{id}/close` | Execute staged close (soft → hard → closed) |
| POST | `/periods/{id}/reopen` | Request PERIOD_REOPEN workflow |
| POST | `/year-end` | Year-end close + next FY generation |

### Backward-compatible aliases (M9 GL)
- `GET/POST /erp/fiscal-periods`
- `POST /erp/fiscal-periods/{id}/lock|close`

## Lock states

| Status | Posting |
|--------|---------|
| `open` | All users |
| `soft_locked` | Privileged (`fiscal.soft_post`, CFO, controller) |
| `hard_locked` | Blocked |
| `closed` | Blocked |

## Posting gate

All paths call `posting_validation_service.validate_period_open()`:
- M10 Journal `posting_validator`
- M9 GL `posting_service`
- M13 AP invoice approve
- M14 AR invoice issue
- M1 IAM `is_fiscal_period_open` (date-aware via erp.fiscal_periods)

Error code: `PERIOD_CLOSED`

## Events

**Emitted:** `erp.period.opened`, `erp.period.soft_locked`, `erp.period.hard_locked`, `erp.period.closed`, `erp.period.reopened`, `erp.fiscal_year.closed`, `erp.year_end.completed` (+ legacy `erp.fiscal_period.*`)

**Consumed:** `reconciliation.completed`, `erp.gst.return.generated`, workflow approvals for PERIOD_CLOSE / PERIOD_REOPEN

## Workflows
- `PERIOD_CLOSE` — month-end close approval
- `PERIOD_REOPEN` — reopen with maker-checker + audit

## Blueprint compliance

| Requirement | Status |
|-------------|--------|
| Fiscal years + periods | ✅ |
| Soft/hard/closed locks | ✅ |
| Posting validation engine | ✅ |
| Close checklist + workflow | ✅ |
| Compliance overdue gate (M21) | ✅ |
| Checklist: `compliance_obligations_complete`, `tds_returns_filed` | ✅ |
| Reopen with audit | ✅ |
| Year-end close engine | ✅ (P&L zeroing via journal) |
| AP/AR/Journal integration | ✅ |
| IAM permissions | ✅ |
| Event bus | ✅ |
| GL route aliases | ✅ |
