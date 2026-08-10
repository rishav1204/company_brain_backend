from __future__ import annotations

from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository


def _amount_close(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(float(a) - float(b)) <= tolerance


class VendorMatchService:
    def collect_candidates(self, org_id: str) -> list[dict]:
        candidates: list[dict] = []
        for p in payment_repository.list(org_id, status="completed", limit=500):
            candidates.append({
                "id": p.get("id"),
                "target_type": "ap_payment",
                "amount": float(p.get("amount") or 0),
                "date": p.get("payment_date"),
                "reference": p.get("payment_reference"),
                "counterparty_ref": p.get("vendor_id"),
            })
        for inv in invoice_repository.list_outstanding(org_id):
            outstanding = float(inv.get("outstanding") or inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0)
            if outstanding > 0:
                candidates.append({
                    "id": inv.get("id"),
                    "target_type": "ap_invoice",
                    "amount": outstanding,
                    "date": inv.get("due_date") or inv.get("invoice_date"),
                    "reference": inv.get("invoice_number"),
                    "counterparty_ref": inv.get("vendor_id"),
                })
        return candidates

    def match_payments_to_invoices(
        self,
        org_id: str,
        *,
        vendor_id: str | None = None,
        tolerance: float = 0.01,
    ) -> dict:
        payments = [
            p for p in payment_repository.list(org_id, status="completed", limit=500)
            if not vendor_id or str(p.get("vendor_id")) == vendor_id
        ]
        invoices = [
            inv for inv in invoice_repository.list_outstanding(org_id)
            if not vendor_id or str(inv.get("vendor_id")) == vendor_id
        ]
        allocations = payment_repository.list_allocations(org_id, limit=2000)
        allocated_by_payment: dict[str, float] = {}
        allocated_by_invoice: dict[str, float] = {}
        explicit_pairs: list[dict] = []
        for alloc in allocations:
            pid = str(alloc.get("payment_id") or "")
            iid = str(alloc.get("invoice_id") or "")
            amt = float(alloc.get("amount") or 0)
            allocated_by_payment[pid] = allocated_by_payment.get(pid, 0.0) + amt
            allocated_by_invoice[iid] = allocated_by_invoice.get(iid, 0.0) + amt
            explicit_pairs.append({
                "payment_id": pid,
                "invoice_id": iid,
                "amount": amt,
                "match_type": "allocation",
                "confidence": 1.0,
            })

        unmatched_payments: list[dict] = []
        for p in payments:
            pid = str(p.get("id"))
            total = float(p.get("amount") or 0)
            remaining = round(total - allocated_by_payment.get(pid, 0.0), 2)
            if remaining > tolerance:
                unmatched_payments.append({**p, "unallocated_amount": remaining})

        unmatched_invoices: list[dict] = []
        open_invoices: list[dict] = []
        for inv in invoices:
            iid = str(inv.get("id"))
            outstanding = max(
                0.0,
                float(inv.get("outstanding") or inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0),
            )
            remaining = round(outstanding - allocated_by_invoice.get(iid, 0.0), 2)
            if remaining > tolerance:
                row = {**inv, "open_amount": remaining}
                open_invoices.append(row)
                unmatched_invoices.append(row)

        suggested: list[dict] = []
        used_invoices: set[str] = set()
        for p in unmatched_payments:
            pid = str(p.get("id"))
            vid = str(p.get("vendor_id") or "")
            pay_amt = float(p.get("unallocated_amount") or 0)
            best: dict | None = None
            for inv in open_invoices:
                iid = str(inv.get("id"))
                if iid in used_invoices:
                    continue
                if str(inv.get("vendor_id") or "") != vid:
                    continue
                open_amt = float(inv.get("open_amount") or 0)
                if _amount_close(pay_amt, open_amt, tolerance):
                    best = inv
                    break
            if best:
                iid = str(best.get("id"))
                used_invoices.add(iid)
                suggested.append({
                    "payment_id": pid,
                    "invoice_id": iid,
                    "amount": pay_amt,
                    "match_type": "amount_vendor",
                    "confidence": 0.85,
                })

        return {
            "vendor_id": vendor_id,
            "matched": explicit_pairs + suggested,
            "unmatched_payments": unmatched_payments,
            "unmatched_invoices": [i for i in unmatched_invoices if str(i.get("id")) not in used_invoices],
            "summary": {
                "payment_count": len(payments),
                "invoice_count": len(invoices),
                "explicit_allocations": len(explicit_pairs),
                "suggested_matches": len(suggested),
            },
        }

    def vendor_summary(self, org_id: str, *, vendor_id: str) -> dict:
        recon = self.match_payments_to_invoices(org_id, vendor_id=vendor_id)
        payments = [
            p for p in payment_repository.list(org_id, status="completed", limit=500)
            if str(p.get("vendor_id")) == vendor_id
        ]
        invoices = [
            inv for inv in invoice_repository.list_outstanding(org_id)
            if str(inv.get("vendor_id")) == vendor_id
        ]
        return {
            "vendor_id": vendor_id,
            "payments": payments,
            "outstanding_invoices": invoices,
            "reconciliation": recon,
        }


    def apply_suggested_matches(
        self,
        org_id: str,
        *,
        vendor_id: str | None = None,
        auto_only: bool = True,
        tolerance: float = 0.01,
    ) -> dict:
        recon = self.match_payments_to_invoices(org_id, vendor_id=vendor_id, tolerance=tolerance)
        applied: list[dict] = []
        for match in recon.get("matched") or []:
            if match.get("match_type") == "allocation":
                continue
            if auto_only and float(match.get("confidence") or 0) < 0.8:
                continue
            pid = str(match.get("payment_id") or "")
            iid = str(match.get("invoice_id") or "")
            amt = float(match.get("amount") or 0)
            if not pid or not iid or amt <= 0:
                continue
            payment_repository.add_allocation(org_id, payment_id=pid, invoice_id=iid, amount=amt)
            invoice_repository.record_payment(org_id, invoice_id=iid, amount=amt)
            applied.append(match)
        return {"applied": applied, "count": len(applied), "reconciliation": recon}


vendor_match_service = VendorMatchService()
