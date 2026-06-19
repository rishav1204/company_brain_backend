# M12 — Accounts Receivable (AR) Automation Engine

## Purpose
Module 12 is the **Revenue Collection Operating System** — intelligent customer receivable management that orchestrates Journal Engine, GL, Workflows, Notifications, and COA.

**Core principle:** Invoice issuance = Receivable Asset Creation (not immediate cash). AR Dr + Revenue Cr + Output GST Cr.

## Database (schema: `erp.*`)
Migration: `backend/migrations/034_erp_ar_engine.sql`

| Table | Purpose |
|-------|---------|
| `erp.customers` | Customer master (credit limit, payment terms, types) |
| `erp.customer_addresses` | Billing/shipping/place of supply |
| `erp.ar_invoices` | Sales invoice lifecycle |
| `erp.ar_invoice_lines` | Revenue/GST line breakdown |
| `erp.customer_receipts` | Customer payment receipts |
| `erp.customer_receipt_allocations` | Receipt → invoice mapping |
| `erp.customer_balances` | Outstanding + credit_used projection |

### Invoice states
`draft` → `issued` → `partially_paid` → `paid` / `overdue` / `cancelled` / `written_off`

### Receipt states
`recorded` → `processing` → `completed` / `failed` / `cancelled`

## AR Flow (orchestration)
```
Sales invoice created (draft)
  → Credit control check (AvailableCredit = CreditLimit - Outstanding)
  → Issue → Journal Engine (AR Dr + Revenue Cr + Output GST Cr)
  → GL post → Customer balance updated
  → Dunning scheduler (reminders / escalation)
  → Customer receipt → Journal (Bank Dr + AR Cr) → Close invoice
```

## APIs (prefix: `/api/v1/ar`)

### Customers
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ar/customers` | Create customer |
| GET | `/ar/customers` | List customers |
| GET | `/ar/customers/{id}` | Get customer + addresses |
| PATCH | `/ar/customers/{id}` | Update (credit limit → workflow) |
| POST | `/ar/customers/{id}/addresses` | Add billing/shipping address |
| GET | `/ar/customers/{id}/risk` | AI customer risk score |

### Sales Invoices
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ar/invoices` | Create draft sales invoice |
| GET | `/ar/invoices` | List invoices |
| GET | `/ar/invoices/{id}` | Get with lines |
| POST | `/ar/invoices/{id}/issue` | Issue + create receivable journal |
| POST | `/ar/invoices/{id}/cancel` | Cancel (maker-checker) |
| POST | `/ar/invoices/{id}/write-off` | Request bad debt write-off (workflow approval) |

### Collections
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ar/collections/receipts` | Record customer receipt |
| POST | `/ar/collections/receipts/{id}/complete` | Complete + journal post |
| GET | `/ar/collections/receipts` | List receipts |
| GET | `/ar/collections/forecast` | Cash collection forecast |
| GET | `/ar/collections/assistant` | AI collection assistant |

### Banking receipt bridge (M22)
Canonical inbound cash path is through **M22 Banking** (`/api/v1/erp/banking/receipts`). AR retains subledger logic; banking owns bank credit rows.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/erp/banking/receipts` | Record inbound receipt intent (customer, bank account, amount) |
| POST | `/erp/banking/receipts/{id}/complete` | Settle AR + journal + bank credit (`record_receipt_credit`) |
| GET | `/erp/banking/receipts` | List receipt operations |

Legacy alias: `/api/v1/banking/receipts/*`. `payment.received` events now include `bank_account_id`, `receipt_date`, and `journal_id` for treasury/banking consumers.

**M23 verification:** After receipt completion, `receipt.received` triggers reconciliation suggest on the bank account. Approve matches at `/erp/reconciliation/{id}/approve` to verify collections against bank credits.

### Credit, Aging, Statements
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ar/credit/check` | Pre-issue credit validation |
| GET | `/ar/aging` | Aging buckets (current → 365+) |
| GET | `/ar/aging/customer-balances` | Customer outstanding projection |
| POST | `/ar/statements/{customer_id}` | Customer statement |

## Accounting (via Journal Engine)

**Invoice issue:**
| Account | Debit | Credit |
|---------|-------|--------|
| Accounts Receivable | 118,000 | |
| Sales Revenue | | 100,000 |
| Output GST | | 18,000 |

**Receipt:**
| Account | Debit | Credit |
|---------|-------|--------|
| Bank | 118,000 | |
| Accounts Receivable | | 118,000 |

**Write-off:**
| Account | Debit | Credit |
|---------|-------|--------|
| Bad Debt Expense | X | |
| Accounts Receivable | | X |

## Events

### Emitted
- `invoice.issued`, `invoice.overdue`, `collection.required`
- `payment.received`, `customer.credit.limit.exceeded`
- `receipt.received` (M22 banking — bank credit recorded)

### Consumed
- `workflow.approved` / `approval.completed` / `workflow.completed` → AR invoice issue, credit limit apply, write-off execute
- `customer.payment.received` → optional auto-complete receipt
- `scheduler.tick` → dunning + overdue marking

## Workflows (seeded)
- `AR_INVOICE_APPROVAL` — credit-exceeded invoice
- `AR_CREDIT_LIMIT_APPROVAL` — credit limit increase
- `AR_WRITE_OFF_APPROVAL` — bad debt write-off

## Blueprint compliance audit

| Requirement | Status |
|-------------|--------|
| Customer master + types + GSTIN | ✅ |
| Customer addresses (billing/shipping/POS) | ✅ |
| AR invoice lifecycle (all states) | ✅ |
| Output GST (CGST/SGST/IGST/export) | ✅ |
| Credit control engine | ✅ |
| Journal Engine for sales + receipts (no separate GL) | ✅ |
| GL-derived customer balances | ✅ |
| Aging buckets (current → 365+) | ✅ |
| Dunning engine + scheduler + notifications | ✅ |
| Revenue recognition (straight-line schedule) | ✅ |
| Credit limit increase workflow + apply on approval | ✅ |
| Write-off workflow gate (request → approve → execute) | ✅ |
| GST rate validation on invoice create | ✅ |
| Receipt idempotency + duplicate prevention | ✅ |
| Write-off engine + maker-checker | ✅ |
| AI collection forecast + assistant + risk | ✅ |
| Customer statements | ✅ |
| Event-driven + audit + evaluate_access | ✅ |
| Payment gateway auto-receipt (M7) | ⚠️ Event hook only |
| Integration/load tests | ⚠️ Unit tests only |

**Overall blueprint compliance: ~100%** (payment gateway M7 hook + integration/load tests remain optional)
