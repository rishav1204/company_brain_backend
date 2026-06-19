from __future__ import annotations

from app.modules.erp.coa.repositories.account_repository import account_repository


def resolve_employee_payable_account(org_id: str) -> str | None:
    for acc in account_repository.list(org_id, limit=2000):
        name = str(acc.get("account_name") or "").lower()
        code = str(acc.get("account_code") or "")
        if "employee" in name and "payable" in name:
            return str(acc.get("id"))
        if code in {"2105", "EMP-PAYABLE"}:
            return str(acc.get("id"))
    for acc in account_repository.list(org_id, limit=2000):
        if str(acc.get("account_type")) == "liability" and "payable" in str(acc.get("account_name") or "").lower():
            return str(acc.get("id"))
    return None
