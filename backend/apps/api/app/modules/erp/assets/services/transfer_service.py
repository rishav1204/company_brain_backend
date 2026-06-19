from __future__ import annotations

from app.modules.erp.assets.engine.asset_lifecycle_engine import ensure_transferable
from app.modules.erp.assets.events.asset_events import emit_asset_transferred
from app.modules.erp.assets.repositories.asset_repository import asset_repository, transfer_repository


class TransferService:
    def transfer(
        self,
        org_id: str,
        *,
        asset_id: str,
        to_department_id: str | None = None,
        to_location: str | None = None,
        to_custodian_id: str | None = None,
        transfer_date: str | None = None,
        reason: str | None = None,
        actor_id: str | None = None,
    ) -> dict:
        asset = asset_repository.get(org_id, asset_id=asset_id)
        if not asset:
            raise ValueError("Asset not found")
        ensure_transferable(str(asset.get("status")))
        from datetime import date

        tdate = str(transfer_date or date.today().isoformat())[:10]
        transfer = transfer_repository.create(
            org_id,
            asset_id=asset_id,
            from_department_id=asset.get("department_id"),
            to_department_id=to_department_id,
            from_location=asset.get("location"),
            to_location=to_location,
            from_custodian_id=asset.get("custodian_id"),
            to_custodian_id=to_custodian_id,
            transfer_date=tdate,
            reason=reason,
            created_by=actor_id,
        )
        asset_repository.update_operational(
            org_id,
            asset_id=asset_id,
            department_id=to_department_id,
            location=to_location,
            custodian_id=to_custodian_id,
        )
        emit_asset_transferred(org_id, asset_id=asset_id, transfer_id=str(transfer.get("id")))
        return transfer


transfer_service = TransferService()
