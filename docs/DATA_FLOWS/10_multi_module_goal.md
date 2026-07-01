# Golden Path 10 — Multi-Module Goal (Laptop Purchase)

**User prompt:** "Buy 5 laptops from vendor Acme at ₹40,000 each for inventory"

## M38 execution graph (heuristic)

| Step | Tool | Method | Approval |
|------|------|--------|----------|
| 1 | procurement | create_po | Yes |
| 2 | procurement | submit_po | Yes |
| 3 | procurement | create_grn | Yes |
| 4 | procurement | confirm_grn | Yes → **inventory receipt** |

## Data flow across modules

```text
M15 PO (draft) → M2 approval → M15 GRN → confirm → M18 stock layers
  → (future) M17 asset capitalize → depreciation schedule
```

## Rollback strategy (planned)

- After step 1: `procurement.cancel_po`
- After step 3: `procurement.cancel_grn`

## What does NOT happen automatically

- No journal post on PO alone
- No payment until separate payment workflow
- Asset capitalization requires additional goal steps (Phase 2 tools)

## World state usage

If user is on PO screen with `entity_id` in world_state, planner binds params without re-search.

## Tables touched

`erp.purchase_orders`, `erp.grns`, `erp.inventory_movements`, `finance_os.goals`, `finance_os.execution_graphs`
