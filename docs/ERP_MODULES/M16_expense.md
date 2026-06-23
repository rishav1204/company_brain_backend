# Module 16 — Expense Management Engine (Employee Spend Governance)

## Purpose
Employee spend governance: receipt OCR via M6, policy validation, workflow approvals, two-phase accounting (accrual journal on approve + treasury reimbursement payout).

**Migration:** `041_erp_expense_engine.sql`

## APIs (`/api/v1/erp/expenses`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/claims` | Create expense claim (draft) |
| GET | `/claims`, `/claims/{id}` | List/get claims |
| POST | `/claims/{id}/submit`, `/approve`, `/reject`, `/cancel` | Claim lifecycle |
| POST | `/receipts/from-document` | Create draft claim from M6 OCR extraction |
| GET | `/receipts/{id}` | Get expense receipt record |
| POST | `/claims/{id}/reimburse` | Schedule treasury reimbursement |
| POST | `/reimbursements/{id}/execute` | Execute reimbursement payout |
| GET | `/policies` | List expense policies |
| POST | `/advances` | Issue employee advance |
| GET | `/advances?employee_id=` | List open advances |
| GET | `/analytics/spend` | Spend analysis by category |
| GET | `/card-transactions` | Unallocated corporate card transactions |

Employee identity uses `core.users.id` as `employee_id`.

## OCR integration (M6)

- Upload receipts with `document_type=receipt` or `expense_receipt`
- Pipeline emits `receipt_ocr` extraction via `receipt_extractor.py`
- AP `invoice.ai.reviewed` consumer skips receipt document types
- Expense consumer creates draft claims via `ai_expense_service.create_from_extraction`

## Accounting (two-phase)

**Approve (accrual):**
| Account | Debit | Credit |
|---------|-------|--------|
| Expense (per line) | amount | |
| Employee Reimbursement Payable | | total |

**Reimburse (treasury):** `payment_type=reimbursement`, `beneficiary_type=employee` — clears payable via treasury execute.

## Workflows
- `EXPENSE_CLAIM_APPROVAL`, `EXPENSE_POLICY_EXCEPTION`, `EXPENSE_REIMBURSEMENT`

## Events (`source=erp.expense`)
- Emitted: `expense.claim.created`, `expense.claim.approved`, `expense.claim.rejected`, `expense.reimbursement.scheduled`, `expense.reimbursed`, `expense.receipt.extracted`, `policy.violation.detected`
- Consumed: `invoice.ai.reviewed` (receipts only), `ocr.completed` (`receipt_ocr`), workflow approvals, `payment.executed` (reimbursement)

## Blueprint compliance

| Requirement | Status |
|-------------|--------|
| Claims, items, receipts, policies tables | ✅ |
| Receipt OCR via M6 (no duplicate engine) | ✅ |
| Policy engine (limits, receipt mandatory) | ✅ |
| Duplicate detection (receipt hash) | ✅ |
| Fraud scoring stub | ✅ |
| Workflow approvals (M2) | ✅ |
| Accrual journal on approve (M10/M12) | ✅ |
| Treasury reimbursement (M24) | ✅ |
| Employee advances + corporate card stubs | ✅ |
| IAM permissions + roles | ✅ |
