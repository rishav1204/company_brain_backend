# Golden Path 04 — Collections (AR)

```text
AR invoice (M12) → Due date passed → Event invoice.due → M38/M29 collections plan
  → Workflow (M2) → Customer communication
```

## Steps

1. `ar.list_overdue` identifies past-due invoices.
2. Event `invoice.due` triggers `_consume_goal_triggers` → `collections_followup` template.
3. M38 planner: read overdue → `workflow.start` (COLLECTION_FOLLOWUP).
4. Approval required before workflow launch.
5. M33 audit trail for all agent/runtime steps.

## M29 vs M38

M29 `collections_agent` still runs via `_consume_agents_trigger`. M38 adds dynamic multi-step graphs.
