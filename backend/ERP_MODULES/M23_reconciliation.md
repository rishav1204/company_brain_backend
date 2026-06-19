# M23 — Reconciliation Engine (Financial Truth Verification)

## Purpose
Module 23 is the **Reconciliation Control Center** — matching bank transactions to AP/AR subledgers and GL with human/policy approval before any accounting update.

**Critical principle:** AI suggests and scores only. Humans or policy workflows approve matches. Adjustments post through M10 Journal Engine only after explicit approval.

## Architecture

```text
M22 Banking (statements, payments, receipts)
  → M23 Reconciliation (match, approve, exceptions)
  → M10 Journal (adjustments only)
  → M9 GL
```

Primary package: `backend/apps/api/app/modules/erp/reconciliation/`  
API prefix: `/api/v1/erp/reconciliation/*`  
Legacy alias: `/api/v1/banking/reconciliation/*`

## Database (migration `048_erp_reconciliation_engine.sql`)

| Table | Purpose |
|-------|---------|
| `erp.bank_reconciliations` | Match suggestions and approvals (extended with `matched_entity_type/id`, `approved_at`) |
| `erp.reconciliation_match_lines` | Partial, one-to-many, many-to-one allocations |
| `erp.reconciliation_exceptions` | Exception queue |
| `erp.reconciliation_rules` | Configurable match weights (amount, reference, date, narration) |
| `erp.reconciliation_adjustments` | Bank charge / FX / rounding adjustments |

### Status values
`unmatched`, `suggested`, `pending_approval`, `matched`, `partially_matched`, `rejected`, `exception`, `manual_review`

## Matching Engine

Weighted confidence (0–100):
- Amount exact (40), reference (30), date (20), narration fuzzy (10)
- M22 `source_type`/`source_id` fast-path → 100% when bank tx links to AP/AR entity

### Confidence bands
| Score | Band | Action |
|-------|------|--------|
| 95–100 | auto_suggest | High-confidence suggestion + notify |
| 80–94 | likely_match | Finance review |
| 60–79 | review | `pending_approval` |
| &lt;60 | manual | Exception queue |

## APIs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/erp/reconciliation/bank` | Workbench: unreconciled / suggested / matched |
| POST | `/erp/reconciliation/suggest` | Run matcher (suggest only) |
| POST | `/erp/reconciliation/match` | Manual / multi-entity match |
| GET | `/erp/reconciliation` | List by status |
| POST | `/erp/reconciliation/{id}/approve` | Approve match (fiscal lock, no duplicate journal) |
| POST | `/erp/reconciliation/{id}/reject` | Reject → unreconciled |
| POST | `/erp/reconciliation/{id}/escalate` | Manual review + workflow |
| GET | `/erp/reconciliation/exceptions` | Exception queue |
| POST | `/erp/reconciliation/exceptions/{id}/assign` | Assign exception |
| POST | `/erp/reconciliation/adjustment` | Create adjustment intent |
| POST | `/erp/reconciliation/adjustment/{id}/approve` | Approve + M10 journal post |
| GET | `/erp/reconciliation/vendor/{vendor_id}` | Vendor payment vs outstanding |
| GET | `/erp/reconciliation/customer/{customer_id}` | AR outstanding vs receipts |
| POST | `/erp/reconciliation/copilot` | AI Q&A (suggest-only) |

## Events

### Emitted
- `reconciliation.suggested`, `reconciliation.completed`
- `reconciliation.exception.created`
- `reconciliation.adjustment.required`, `reconciliation.adjustment.posted`
- `ai.reconciliation.suggested` (high confidence)

### Consumed
- `bank.transaction.imported`, `bank.statement.imported` → auto-match suggest
- `payment.executed`, `receipt.received` → suggest for linked bank account
- `reconciliation.completed` → cash snapshot refresh (M24)
- `workflow.approved` (BANK_RECONCILIATION) → unlock pending approval

## Dependencies
M3 Events, M4 Audit, M5 Notifications, M9 GL, M10 Journal, M12 Fiscal, M13 AP, M14 AR, M22 Banking

## Out of scope (v1)
- Intercompany reconciliation (M35)
- GST/TDS reconciliation (M14 tax — separate modules)
- AI auto-posting (never)
