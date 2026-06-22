# M31 — Reporting Engine (Canonical ERP Reports)

M31 is the **canonical reporting platform** for ERP financial and operational reports. User-facing APIs read **only** from the `erp_reporting` schema (pre-aggregated snapshot tables), never from transactional tables at request time.

## Golden rule (non-negotiable)

Report GET endpoints must query `erp_reporting.*` tables populated by background materialization. Aggregation runs in batch via events, scheduler, or explicit refresh — **not** per HTTP request on `erp.ledger_entries`.

## Audit: existing endpoints vs M31 delegation

| Legacy / domain route | Current behavior | M31 target |
|----------------------|------------------|------------|
| `GET /api/v1/erp/trial-balance` | Sync scan of `erp.ledger_entries` (GL module) | **Proxy** → M31 `trial_balance_service.get_from_reporting()`; one-time refresh if stale |
| `GET /api/v1/erp/ap/aging` | AP `aging_service` (transactional invoices) | Unchanged; optional read from `erp_reporting.ap_aging_mv` via `GET /erp/reports/ap-aging` |
| `GET /api/v1/erp/ar/aging` | AR `aging_service` | Unchanged; facade at `GET /erp/reports/ar-aging` |
| GST filing APIs (`/erp/gst/*`) | Filing workflow + payload generation | **Facade** at `GET /erp/reports/gst` reads `erp_reporting.gst_summary_mv` |
| TDS filing APIs (`/erp/tds/*`) | Filing workflow | **Facade** at `GET /erp/reports/tds` reads `erp_reporting.tds_summary_mv` |
| M24 treasury (`/erp/treasury/cash-position`) | Live treasury compute | **Facade** at `GET /erp/reports/treasury/cash-position` (snapshot optional) |
| M30 forecasting (`/finance-os/forecasting/*`) | Predictions in `finance_os.forecasts` | **Facade** at `GET /erp/reports/forecast/*` + variance vs actuals |

## Persistence

Migration `056_erp_reporting_engine.sql`:

- `erp_reporting.trial_balance_mv`
- `erp_reporting.pnl_mv`
- `erp_reporting.balance_sheet_mv`
- `erp_reporting.ap_aging_mv`, `ar_aging_mv`
- `erp_reporting.gst_summary_mv`, `tds_summary_mv`
- `erp_reporting.report_runs` (async exports)
- `erp_reporting.report_snapshots` (frozen period-end reports)

## API prefix

`/api/v1/erp/reports/*`

## Events

**Emitted:** `report.generated`, `report.exported`, `report.snapshot.created`, `reports.generate.requested`, `reports.generate.completed`, `reports.refresh.requested`

**Consumed (debounced refresh):** `journal.posted`, `erp.journal.posted`, `invoice.approved`, `payment.executed`, `payment.received`, `reconciliation.completed`, `erp.fiscal_period.closed`, `erp.period.closed`, `forecast.generated`, `scheduler.reports.daily`

## Async flow

1. `POST /erp/reports/export` → `report_runs` row (`queued`)
2. Publish `reports.generate.requested` → `reports.generate` queue
3. Worker generates PDF/CSV/Excel → updates run → `report.exported`
4. Client polls `GET /erp/reports/export/{run_id}`

## Dependencies

M9 GL, M10 COA mappings, M12/M13 AP/AR aging, M19 GST, M20 TDS, M24 Treasury, M30 Forecasting.

## Phase 2

Cash flow statement returns `{status: "phase2", sections: []}` until indirect method is implemented.
