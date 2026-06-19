from __future__ import annotations

from app.modules.erp.inventory.repositories.item_repository import policy_repository
from app.modules.erp.inventory.repositories.movement_repository import balance_repository, movement_repository


class InventoryCloseService:
    def validate_period_close(self, org_id: str, *, period_id: str | None = None) -> dict:
        policy = policy_repository.get_active(org_id) or {}
        rule = str(policy.get("negative_stock_rule") or "block")
        issues: list[str] = []
        balances = balance_repository.list_all(org_id, limit=5000)
        negative = [b for b in balances if float(b.get("quantity_on_hand") or 0) < -0.0001]
        if negative:
            msg = f"{len(negative)} item/warehouse balance(s) with negative stock"
            if rule == "block":
                issues.append(msg)
            elif rule == "warn":
                issues.append(f"WARN: {msg}")

        movements = movement_repository.list(org_id, limit=500)
        unposted = [m for m in movements if float(m.get("total_cost") or 0) > 0 and not m.get("journal_id")
                    and str(m.get("movement_type")) in {"receipt", "issue", "adjustment"}]
        if unposted:
            issues.append(f"{len(unposted)} movement(s) with value but no journal")

        ok = not any(not i.startswith("WARN:") for i in issues)
        return {"ok": ok, "issues": issues, "period_id": period_id}

    def complete_inventory_checklist(self, org_id: str, *, period_id: str, actor_id: str) -> dict:
        result = self.validate_period_close(org_id, period_id=period_id)
        if not result["ok"]:
            raise ValueError("; ".join(result["issues"]))
        from app.modules.erp.fiscal.services.close_service import close_service

        return close_service.complete_checklist_item(
            org_id, period_id=period_id, check_name="inventory_reconciled", actor_id=actor_id
        )


inventory_close_service = InventoryCloseService()
