from __future__ import annotations

from uuid import UUID

from app.modules.core.iam.repositories.organization_repository import organization_repository
from app.modules.erp.security.company_scope import require_company_id_for_erp_write
from app.services.db import get_db_conn, set_rls_org
from psycopg.types.json import Json


class CompanyResolutionService:
    """Resolve company_id for ERP writes and surface multi-entity data quality issues."""

    @staticmethod
    def _org_uuid(org_id: str) -> bool:
        try:
            UUID(str(org_id))
            return True
        except ValueError:
            return False

    def resolve_for_write(
        self,
        org_id: str,
        *,
        company_id: str | None,
        operation: str,
        attrs: dict | None = None,
    ) -> str:
        if self._org_uuid(org_id):
            unresolved = self.flag_count(org_id)
            if unresolved > 0:
                raise ValueError(
                    f"Unresolved company_id data quality flags ({unresolved}) — "
                    f"remediate via /erp/admin/company-data-quality before {operation}"
                )
        normalized = str(company_id or "").strip()
        if normalized:
            return require_company_id_for_erp_write(
                org_id=org_id,
                company_id=normalized,
                operation=operation,
                attrs=attrs,
            )
        companies = organization_repository.list_companies(org_id, limit=10)
        if not companies:
            raise ValueError(f"No company configured for org {org_id}")
        if len(companies) == 1:
            return require_company_id_for_erp_write(
                org_id=org_id,
                company_id=str(companies[0]["id"]),
                operation=operation,
                attrs=attrs,
            )
        raise ValueError(
            f"company_id is required for ERP operation: {operation} "
            f"(org has {len(companies)} companies)"
        )

    def list_data_quality_flags(self, org_id: str, *, limit: int = 200) -> list[dict]:
        limit = max(1, min(int(limit or 200), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, table_name, row_id::text, company_id::text,
                           issue_code, detected_at::text, resolved_at::text
                    FROM erp.company_id_data_quality
                    WHERE org_id = %s::uuid AND resolved_at IS NULL
                    ORDER BY detected_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def flag_count(self, org_id: str) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*)::int AS cnt
                    FROM erp.company_id_data_quality
                    WHERE org_id = %s::uuid AND resolved_at IS NULL
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return int((row or {}).get("cnt") or 0)

    def remediate_flag(
        self,
        org_id: str,
        *,
        flag_id: str,
        correct_company_id: str,
        remediated_by: str | None = None,
    ) -> dict:
        correct_company_id = str(correct_company_id).strip()
        if not correct_company_id:
            raise ValueError("correct_company_id is required")
        require_company_id_for_erp_write(
            org_id=org_id,
            company_id=correct_company_id,
            operation="company_id.remediate",
        )
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, table_name, row_id::text, issue_code
                    FROM erp.company_id_data_quality
                    WHERE org_id = %s::uuid AND id = %s::uuid AND resolved_at IS NULL
                    FOR UPDATE
                    """,
                    (org_id, flag_id),
                )
                flag = cur.fetchone()
                if not flag:
                    raise ValueError("Data quality flag not found or already resolved")
                table_name = str(flag["table_name"])
                row_id = str(flag["row_id"])
                allowed = {
                    "erp.journals",
                    "erp.ap_invoices",
                    "erp.ar_invoices",
                    "erp.vouchers",
                }
                if table_name not in allowed:
                    raise ValueError(f"Unsupported table for remediation: {table_name}")
                cur.execute(
                    f"UPDATE {table_name} SET company_id = %s::uuid, updated_at = now() WHERE id = %s::uuid AND org_id = %s::uuid",
                    (correct_company_id, row_id, org_id),
                )
                cur.execute(
                    """
                    UPDATE erp.company_id_data_quality
                    SET resolved_at = now(), company_id = %s::uuid,
                        metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb
                    WHERE id = %s::uuid
                    """,
                    (
                        correct_company_id,
                        Json({"remediated_by": remediated_by, "correct_company_id": correct_company_id}),
                        flag_id,
                    ),
                )
        return {"flag_id": flag_id, "status": "resolved", "company_id": correct_company_id}

    def bulk_auto_remediate(self, org_id: str, *, remediated_by: str | None = None) -> dict:
        """Resolve flags when row metadata contains authoritative company_id."""
        resolved = 0
        flags = self.list_data_quality_flags(org_id, limit=500)
        for flag in flags:
            table_name = str(flag.get("table_name") or "")
            row_id = str(flag.get("row_id") or "")
            meta_company = self._row_metadata_company(org_id, table_name, row_id)
            if meta_company:
                self.remediate_flag(
                    org_id,
                    flag_id=str(flag["id"]),
                    correct_company_id=meta_company,
                    remediated_by=remediated_by,
                )
                resolved += 1
        return {"resolved": resolved, "remaining": self.flag_count(org_id)}

    def _row_metadata_company(self, org_id: str, table_name: str, row_id: str) -> str | None:
        allowed = {"erp.journals", "erp.ap_invoices", "erp.ar_invoices", "erp.vouchers"}
        if table_name not in allowed:
            return None
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT metadata FROM {table_name} WHERE id = %s::uuid AND org_id = %s::uuid",
                    (row_id, org_id),
                )
                row = cur.fetchone()
        meta = (row or {}).get("metadata") if isinstance((row or {}).get("metadata"), dict) else {}
        cid = str(meta.get("authoritative_company_id") or meta.get("company_id") or "").strip()
        return cid or None


company_resolution_service = CompanyResolutionService()
