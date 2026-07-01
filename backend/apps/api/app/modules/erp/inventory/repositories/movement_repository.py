from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class MovementRepository:
    def create(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        movement_type: str,
        quantity: float,
        unit_cost: float,
        total_cost: float,
        movement_date: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        journal_id: str | None = None,
        created_by: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        mid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.inventory_movements (
                      id, org_id, item_id, warehouse_id, movement_type, quantity, unit_cost,
                      total_cost, movement_date, reference_type, reference_id, journal_id,
                      created_by, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s::numeric,%s::numeric,%s::numeric,
                            %s::date,%s,%s::uuid,%s::uuid,%s::uuid,%s::jsonb)
                    RETURNING id::text, movement_type, total_cost
                    """,
                    (
                        mid, org_id, item_id, warehouse_id, movement_type, quantity, unit_cost,
                        total_cost, movement_date, reference_type, reference_id, journal_id,
                        created_by, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": mid})

    def list(
        self,
        org_id: str,
        *,
        item_id: str | None = None,
        warehouse_id: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        clauses = ["org_id = %s::uuid"]
        params: list = [org_id]
        if item_id:
            clauses.append("item_id = %s::uuid")
            params.append(item_id)
        if warehouse_id:
            clauses.append("warehouse_id = %s::uuid")
            params.append(warehouse_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, item_id::text, warehouse_id::text, movement_type, quantity,
                           unit_cost, total_cost, movement_date::text, reference_type, journal_id::text
                    FROM erp.inventory_movements WHERE {' AND '.join(clauses)}
                    ORDER BY movement_date DESC, created_at DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]


class BalanceRepository:
    def get(self, org_id: str, *, item_id: str, warehouse_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, quantity_on_hand, inventory_value, weighted_avg_cost
                    FROM erp.inventory_balances
                    WHERE org_id = %s::uuid AND item_id = %s::uuid AND warehouse_id = %s::uuid
                    """,
                    (org_id, item_id, warehouse_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def upsert(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        quantity_on_hand: float,
        inventory_value: float,
        weighted_avg_cost: float,
    ) -> dict:
        bid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.inventory_balances (
                      id, org_id, item_id, warehouse_id, quantity_on_hand, inventory_value, weighted_avg_cost
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::numeric,%s::numeric,%s::numeric)
                    ON CONFLICT (org_id, item_id, warehouse_id) DO UPDATE SET
                      quantity_on_hand = EXCLUDED.quantity_on_hand,
                      inventory_value = EXCLUDED.inventory_value,
                      weighted_avg_cost = EXCLUDED.weighted_avg_cost,
                      last_updated = NOW()
                    RETURNING id::text, quantity_on_hand, inventory_value, weighted_avg_cost
                    """,
                    (bid, org_id, item_id, warehouse_id, quantity_on_hand, inventory_value, weighted_avg_cost),
                )
                return dict(cur.fetchone() or {})

    def list_all(self, org_id: str, *, warehouse_id: str | None = None, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        clauses = ["b.org_id = %s::uuid"]
        params: list = [org_id]
        if warehouse_id:
            clauses.append("b.warehouse_id = %s::uuid")
            params.append(warehouse_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT b.item_id::text, i.item_code, i.item_name, b.warehouse_id::text,
                           w.warehouse_code, b.quantity_on_hand, b.inventory_value, b.weighted_avg_cost
                    FROM erp.inventory_balances b
                    JOIN erp.inventory_items i ON i.id = b.item_id
                    JOIN erp.warehouses w ON w.id = b.warehouse_id
                    WHERE {' AND '.join(clauses)}
                    ORDER BY i.item_code LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in cur.fetchall()]


class LayerRepository:
    def create(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        movement_id: str | None,
        remaining_quantity: float,
        unit_cost: float,
        receipt_date: str,
    ) -> dict:
        lid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.inventory_cost_layers (
                      id, org_id, item_id, warehouse_id, movement_id,
                      remaining_quantity, unit_cost, receipt_date
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::numeric,%s::numeric,%s::date)
                    RETURNING id::text
                    """,
                    (lid, org_id, item_id, warehouse_id, movement_id, remaining_quantity, unit_cost, receipt_date),
                )
                return dict(cur.fetchone() or {"id": lid})

    def list_open(self, org_id: str, *, item_id: str, warehouse_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, remaining_quantity, unit_cost, receipt_date::text
                    FROM erp.inventory_cost_layers
                    WHERE org_id = %s::uuid AND item_id = %s::uuid AND warehouse_id = %s::uuid
                      AND remaining_quantity > 0
                    ORDER BY receipt_date, created_at
                    LIMIT %s
                    """,
                    (org_id, item_id, warehouse_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def reduce(self, org_id: str, *, layer_id: str, quantity: float) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.inventory_cost_layers
                    SET remaining_quantity = remaining_quantity - %s::numeric
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (quantity, org_id, layer_id),
                )


class GrnLinkRepository:
    def exists(self, org_id: str, *, grn_item_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM erp.grn_inventory_links WHERE org_id = %s::uuid AND grn_item_id = %s::uuid LIMIT 1",
                    (org_id, grn_item_id),
                )
                return cur.fetchone() is not None

    def list_by_grn(self, org_id: str, *, goods_receipt_id: str, limit: int = 500) -> list[dict]:
        limit = clamp_limit(limit, default=500, maximum=500)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT l.id::text, l.grn_item_id::text, l.inventory_movement_id::text,
                           m.total_cost, m.quantity
                    FROM erp.grn_inventory_links l
                    JOIN erp.inventory_movements m ON m.id = l.inventory_movement_id
                    WHERE l.org_id = %s::uuid AND l.goods_receipt_id = %s::uuid
                    LIMIT %s
                    """,
                    (org_id, goods_receipt_id, limit),
                )
                return [dict(r) for r in cur.fetchall()]

    def create(self, org_id: str, *, goods_receipt_id: str, grn_item_id: str, movement_id: str) -> dict:
        lid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.grn_inventory_links (id, org_id, goods_receipt_id, grn_item_id, inventory_movement_id)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::uuid)
                    RETURNING id::text
                    """,
                    (lid, org_id, goods_receipt_id, grn_item_id, movement_id),
                )
                return dict(cur.fetchone() or {"id": lid})


class ValuationRepository:
    def create(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str | None,
        valuation_date: str,
        valuation_method: str,
        quantity: float,
        inventory_value: float,
    ) -> dict:
        vid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.inventory_valuations (
                      id, org_id, item_id, warehouse_id, valuation_date,
                      valuation_method, quantity, inventory_value
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::date,%s,%s::numeric,%s::numeric)
                    RETURNING id::text
                    """,
                    (vid, org_id, item_id, warehouse_id, valuation_date, valuation_method, quantity, inventory_value),
                )
                return dict(cur.fetchone() or {"id": vid})

    def list(self, org_id: str, *, valuation_date: str | None = None, limit: int = 200) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if valuation_date:
                    cur.execute(
                        """
                        SELECT id::text, item_id::text, valuation_date::text, quantity, inventory_value, valuation_method
                        FROM erp.inventory_valuations
                        WHERE org_id = %s::uuid AND valuation_date = %s::date
                        ORDER BY created_at DESC LIMIT %s
                        """,
                        (org_id, valuation_date, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, item_id::text, valuation_date::text, quantity, inventory_value, valuation_method
                        FROM erp.inventory_valuations
                        WHERE org_id = %s::uuid
                        ORDER BY valuation_date DESC LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in cur.fetchall()]


class AdjustmentRepository:
    def create(
        self,
        org_id: str,
        *,
        item_id: str,
        warehouse_id: str,
        adjustment_date: str,
        quantity_variance: float,
        value_variance: float,
        reason: str | None,
        movement_id: str | None,
        journal_id: str | None,
        created_by: str | None,
        status: str = "posted",
    ) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.inventory_adjustments (
                      id, org_id, item_id, warehouse_id, adjustment_date,
                      quantity_variance, value_variance, reason, movement_id, journal_id, created_by, status
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s::date,%s::numeric,%s::numeric,%s,%s::uuid,%s::uuid,%s::uuid,%s)
                    RETURNING id::text
                    """,
                    (
                        aid, org_id, item_id, warehouse_id, adjustment_date,
                        quantity_variance, value_variance, reason, movement_id, journal_id, created_by, status,
                    ),
                )
                return dict(cur.fetchone() or {"id": aid})


movement_repository = MovementRepository()
balance_repository = BalanceRepository()
layer_repository = LayerRepository()
grn_link_repository = GrnLinkRepository()
valuation_repository = ValuationRepository()
adjustment_repository = AdjustmentRepository()
