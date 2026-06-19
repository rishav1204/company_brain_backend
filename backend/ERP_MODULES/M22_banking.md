# Module 22 — Banking Engine

Enterprise Banking Operations Platform: bank accounts, statement imports, payment execution, receipt tracking, beneficiaries, and bank transaction ledger. Canonical money-movement layer between AP/AR and the bank.

**Migration:** `047_erp_banking_engine.sql` (extends `035_erp_treasury_engine.sql`)  
**Package:** `backend/apps/api/app/modules/erp/banking/`

## API

Primary: **`/api/v1/erp/banking/*`**  
Backward alias: **`/api/v1/banking/*`**

| Method | Path | Description |
|--------|------|-------------|
| POST/GET/PATCH | `/accounts` | Bank account CRUD (encrypted account numbers) |
| POST | `/statements/import` | CSV/Excel/MT940 upload |
| POST | `/transactions/import` | JSON bulk import |
| POST | `/transactions/sync` | M7 connector feed |
| GET | `/transactions` | List bank transactions |
| POST/GET | `/payments` | Payment request lifecycle |
| POST | `/payments/{id}/execute` | Execute approved payment via bank rail |
| POST/GET | `/beneficiaries` | Beneficiary master |
| POST | `/beneficiaries/{id}/verify` | Verify beneficiary |
| POST/GET | `/receipts` | AR receipt orchestration |
| POST | `/copilot` | Banking Q&A (heuristic) |

Reconciliation (M23): **`/api/v1/erp/reconciliation/*`** (alias `/banking/reconciliation/*`) — see [M23_reconciliation.md](M23_reconciliation.md)

## Canonical transaction format

```json
{"date": "2025-06-01", "amount": 1000, "type": "credit", "reference": "REF1", "narration": "..."}
```

## Payment flow (AP)

```text
AP schedule → payment.scheduled → payment_request → workflow → execute
→ bank_rail → bank_transaction debit → AP journal (skip duplicate bank tx)
```

Direct `POST /ap/payments/{id}/execute` blocked in production unless `ALLOW_DIRECT_AP_EXECUTE=true`.

## Receipt flow (AR)

```text
POST /receipts → POST /receipts/{id}/complete → AR journal + bank credit + receipt.received
```

## Events

Emitted: `bank.account.created`, `bank.statement.imported`, `bank.transaction.imported`, `payment.executed`, `payment.failed`, `receipt.received`

## Connectors (M7)

ICICI, HDFC, Axis, RazorpayX via `connector_registry` — stub implementations until operator credentials configured.

## Blueprint compliance: ~95%

Inter-account transfers are orchestrated by **M24 Treasury** (`POST /erp/treasury/transfers`); execution uses M22 `internal_transfer` payment type + M10 journal.
