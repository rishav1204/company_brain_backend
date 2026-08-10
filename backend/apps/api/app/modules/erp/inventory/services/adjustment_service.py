from __future__ import annotations

from datetime import date

from app.modules.erp.inventory.engine.cogs_engine import build_adjustment_journal_lines
from app.modules.erp.inventory.engine.movement_engine import check_negative_stock
from app.modules.erp.inventory.events.inventory_events import emit_inventory_adjusted
from app.modules.erp.inventory.repositories.item_repository import item_repository, policy_repository
from app.modules.erp.inventory.repositories.movement_repository import adjustment_repository, balance_repository, movement_repository
from app.modules.erp.inventory.validators.adjustment_validator import validate_adjustment_amount
from app.modules.erp.inventory.validators.stock_validator import validate_adjustment
from app.modules.erp.journals.services.journal_draft_conn import approve_with_conn, create_draft_with_conn
from app.modules.erp.journals.services.posting_orchestrator import posting_orchestrator
from app.services.db import get_db_conn, set_rls_org


class AdjustmentService:
    def create(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        quantity_variance: float,
        adjustment_date: str | None = None,
        reason: str | None = None,
        actor_id: str | None = None,
        skip_workflow_check: bool = False,
    ) -> dict:
        validate_adjustment(quantity_variance=quantity_variance)
        item = item_repository.get(org_id, item_id=item_id)
        if not item:
            raise ValueError("Item not found")
        policy = policy_repository.get_active(org_id) or {}
        balance = balance_repository.get(org_id, item_id=item_id, warehouse_id=warehouse_id) or {
            "quantity_on_hand": 0,
            "inventory_value": 0,
            "weighted_avg_cost": 0,
        }
        qty_on_hand = float(balance.get("quantity_on_hand") or 0)
        unit_cost = float(balance.get("weighted_avg_cost") or 0)
        value_variance = round(quantity_variance * unit_cost, 2)
        validate_adjustment_amount(value_variance=value_variance)

        new_qty = qty_on_hand + quantity_variance
        check_negative_stock(qty_after=new_qty, rule=str(policy.get("negative_stock_rule") or "block"))

        threshold = float(policy.get("adjustment_approval_threshold") or 0)
        needs_workflow = abs(value_variance) >= threshold and not skip_workflow_check
        if needs_workflow:
            adj = adjustment_repository.create(
                org_id,
                item_id=item_id,
                warehouse_id=warehouse_id,
                adjustment_date=str(adjustment_date or date.today().isoformat())[:10],
                quantity_variance=quantity_variance,
                value_variance=value_variance,
                reason=reason,
                movement_id=None,
                journal_id=None,
                created_by=actor_id,
                status="pending_approval",
            )
            try:
                from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

                handle_entity_created(
                    org_id=org_id,
                    payload={
                        "entity_type": "inventory_adjustment",
                        "entity_id": str(adj["id"]),
                        "started_by": actor_id,
                        "metadata": {
                            "adjustment_id": str(adj["id"]),
                            "item_id": item_id,
                            "warehouse_id": warehouse_id,
                            "quantity_variance": quantity_variance,
                            "value_variance": value_variance,
                            "adjustment_date": str(adjustment_date or date.today().isoformat())[:10],
                            "reason": reason,
                        },
                    },
                )
            except Exception:
                pass
            return {"adjustment_id": str(adj["id"]), "status": "pending_approval"}

        return self._post_adjustment(
            org_id,
            item=item,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity_variance=quantity_variance,
            value_variance=value_variance,
            adjustment_date=str(adjustment_date or date.today().isoformat())[:10],
            reason=reason,
            actor_id=actor_id,
        )

    def mark_workflow_approved(self, org_id: str, *, adjustment_id: str) -> dict:
        return {"adjustment_id": adjustment_id, "workflow_approved": True}

    def _post_adjustment(
        self,
        org_id: str,
        *,
        item: dict,
        item_id: str,
        warehouse_id: str,
        quantity_variance: float,
        value_variance: float,
        adjustment_date: str,
        reason: str | None,
        actor_id: str | None,
    ) -> dict:
        from app.modules.erp.fiscal.services.posting_guard import ensure_posting_allowed

        ensure_posting_allowed(org_id, adjustment_date)

        balance = balance_repository.get(org_id, item_id=item_id, warehouse_id=warehouse_id) or {
            "quantity_on_hand": 0,
            "inventory_value": 0,
            "weighted_avg_cost": 0,
        }
        journal_id = None
        journal = None
        post_result = None
        movement = None
        adj = None

        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            if abs(value_variance) > 0.0001:
                lines = build_adjustment_journal_lines(
                    org_id,
                    value_variance=value_variance,
                    inventory_account_id=item.get("inventory_account_id"),
                )
                journal = create_draft_with_conn(
                    conn,
                    org_id,
                    created_by=actor_id,
                    journal_type="adjustment",
                    posting_date=adjustment_date,
                    description=f"Inventory adjustment {item.get('item_code')}",
                    source_type="inventory_adjustment",
                    source_id=None,
                    company_id=item.get("company_id"),
                    lines=lines,
                    idempotency_key=f"inv-adj:{item_id}:{warehouse_id}:{adjustment_date}:{quantity_variance}",
                )
                journal_id = str(journal["journal"]["id"])
                approve_with_conn(
                    conn,
                    org_id,
                    journal_id=journal_id,
                    approver_id=actor_id or "system",
                    skip_maker_checker=True,
                )
                post_result = posting_orchestrator.post_journal_with_conn(
                    conn,
                    org_id,
                    journal_id=journal_id,
                    posted_by=actor_id or "system",
                    defer_side_effects=True,
                )

            movement = movement_repository.create_conn(
                conn,
                org_id,
                item_id=item_id,
                warehouse_id=warehouse_id,
                movement_type="adjustment",
                quantity=quantity_variance,
                unit_cost=float(balance.get("weighted_avg_cost") or 0),
                total_cost=abs(value_variance),
                movement_date=adjustment_date,
                reference_type="adjustment",
                reference_id=None,
                journal_id=journal_id,
                created_by=actor_id,
            )

            new_qty = float(balance.get("quantity_on_hand") or 0) + quantity_variance
            new_value = round(float(balance.get("inventory_value") or 0) + value_variance, 2)
            new_avg = float(balance.get("weighted_avg_cost") or 0)
            if new_qty > 0:
                new_avg = round(new_value / new_qty, 4)
            else:
                new_avg = 0.0
                new_value = 0.0

            balance_repository.upsert_conn(
                conn,
                org_id,
                item_id=item_id,
                warehouse_id=warehouse_id,
                quantity_on_hand=new_qty,
                inventory_value=new_value,
                weighted_avg_cost=new_avg,
            )
            adj = adjustment_repository.create_conn(
                conn,
                org_id,
                item_id=item_id,
                warehouse_id=warehouse_id,
                adjustment_date=adjustment_date,
                quantity_variance=quantity_variance,
                value_variance=value_variance,
                reason=reason,
                movement_id=str(movement["id"]),
                journal_id=journal_id,
                created_by=actor_id,
                status="posted",
            )

        if journal:
            posting_orchestrator._emit_post_side_effects(
                org_id,
                journal_id=journal_id,
                journal=journal["journal"],
                batch_id=str((post_result or {}).get("ledger_batch_id") or ""),
                posted_by=actor_id or "system",
            )

        emit_inventory_adjusted(org_id, adjustment_id=str(adj["id"]), item_id=item_id)
        return {"adjustment_id": str(adj["id"]), "status": "posted", "movement_id": str(movement["id"]), "journal_id": journal_id}

    def apply_from_workflow(
        self,
        org_id: str,
        *,
        adjustment_id: str,
        item_id: str,
        warehouse_id: str,
        quantity_variance: float,
        value_variance: float,
        adjustment_date: str,
        reason: str | None,
        actor_id: str | None,
    ) -> dict:
        item = item_repository.get(org_id, item_id=item_id)
        if not item:
            raise ValueError("Item not found")
        return self._post_adjustment(
            org_id,
            item=item,
            item_id=item_id,
            warehouse_id=warehouse_id,
            quantity_variance=quantity_variance,
            value_variance=value_variance,
            adjustment_date=adjustment_date,
            reason=reason,
            actor_id=actor_id,
        )


adjustment_service = AdjustmentService()
