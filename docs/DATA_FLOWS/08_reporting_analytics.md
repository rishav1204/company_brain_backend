# Golden Path 08 — Reporting and Analytics

```text
Posted GL (M10) → Report definitions (M31) → Analytics cubes (M32) → Forecasts (M30)
```

## Event-driven refresh

Consumers: `_consume_reporting_refresh`, `_consume_analytics_refresh`, `_consume_forecasting_refresh` on `journal.posted`, `reconciliation.completed`, etc.

## M38 role

Read-only analysis: memory search, graph traverse, report queries. No ledger mutation.
