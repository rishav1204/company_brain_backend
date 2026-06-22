# M32 — Analytics & Business Intelligence Engine

M32 is the **executive financial intelligence layer** of Finance OS. It transforms reports, forecasts, treasury, compliance, and workflow metrics into KPIs, trends, insights, and management actions.

## Golden rule (non-negotiable)

Analytics GET endpoints read **only** from `finance_analytics.*` (KPI snapshots, trends, insights, dashboard snapshots). KPI computation runs in batch via read-models + engines — **never** ad-hoc transactional ERP scans per HTTP request.

## M31 vs M32

| Layer | Question | Source |
|-------|----------|--------|
| M31 Reporting | What happened? | `erp_reporting.*` |
| M32 Analytics | Why? What changed? What should we do? | `finance_analytics.*` |

## Upstream delegation (do not duplicate)

| Upstream | Service to call (batch read-models only) |
|----------|------------------------------------------|
| M31 Reporting | `report_engine`, `pnl_service`, `aging_report_service`, `treasury_report_service`, `forecast_report_service` |
| M30 Forecasting | `forecast_query_service.get_series()`, `forecast_accuracy_query_service` |
| M26 Workflow Intelligence | `workflow_pattern_service.analytics(workflow_type="PERIOD_CLOSE")` |
| M24 Treasury | `liquidity_service.analyze()`, `cash_position_service.compute_live_position()` |
| M21 Compliance | `compliance_dashboard_service.build()` |
| M23 Reconciliation | `run_reconciliation_scan()` |
| M12 Fiscal | `fiscal_period_repository.list()` / `get()` for close timestamps |
| M27 Memory | `memory_copilot` / retrieval (AI evidence only) |
| M28 Graph | `graph_copilot` / causality (AI evidence only) |

## KPI catalog

| Code | Category |
|------|----------|
| `finance.gross_profit_margin` | Financial |
| `finance.net_profit_margin` | Financial |
| `finance.ebitda_margin` | Financial (proxy v1) |
| `collections.dso` | Collections |
| `vendor.dpo` | Vendor |
| `working_capital.net` | Working capital |
| `treasury.cash_runway_days` | Treasury |
| `treasury.liquidity_coverage` | Treasury |
| `compliance.filing_pct` | Compliance |
| `compliance.penalty_exposure` | Compliance |
| `reconciliation.rate` | Reconciliation |
| `close.duration_days` | Close |
| `close.efficiency_score` | Close |
| `close.sla_breach_count` | Close |
| `forecast.accuracy_avg` | Forecast |

## Persistence

Migration `057_finance_analytics_engine.sql`:

- `finance_analytics.kpi_snapshots`
- `finance_analytics.kpi_trends`
- `finance_analytics.executive_insights`
- `finance_analytics.dashboard_snapshots`
- `finance_analytics.anomaly_flags`

## API prefix

`/api/v1/finance-os/analytics/*`

## Events

**Emitted:** `kpi.updated`, `insight.generated`, `risk.detected`, `dashboard.refreshed`, `analytics.refresh.requested`

**Consumed (debounced):** `report.generated`, `report.snapshot.created`, `forecast.generated`, `forecast.accuracy.calculated`, `erp.period.closed`, `erp.fiscal_period.closed`, `payment.executed`, `reconciliation.completed`, `scheduler.analytics.daily`
