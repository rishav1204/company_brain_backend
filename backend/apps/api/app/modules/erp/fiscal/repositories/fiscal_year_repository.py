from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class FiscalYearRepository:
    def create(self, org_id: str, **fields) -> dict:
        yid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if fields.get("is_current"):
                    cur.execute(
                        "UPDATE erp.fiscal_years SET is_current = false WHERE org_id = %s::uuid",
                        (org_id,),
                    )
                cur.execute(
                    """
                    INSERT INTO erp.fiscal_years (
                      id, org_id, company_id, fiscal_year_code, start_date, end_date, status, is_current, metadata
                    ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::date,%s::date,%s,%s,%s::jsonb)
                    RETURNING id::text, fiscal_year_code, start_date::text, end_date::text, status, is_current
                    """,
                    (
                        yid, org_id, fields.get("company_id"), fields["fiscal_year_code"],
                        fields["start_date"], fields["end_date"], fields.get("status", "open"),
                        bool(fields.get("is_current")), Json(fields.get("metadata") or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": yid})

    def list(self, org_id: str, *, company_id: str | None = None, limit: int = 500) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if company_id:
            where.append("company_id = %s::uuid")
            params.append(company_id)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, fiscal_year_code, start_date::text, end_date::text, status, is_current
                    FROM erp.fiscal_years WHERE {' AND '.join(where)} ORDER BY start_date DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get(self, org_id: str, *, fiscal_year_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, fiscal_year_code, start_date::text, end_date::text, status, is_current, company_id::text
                    FROM erp.fiscal_years WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, fiscal_year_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def set_status(self, org_id: str, *, fiscal_year_id: str, status: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.fiscal_years SET status = %s, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status
                    """,
                    (status, org_id, fiscal_year_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Fiscal year not found")
                return dict(row)


fiscal_year_repository = FiscalYearRepository()
