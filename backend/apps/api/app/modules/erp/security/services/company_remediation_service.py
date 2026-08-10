from __future__ import annotations

from app.modules.erp.security.company_resolution_service import company_resolution_service
from app.services.db import get_db_conn


class CompanyRemediationService:
    """Operational remediation runner for DB-04 (post-migration follow-up)."""

    def run_python_pass(self, *, remediated_by: str = "system.remediation") -> dict:
        """Second pass after SQL migration: metadata-based fixes per org."""
        org_ids = self._orgs_with_unresolved_flags()
        total_resolved = 0
        per_org: dict[str, dict] = {}
        for org_id in org_ids:
            result = company_resolution_service.bulk_auto_remediate(
                org_id, remediated_by=remediated_by
            )
            per_org[org_id] = result
            total_resolved += int(result.get("resolved") or 0)
        return {
            "orgs_processed": len(org_ids),
            "resolved": total_resolved,
            "remaining": self.unresolved_flag_count(),
            "per_org": per_org,
        }

    def unresolved_flag_count(self) -> int:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt
                    FROM erp.company_id_data_quality
                    WHERE resolved_at IS NULL
                    """
                )
                row = cur.fetchone()
                return int((row or {}).get("cnt") or 0)

    def summary(self) -> dict:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      COUNT(*) FILTER (WHERE resolved_at IS NULL)::int AS unresolved,
                      COUNT(*) FILTER (WHERE resolved_at IS NOT NULL)::int AS resolved,
                      COUNT(DISTINCT org_id) FILTER (WHERE resolved_at IS NULL)::int AS orgs_with_open_flags
                    FROM erp.company_id_data_quality
                    """
                )
                row = dict(cur.fetchone() or {})
                cur.execute(
                    """
                    SELECT conname, convalidated
                    FROM pg_constraint
                    WHERE conname IN (
                      'chk_erp_journals_company_id_not_null',
                      'chk_erp_ap_invoices_company_id_not_null',
                      'chk_erp_ar_invoices_company_id_not_null',
                      'chk_erp_vouchers_company_id_not_null'
                    )
                    ORDER BY conname
                    """
                )
                constraints = [dict(r) for r in (cur.fetchall() or [])]
        row["constraints"] = constraints
        return row

    def _orgs_with_unresolved_flags(self) -> list[str]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT org_id::text
                    FROM erp.company_id_data_quality
                    WHERE resolved_at IS NULL
                    ORDER BY 1
                    """
                )
                return [str(r["org_id"]) for r in (cur.fetchall() or [])]


company_remediation_service = CompanyRemediationService()
