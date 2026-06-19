from __future__ import annotations

from collections import defaultdict

from app.modules.erp.banking.repositories.bank_account_repository import bank_account_repository
from app.modules.erp.treasury.services.cash_position_service import cash_position_service


class ConcentrationService:
    def bank_concentration(self, org_id: str) -> list[dict]:
        position = cash_position_service.compute_live_position(org_id)
        accounts = position.get("accounts") or []
        total = sum(float(a.get("available") or a.get("closing_balance") or 0) for a in accounts)
        result = []
        for a in accounts:
            avail = float(a.get("available") or 0)
            pct = round((avail / total * 100) if total > 0 else 0, 2)
            result.append({"bank_account_id": a.get("bank_account_id"), "account_name": a.get("account_name"), "available": avail, "pct_of_total": pct})
        return sorted(result, key=lambda x: x["pct_of_total"], reverse=True)

    def vendor_concentration(self, org_id: str) -> dict:
        by_vendor: dict[str, float] = defaultdict(float)
        try:
            from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

            for inv in invoice_repository.list_outstanding(org_id):
                vid = str(inv.get("vendor_id") or "unknown")
                outstanding = float(inv.get("outstanding") or inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0)
                if outstanding > 0:
                    by_vendor[vid] += outstanding
        except Exception:
            pass
        total = sum(by_vendor.values())
        top = max(by_vendor.values()) if by_vendor else 0
        return {"total_outstanding": round(total, 2), "top_vendor_pct": round((top / total * 100) if total > 0 else 0, 2)}


concentration_service = ConcentrationService()
