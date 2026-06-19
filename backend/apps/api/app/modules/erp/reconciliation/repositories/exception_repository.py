from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ExceptionRepository:
    def create(
        self,
        org_id: str,
        *,
        bank_transaction_id: str | None,
        reconciliation_id: str | None,
        exception_type: str,
        description: str,
        metadata: dict | None = None,
    ) -> dict:
        eid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.reconciliation_exceptions (
                      id, org_id, bank_transaction_id, reconciliation_id,
                      exception_type, description, status, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,'open',%s::jsonb)
                    RETURNING id::text, exception_type, status
                    """,
                    (eid, org_id, bank_transaction_id, reconciliation_id, exception_type, description, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {"id": eid})

    def list(self, org_id: str, *, status: str | None = "open", limit: int = 200) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, bank_transaction_id::text, reconciliation_id::text,
                           exception_type, description, status, assigned_to::text, created_at::text
                    FROM erp.reconciliation_exceptions
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def assign(self, org_id: str, *, exception_id: str, assigned_to: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.reconciliation_exceptions
                    SET assigned_to = %s::uuid, status = 'assigned', updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, assigned_to::text
                    """,
                    (assigned_to, org_id, exception_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Exception not found")
                return dict(row)


exception_repository = ExceptionRepository()
