# Golden Path 05 — Period Close (Long-Running M38 Goal)

```text
Scheduler / user request → M38 period_close goal → inventory validate → recon exceptions
  → fiscal checklist → (future: GST, AP, AR, treasury, depreciation, reports) → fiscal close
```

## Characteristics

- **9-step DAG** with checkpoints in `finance_os.execution_graphs`
- Survives server restarts via persisted `goal_runs` and `POST .../resume`
- Each step is read or draft until fiscal close approval

## M38 execution graph (9 steps)

| Step | Tool | Method | Approval |
|------|------|--------|----------|
| 1 | inventory | validate_close | No |
| 2 | reconciliation | list_exceptions | No |
| 3 | reconciliation | list | No |
| 4 | ap | list_outstanding | No |
| 5 | ar | list_outstanding | No |
| 6 | treasury | get_cash_position | No |
| 7 | tax_gst | list_returns | No |
| 8 | gl | trial_balance | No |
| 9 | fiscal | close_checklist | Yes |

## Current heuristic plan

Implemented in `goal_planner.py` — triggers on chat "Run period close checklist" or event `erp.period.close.requested`.

## Trigger

Event `erp.period.close.requested` or chat: "Run period close checklist"
