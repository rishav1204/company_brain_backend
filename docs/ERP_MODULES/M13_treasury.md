# Module 24 — Treasury & Cash Management (M24 only)

> Full specification: [M24_treasury.md](M24_treasury.md)

## Purpose
M24 is the **Enterprise Cash Management** layer — cash position, liquidity buckets, cash forecasting, and treasury copilot. **Banking operations (M22)** live in `modules/erp/banking/`. **Reconciliation (M23)** lives in `modules/erp/reconciliation/`.

**Core principle:** Revenue ≠ Cash. M24 reads bank balances from M22 for position/forecasting. All accounting still flows through Journal Engine → GL.

## Database (schema: `erp.*`)
Migration: `backend/migrations/035_erp_treasury_engine.sql`

| Table | Purpose |
|-------|---------|
| `erp.bank_accounts` | Org bank master (encrypted account numbers, COA link) |
| `erp.bank_transactions` | Bank feed / import lines |
| `erp.payment_requests` | Treasury payment orchestration |
| `erp.bank_reconciliations` | Bank-to-ledger match records |

### Bank account types
`current`, `savings`, `cash_credit`, `overdraft`, `escrow`, `petty_cash`

### Payment request states
`draft` → `pending_approval` → `approved` → `processing` → `completed` / `failed` / `cancelled`

### Reconciliation states
`matched`, `suggested`, `exception`, `manual_review`

## APIs

### Banking (`/api/v1/banking`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/banking/accounts` | Create bank account (encrypted) |
| GET | `/banking/accounts` | List accounts (masked) |
| GET | `/banking/accounts/{id}` | Get account |
| PATCH | `/banking/accounts/{id}` | Update / deactivate |
| POST | `/banking/transactions/import` | Manual transaction import |
| POST | `/banking/transactions/sync` | M7 connector bank feed sync |
| GET | `/banking/transactions` | List transactions |
| POST | `/banking/payments` | Create payment request |
| GET | `/banking/payments` | List payment requests |
| GET | `/banking/payments/{id}` | Get payment request (verify workflow_approved) |
| POST | `/banking/payments/{id}/cancel` | Cancel draft/pending/approved payment |
| POST | `/banking/payments/{id}/execute` | Execute approved payment (manual after workflow) |

Reconciliation APIs moved to **M23** — see [M23_reconciliation.md](M23_reconciliation.md) (`/erp/reconciliation/*`).

### Treasury (`/api/v1/treasury`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/treasury/position` | Cash position dashboard |
| GET | `/treasury/liquidity` | Liquidity buckets (today → 180d) |
| GET | `/treasury/cashflow/forecast` | Cash flow forecast |
| POST | `/treasury/copilot` | AI treasury Q&A (advisory only) |

## Cash position formula
```text
Available Cash = reconciled bank credits − debits − restricted
Net Liquidity = Available + Expected Collections − Upcoming Payments
```

## Flows

### Bank feed
```text
M7 Connector (stub_bank / future ICICI HDFC Axis RazorpayX)
  → bank_feed_service → erp.bank_transactions
  → reconciliation_engine → suggestions → human approve
```

### Payment execution
```text
AP payment.scheduled → treasury payment_request (auto-linked)
Payment request → TREASURY_PAYMENT_APPROVAL workflow → mark_workflow_approved
  → manual POST /banking/payments/{id}/execute (operator verifies workflow_approved via GET)
  → bank_rail_service.execute_payment (M7 stub / provider registry)
  → bank_transaction debit recorded
  → vendor_payment: AP payment_service journal (skip duplicate bank tx)
  → internal_transfer / salary / tax: treasury journal
  → payment.executed event + realtime push
```

Workflow `payment_execution` step may also call `execute_request` when workflow progression reaches that step.

### AP bridge
- `payment.scheduled` always creates linked treasury `payment_request` (`source_type=ap_payment`)
- `bank_account_service.resolve_ledger_account()` accepts treasury bank ID or legacy COA UUID
- AP `execute_payment` resolves bank via treasury helper; records `bank_transaction` debit when not skipped
- Beneficiary verification via `vendor_bank_repository` (verified + IFSC); blocks unverified ≥ ₹1L

## Events

### Emitted
- `payment.executed`, `bank.transaction.imported`, `reconciliation.completed`, `cash.position.updated`
- `erp.payment.completed` (includes `journal_id`)

### Consumed
- `payment.scheduled` → auto treasury payment_request creation
- `erp.invoice.approved` / `invoice.approved` → cash position refresh
- `payment.received` / `customer.payment.received` → credit bank_transaction + position refresh
- `webhook.received` (entity_type=payment_gateway) → gateway settlement feed import
- `bank.statement.imported`, `bank.feed.imported`, `bank.transaction.imported`
- `workflow.approved` / `approval.completed` → treasury payment approval (unlock execute)
- `scheduler.reconciliation.daily` → auto suggest matches

## Workflows (seeded)
- `TREASURY_PAYMENT_APPROVAL` — threshold-based CFO/dual approval
- `BANK_RECONCILIATION` — reused for exception review (existing)

## Security
- Roles: `treasury_manager`, `cfo`, `finance_admin`
- Permissions: `bank.read`, `bank.reconcile`, `payment.approve`, `payment.execute`
- Maker-checker on payment execute and reconciliation approve
- Account numbers encrypted via `field_crypto` — never returned in plaintext

## M7 bank connectors
Provider stubs registered (credential-gated until `live` config): `stub_bank`, `icici`, `hdfc`, `axis`, `razorpayx`, `yes_bank`, `kotak`. All implement `execute_payment` delegating to stub until production API keys configured.

## Blueprint compliance audit

| Requirement | Status |
|-------------|--------|
| Bank account master + types + encrypted numbers | ✅ |
| Bank transactions + feed import (M7 stub + gateway) | ✅ |
| Payment requests + lifecycle + workflows | ✅ |
| AP auto-link on payment.scheduled | ✅ |
| GET payment + cancel API | ✅ |
| Bank rail execute_payment stub + provider registry | ✅ |
| Bank transaction on payment complete | ✅ |
| Beneficiary verification (vendor bank DB) | ✅ |
| Vendor payment → AP journal bridge | ✅ |
| Internal transfer journal | ✅ |
| Treasury policies (5L CFO, 25L dual) at execute | ✅ |
| Fraud/anomaly (duplicate, timing, new beneficiary) | ✅ |
| Reconciliation: ledger + AP/AR subledger matching | ✅ |
| BANK_RECONCILIATION workflow on exceptions | ✅ |
| Escalate to manual_review API | ✅ |
| AI reconciliation.suggested events | ✅ |
| Human approval required for reconcile | ✅ |
| Cash position dashboard + realtime push | ✅ |
| Liquidity buckets (today → 180d) | ✅ |
| Cashflow forecast (AP/AR/treasury/salary/tax/org hooks) | ✅ |
| Notifications for payment/reconcile/position events | ✅ |
| Security enforce_treasury_action on mutating routes | ✅ |
| Unit tests (engine + orchestration) | ✅ |

**Compliance: 100%** (architecture-complete; live bank API credentials are operator-configured, not bundled).
