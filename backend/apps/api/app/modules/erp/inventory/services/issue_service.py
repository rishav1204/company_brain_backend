from __future__ import annotations

from datetime import date

from app.modules.erp.inventory.engine.cogs_engine import build_cogs_journal_lines
from app.modules.erp.inventory.engine.movement_engine import check_negative_stock
from app.modules.erp.inventory.engine.stock_engine import costing_service
from app.modules.erp.inventory.engine.valuation_engine import resolve_method
from app.modules.erp.inventory.events.inventory_events import emit_inventory_issued
from app.modules.erp.inventory.repositories.item_repository import item_repository, policy_repository
from app.modules.erp.inventory.repositories.movement_repository import balance_repository, layer_repository, movement_repository
from app.modules.erp.inventory.validators.stock_validator import validate_issue
from app.modules.erp.journals.services.approval_service import approval_service as journal_approval_service
from app.modules.erp.journals.services.journal_service import journal_service
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator


class IssueService:
    def issue(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        quantity: float,
        movement_type: str = "issue",
        movement_date: str | None = None,
        reference_type: str | None = None,
        reference_id: str | None = None,
        actor_id: str | None = None,
        post_journal: bool = True,
    ) -> dict:
        validate_issue(quantity=quantity)
        item = item_repository.get(org_id, item_id=item_id)
        if not item:
            raise ValueError("Item not found")
        policy = policy_repository.get_active(org_id) or {}
        method = resolve_method(item.get("valuation_method"), policy.get("valuation_method"))
        balance = balance_repository.get(org_id, item_id=item_id, warehouse_id=warehouse_id) or {
            "quantity_on_hand": 0,
            "inventory_value": 0,
            "weighted_avg_cost": 0,
        }
        qty_on_hand = float(balance.get("quantity_on_hand") or 0)
        check_negative_stock(qty_after=qty_on_hand - quantity, rule=str(policy.get("negative_stock_rule") or "block"))

        layers = layer_repository.list_open(org_id, item_id=item_id, warehouse_id=warehouse_id) if method == "fifo" else []
        total_cost, unit_cost, consumed = costing_service.issue_cost(
            method=method,
            issue_qty=quantity,
            balance=balance,
            layers=layers,
        )

        mdate = str(movement_date or date.today().isoformat())[:10]
        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        ensure_posting_allowed(org_id, mdate)

        journal_id = None
        if post_journal and total_cost > 0:
            lines = build_cogs_journal_lines(
                org_id,
                total_cost=total_cost,
                cogs_account_id=item.get("cogs_account_id"),
                inventory_account_id=item.get("inventory_account_id"),
            )
            ref_key = reference_id or f"{item_id}:{warehouse_id}:{mdate}"
            journal = journal_service.create_draft(
                org_id,
                created_by=actor_id,
                journal_type="issue",
                posting_date=mdate,
                description=f"Inventory issue {item.get('item_code')}",
                source_type="inventory_issue",
                source_id=reference_id,
                company_id=item.get("company_id"),
                lines=lines,
                idempotency_key=f"inv-issue:{reference_type or 'manual'}:{ref_key}",
            )
            journal_id = str(journal["journal"]["id"])
            journal_approval_service.approve(org_id, journal_id=journal_id, approver_id=actor_id or "system", skip_maker_checker=True)
            posting_orchestrator.post_journal(org_id, journal_id=journal_id, posted_by=actor_id or "system")

        movement = movement_repository.create(
            org_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=-quantity,
            unit_cost=unit_cost,
            total_cost=total_cost,
            movement_date=mdate,
            reference_type=reference_type,
            reference_id=reference_id,
            journal_id=journal_id,
            created_by=actor_id,
        )

        if method == "fifo":
            for layer in consumed:
                layer_repository.reduce(org_id, layer_id=str(layer["layer_id"]), quantity=float(layer["quantity"]))

        new_qty = qty_on_hand - quantity
        new_value = round(float(balance.get("inventory_value") or 0) - total_cost, 2)
        new_avg = float(balance.get("weighted_avg_cost") or 0)
        if method == "weighted_average" and new_qty > 0:
            new_avg = round(new_value / new_qty, 4)
        elif new_qty <= 0:
            new_avg = 0.0
            new_value = 0.0

        balance_repository.upsert(
            org_id,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity_on_hand=new_qty,
            inventory_value=new_value,
            weighted_avg_cost=new_avg,
        )
        emit_inventory_issued(org_id, movement_id=str(movement["id"]), item_id=item_id, quantity=quantity, total_cost=total_cost)
        return movement


issue_service = IssueService()
