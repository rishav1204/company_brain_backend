from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class GrnRepository:
    def create(
        self,
        org_id: str,
        *,
        grn_number: str,
        po_id: str,
        received_by: str | None = None,
        received_date: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        gid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.goods_receipts (
                      id, org_id, grn_number, po_id, received_by, received_date, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s,%s::uuid,%s::uuid,COALESCE(%s::date,CURRENT_DATE),%s::jsonb)
                    RETURNING id::text, grn_number, status, po_id::text
                    """,
                    (gid, org_id, grn_number, po_id, received_by, received_date, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {"id": gid})

    def get(self, org_id: str, *, grn_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, grn_number, po_id::text, received_by::text, received_date::text,
                           status, workflow_approved, metadata, created_at::text
                    FROM erp.goods_receipts
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, grn_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_for_po(self, org_id: str, *, po_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, grn_number, status, received_date::text, received_by::text
                    FROM erp.goods_receipts
                    WHERE org_id = %s::uuid AND po_id = %s::uuid
                    ORDER BY created_at DESC
                    """,
                    (org_id, po_id),
                )
                return [dict(r) for r in cur.fetchall()]

    def set_status(
        self,
        org_id: str,
        *,
        grn_id: str,
        status: str,
        workflow_approved: bool | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.goods_receipts
                    SET status = %s,
                        workflow_approved = COALESCE(%s, workflow_approved),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, grn_number, status, workflow_approved
                    """,
                    (status, workflow_approved, org_id, grn_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def add_item(
        self,
        org_id: str,
        *,
        grn_id: str,
        po_item_id: str,
        received_quantity: float,
        accepted_quantity: float | None = None,
        rejected_quantity: float = 0,
    ) -> dict:
        iid = str(uuid4())
        accepted = accepted_quantity if accepted_quantity is not None else received_quantity
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.goods_receipt_items (
                      id, org_id, grn_id, po_item_id, received_quantity, accepted_quantity, rejected_quantity
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::numeric,%s::numeric,%s::numeric)
                    RETURNING id::text, po_item_id::text, received_quantity, accepted_quantity
                    """,
                    (iid, org_id, grn_id, po_item_id, received_quantity, accepted, rejected_quantity),
                )
                return dict(cur.fetchone() or {"id": iid})

    def list_items(self, org_id: str, *, grn_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, po_item_id::text, received_quantity, accepted_quantity, rejected_quantity
                    FROM erp.goods_receipt_items
                    WHERE org_id = %s::uuid AND grn_id = %s::uuid
                    """,
                    (org_id, grn_id),
                )
                return [dict(r) for r in cur.fetchall()]


grn_repository = GrnRepository()
