from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PoRepository:
    def create(
        self,
        org_id: str,
        *,
        po_number: str,
        vendor_id: str,
        pr_id: str | None = None,
        po_date: str | None = None,
        expected_delivery_date: str | None = None,
        company_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.purchase_orders (
                      id, org_id, company_id, po_number, vendor_id, pr_id, po_date,
                      expected_delivery_date, created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::uuid,%s::uuid,
                            COALESCE(%s::date, CURRENT_DATE),%s::date,%s::uuid,%s::jsonb)
                    RETURNING id::text, po_number, status, vendor_id::text, total_amount
                    """,
                    (
                        pid, org_id, company_id, po_number, vendor_id, pr_id,
                        po_date, expected_delivery_date, created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": pid})

    def get(self, org_id: str, *, po_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, po_number, vendor_id::text, pr_id::text, status,
                           workflow_approved, po_date::text, expected_delivery_date::text,
                           subtotal, gst_amount, total_amount, sent_at::text, metadata,
                           company_id::text, created_by::text, approved_by::text,
                           created_at::text, updated_at::text
                    FROM erp.purchase_orders
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, po_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, vendor_id: str | None = None, limit: int = 100) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            clauses.append("status = %s")
            params.append(status)
        if vendor_id:
            clauses.append("vendor_id = %s::uuid")
            params.append(vendor_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, po_number, vendor_id::text, status, total_amount, po_date::text
                    FROM erp.purchase_orders
                    WHERE {' AND '.join(clauses)}
                    ORDER BY created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]

    def set_status(
        self,
        org_id: str,
        *,
        po_id: str,
        status: str,
        workflow_approved: bool | None = None,
        approved_by: str | None = None,
        sent_at: bool = False,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.purchase_orders
                    SET status = %s,
                        workflow_approved = COALESCE(%s, workflow_approved),
                        approved_by = COALESCE(%s::uuid, approved_by),
                        sent_at = CASE WHEN %s THEN NOW() ELSE sent_at END,
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, po_number, status, workflow_approved, total_amount
                    """,
                    (status, workflow_approved, approved_by, sent_at, org_id, po_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {}

    def add_item(
        self,
        org_id: str,
        *,
        po_id: str,
        item_name: str,
        quantity: float,
        unit_price: float,
        hsn_sac: str | None = None,
    ) -> dict:
        iid = str(uuid4())
        amount = round(quantity * unit_price, 2)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.purchase_order_items (
                      id, org_id, po_id, item_name, quantity, unit_price, amount, hsn_sac
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::numeric,%s::numeric,%s::numeric,%s)
                    RETURNING id::text, item_name, quantity, unit_price, amount, received_quantity
                    """,
                    (iid, org_id, po_id, item_name, quantity, unit_price, amount, hsn_sac),
                )
                item = dict(cur.fetchone() or {"id": iid})
                cur.execute(
                    """
                    UPDATE erp.purchase_orders
                    SET subtotal = (SELECT COALESCE(SUM(amount), 0) FROM erp.purchase_order_items WHERE po_id = %s::uuid),
                        total_amount = subtotal + gst_amount,
                        updated_at = NOW()
                    WHERE id = %s::uuid
                    """,
                    (po_id, po_id),
                )
                return item

    def list_items(self, org_id: str, *, po_id: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, item_name, quantity, received_quantity, unit_price, amount, hsn_sac
                    FROM erp.purchase_order_items
                    WHERE org_id = %s::uuid AND po_id = %s::uuid
                    ORDER BY created_at
                    LIMIT %s
                    """,
                    (org_id, po_id),
                )
                return [dict(r) for r in cur.fetchall()]

    def update_received_qty(self, org_id: str, *, po_item_id: str, received_quantity: float) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.purchase_order_items
                    SET received_quantity = %s::numeric
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, po_id::text, quantity, received_quantity
                    """,
                    (received_quantity, org_id, po_item_id),
                )
                return dict(cur.fetchone() or {})

    def rollup_receipt_status(self, org_id: str, *, po_id: str) -> str:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                      COALESCE(SUM(quantity), 0) AS ordered,
                      COALESCE(SUM(received_quantity), 0) AS received
                    FROM erp.purchase_order_items
                    WHERE org_id = %s::uuid AND po_id = %s::uuid
                    """,
                    (org_id, po_id),
                )
                row = cur.fetchone()
                ordered = float((row or {}).get("ordered") or 0)
                received = float((row or {}).get("received") or 0)
                if received <= 0:
                    new_status = "sent"
                elif received < ordered:
                    new_status = "partially_received"
                else:
                    new_status = "received"
                cur.execute(
                    """
                    UPDATE erp.purchase_orders SET status = %s, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid AND status NOT IN ('closed','cancelled')
                    """,
                    (new_status, org_id, po_id),
                )
                return new_status


po_repository = PoRepository()
