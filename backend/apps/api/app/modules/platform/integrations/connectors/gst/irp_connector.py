from __future__ import annotations

from datetime import datetime, timezone

from app.modules.platform.integrations.adapters.canonical_models import CanonicalEInvoice
from app.modules.platform.integrations.services.connector_registry import connector_registry


class IrpConnector:
    """NIC IRP stub — production credentials route through Integration Layer."""

    connector_type = "irp"
    provider_name = "gstn_irp"

    def health(self) -> dict:
        return {"ready": True, "provider": self.provider_name}

    def generate_irn(self, *, idempotency_key: str, payload: dict) -> CanonicalEInvoice:
        ref = str(payload.get("invoice_number") or idempotency_key)[:12]
        return CanonicalEInvoice(
            irn=f"IRN{ref}{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            ack_no=f"ACK{ref}",
            ack_date=datetime.now(timezone.utc).isoformat(),
            qr_code=f"data:stub-qr:{ref}",
            status="generated",
            raw={"idempotency_key": idempotency_key, **(payload or {})},
        )

    def cancel_irn(self, *, irn: str, reason: str = "") -> dict:
        return {"irn": irn, "status": "cancelled", "reason": reason}


connector_registry.register(IrpConnector())
