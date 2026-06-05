from __future__ import annotations

from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository
from app.modules.erp.accounts_payable.repositories.vendor_balance_repository import vendor_balance_repository
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository


class StatementService:
    def reconcile(self, org_id: str, *, vendor_id: str, statement_lines: list[dict]) -> dict:
        vendor = vendor_repository.get(org_id, vendor_id=vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")
        erp_invoices = invoice_repository.list(org_id, vendor_id=vendor_id, limit=500)
        erp_outstanding = sum(
            max(0.0, float(i.get("total_amount") or 0) - float(i.get("paid_amount") or 0))
            for i in erp_invoices
            if str(i.get("status")) in {"approved", "partially_paid"}
        )
        stmt_total = sum(float(l.get("amount") or 0) for l in statement_lines)
        balance = vendor_balance_repository.get(org_id, vendor_id=vendor_id)
        differences = []
        erp_by_number = {
            str(i.get("invoice_number")): i
            for i in erp_invoices
            if str(i.get("status")) in {"approved", "partially_paid"}
        }
        for line in statement_lines:
            inv_no = str(line.get("invoice_number") or line.get("reference") or "").strip()
            stmt_amt = float(line.get("amount") or 0)
            if not inv_no:
                continue
            erp_inv = erp_by_number.get(inv_no)
            if not erp_inv:
                differences.append({
                    "type": "missing_in_erp",
                    "invoice_number": inv_no,
                    "statement_amount": stmt_amt,
                })
                continue
            erp_out = max(0.0, float(erp_inv.get("total_amount") or 0) - float(erp_inv.get("paid_amount") or 0))
            if round(stmt_amt, 2) != round(erp_out, 2):
                differences.append({
                    "type": "line_mismatch",
                    "invoice_number": inv_no,
                    "statement_amount": stmt_amt,
                    "erp_outstanding": erp_out,
                    "variance": round(stmt_amt - erp_out, 2),
                })
        if round(stmt_total, 2) != round(erp_outstanding, 2):
            differences.append({
                "type": "balance_mismatch",
                "vendor_statement": stmt_total,
                "erp_outstanding": erp_outstanding,
                "variance": round(stmt_total - erp_outstanding, 2),
            })
        return {
            "vendor_id": vendor_id,
            "vendor_name": vendor.get("vendor_name"),
            "erp_outstanding": erp_outstanding,
            "statement_total": stmt_total,
            "projected_balance": balance,
            "differences": differences,
            "reconciled": len(differences) == 0,
        }


statement_service = StatementService()
