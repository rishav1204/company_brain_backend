from __future__ import annotations

from datetime import datetime, timezone

from app.modules.platform.integrations.adapters.canonical_models import CanonicalGSTReturn
from app.modules.platform.integrations.services.connector_registry import connector_registry


class GstnProviderConnector:
    """GSTN portal stub — mirrors bank-provider registry pattern for government APIs."""

    connector_type = "gst"
    provider_name = "gstn"

    def health(self) -> dict:
        return {"ready": True, "provider": self.provider_name}

    def submit_return(self, *, idempotency_key: str, payload: dict) -> CanonicalGSTReturn:
        return CanonicalGSTReturn(
            return_period=str(payload.get("return_period") or ""),
            status="submitted",
            filed_at=datetime.now(timezone.utc).isoformat(),
            raw={"idempotency_key": idempotency_key, "provider": "gstn", **(payload or {})},
        )


connector_registry.register(GstnProviderConnector())
