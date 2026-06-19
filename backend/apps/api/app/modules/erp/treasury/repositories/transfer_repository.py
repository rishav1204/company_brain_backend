from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TransferRepository:
    def create(
        self,
        org_id: str,
        *,
        source_account_id: str,
        destination_account_id: str,
        transfer_amount: float,
        transfer_date: str,
        status: str = "draft",
        metadata: dict | None = None,
    ) -> dict:
        tid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.inter_account_transfers (
                      id, org_id, source_account_id, destination_account_id,
                      transfer_amount, transfer_date, status, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s::jsonb)
                    RETURNING id::text, status, transfer_amount
                    """,
                    (tid, org_id, source_account_id, destination_account_id, transfer_amount, transfer_date, status, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {"id": tid})

    def get(self, org_id: str, *, transfer_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, source_account_id::text, destination_account_id::text,
                           transfer_amount, transfer_date::text, status, payment_request_id::text, metadata
                    FROM erp.inter_account_transfers
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, transfer_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 100) -> list[dict]:
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
                    SELECT id::text, source_account_id::text, destination_account_id::text,
                           transfer_amount, transfer_date::text, status
                    FROM erp.inter_account_transfers
                    WHERE {' AND '.join(where)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_status(self, org_id: str, *, transfer_id: str, status: str, payment_request_id: str | None = None, approved_by: str | None = None) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.inter_account_transfers
                    SET status = %s,
                        payment_request_id = COALESCE(%s::uuid, payment_request_id),
                        approved_by = COALESCE(%s::uuid, approved_by),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, payment_request_id::text
                    """,
                    (status, payment_request_id, approved_by, org_id, transfer_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Transfer not found")
                return dict(row)


transfer_repository = TransferRepository()
