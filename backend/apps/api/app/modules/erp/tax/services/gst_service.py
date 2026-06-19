from __future__ import annotations

from app.modules.erp.tax.repositories.gst_repository import gst_registration_repository, gst_transaction_repository
from app.modules.erp.tax.validators.gstin_validator import state_from_gstin, validate_gstin


class GstService:
    def create_registration(self, org_id: str, **fields) -> dict:
        gstin = validate_gstin(fields["gstin"])
        state = fields.get("state_code") or state_from_gstin(gstin)
        return gst_registration_repository.create(
            org_id,
            gstin=gstin,
            legal_name=fields["legal_name"],
            trade_name=fields.get("trade_name"),
            state_code=state,
            registration_type=fields.get("registration_type", "regular"),
        )

    def list_registrations(self, org_id: str) -> list[dict]:
        return gst_registration_repository.list(org_id)

    def list_transactions(self, org_id: str, *, return_period: str | None = None, gst_type: str | None = None) -> list[dict]:
        return gst_transaction_repository.list(org_id, return_period=return_period, gst_type=gst_type)


gst_service = GstService()
