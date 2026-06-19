from __future__ import annotations

from datetime import date

from app.modules.erp.inventory.engine.cogs_engine import build_cogs_journal_lines, build_receipt_journal_lines
from app.modules.erp.inventory.engine.movement_engine import check_negative_stock
from app.modules.erp.inventory.engine.stock_engine import costing_service
from app.modules.erp.inventory.engine.valuation_engine import resolve_method
from app.modules.erp.inventory.events.inventory_events import emit_inventory_issued, emit_inventory_received
from app.modules.erp.inventory.repositories.item_repository import item_repository, policy_repository
from app.modules.erp.inventory.repositories.movement_repository import (
    balance_repository,
    grn_link_repository,
    layer_repository,
    movement_repository,
)
from app.modules.erp.inventory.validators.stock_validator import validate_issue, validate_receipt
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator


class InventoryService:
    def get_balance(self, org_id: str, *, item_id: str, warehouse_id: str) -> dict:
        bal = balance_repository.get(org_id, item_id=item_id, warehouse_id=warehouse_id)
        return bal or {
            "quantity_on_hand": 0,
            "inventory_value": 0,
            "weighted_avg_cost": 0,
        }

    def list_balances(self, org_id: str, *, warehouse_id: str | None = None) -> list[dict]:
        return balance_repository.list_all(org_id, warehouse_id=warehouse_id)

    def _apply_receipt(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        quantity: float,
        unit_cost: float,
        movement_date: str,
        reference_type: str | None,
        reference_id: str | None,
        actor_id: str | None,
        post_journal: bool,
        idempotency_suffix: str,
    ) -> dict:
        validate_receipt(quantity=quantity, unit_cost=unit_cost)
        item = item_repository.get(org_id, item_id=item_id)
        if not item:
            raise ValueError("Item not found")
        policy = policy_repository.get_active(org_id) or {}
        method = resolve_method(item.get("valuation_method"), policy.get("valuation_method"))
        balance = self.get_balance(org_id, item_id=item_id, warehouse_id=warehouse_id)
        total_cost = costing_service.receipt_cost(qty=quantity, unit_cost=unit_cost)

        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        ensure_posting_allowed(org_id, movement_date)

        journal_id = None
        if post_journal and total_cost > 0:
            lines = build_receipt_journal_lines(
                org_id,
                total_cost=total_cost,
                inventory_account_id=item.get("inventory_account_id"),
            )
            journal = journal_service.create_draft(
                org_id,
                created_by=actor_id,
                journal_type="receipt",
                posting_date=movement_date,
                description=f"Inventory receipt {item.get('item_code')}",
                source_type="goods_receipt" if reference_type == "goods_receipt" else "inventory_receipt",
                source_id=reference_id,
                company_id=item.get("company_id"),
                lines=lines,
                idempotency_key=f"inv-receipt:{idempotency_suffix}",
            )
            journal_id = str(journal["journal"]["id"])
            journal_approval_service.approve(org_id, journal_id=journal_id, approver_id=actor_id or "system", skip_maker_checker=True)
            posting_orchestrator.post_journal(org_id, journal_id=journal_id, posted_by=actor_id or "system")

        movement = movement_repository.create(
            org_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            movement_type="receipt",
            quantity=quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            movement_date=movement_date,
            reference_type=reference_type,
            reference_id=reference_id,
            journal_id=journal_id,
            created_by=actor_id,
        )

        if method == "fifo":
            layer_repository.create(
                org_id,
                item_id=item_id,
                warehouse_id=warehouse_id,
                movement_id=str(movement["id"]),
                remaining_quantity=quantity,
                unit_cost=unit_cost,
                receipt_date=movement_date,
            )
            new_qty = float(balance.get("quantity_on_hand") or 0) + quantity
            new_value = float(balance.get("inventory_value") or 0) + total_cost
            new_avg = float(balance.get("weighted_avg_cost") or 0)
        else:
            new_qty, new_value, new_avg = costing_service.receipt_average(
                balance=balance, receipt_qty=quantity, unit_cost=unit_cost,
            )

        balance_repository.upsert(
            org_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity_on_hand=new_qty,
            inventory_value=new_value,
            weighted_avg_cost=new_avg,
        )
        emit_inventory_received(org_id, movement_id=str(movement["id"]), item_id=item_id, quantity=quantity)
        return movement

    def receive_manual(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        quantity: float,
        unit_cost: float,
        movement_date: str | None = None,
        actor_id: str | None = None,
        post_journal: bool = True,
    ) -> dict:
        mdate = str(movement_date or date.today().isoformat())[:10]
        return self._apply_receipt(
            org_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity=quantity,
            unit_cost=unit_cost,
            movement_date=mdate,
            reference_type="manual_receipt",
            reference_id=None,
            actor_id=actor_id,
            post_journal=post_journal,
            idempotency_suffix=f"{item_id}:{warehouse_id}:{mdate}:{quantity}",
        )

    def receive_from_grn(self, org_id: str, *, grn_id: str, actor_id: str | None = None) -> list[dict]:
        from app.modules.erp.procurement.repositories.grn_repository import grn_repository
        from app.modules.erp.procurement.repositories.po_repository import po_repository

        grn = grn_repository.get(org_id, grn_id=grn_id)
        if not grn:
            raise ValueError("GRN not found")
        policy = policy_repository.get_active(org_id) or {}
        default_wh = policy.get("default_warehouse_id")
        results: list[dict] = []
        po_id = str(grn.get("po_id"))
        po_items = {str(i["id"]): i for i in po_repository.list_items(org_id, po_id=po_id)}

        for line in grn_repository.list_items(org_id, grn_id=grn_id):
            grn_item_id = str(line["id"])
            if grn_link_repository.exists(org_id, grn_item_id=grn_item_id):
                continue
            qty = float(line.get("accepted_quantity") or line.get("received_quantity") or 0)
            if qty <= 0:
                continue
            item_id = line.get("inventory_item_id")
            warehouse_id = line.get("warehouse_id") or default_wh
            if not item_id:
                po_item = po_items.get(str(line.get("po_item_id"))) or {}
                sku = str(po_item.get("item_name") or "ITEM")[:40].upper().replace(" ", "-")
                existing = item_repository.get_by_code(org_id, item_code=sku)
                if existing:
                    item_id = existing["id"]
                else:
                    created = item_repository.create(
                        org_id,
                        item_code=sku,
                        item_name=str(po_item.get("item_name") or sku),
                        item_type="trading_goods",
                        valuation_method=policy.get("valuation_method"),
                    )
                    item_id = created["id"]
            if not warehouse_id:
                raise ValueError("Warehouse required for GRN inventory receipt")
            unit_cost = float(po_items.get(str(line.get("po_item_id")), {}).get("unit_price") or 0)
            mdate = str(grn.get("received_date") or date.today().isoformat())[:10]
            movement = self._apply_receipt(
                org_id,
                item_id=str(item_id),
                warehouse_id=str(warehouse_id),
                quantity=qty,
                unit_cost=unit_cost,
                movement_date=mdate,
                reference_type="goods_receipt",
                reference_id=grn_id,
                actor_id=actor_id,
                post_journal=True,
                idempotency_suffix=f"grn:{grn_item_id}",
            )
            grn_link_repository.create(
                org_id,
                goods_receipt_id=grn_id,
                grn_item_id=grn_item_id,
                movement_id=str(movement["id"]),
            )
            results.append(movement)
        return results


inventory_service = InventoryService()
