from __future__ import annotations

from app.modules.erp.tax.repositories.compliance_repository import tds_transaction_repository
from app.modules.erp.tax.repositories.tds_reconciliation_repository import tds_reconciliation_repository


class TdsReconciliationService:
    def reconcile_26as(
        self,
        org_id: str,
        *,
        financial_year: str,
        quarter: str | None,
        rows: list[dict],
    ) -> dict:
        books = tds_transaction_repository.list(org_id, limit=2000)
        if quarter:
            books = [t for t in books if str(t.get("quarter") or "") == quarter]
        books = [t for t in books if str(t.get("financial_year") or "") == financial_year]

        book_by_pan_section: dict[str, float] = {}
        for tx in books:
            meta = tx.get("metadata") if isinstance(tx.get("metadata"), dict) else {}
            pan = str(meta.get("pan") or "unknown")
            key = f"{pan}:{tx.get('section_code')}"
            book_by_pan_section[key] = round(book_by_pan_section.get(key, 0) + float(tx.get("tds_amount") or 0), 2)

        as_by_pan_section: dict[str, float] = {}
        for row in rows:
            pan = str(row.get("pan") or row.get("deductee_pan") or "unknown")
            section = str(row.get("section_code") or row.get("section") or "")
            key = f"{pan}:{section}"
            as_by_pan_section[key] = round(as_by_pan_section.get(key, 0) + float(row.get("tds_amount") or row.get("tax_deducted") or 0), 2)

        flags: list[dict] = []
        all_keys = set(book_by_pan_section) | set(as_by_pan_section)
        for key in sorted(all_keys):
            book_amt = book_by_pan_section.get(key, 0)
            as_amt = as_by_pan_section.get(key, 0)
            if abs(book_amt - as_amt) > 0.01:
                issue = "amount_mismatch"
                if book_amt == 0:
                    issue = "missing_deduction_in_books"
                elif as_amt == 0:
                    issue = "missing_deposit_in_26as"
                flags.append({"key": key, "books": book_amt, "form26as": as_amt, "issue": issue})

        result = {
            "financial_year": financial_year,
            "quarter": quarter,
            "flags": flags,
            "summary": {
                "book_entries": len(books),
                "26as_rows": len(rows),
                "mismatch_count": len(flags),
            },
        }
        saved = tds_reconciliation_repository.create(
            org_id,
            source_type="26AS",
            financial_year=financial_year,
            quarter=quarter,
            payload={"rows": rows},
            result=result,
        )
        return {**result, "reconciliation_id": saved.get("id")}

    def list_reconciliations(self, org_id: str) -> list[dict]:
        return tds_reconciliation_repository.list(org_id)


tds_reconciliation_service = TdsReconciliationService()
