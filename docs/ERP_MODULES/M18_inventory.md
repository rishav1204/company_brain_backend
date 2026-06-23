# Module 18 — Inventory & Stock Accounting Engine

## Purpose
Finance-centric inventory: item/warehouse master, FIFO and weighted-average costing, GRN-driven receipts with GRNI journals, COGS on issue, transfers/adjustments, fiscal close validation, and reporting hooks — without manufacturing/MRP/BOM.

**Migration:** `043_erp_inventory_engine.sql`

## APIs (`/api/v1/erp/inventory`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/items` | Create inventory item |
| GET | `/items`, `/items/{id}` | List/get items |
| POST | `/warehouses` | Create warehouse |
| GET | `/warehouses`, `/warehouses/{id}` | List/get warehouses |
| GET | `/balances` | On-hand qty + value by item/warehouse |
| POST | `/receipts` | Manual inventory receipt |
| POST | `/receipts/from-grn` | Receipt from confirmed GRN |
| POST | `/issues` | Issue stock + COGS journal |
| POST | `/transfers` | Warehouse transfer (no GL) |
| POST | `/adjustments` | Stock adjustment (+ workflow if above threshold) |
| GET | `/valuation` | List valuation snapshots |
| POST | `/valuation/run` | Run period-end valuation snapshot |
| GET | `/valuation/movements` | Movement history |
| POST | `/valuation/ai/analyze` | AI inventory analysis stub |

## Accounting

**GRN receipt (GRNI two-phase):**
| Account | Debit | Credit |
|---------|-------|--------|
| Inventory Asset | qty × unit_cost | |
| GRNI Clearing | | qty × unit_cost |

**AP invoice approve (stock purchase with GRN link):**
| Account | Debit | Credit |
|---------|-------|--------|
| GRNI Clearing | invoice_amount | |
| GST Input | gst | |
| Vendor Payable | | total |

**Issue / COGS:**
| Account | Debit | Credit |
|---------|-------|--------|
| COGS | total_cost | |
| Inventory Asset | | total_cost |

**Negative adjustment:**
| Account | Debit | Credit |
|---------|-------|--------|
| Inventory Loss | \|variance\| | |
| Inventory Asset | | \|variance\| |

Transfers update quantities only — no journal.

## Costing
- **FIFO:** `inventory_cost_layers` consumed oldest-first
- **Weighted average:** `weighted_avg_cost` on `inventory_balances`
- Item-level `valuation_method` overrides org policy

## Workflows
- `INVENTORY_ADJUSTMENT_APPROVAL` — large adjustments (policy threshold)

## Events (`source=erp.inventory`)
- Emitted: `inventory.received`, `inventory.issued`, `inventory.adjusted`, `inventory.transferred`, `inventory.valued`, `inventory.closed`
- Consumed: `grn.confirmed` (auto-receipt), `invoice.approved` (GRNI reconciliation check), workflow approvals

## Integrations
- **M15 Procurement:** `grn.confirmed` → `receipt_service.receive_from_grn`; `grn_service.maybe_accrue` in-process fallback; `goods_receipt_items.inventory_item_id` / `warehouse_id` bridge columns
- **M13 AP:** Invoice approve uses GRNI clearing path when `goods_receipt_id` linked and GRN inventory links exist
- **M12 Fiscal:** `inventory_close_service` validates negative stock and unposted movement journals; completes `inventory_reconciled` checklist item
- **M31 Reporting:** Balances + valuation APIs + events as data sources

## Blueprint compliance

| Requirement | Status |
|-------------|--------|
| Item + warehouse master | ✅ |
| Movement ledger + balance projection | ✅ |
| FIFO layers + weighted average | ✅ |
| GRN receipt + GRNI journal | ✅ |
| COGS on issue | ✅ |
| Transfer (no GL) | ✅ |
| Adjustments + workflow | ✅ |
| Negative stock policy | ✅ |
| Period close validation | ✅ |
| AP GRNI clearing | ✅ |
| No manufacturing/MRP | ✅ (out of scope) |
| Events/workflows/IAM | ✅ |
| AI stubs | ✅ |
