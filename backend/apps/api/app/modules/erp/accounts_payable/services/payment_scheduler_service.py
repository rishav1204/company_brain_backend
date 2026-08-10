from __future__ import annotations

from datetime import date

from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.ports.intelligence_registry import intelligence_registry


class PaymentSchedulerService:
    def _resolve_cash_available(self, org_id: str, cash_available: float | None) -> tuple[float, bool]:
        if cash_available is not None:
            return float(cash_available), False
        outstanding = invoice_repository.list_outstanding(org_id)
        total = sum(max(0.0, float(inv.get("outstanding") or 0)) for inv in outstanding)
        return total, True

    def propose_schedule(self, org_id: str, *, cash_available: float | None = None, as_of_date: str | None = None) -> dict:
        cash_available, cash_inferred = self._resolve_cash_available(org_id, cash_available)
        outstanding = invoice_repository.list_outstanding(org_id)
        ranked = intelligence_registry.ap_risk().rank_invoices_for_payment(outstanding)
        proposals: list[dict] = []
        remaining = float(cash_available)
        for inv in ranked:
            amount = float(inv.get("outstanding") or 0)
            if amount <= 0 or remaining < amount:
                continue
            proposals.append({
                "invoice_id": inv.get("id"),
                "vendor_id": inv.get("vendor_id"),
                "amount": amount,
                "due_date": inv.get("due_date"),
                "priority_score": inv.get("priority_score"),
            })
            remaining -= amount
        return {
            "as_of_date": as_of_date or date.today().isoformat(),
            "cash_available": cash_available,
            "cash_inferred_from_outstanding": cash_inferred,
            "proposals": proposals,
            "remaining_cash": remaining,
        }

    def payment_recommendations(self, org_id: str, *, cash_available: float | None = None, as_of_date: str | None = None) -> dict:
        """AI payment assistant: which vendors/invoices to pay this week."""
        schedule = self.propose_schedule(org_id, cash_available=cash_available, as_of_date=as_of_date)
        cash_available = float(schedule["cash_available"])
        by_vendor: dict[str, dict] = {}
        for proposal in schedule.get("proposals") or []:
            vid = str(proposal.get("vendor_id"))
            bucket = by_vendor.setdefault(vid, {"vendor_id": vid, "invoices": [], "total_amount": 0.0})
            bucket["invoices"].append(proposal)
            bucket["total_amount"] += float(proposal.get("amount") or 0)
        recommendations = sorted(by_vendor.values(), key=lambda v: v["total_amount"], reverse=True)
        return {
            **schedule,
            "recommendations": recommendations,
            "summary": f"Pay {len(recommendations)} vendor(s) within available cash of {cash_available:,.2f}",
        }


payment_scheduler_service = PaymentSchedulerService()
