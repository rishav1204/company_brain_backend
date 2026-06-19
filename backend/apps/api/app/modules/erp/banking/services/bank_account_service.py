from __future__ import annotations

import re

from app.modules.platform.governance.utils.field_crypto import encrypt_field
from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.banking.events.banking_events import emit_bank_account_created

IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$", re.IGNORECASE)
MASK = "****"


def mask_account_number(encrypted: str) -> str:
    return MASK + encrypted[-4:] if encrypted else MASK


class BankAccountService:
    def _validate_ifsc(self, ifsc_code: str) -> None:
        if not IFSC_RE.match(ifsc_code.strip()):
            raise ValueError("Invalid IFSC code format")

    def create_account(
        self,
        org_id: str,
        *,
        account_name: str,
        bank_name: str,
        account_number: str,
        ifsc_code: str,
        currency_code: str,
        account_type: str,
        ledger_account_id: str,
        company_id: str | None,
        created_by: str | None,
        opening_balance: float = 0,
    ) -> dict:
        self._validate_ifsc(ifsc_code)
        if account_type not in {"current", "savings", "cash_credit", "overdraft", "escrow", "petty_cash"}:
            raise ValueError("Invalid account type")
        encrypted = encrypt_field(account_number.strip())
        row = bank_account_repository.create(
            org_id,
            account_name=account_name,
            bank_name=bank_name,
            account_number_encrypted=encrypted,
            ifsc_code=ifsc_code.upper(),
            currency_code=currency_code,
            account_type=account_type,
            ledger_account_id=ledger_account_id,
            company_id=company_id,
            created_by=created_by,
            metadata={"opening_balance": opening_balance},
        )
        emit_bank_account_created(org_id, bank_account_id=str(row["id"]))
        self._audit(org_id, bank_account_id=str(row["id"]), action="bank.account.created", actor_id=created_by)
        return {**row, "account_number_masked": mask_account_number(encrypted)}

    def get_account(self, org_id: str, *, bank_account_id: str) -> dict:
        row = bank_account_repository.get(org_id, bank_account_id=bank_account_id)
        if not row:
            raise ValueError("Bank account not found")
        row = dict(row)
        row.pop("account_number_encrypted", None)
        row["account_number_masked"] = MASK
        return row

    def list_accounts(self, org_id: str, *, active_only: bool = True) -> list[dict]:
        return [{**r, "account_number_masked": MASK} for r in bank_account_repository.list(org_id, active_only=active_only)]

    def update_account(self, org_id: str, *, bank_account_id: str, account_name: str | None = None, is_active: bool | None = None, ledger_account_id: str | None = None, actor_id: str | None = None) -> dict:
        row = bank_account_repository.update(org_id, bank_account_id=bank_account_id, account_name=account_name, is_active=is_active, ledger_account_id=ledger_account_id)
        self._audit(org_id, bank_account_id=bank_account_id, action="bank.account.updated", actor_id=actor_id)
        return row

    def resolve_ledger_account(self, org_id: str, *, bank_account_id: str) -> str:
        row = bank_account_repository.get(org_id, bank_account_id=bank_account_id)
        if row and row.get("ledger_account_id"):
            return str(row["ledger_account_id"])
        by_ledger = bank_account_repository.get_by_ledger_account(org_id, ledger_account_id=bank_account_id)
        if by_ledger:
            return bank_account_id
        return bank_account_id

    def _audit(self, org_id: str, *, bank_account_id: str, action: str, actor_id: str | None) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service
            audit_service.record(org_id=org_id, actor_type="user", actor_id=actor_id or "erp.banking", action=action, object_ref=f"erp:bank_account:{bank_account_id}", entity_type="bank_account", entity_id=bank_account_id, source_service="erp.banking")
        except Exception:
            pass


bank_account_service = BankAccountService()
