from __future__ import annotations

from datetime import datetime, timezone

from app.modules.erp.inventory.engine.account_resolver import resolve_cogs_account, resolve_inventory_account
from app.modules.erp.inventory.repositories.item_repository import item_repository, policy_repository, warehouse_repository


class ItemService:
    def _item_code(self) -> str:
        return f"INV-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    def create(
        self,
        org_id: str,
        *,
        item_name: str,
        item_code: str | None = None,
        item_type: str = "trading_goods",
        uom: str = "EA",
        valuation_method: str | None = None,
        company_id: str | None = None,
    ) -> dict:
        policy = policy_repository.get_active(org_id) or {}
        return item_repository.create(
            org_id,
            item_code=item_code or self._item_code(),
            item_name=item_name,
            item_type=item_type,
            uom=uom,
            valuation_method=valuation_method or policy.get("valuation_method"),
            inventory_account_id=resolve_inventory_account(org_id),
            cogs_account_id=resolve_cogs_account(org_id),
            company_id=company_id,
        )

    def get(self, org_id: str, *, item_id: str) -> dict | None:
        return item_repository.get(org_id, item_id=item_id)

    def list(self, org_id: str, *, status: str | None = None) -> list[dict]:
        return item_repository.list(org_id, status=status)


class WarehouseService:
    def create(self, org_id: str, *, warehouse_code: str, warehouse_name: str, location: str | None = None) -> dict:
        return warehouse_repository.create(org_id, warehouse_code=warehouse_code, warehouse_name=warehouse_name, location=location)

    def get(self, org_id: str, *, warehouse_id: str) -> dict | None:
        return warehouse_repository.get(org_id, warehouse_id=warehouse_id)

    def list(self, org_id: str) -> list[dict]:
        return warehouse_repository.list_active(org_id)


item_service = ItemService()
warehouse_service = WarehouseService()
