from __future__ import annotations

from uuid import uuid4

from app.modules.erp.accounts_payable.engine.payable_engine import resolve_default_payable_account
from app.modules.erp.accounts_payable.repositories.vendor_balance_repository import vendor_balance_repository
from app.modules.erp.accounts_payable.repositories.vendor_repository import vendor_repository
from app.modules.erp.tax.repositories.itc_repository import itc_ledger_repository
from app.services.db import get_db_conn, set_rls_org
from app.services.logger import log_event


class SubledgerGlReconciliationService:
    """Nightly AP/AR subledger vs GL control account and ITC vs GST GL checks (DB-23/24)."""

    def run_daily(self, org_id: str, *, tolerance: float = 1.0) -> dict:
        ap = self._reconcile_ap_subledger(org_id, tolerance=tolerance)
        ar = self._reconcile_ar_subledger(org_id, tolerance=tolerance)
        itc = self._reconcile_itc_vs_gl(org_id, tolerance=tolerance)
        result = {"ap_subledger": ap, "ar_subledger": ar, "itc_gl": itc}
        variance = float(ap.get("variance") or 0) + float(ar.get("variance") or 0)
        self._persist_run(org_id, run_type="daily", details=result, variance_amount=variance)
        log_event("erp.subledger_gl_reconciliation.completed", org_id=org_id, **result)
        return result

    def _reconcile_ar_subledger(self, org_id: str, *, tolerance: float) -> dict:
        from app.modules.erp.accounts_receivable.engine.account_resolver import resolve_receivable_account
        from app.modules.erp.accounts_receivable.repositories.customer_balance_repository import customer_balance_repository
        from app.modules.erp.accounts_receivable.repositories.customer_repository import customer_repository

        customers = customer_repository.list(org_id, limit=500)
        variances: list[dict] = []
        subledger_total = 0.0
        gl_total = 0.0
        for customer in customers:
            cid = str(customer.get("id"))
            receivable_id = resolve_receivable_account(org_id, customer)
            if not receivable_id:
                continue
            subledger = float(
                (customer_balance_repository.get(org_id, customer_id=cid) or {}).get("outstanding_amount") or 0
            )
            gl_outstanding = customer_balance_repository.compute_gl_outstanding(
                org_id, customer_id=cid, receivable_account_id=receivable_id
            )
            subledger_total += subledger
            gl_total += gl_outstanding
            delta = round(subledger - gl_outstanding, 2)
            if abs(delta) > tolerance:
                variances.append({
                    "customer_id": cid,
                    "subledger": subledger,
                    "gl": gl_outstanding,
                    "variance": delta,
                })
        return {
            "subledger_total": round(subledger_total, 2),
            "gl_total": round(gl_total, 2),
            "variance": round(subledger_total - gl_total, 2),
            "variances": variances[:50],
            "within_tolerance": abs(subledger_total - gl_total) <= tolerance,
        }

    def _reconcile_ap_subledger(self, org_id: str, *, tolerance: float) -> dict:
        vendors = vendor_repository.list(org_id, limit=500)
        variances: list[dict] = []
        subledger_total = 0.0
        gl_total = 0.0
        for vendor in vendors:
            vid = str(vendor.get("id"))
            payable_id = resolve_default_payable_account(org_id, vendor)
            if not payable_id:
                continue
            subledger = float(
                (vendor_balance_repository.get(org_id, vendor_id=vid) or {}).get("outstanding_amount") or 0
            )
            gl_outstanding = vendor_balance_repository.compute_gl_outstanding(
                org_id, vendor_id=vid, payable_account_id=payable_id
            )
            subledger_total += subledger
            gl_total += gl_outstanding
            delta = round(subledger - gl_outstanding, 2)
            if abs(delta) > tolerance:
                variances.append({
                    "vendor_id": vid,
                    "subledger": subledger,
                    "gl": gl_outstanding,
                    "variance": delta,
                })
        return {
            "subledger_total": round(subledger_total, 2),
            "gl_total": round(gl_total, 2),
            "variance": round(subledger_total - gl_total, 2),
            "variances": variances[:50],
            "within_tolerance": abs(subledger_total - gl_total) <= tolerance,
        }

    def _reconcile_itc_vs_gl(self, org_id: str, *, tolerance: float) -> dict:
        from app.modules.erp.coa.repositories.mapping_repository import mapping_repository

        itc_summary = itc_ledger_repository.summary_by_period(org_id, return_period=None)
        claimed = float(itc_summary.get("claimed_total") or itc_summary.get("total_claimed") or 0)
        mappings = mapping_repository.list_gst_mappings(org_id, limit=500)
        input_types = {"cgst_input", "sgst_input", "igst_input", "gst_input", "input_gst"}
        account_ids = [
            str(m["account_id"])
            for m in mappings
            if m.get("itc_eligible") and str(m.get("gst_type") or "").lower() in input_types
        ]
        gl_input = 0.0
        if account_ids:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(ab.closing_balance), 0)::float8 AS gl_balance
                        FROM erp.account_balances ab
                        WHERE ab.org_id = %s::uuid
                          AND ab.account_id = ANY(%s::uuid[])
                        """,
                        (org_id, account_ids),
                    )
                    row = cur.fetchone()
                    gl_input = float((row or {}).get("gl_balance") or 0)
        else:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT COALESCE(SUM(ab.closing_balance), 0)::float8 AS gl_balance
                        FROM erp.account_balances ab
                        JOIN erp.chart_of_accounts a ON a.id = ab.account_id
                        JOIN erp.account_groups ag ON ag.id = a.group_id
                        WHERE ab.org_id = %s::uuid
                          AND lower(ag.nature) = 'debit'
                          AND (
                            lower(a.account_name) LIKE '%gst%input%'
                            OR lower(a.account_code) LIKE '%gst%in%'
                          )
                        """,
                        (org_id,),
                    )
                    row = cur.fetchone()
                    gl_input = float((row or {}).get("gl_balance") or 0)
        variance = round(claimed - gl_input, 2)
        return {
            "itc_claimed": round(claimed, 2),
            "gst_input_gl": round(gl_input, 2),
            "variance": variance,
            "within_tolerance": abs(variance) <= tolerance,
            "mapping_accounts_used": len(account_ids),
        }

    def _persist_run(self, org_id: str, *, run_type: str, details: dict, variance_amount: float | None = None) -> None:
        variance = variance_amount if variance_amount is not None else float(details.get("ap_subledger", {}).get("variance") or 0)
        try:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO erp.subledger_gl_reconciliation_runs
                            (id, org_id, run_type, status, variance_amount, details)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb)
                        """,
                        (
                            str(uuid4()),
                            org_id,
                            run_type,
                            "completed",
                            variance,
                            details,
                        ),
                    )
        except Exception as exc:
            log_event("erp.subledger_gl_reconciliation.persist_failed", org_id=org_id, error=str(exc))


subledger_gl_reconciliation_service = SubledgerGlReconciliationService()
