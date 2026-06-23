from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TdsReturnRepository:
    def create(self, org_id: str, *, return_period: str, form_type: str, payload: dict) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.tds_returns (id, org_id, return_period, form_type, status, payload)
                    VALUES (%s::uuid,%s::uuid,%s,%s,'draft',%s::jsonb)
                    ON CONFLICT (org_id, return_period, form_type) DO UPDATE SET payload=EXCLUDED.payload, updated_at=NOW()
                    RETURNING id::text, return_period, form_type, status
                    """,
                    (rid, org_id, return_period, form_type, Json(payload)),
                )
                return dict(cur.fetchone() or {"id": rid})

    def list(self, org_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, return_period, form_type, status, workflow_approved FROM erp.tds_returns WHERE org_id=%s::uuid ORDER BY return_period DESC LIMIT %s",
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get(self, org_id: str, *, return_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id::text, return_period, form_type, status, payload, workflow_approved FROM erp.tds_returns WHERE org_id=%s::uuid AND id=%s::uuid",
                    (org_id, return_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def set_status(self, org_id: str, *, return_id: str, status: str, workflow_approved: bool | None = None, filed_by: str | None = None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.tds_returns
                    SET status=%s, workflow_approved=COALESCE(%s, workflow_approved),
                        filed_at=CASE WHEN %s='filed' THEN NOW() ELSE filed_at END,
                        filed_by=COALESCE(%s::uuid, filed_by), updated_at=NOW()
                    WHERE org_id=%s::uuid AND id=%s::uuid
                    RETURNING id::text, status, workflow_approved
                    """,
                    (status, workflow_approved, status, filed_by, org_id, return_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("TDS return not found")
                return dict(row)


tds_return_repository = TdsReturnRepository()
