from __future__ import annotations

from datetime import datetime

from app.modules.erp.query_services import ap_queries
from app.modules.finance_os.invoice_ai.ai.duplicate_scorer import classify_duplicate_status, weighted_duplicate_score
from app.modules.finance_os.invoice_ai.repositories.duplicate_repository import DuplicateRepository

duplicate_repository = DuplicateRepository()


class DuplicateService:
    def score(self, org_id: str, *, extraction: dict) -> dict:
        vendor_id = extraction.get("vendor_id")
        if not vendor_id and extraction.get("vendor_gstin"):
            v = ap_queries.find_vendor_by_gstin(org_id, gstin=str(extraction["vendor_gstin"]))
            vendor_id = v.get("id") if v else None

        invoice_number = str(extraction.get("invoice_number") or "")
        total = float(extraction.get("total_amount") or 0)
        invoice_date = str(extraction.get("invoice_date") or "")[:10]

        matched_invoice_id = None

        if vendor_id and invoice_number:
            dup = ap_queries.check_duplicate_invoice(
                org_id,
                vendor_id=str(vendor_id),
                invoice_number=invoice_number,
                total_amount=total,
                invoice_date=invoice_date or datetime.utcnow().date().isoformat(),
            )
            if dup and dup.get("duplicate"):
                existing = dup.get("existing_invoice") or {}
                matched_invoice_id = existing.get("id")
                score, breakdown = 100.0, {"checksum_hit": True, "total": 100.0}
                status = "confirmed"
            else:
                score, breakdown = self._scan_candidates(
                    org_id,
                    vendor_id=str(vendor_id),
                    invoice_number=invoice_number,
                    total=total,
                    invoice_date=invoice_date,
                )
                status = classify_duplicate_status(score)
                if status != "clean":
                    matched_invoice_id = breakdown.get("matched_invoice_id")
        else:
            score, breakdown = weighted_duplicate_score(
                invoice_number_match=False,
                vendor_match=bool(extraction.get("vendor_gstin")),
                amount_delta_pct=1.0,
                date_delta_days=None,
            )
            status = classify_duplicate_status(score)

        return duplicate_repository.create(
            org_id,
            data={
                "extraction_id": extraction["id"],
                "matched_invoice_id": matched_invoice_id,
                "similarity_score": score,
                "status": status,
                "score_breakdown": breakdown,
            },
        )

    def _scan_candidates(
        self,
        org_id: str,
        *,
        vendor_id: str,
        invoice_number: str,
        total: float,
        invoice_date: str,
    ) -> tuple[float, dict]:
        candidates = ap_queries.list_invoices(org_id, vendor_id=vendor_id, limit=50)
        best_score = 0.0
        best_breakdown: dict = {}
        for cand in candidates:
            inv_no_match = str(cand.get("invoice_number") or "").lower() == invoice_number.lower()
            cand_total = float(cand.get("total_amount") or 0)
            delta = abs(cand_total - total) / max(total, 1)
            date_delta = None
            if invoice_date and cand.get("invoice_date"):
                try:
                    d1 = datetime.fromisoformat(invoice_date[:10])
                    d2 = datetime.fromisoformat(str(cand["invoice_date"])[:10])
                    date_delta = abs((d1 - d2).days)
                except ValueError:
                    date_delta = None
            score, breakdown = weighted_duplicate_score(
                invoice_number_match=inv_no_match,
                vendor_match=True,
                amount_delta_pct=delta,
                date_delta_days=date_delta,
            )
            if score > best_score:
                best_score = score
                best_breakdown = {**breakdown, "matched_invoice_id": cand.get("id")}
        if not best_breakdown:
            best_breakdown = {"total": 0}
        return best_score, best_breakdown

    def confirm(
        self,
        org_id: str,
        *,
        extraction_id: str,
        status: str,
        matched_invoice_id: str | None = None,
    ) -> dict | None:
        return duplicate_repository.update_status(
            org_id,
            extraction_id,
            status=status,
            matched_invoice_id=matched_invoice_id,
        )

    def latest(self, org_id: str, extraction_id: str) -> dict | None:
        return duplicate_repository.latest_for_extraction(org_id, extraction_id)


duplicate_service = DuplicateService()
