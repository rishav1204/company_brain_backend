from __future__ import annotations

from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.banking.integrations.bank_connector_facade import resolve_bank_connector


class BankRailService:
    def execute_payment(self, org_id: str, *, bank_account_id: str, amount: float, reference: str, beneficiary_ref: str = "", metadata: dict | None = None) -> dict:
        account = bank_account_repository.get(org_id, bank_account_id=bank_account_id) or {}
        acct_meta = account.get("metadata") if isinstance(account.get("metadata"), dict) else {}
        provider = str(acct_meta.get("provider") or "").strip() or None
        connector = resolve_bank_connector(provider=provider)
        if not connector or not hasattr(connector, "execute_payment"):
            raise ValueError("Bank connector not available")
        result = connector.execute_payment(amount=amount, reference=reference, beneficiary={"ref": beneficiary_ref, **(metadata or {})}, idempotency_key=f"{org_id}:{reference}")
        if str(result.get("status", "")).lower() in {"failed", "error"}:
            raise ValueError(result.get("reason") or "Bank rail execution failed")
        return result


bank_rail_service = BankRailService()
