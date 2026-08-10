from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib import error, request

from app.modules.platform.integrations.adapters.canonical_models import CanonicalBankTransaction
from app.modules.platform.integrations.connectors.banks.stub_bank_connector import StubBankConnector
from app.modules.platform.integrations.services.connector_registry import connector_registry


def _bank_config() -> dict:
    return {
        "base_url": os.getenv("BANK_API_BASE_URL", "").strip(),
        "api_key": os.getenv("BANK_API_KEY", "").strip(),
        "client_id": os.getenv("BANK_CLIENT_ID", "").strip(),
        "provider": os.getenv("BANK_CONNECTOR_PROVIDER", "http_bank").strip(),
    }


class ProductionBankConnector:
    connector_type = "bank"
    provider_name = "http_bank"

    def health(self) -> dict:
        cfg = _bank_config()
        return {"ready": bool(cfg["base_url"] and cfg["api_key"]), "provider": self.provider_name}

    def _post(self, path: str, payload: dict) -> dict:
        cfg = _bank_config()
        if not cfg["base_url"]:
            raise RuntimeError("BANK_API_BASE_URL not configured")
        url = f"{cfg['base_url'].rstrip('/')}/{path.lstrip('/')}"
        body = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg['api_key']}",
            "X-Client-Id": cfg["client_id"],
        }
        req = request.Request(url, data=body, headers=headers, method="POST")
        with request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def import_transactions(self, *, idempotency_key: str, payload: dict) -> list[CanonicalBankTransaction]:
        cfg = _bank_config()
        if not cfg["base_url"]:
            return StubBankConnector().import_transactions(idempotency_key=idempotency_key, payload=payload)
        try:
            result = self._post("/transactions/import", {"idempotency_key": idempotency_key, **payload})
            rows = result.get("transactions") if isinstance(result.get("transactions"), list) else [result]
            out: list[CanonicalBankTransaction] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                out.append(
                    CanonicalBankTransaction(
                        bank_tx_id=str(row.get("id") or idempotency_key),
                        amount=float(row.get("amount") or 0),
                        currency=str(row.get("currency") or "INR"),
                        occurred_at=str(row.get("occurred_at") or row.get("value_date") or ""),
                        description=str(row.get("description") or row.get("narration") or ""),
                        reference=str(row.get("reference") or row.get("utr") or ""),
                        raw=row,
                    )
                )
            return out or StubBankConnector().import_transactions(idempotency_key=idempotency_key, payload=payload)
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            from app.modules.platform.integrations.connectors.connector_errors import fail_closed_in_prod

            fail_closed_in_prod(exc, operation="bank.import_transactions")
            return StubBankConnector().import_transactions(idempotency_key=idempotency_key, payload=payload)

    def execute_payment(
        self,
        *,
        amount: float,
        reference: str,
        beneficiary: dict | None = None,
        idempotency_key: str | None = None,
        payment_mode: str = "NEFT",
    ) -> dict:
        cfg = _bank_config()
        if not cfg["base_url"]:
            return StubBankConnector().execute_payment(
                amount=amount, reference=reference, beneficiary=beneficiary, idempotency_key=idempotency_key
            )
        try:
            result = self._post(
                "/payments/execute",
                {
                    "amount": amount,
                    "reference": reference,
                    "beneficiary": beneficiary or {},
                    "idempotency_key": idempotency_key,
                    "mode": payment_mode,
                },
            )
            return {
                "status": str(result.get("status") or "completed"),
                "bank_reference": str(result.get("utr") or result.get("bank_reference") or reference),
                "executed_at": str(result.get("executed_at") or datetime.now(timezone.utc).isoformat()),
                "provider": self.provider_name,
                "raw": result,
            }
        except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
            from app.modules.platform.integrations.connectors.connector_errors import fail_closed_in_prod

            fail_closed_in_prod(exc, operation="bank.execute_payment")
            return {"status": "failed", "reason": str(exc), "provider": self.provider_name}


connector_registry.register(ProductionBankConnector())
