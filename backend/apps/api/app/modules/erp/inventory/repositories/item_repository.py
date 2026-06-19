from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class PolicyRepository:
    def get_active(self, org_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, valuation_method, negative_stock_rule,
                           default_warehouse_id::text, adjustment_approval_threshold
                    FROM erp.inventory_policies
                    WHERE org_id = %s::uuid AND is_active = true
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (org_id,),
                )
                row = cur.fetchone()
                return dict(row) if row else None


class ItemRepository:
    def create(
        self,
        org_id: str,
        *,
        item_code: str,
        item_name: str,
        item_type: str = "trading_goods",
        uom: str = "EA",
        valuation_method: str | None = None,
        inventory_account_id: str | None = None,
        cogs_account_id: str | None = None,
        company_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        iid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.inventory_items (
                      id, org_id, company_id, item_code, item_name, item_type, uom,
                      valuation_method, inventory_account_id, cogs_account_id, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, item_code, status
                    """,
                    (
                        iid, org_id, company_id, item_code, item_name, item_type, uom,
                        valuation_method or "weighted_average", inventory_account_id, cogs_account_id, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": iid})

    def get(self, org_id: str, *, item_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, item_code, item_name, item_type, uom, valuation_method,
                           inventory_account_id::text, cogs_account_id::text, status, company_id::text
                    FROM erp.inventory_items WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, item_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_code(self, org_id: str, *, item_code: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, item_code, item_name FROM erp.inventory_items
                    WHERE org_id = %s::uuid AND item_code = %s
                    """,
                    (org_id, item_code),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, status: str | None = None, limit: int = 200) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, item_code, item_name, item_type, uom, status
                    FROM erp.inventory_items WHERE {' AND '.join(clauses)}
                    ORDER BY item_code LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]


class WarehouseRepository:
    def create(
        self,
        org_id: str,
        *,
        warehouse_code: str,
        warehouse_name: str,
        location: str | None = None,
    ) -> dict:
        wid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.warehouses (id, org_id, warehouse_code, warehouse_name, location)
                    VALUES (%s::uuid,%s::uuid,%s,%s,%s)
                    RETURNING id::text, warehouse_code
                    """,
                    (wid, org_id, warehouse_code, warehouse_name, location),
                )
                return dict(cur.fetchone() or {"id": wid})

    def get(self, org_id: str, *, warehouse_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, warehouse_code, warehouse_name, location, is_active
                    FROM erp.warehouses WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, warehouse_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list_active(self, org_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, warehouse_code, warehouse_name, location
                    FROM erp.warehouses WHERE org_id = %s::uuid AND is_active = true
                    ORDER BY warehouse_code
                    """,
                    (org_id,),
                )
                return [dict(r) for r in cur.fetchall()]


policy_repository = PolicyRepository()
item_repository = ItemRepository()
warehouse_repository = WarehouseRepository()
