from __future__ import annotations

from app.modules.erp.assets.repositories.asset_repository import asset_repository
from app.modules.erp.assets.repositories.category_repository import category_repository
from app.modules.erp.assets.repositories.depreciation_repository import depreciation_repository


class AssetRegisterService:
    def get_register(
        self,
        org_id: str,
        *,
        status: str | None = None,
        category_id: str | None = None,
    ) -> dict:
        assets = asset_repository.list(org_id, status=status, category_id=category_id, limit=500)
        categories = {c["id"]: c for c in category_repository.list_active(org_id)}
        rows = []
        total_cost = 0.0
        total_book = 0.0
        for a in assets:
            full = asset_repository.get(org_id, asset_id=str(a["id"])) or a
            cat = categories.get(str(full.get("asset_category_id") or ""), {})
            rows.append({
                **a,
                "category_name": cat.get("category_name"),
                "accumulated_depreciation": full.get("accumulated_depreciation"),
                "location": full.get("location"),
                "custodian_id": full.get("custodian_id"),
            })
            total_cost += float(a.get("cost") or 0)
            total_book += float(a.get("book_value") or 0)
        return {
            "assets": rows,
            "summary": {
                "count": len(rows),
                "total_cost": round(total_cost, 2),
                "total_book_value": round(total_book, 2),
            },
        }

    def depreciation_history(self, org_id: str, *, asset_id: str) -> list[dict]:
        return depreciation_repository.list_for_asset(org_id, asset_id=asset_id)


asset_register_service = AssetRegisterService()
