from __future__ import annotations

from app.modules.erp.accounts_payable.engine.payable_engine import resolve_default_payable_account
from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.accounts_payable.repositories.vendor_balance_repository import vendor_balance_repository
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository


class VendorBalanceService:
    def refresh_vendor(self, org_id: str, *, vendor_id: str) -> dict:
        vendor = vendor_repository.get(org_id, vendor_id=vendor_id) or {}
        payable_id = resolve_default_payable_account(org_id, vendor)
        gl_outstanding = 0.0
        if payable_id:
            gl_outstanding = vendor_balance_repository.compute_gl_outstanding(
                org_id, vendor_id=vendor_id, payable_account_id=payable_id
            )

        invoices = invoice_repository.list(org_id, vendor_id=vendor_id, limit=500)
        # INT-01: include approved invoices whose journals are not yet posted (journal_id present but not posted).
        unposted = 0.0
        try:
            from app.modules.erp.journals.repositories.journal_repository import journal_repository

            for i in invoices:
                if str(i.get("status")) not in {"approved", "partially_paid"}:
                    continue
                outstanding = max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0))
                jid = str(i.get("journal_id") or "").strip()
                if not jid:
                    unposted += outstanding
                    continue
                j = journal_repository.get(org_id, journal_id=jid) or {}
                if str(j.get("journal_status")) != "posted":
                    unposted += outstanding
        except Exception:
            unposted = sum(
                max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0))
                for i in invoices
                if str(i.get("status")) in {"approved", "partially_paid"}
            )
        outstanding = max(gl_outstanding, 0.0) + unposted
        if outstanding <= 0:
            outstanding = sum(
                max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0))
                for i in invoices
                if str(i.get("status")) in {"approved", "partially_paid"}
            )
        return vendor_balance_repository.upsert(org_id, vendor_id=vendor_id, outstanding_amount=outstanding)

    def refresh_all(self, org_id: str) -> list[dict]:
        outstanding = invoice_repository.list_outstanding(org_id)
        by_vendor: dict[str, float] = {}
        for inv in outstanding:
            vid = str(inv.get("vendor_id"))
            by_vendor[vid] = by_vendor.get(vid, 0.0) + float(inv.get("outstanding") or 0)
        results = []
        for vid, amount in by_vendor.items():
            results.append(vendor_balance_repository.upsert(org_id, vendor_id=vid, outstanding_amount=amount))
        return results

    def list_balances(self, org_id: str) -> list[dict]:
        return vendor_balance_repository.list(org_id)


vendor_balance_service = VendorBalanceService()
