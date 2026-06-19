from __future__ import annotations

from datetime import datetime, timezone

from app.modules.platform.integrations.adapters.canonical_models import CanonicalBankTransaction
from app.modules.platform.integrations.services.connector_registry import connector_registry


class StubBankConnector:
    connector_type = "bank"
    provider_name = "stub_bank"

    def health(self) -> dict:
        return {"ready": True}

    def import_transactions(self, *, idempotency_key: str, payload: dict) -> list[CanonicalBankTransaction]:
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

    def execute_payment(
        self,
        *,
        amount: float,
        reference: str,
        beneficiary: dict | None = None,
        idempotency_key: str | None = None,
    ) -> dict:
        if amount <= 0:
            return {"status": "failed", "reason": "Invalid amount"}
        return {
            "status": "completed",
            "bank_reference": f"STUB-{reference[:16]}",
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "provider": self.provider_name,
            "idempotency_key": idempotency_key,
            "beneficiary_ref": (beneficiary or {}).get("ref"),
        }


connector_registry.register(StubBankConnector())
