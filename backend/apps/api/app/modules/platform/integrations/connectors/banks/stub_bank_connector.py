from __future__ import annotations

from app.modules.platform.integrations.adapters.canonical_models import CanonicalBankTransaction
from app.modules.platform.integrations.services.connector_registry import connector_registry


class StubBankConnector:
    connector_type = "bank"
    provider_name = "stub_bank"

    def health(self) -> dict:
        return {"ready": True}

    def import_transactions(self, *, idempotency_key: str, payload: dict) -> list[CanonicalBankTransaction]:
        # Idempotency should be enforced by caller using platform idempotency service.
        tx = CanonicalBankTransaction(
            bank_tx_id=str(payload.get("id") or idempotency_key),
            amount=float(payload.get("amount") or 0),
            currency=str(payload.get("currency") or "INR"),
            occurred_at=str(payload.get("occurred_at") or ""),
            description=str(payload.get("description") or ""),
            reference=str(payload.get("reference") or ""),
            raw=payload,
        )
        return [tx]


connector_registry.register(StubBankConnector())

