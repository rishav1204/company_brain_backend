# Module 15 — Procurement Engine (Spend Control System)

## Purpose
Enterprise spend control: PR → PO → GRN → 3-way match → AP invoice. Procurement does **not** post GL entries.

**Migration:** `040_erp_procurement_engine.sql`

## APIs (`/api/v1/erp/procurement`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/pr` | Create purchase requisition |
| GET | `/pr`, `/pr/{id}` | List/get PR |
| POST | `/pr/{id}/submit`, `/approve`, `/cancel`, `/convert-po` | PR lifecycle |
| POST | `/po` | Create purchase order |
| GET | `/po`, `/po/{id}` | List/get PO |
| POST | `/po/{id}/submit`, `/approve`, `/send`, `/close` | PO lifecycle |
| POST | `/grn` | Create goods receipt |
| POST | `/grn/{id}/confirm` | Confirm GRN → emits `grn.confirmed`; M18 inventory receipt via event + `maybe_accrue` |
| GET | `/matches` | List match records |
| POST | `/match` | Run three-way match |
| POST | `/match/{id}/override` | Override exception |
| GET | `/analytics/spend` | Spend analysis |
| GET | `/policies` | Procurement policies |

Vendor master: `/api/v1/ap/vendors` (M13 — no duplicate vendor table).

## Three-way match

Canonical engine: `matching_service.run_match()` — line-level qty/price/amount with configurable tolerances from `erp.procurement_policies`.

Match statuses: `matched`, `matched_within_tolerance`, `exception`, `rejected`

AP integration:
- `erp.ap_invoices.purchase_order_id`, `goods_receipt_id` FKs
- Invoice approve gated on match status
- Payment execute checks `procurement_matches` (defense in depth)
- PO line `expense_account_id` → fixed asset COA routes capex to M17 (via AP invoice approve)

## Workflows
- `PR_APPROVAL`, `PO_APPROVAL`, `GRN_CONFIRMATION`, `PROCUREMENT_EXCEPTION`

## Events (`source=erp.procurement`)
- Emitted: `pr.created`, `pr.approved`, `po.created`, `po.approved`, `po.sent`, `grn.created`, `grn.confirmed`, `three_way_match.completed`, `three_way_match.exception`
- Consumed: `vendor.created`, `erp.invoice.approved` (budget consume), workflow approvals

## M18 Inventory integration
- `grn.confirmed` consumed by M18 `receipt_service.receive_from_grn` (idempotent via `grn_inventory_links`)
- `grn_service.maybe_accrue()` delegates in-process receipt when inventory module active
- `erp.goods_receipt_items` bridge: `inventory_item_id`, `warehouse_id` (migration 043)
- M15 does not post GL; inventory GRNI journal posted by M18 on receipt

## Blueprint compliance

| Requirement | Status |
|-------------|--------|
| PR / PO / GRN tables | ✅ |
| Vendor master reuse (M13) | ✅ |
| 3-way matching engine | ✅ |
| Approval workflows (M2) | ✅ |
| Budget envelopes (future-proof) | ✅ |
| Procurement policies | ✅ |
| AP invoice linkage + approve gate | ✅ |
| No GL from procurement | ✅ |
| AI stubs (recommend, spend, anomaly) | ✅ |
| IAM permissions + roles | ✅ |
| Audit on mutations | ✅ |
| M18 inventory receipt on GRN confirm | ✅ |
