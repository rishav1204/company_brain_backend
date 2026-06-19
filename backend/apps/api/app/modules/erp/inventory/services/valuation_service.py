from __future__ import annotations

from datetime import date

from app.modules.erp.inventory.engine.valuation_engine import resolve_method
from app.modules.erp.inventory.events.inventory_events import emit_inventory_valued
from app.modules.erp.inventory.repositories.item_repository import item_repository, policy_repository
from app.modules.erp.inventory.repositories.movement_repository import balance_repository, valuation_repository
from app.modules.erp.inventory.validators.valuation_validator import validate_valuation_date


class ValuationService:
    def run_snapshot(self, org_id: str, *, valuation_date: str | None = None) -> list[dict]:
        vdate = validate_valuation_date(valuation_date or date.today().isoformat())
        policy = policy_repository.get_active(org_id) or {}
        method = str(policy.get("valuation_method") or "weighted_average")
        balances = balance_repository.list_all(org_id)
        results: list[dict] = []
        for bal in balances:
            item_id = str(bal["item_id"])
            item = item_repository.get(org_id, item_id=item_id) or {}
            item_method = resolve_method(item.get("valuation_method"), method)
            snap = valuation_repository.create(
                org_id,
                item_id=item_id,
                warehouse_id=str(bal["warehouse_id"]),
                valuation_date=vdate,
                valuation_method=item_method,
                quantity=float(bal.get("quantity_on_hand") or 0),
                inventory_value=float(bal.get("inventory_value") or 0),
            )
            results.append(snap)
        emit_inventory_valued(org_id, valuation_date=vdate, item_count=len(results))
        return results

    def list_snapshots(self, org_id: str, *, valuation_date: str | None = None) -> list[dict]:
        return valuation_repository.list(org_id, valuation_date=valuation_date)


valuation_service = ValuationService()
