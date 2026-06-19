from __future__ import annotations

from datetime import datetime, timezone

from app.modules.platform.integrations.adapters.canonical_models import CanonicalTdsReturn
from app.modules.platform.integrations.services.connector_registry import connector_registry


class StubTdsConnector:
    connector_type = "tds"
    provider_name = "stub_tds"

    def health(self) -> dict:
        return {"ready": True, "provider": self.provider_name}

    def submit_return(self, *, idempotency_key: str, payload: dict) -> CanonicalTdsReturn:
        form_type = str(payload.get("form_type") or "26Q")
        period = str(payload.get("return_period") or "")
        ack = f"ACK-{form_type}-{period.replace('-', '')}"
        return CanonicalTdsReturn(
            return_period=period,
            form_type=form_type,
            status="submitted",
            acknowledgment_no=ack,
            filed_at=datetime.now(timezone.utc).isoformat(),
            raw={"idempotency_key": idempotency_key, **(payload or {})},
        )

    def generate_fvu(self, *, payload: dict) -> dict:
        form_type = str(payload.get("form_type") or "26Q")
        period = str(payload.get("return_period") or "")
        return {
            "fvu_file_name": f"{form_type}_{period.replace('-', '')}.fvu",
            "fvu_payload": payload,
            "status": "generated",
            "provider": self.provider_name,
        }

    def validate_challan(self, *, challan_no: str, bsr_code: str | None, amount: float) -> dict:
        valid = bool(challan_no) and amount > 0
        return {
            "valid": valid,
            "challan_no": challan_no,
            "bsr_code": bsr_code,
            "amount": amount,
            "message": "Challan validated (stub)" if valid else "Invalid challan details",
        }


connector_registry.register(StubTdsConnector())
