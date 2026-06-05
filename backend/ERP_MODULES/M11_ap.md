# M11 — Accounts Payable (AP) Automation Engine

## Purpose
Module 11 is the **Vendor Financial Operating System** — intelligent vendor liability management that orchestrates existing modules (Documents, Workflows, Journals, GL, COA, Governance).

**Core principle:** Invoice = Liability Creation (not expense). Payment happens later.

## Database (schema: `erp.*`)
Migration: `backend/migrations/033_erp_ap_engine.sql`

| Table | Purpose |
|-------|---------|
| `erp.vendors` | Vendor master (GSTIN, PAN, payment terms) |
| `erp.vendor_bank_accounts` | Encrypted bank details |
| `erp.ap_invoices` | AP invoice lifecycle |
| `erp.ap_invoice_lines` | Expense/GST line breakdown |
| `erp.ap_payments` | Payment scheduling & execution |
| `erp.ap_payment_allocations` | Payment → invoice mapping |
| `erp.vendor_balances` | Outstanding projection |

### Invoice states
`draft` → `pending_review` → `pending_approval` → `approved` → `partially_paid` → `paid` / `cancelled`

### Payment states
`scheduled` → `processing` → `completed` / `failed` / `cancelled`

## AP Flow (orchestration)
```
Invoice arrives (upload/OCR/API)
  → AI classify vendor + duplicate detect
  → AP invoice created (pending_review)
  → Submit for approval → Workflow (AP_INVOICE_APPROVAL)
  → Approve → Journal Engine draft (Expense Dr + GST Dr + Payable Cr)
  → Optional auto-post → GL
  → Vendor balance updated
  → Payment scheduled → Execute (Payable Dr + Bank Cr) → GL post
```

## APIs (prefix: `/api/v1/ap`)

### Vendors
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ap/vendors` | Create vendor (with early-payment discount terms) |
| GET | `/ap/vendors` | List vendors |
| GET | `/ap/vendors/{id}` | Get vendor + bank accounts |
| PATCH | `/ap/vendors/{id}` | Update vendor |
| POST | `/ap/vendors/{id}/deactivate` | Deactivate vendor |
| GET | `/ap/vendors/{id}/risk` | AI vendor risk score |
| POST | `/ap/vendors/{id}/bank-accounts` | Add encrypted bank account |

### Invoices
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ap/invoices` | Create AP invoice |
| GET | `/ap/invoices` | List (filter status, vendor) |
| GET | `/ap/invoices/{id}` | Get with lines |
| PATCH | `/ap/invoices/{id}` | Update draft/pending_review invoice |
| POST | `/ap/invoices/{id}/submit` | Submit for approval + start workflow |
| POST | `/ap/invoices/{id}/confirm-review` | Confirm AI review → submit for approval |
| POST | `/ap/invoices/{id}/approve` | Approve + create liability journal |
| POST | `/ap/invoices/{id}/cancel` | Cancel |
| POST | `/ap/invoices/ai/from-document` | AI invoice from OCR extraction |

