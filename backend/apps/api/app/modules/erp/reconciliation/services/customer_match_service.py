from __future__ import annotations

from app.modules.erp.accounts_receivable.repositories.invoice_repository import ar_invoice_repository
from app.modules.erp.accounts_receivable.repositories.receipt_repository import receipt_repository


def _amount_close(a: float, b: float, tolerance: float = 0.01) -> bool:
    return abs(float(a) - float(b)) <= tolerance


class CustomerMatchService:
    def collect_candidates(self, org_id: str) -> list[dict]:
        candidates: list[dict] = []
        for r in receipt_repository.list(org_id, limit=500):
            if str(r.get("status")) != "completed":
                continue
            candidates.append({
                "id": r.get("id"),
                "target_type": "ar_receipt",
                "amount": float(r.get("amount") or 0),
                "date": r.get("receipt_date"),
                "reference": r.get("receipt_reference"),
                "counterparty_ref": r.get("customer_id"),
            })
        for inv in ar_invoice_repository.list_outstanding(org_id):
            outstanding = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
            if outstanding > 0:
                candidates.append({
                    "id": inv.get("id"),
                    "target_type": "ar_invoice",
                    "amount": outstanding,
                    "date": inv.get("due_date") or inv.get("invoice_date"),
                    "reference": inv.get("invoice_number"),
                    "counterparty_ref": inv.get("customer_id"),
                })
        return candidates

    def match_receipts_to_invoices(
        self,
        org_id: str,
        *,
        customer_id: str | None = None,
        tolerance: float = 0.01,
    ) -> dict:
        receipts = [
            r for r in receipt_repository.list(org_id, limit=500)
            if str(r.get("status")) == "completed"
            and (not customer_id or str(r.get("customer_id")) == customer_id)
        ]
        invoices = [
            inv for inv in ar_invoice_repository.list_outstanding(org_id)
            if not customer_id or str(inv.get("customer_id")) == customer_id
        ]
        allocations = receipt_repository.list_allocations(org_id, limit=2000)
        allocated_by_receipt: dict[str, float] = {}
        allocated_by_invoice: dict[str, float] = {}
        explicit_pairs: list[dict] = []
        for alloc in allocations:
            rid = str(alloc.get("receipt_id") or "")
            iid = str(alloc.get("invoice_id") or "")
            amt = float(alloc.get("amount") or 0)
            allocated_by_receipt[rid] = allocated_by_receipt.get(rid, 0.0) + amt
            allocated_by_invoice[iid] = allocated_by_invoice.get(iid, 0.0) + amt
            explicit_pairs.append({
                "receipt_id": rid,
                "invoice_id": iid,
                "amount": amt,
                "match_type": "allocation",
                "confidence": 1.0,
            })

        unmatched_receipts: list[dict] = []
        for r in receipts:
            rid = str(r.get("id"))
            total = float(r.get("amount") or 0)
            remaining = round(total - allocated_by_receipt.get(rid, 0.0), 2)
            if remaining > tolerance:
                unmatched_receipts.append({**r, "unallocated_amount": remaining})

        unmatched_invoices: list[dict] = []
        open_invoices: list[dict] = []
        for inv in invoices:
            iid = str(inv.get("id"))
            outstanding = max(0.0, float(inv.get("total_amount") or 0) - float(inv.get("paid_amount") or 0))
            remaining = round(outstanding - allocated_by_invoice.get(iid, 0.0), 2)
            if remaining > tolerance:
                row = {**inv, "open_amount": remaining}
                open_invoices.append(row)
                unmatched_invoices.append(row)

        suggested: list[dict] = []
        used_invoices: set[str] = set()
        for r in unmatched_receipts:
            rid = str(r.get("id"))
            cid = str(r.get("customer_id") or "")
            rcpt_amt = float(r.get("unallocated_amount") or 0)
            best: dict | None = None
            for inv in open_invoices:
                iid = str(inv.get("id"))
                if iid in used_invoices:
                    continue
                if str(inv.get("customer_id") or "") != cid:
                    continue
                open_amt = float(inv.get("open_amount") or 0)
                if _amount_close(rcpt_amt, open_amt, tolerance):
                    best = inv
                    break
            if best:
                iid = str(best.get("id"))
                used_invoices.add(iid)
                suggested.append({
                    "receipt_id": rid,
                    "invoice_id": iid,
                    "amount": rcpt_amt,
                    "match_type": "amount_customer",
                    "confidence": 0.85,
                })

        return {
            "customer_id": customer_id,
            "matched": explicit_pairs + suggested,
            "unmatched_receipts": unmatched_receipts,
            "unmatched_invoices": [i for i in unmatched_invoices if str(i.get("id")) not in used_invoices],
            "summary": {
                "receipt_count": len(receipts),
                "invoice_count": len(invoices),
                "explicit_allocations": len(explicit_pairs),
                "suggested_matches": len(suggested),
            },
        }

    def customer_summary(self, org_id: str, *, customer_id: str) -> dict:
        recon = self.match_receipts_to_invoices(org_id, customer_id=customer_id)
        receipts = [
            r for r in receipt_repository.list(org_id, limit=500)
            if str(r.get("customer_id")) == customer_id
        ]
        invoices = [
            inv for inv in ar_invoice_repository.list_outstanding(org_id)
            if str(inv.get("customer_id")) == customer_id
        ]
        total_outstanding = sum(
            max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0)) for i in invoices
        )
        return {
            "customer_id": customer_id,
            "receipts": receipts,
            "outstanding_invoices": invoices,
            "total_outstanding": round(total_outstanding, 2),
            "reconciliation": recon,
        }

    def apply_suggested_matches(
        self,
        org_id: str,
        *,
        customer_id: str | None = None,
        auto_only: bool = True,
        tolerance: float = 0.01,
    ) -> dict:
        recon = self.match_receipts_to_invoices(org_id, customer_id=customer_id, tolerance=tolerance)
        applied: list[dict] = []
        for match in recon.get("matched") or []:
            if match.get("match_type") == "allocation":
                continue
            if auto_only and float(match.get("confidence") or 0) < 0.8:
                continue
            rid = str(match.get("receipt_id") or "")
            iid = str(match.get("invoice_id") or "")
            amt = float(match.get("amount") or 0)
            if not rid or not iid or amt <= 0:
                continue
            receipt_repository.add_allocation(org_id, receipt_id=rid, invoice_id=iid, amount=amt)
            ar_invoice_repository.record_receipt(org_id, invoice_id=iid, amount=amt)
            applied.append(match)
        return {"applied": applied, "count": len(applied), "reconciliation": recon}


customer_match_service = CustomerMatchService()
