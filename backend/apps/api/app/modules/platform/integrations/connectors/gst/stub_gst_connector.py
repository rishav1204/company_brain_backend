from __future__ import annotations

from datetime import datetime, timezone

from app.modules.platform.integrations.adapters.canonical_models import CanonicalGSTReturn
from app.modules.platform.integrations.services.connector_registry import connector_registry


class StubGstConnector:
    connector_type = "gst"
    provider_name = "stub_gst"

    def health(self) -> dict:
        return {"ready": True}

    def submit_return(self, *, idempotency_key: str, payload: dict) -> CanonicalGSTReturn:
        return CanonicalGSTReturn(
            return_period=str(payload.get("return_period") or ""),
            status="submitted",
            filed_at=datetime.now(timezone.utc).isoformat(),
            raw={"idempotency_key": idempotency_key, **(payload or {})},
        )

    def generate_irn(self, *, idempotency_key: str, payload: dict) -> dict:
        ref = str(payload.get("invoice_number") or idempotency_key)[:12]
        return {
            "irn": f"IRN{ref}{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            "ack_no": f"ACK{ref}",
            "ack_date": datetime.now(timezone.utc).isoformat(),
            "qr_code": f"data:stub-qr:{ref}",
            "status": "generated",
        }

    def cancel_irn(self, *, irn: str, reason: str = "") -> dict:
        return {"irn": irn, "status": "cancelled", "reason": reason}

    def generate_eway_bill(self, *, idempotency_key: str, payload: dict) -> dict:
        return {
            "eway_bill_no": f"EWB{idempotency_key[:10].upper()}",
            "status": "generated",
            "valid_upto": datetime.now(timezone.utc).isoformat(),
        }

    def cancel_eway_bill(self, *, eway_bill_no: str, reason: str = "") -> dict:
        return {"eway_bill_no": eway_bill_no, "status": "cancelled", "reason": reason}


connector_registry.register(StubGstConnector())
