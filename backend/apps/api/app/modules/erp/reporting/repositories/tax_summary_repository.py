from __future__ import annotations

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class TaxSummaryRepository:
    def __init__(self, table: str, type_col: str) -> None:
        self._table = table
        self._type_col = type_col

    def upsert(
        self,
        org_id: str,
        *,
        return_period: str,
        type_value: str,
        payload: dict,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    INSERT INTO erp_reporting.{self._table} (
                      org_id, return_period, {self._type_col}, payload, refreshed_at
                    )
                    VALUES (%s::uuid, %s, %s, %s::jsonb, now())
                    ON CONFLICT (org_id, return_period, {self._type_col})
                    DO UPDATE SET payload = EXCLUDED.payload, refreshed_at = now()
                    RETURNING return_period, {self._type_col} AS type_value, refreshed_at::text
                    """,
                    (org_id, return_period, type_value, Json(payload)),
                )
                return dict(cur.fetchone() or {})

    def get(self, org_id: str, *, return_period: str, type_value: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT return_period, {self._type_col} AS type_value, payload, refreshed_at::text
                    FROM erp_reporting.{self._table}
                    WHERE org_id = %s::uuid AND return_period = %s AND {self._type_col} = %s
                    """,
                    (org_id, return_period, type_value),
                )
                row = cur.fetchone()
                return dict(row) if row else None


gst_summary_repository = TaxSummaryRepository("gst_summary_mv", "return_type")
tds_summary_repository = TaxSummaryRepository("tds_summary_mv", "form_type")