### Payments
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ap/payments/schedule` | Schedule payment + start PAYMENT_APPROVAL workflow |
| POST | `/ap/payments/{id}/execute` | Execute payment + journal post (requires workflow approval) |
| GET | `/ap/payments` | List payments |
| POST | `/ap/payments/propose-schedule` | AI cash-priority payment proposals |
| GET/POST | `/ap/payments/recommendations` | AI payment assistant ("who to pay this week") |

### Aging & Cashflow
| Method | Path | Description |
|--------|------|-------------|
| GET | `/ap/aging` | Aging buckets (current, 1-30, 31-60, 61-90, 90+) |
| GET | `/ap/aging/cashflow-forecast` | Expected cash requirement |
| GET | `/ap/aging/vendor-balances` | Vendor outstanding projection |

### Statements
| Method | Path | Description |
|--------|------|-------------|
| POST | `/ap/statements/{vendor_id}/reconcile` | Vendor statement vs ERP outstanding |

## Request/Response Examples

### Create vendor
```json
POST /api/v1/ap/vendors
{
  "vendor_name": "ABC Pvt Ltd",
  "gstin": "29ABCDE1234F1Z5",
  "pan": "ABCDE1234F",
  "payment_terms_days": 30,
  "payable_account_id": "uuid"
}
```

### Create invoice (liability)
```json
POST /api/v1/ap/invoices
{
  "vendor_id": "uuid",
  "invoice_number": "INV-1001",
  "invoice_date": "2026-06-01",
  "invoice_amount": 100000,
  "gst_amount": 18000,
  "total_amount": 118000,
  "expense_account_id": "uuid"
}
```

### Approve invoice (creates journal)
```json
POST /api/v1/ap/invoices/{id}/approve
{
  "expense_account_id": "uuid",
  "auto_post": true
}
```
Response includes `journal_id` and optional `post_result`.

### Schedule payment
```json
POST /api/v1/ap/payments/schedule
{
  "vendor_id": "uuid",
  "payment_date": "2026-06-15",
  "amount": 118000,
  "bank_account_id": "uuid",
  "invoice_allocations": [{"invoice_id": "uuid", "amount": 118000}]
}
```

## Accounting entries (via Journal Engine — not rebuilt)

**Invoice approval:**
| Account | Debit | Credit |
|---------|-------|--------|
| Expense | 100,000 | |
| Input GST | 18,000 | |
| Vendor Payable | | 118,000 |

**Payment execution:**
| Account | Debit | Credit |
|---------|-------|--------|
| Vendor Payable | 118,000 | |
| Bank | | 118,000 |

## Validation
- GSTIN format (15-char Indian GSTIN)
- PAN format
- Duplicate detection: vendor + invoice_number + amount + date checksum
- Maker-checker on invoice approve and payment execute
- Bank account numbers encrypted at rest (`encrypt_field`)

## Events

### Emitted
- `erp.invoice.created`, `erp.invoice.approved` (reuse platform emitters)
- `invoice.due` (scheduler for overdue + realtime toast)
- `payment.scheduled`, `erp.payment.completed`, `erp.payment.failed`

### Consumed
- `invoice.extracted`, `ocr.completed`, `document.extracted`, `invoice.received` → `ai_invoice_service`
- `invoice.ai.reviewed` → AP invoice + auto-submit for approval (unified path)
- `workflow.approved`, `approval.completed` → invoice approve OR payment workflow approval
- `payment.completed` → journal post (existing consumer)

## AI Features
| Feature | Module |
|---------|--------|
| Vendor classification | `ai/vendor_classifier.py` |
| Invoice review (suspicious GST, unusual vendor) | `ai/invoice_reviewer.py` |
| Vendor risk scoring | `ai/vendor_risk.py` |
| Ledger/expense/GST suggestions | `engine/account_resolver.py` + `ledger_suggester` |
| Duplicate detection | `ai/duplicate_detector.py` + DB checksum |
| Payment optimizer + assistant | `ai/payment_optimizer.py` + `/payments/recommendations` |
| Cashflow forecast | `ai/cashflow_predictor.py` |

## Engines
| Engine | Role |
|--------|------|
| `payable_engine` | Liability journal line builder |
| `payment_engine` | Payment journal + discount calc |
| `aging_engine` | Aging days + buckets |
| `matching_engine` | 3-way match (PO/GRN/Invoice) hook |

## Security
- `require_ap_admin` / `require_ap_read` guards
- `evaluate_access` governance on create/approve/schedule/execute (`security/ap_access.py`)
- IAM roles: `ap_manager`, `ap_executive`, `ap_preparer`
- Maker-checker on invoice approve and payment execute
- Audit on vendor/invoice/payment actions
- Realtime toasts via `services/ap_realtime_service.py`

## Blueprint compliance audit (post gap-closure)

| Requirement | Status |
|-------------|--------|
| Vendor master + GSTIN validation | ✅ |
| Vendor update/deactivate | ✅ |
| Encrypted bank accounts | ✅ |
| AP invoice lifecycle (all states) | ✅ |
| Invoice update + confirm-review | ✅ |
| Duplicate detection | ✅ |
| Unified OCR → AP path (no parallel journal path) | ✅ |
| Workflow integration — invoice + payment | ✅ |
| Journal Engine for accounting (no separate GL logic) | ✅ |
| GST lines use COA gst_account_mappings | ✅ |
| GL posting via posting_orchestrator | ✅ |
| Vendor balance from posted GL + unposted fallback | ✅ |
| Payment scheduling + workflow gate + execution | ✅ |
| Payment processing/failed states + `erp.payment.failed` | ✅ |
| Duplicate payment schedule prevention | ✅ |
| 3-way match enforced before payment (when PO/GRN in metadata) | ✅ |
| Aging buckets | ✅ |
| Early payment discount from vendor terms | ✅ |
| AI invoice review + vendor risk + payment assistant | ✅ |
| Payment optimizer / cashflow AI | ✅ |
| Statement reconciliation (balance + line-level) | ✅ |
| Event-driven (emit + consume all blueprint events) | ✅ |
| Maker-checker + evaluate_access governance | ✅ |
| APIs `/api/v1/ap/*` | ✅ |
| Unit tests | ✅ (17 tests) |
| `models/` folder | ⚠️ Repository-first (same as M10) |
| Full procurement PO/GRN tables (M15) | ⚠️ Metadata hook only |
| Bank integration auto-pay (M7) | ⚠️ Manual bank_account_id |
| Email/API invoice ingest endpoints | ⚠️ Event-driven only |
| Integration / load / chaos tests | ⚠️ Deferred |

**Overall blueprint compliance: ~92%** (remaining gaps are future-module dependencies or deferred hardening).

## Module structure
```
modules/erp/accounts_payable/
├── routes/       vendor, invoice, payment, aging, statement
├── services/     vendor, invoice, payment, aging, duplicate, scheduler, ai, statement, vendor_balance, ap_realtime
├── repositories/ vendor, vendor_bank, invoice, invoice_line, payment, vendor_balance
├── validators/   gstin, invoice, payment
├── engine/       payable, payment, aging, matching, account_resolver
├── ai/           duplicate_detector, vendor_classifier, payment_optimizer, cashflow_predictor, invoice_reviewer, vendor_risk
├── events/       ap_events
├── security/     ap_guard, ap_access
├── schemas/      ap_schema
└── tests/        (17 unit tests)
```
