from __future__ import annotations


class VendorMatchService:
    def collect_candidates(self, org_id: str) -> list[dict]:
        candidates: list[dict] = []
        try:
            from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository

            for p in payment_repository.list(org_id, status="completed"):
                candidates.append({
                    "id": p.get("id"),
                    "target_type": "ap_payment",
                    "amount": float(p.get("amount") or 0),
                    "date": p.get("payment_date"),
                    "reference": p.get("payment_reference"),
                    "counterparty_ref": p.get("vendor_id"),
                })
        except Exception:
            pass
        try:
            from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

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
        except Exception:
            pass
        return candidates

    def vendor_summary(self, org_id: str, *, vendor_id: str) -> dict:
        payments: list[dict] = []
        invoices: list[dict] = []
        try:
            from app.modules.erp.accounts_payable.repositories.payment_repository import payment_repository

            for p in payment_repository.list(org_id, status="completed"):
                if str(p.get("vendor_id")) == vendor_id:
                    payments.append(p)
        except Exception:
            pass
        try:
            from app.modules.erp.accounts_payable.repositories.invoice_repository import invoice_repository

            for inv in invoice_repository.list_outstanding(org_id):
                if str(inv.get("vendor_id")) == vendor_id:
                    invoices.append(inv)
        except Exception:
            pass
        statement_recon = None
        try:
            from app.modules.erp.accounts_payable.services.statement_service import statement_service

            statement_recon = {"vendor_id": vendor_id, "note": "Use AP POST /statements/{vendor_id}/reconcile for full statement compare"}
        except Exception:
            pass
        return {
            "vendor_id": vendor_id,
            "payments": payments,
            "outstanding_invoices": invoices,
            "statement_reconcile": statement_recon,
        }


vendor_match_service = VendorMatchService()
