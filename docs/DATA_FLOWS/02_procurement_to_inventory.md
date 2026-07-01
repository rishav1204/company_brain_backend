# Golden Path 02 — Procurement to Inventory

```text
Vendor (M15) → PO draft → PO approved → GRN → GRN confirm → M18 stock receipt → GRNI → AP match (M11)
```

## Critical rule

**Inventory updates only on GRN confirm**, not on PO creation alone.

## Steps

1. Create PO draft (`procurement.create_po`) — no stock change.
2. Submit PO (`procurement.submit_po`) — workflow approval.
3. Create GRN (`procurement.create_grn`) — links to PO lines.
4. Confirm GRN (`procurement.confirm_grn`) — triggers M15→M18 integration.
5. Stock layers updated in `erp.inventory_*`; GRNI accrual if configured.
6. AP three-way match when invoice arrives.

## M38 tool chain

See [`10_multi_module_goal.md`](10_multi_module_goal.md) for full laptop purchase goal.

## Key events

`po.created`, `po.approved`, `grn.created`, `grn.confirmed` → M38 `inventory_received` goal
