# M24 — Treasury Management Engine

## Purpose
Module 24 is the **Cash Intelligence & Liquidity Control Platform** — cash position, liquidity monitoring, forecasting, inter-account transfers, and treasury advisory AI.

**Critical principle:** Banking (M22) processes transactions; Treasury (M24) optimizes cash. AI is advisory only — never auto-executes transfers or payments.

## Architecture

```text
M22 Banking (reconciled balances) → M23 Reconciliation (truth) → M24 Treasury (intelligence)
  → M30 Forecasting / M31 Reporting / AI Finance OS
```

Package: `backend/apps/api/app/modules/erp/treasury/`  
API prefix: `/api/v1/erp/treasury/*`  
Legacy alias: `/api/v1/treasury/*`

## Database (migration `049_erp_treasury_m24_engine.sql`)

| Table | Purpose |
|-------|---------|
| `erp.cash_positions` | Daily per-account snapshots (opening, inflows, outflows, closing) |
| `erp.inter_account_transfers` | Transfer lifecycle with M22 payment_request link |
| `erp.cash_forecasts` | Persisted horizon forecasts with confidence_score |
| `erp.liquidity_alerts` | Liquidity risk/monitor alerts |

## Formulas

**Closing cash (per account, per day):**
```text
closing_balance = opening_balance + inflows - outflows
```

**Liquidity coverage:**
```text
coverage = available_cash / total_upcoming_obligations
```
Bands: >1.5 healthy | 1.0–1.5 monitor | <1.0 risk

**Forecast:**
```text
forecast_balance(d) = current_closing + inflows(d) - outflows(d)
```

## APIs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/erp/treasury/cash-position` | Live position + recent snapshots |
| GET | `/erp/treasury/cash-position/history` | Historical snapshots |
| GET | `/erp/treasury/liquidity` | Coverage ratio, buckets, health band |
| GET | `/erp/treasury/forecast` | Forecast (`horizon_days` 7–180) |
| GET | `/erp/treasury/dashboard` | Unified CFO dashboard |
| POST | `/erp/treasury/transfers` | Create inter-account transfer |
| GET | `/erp/treasury/transfers` | List transfers |
| POST | `/erp/treasury/transfers/{id}/approve` | Approve + execute via M22 |
| POST | `/erp/treasury/transfers/{id}/cancel` | Cancel transfer |
| GET | `/erp/treasury/alerts` | Liquidity alerts |
| POST | `/erp/treasury/alerts/{id}/acknowledge` | Acknowledge alert |
| POST | `/erp/treasury/copilot` | Advisory Q&A |

Legacy: `/treasury/position`, `/treasury/liquidity`, `/treasury/cashflow/forecast`

## Transfer flow

```text
POST /transfers → pending_approval → TREASURY_TRANSFER_APPROVAL workflow
→ approve → M22 internal_transfer payment_request → M10 journal → completed
```

Approval tiers: <₹5L manager | ₹5L–₹50L controller | >₹50L CFO

## Events

### Emitted
- `cash.position.updated`, `liquidity_alert.created`, `cash.forecast.updated`, `treasury.risk.detected`

### Consumed
- `reconciliation.completed` → cash snapshot
- `payment.executed`, `receipt.received` → position refresh
- `scheduler.treasury.daily` → snapshot + forecast + liquidity monitor

## Dependencies
M3 Events, M4 Audit, M5 Notifications, M9 GL, M10 Journal, M12 Fiscal, M13 AP, M14 AR, M21 Compliance, M22 Banking, M23 Reconciliation

## Out of scope
Forex trading, derivatives, hedging, investment banking, automated cash sweeps (advisory stub only)
