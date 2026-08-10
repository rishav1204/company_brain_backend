from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class CoaVersionRepository:
    def create(
        self,
        org_id: str,
        *,
        fiscal_year: str,
        version_label: str,
        effective_from: str,
        effective_to: str | None,
        snapshot: dict,
    ) -> dict:
        vid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.coa_versions (
                      id, org_id, fiscal_year, version_label, effective_from, effective_to, snapshot
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s::date,%s::date,%s::jsonb)
                    ON CONFLICT (org_id, fiscal_year, version_label) DO UPDATE
                      SET snapshot = EXCLUDED.snapshot,
                          effective_from = EXCLUDED.effective_from,
                          effective_to = EXCLUDED.effective_to
                    RETURNING id::text, fiscal_year, version_label, effective_from::text, effective_to::text, created_at::text
                    """,
                    (vid, org_id, fiscal_year, version_label, effective_from, effective_to, Json(snapshot)),
                )
                return dict(cur.fetchone() or {"id": vid})

    def list(self, org_id: str, *, fiscal_year: str | None = None, limit: int = 50) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if fiscal_year:
            where.append("fiscal_year = %s")
            params.append(fiscal_year)
        params.append(max(1, min(limit, 200)))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, fiscal_year, version_label, effective_from::text, effective_to::text, created_at::text
                    FROM erp.coa_versions
                    WHERE {' AND '.join(where)}
                    ORDER BY effective_from DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get(self, org_id: str, *, version_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, fiscal_year, version_label, effective_from::text, effective_to::text,
                           snapshot, created_at::text
                    FROM erp.coa_versions
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, version_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None


coa_version_repository = CoaVersionRepository()
