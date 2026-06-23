# M30 — Forecasting Engine (Executive Intelligence Layer)

M30 provides **read-only** predictive financial intelligence across cash, collections, expenses, tax, and working capital.

## Golden rule (hard)

M30 **reads, predicts, explains**. It must never:
- Post journals
- Execute payments
- File GST
- Mutate ERP records

## Inputs (read-only)

- **Cash**: `erp.cash_positions` (derived from reconciled bank transactions)
- **Collections**: `erp.ar_invoices` outstanding + receipts events/history
- **Payments**: `erp.ap_invoices` outstanding (rule v1 proxy)
- **Expenses**: expense claims / posted ledger entries (rule v1 baseline)
- **Tax**: `erp.compliance_obligations` (and GST tables where available)
- **Memory**: M27 retrieval (customer/vendor behavior)
- **Graph**: M28 lineage/dependencies (evidence/attribution)

## Persistence (Finance OS)

Migration `055_finance_os_forecasting_engine.sql` adds:
- `finance_os.forecasts`
- `finance_os.forecast_explanations`
- `finance_os.forecast_accuracy`

## Horizons

Supported: **7 / 30 / 60 / 90 / 180 / 365 days**

## Confidence bands

- **High**: \(>= 90\)
- **Medium**: \(70–89.99\)
- **Low**: \(< 70\)

## Events

Emitted:
- `forecast.generated`
- `forecast.updated`
- `forecast.risk.detected`
- `forecast.accuracy.calculated`

Consumed (to refresh):
- `journal.posted`, `erp.journal.posted`
- `payment.received`
- `reconciliation.completed`
- `cash.position.updated`
- `expense.claim.approved`
- `scheduler.treasury.daily`

## APIs

Base path: `/api/v1/finance-os/forecasting`

- `GET /cash?horizon_days=30&as_of_date=YYYY-MM-DD`
- `GET /collections?horizon_days=30`
- `GET /expenses?horizon_days=30`
- `GET /tax?horizon_days=30`
- `GET /working-capital?horizon_days=90`
- `GET /scenarios?horizon_days=90`
- `GET /dashboard`

