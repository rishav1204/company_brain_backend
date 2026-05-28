from __future__ import annotations

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
            filed_at=None,
            raw={"idempotency_key": idempotency_key, **(payload or {})},
        )


connector_registry.register(StubGstConnector())

