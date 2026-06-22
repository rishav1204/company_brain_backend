from __future__ import annotations

from app.services.db import get_db_conn, set_rls_org


class AgingRepository:
    def __init__(self, table: str, entity_col: str, name_col: str) -> None:
        self._table = table
        self._entity_col = entity_col
        self._name_col = name_col

    def replace_as_of(self, org_id: str, *, as_of_date: str, rows: list[dict]) -> int:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"DELETE FROM erp_reporting.{self._table} WHERE org_id = %s::uuid AND as_of_date = %s::date",
                    (org_id, as_of_date),
                )
                count = 0
                for row in rows:
                    cur.execute(
                        f"""
                        INSERT INTO erp_reporting.{self._table} (
                          org_id, as_of_date, {self._entity_col}, {self._name_col},
                          bucket_current, bucket_1_30, bucket_31_60, bucket_61_90, bucket_90_plus,
                          total_outstanding, refreshed_at
                        )
                        VALUES (
                          %s::uuid, %s::date, %s::uuid, %s,
                          %s::numeric, %s::numeric, %s::numeric, %s::numeric, %s::numeric,
                          %s::numeric, now()
                        )
                        """,
                        (
                            org_id,
                            as_of_date,
                            row["entity_id"],
                            row.get("entity_name"),
                            row.get("bucket_current", 0),
                            row.get("bucket_1_30", 0),
                            row.get("bucket_31_60", 0),
                            row.get("bucket_61_90", 0),
                            row.get("bucket_90_plus", 0),
                            row.get("total_outstanding", 0),
                        ),
                    )
                    count += 1
                return count

    def list_as_of(
        self,
        org_id: str,
        *,
        as_of_date: str,
        cursor: str | None = None,
        limit: int = 100,
    ) -> tuple[list[dict], str | None]:
        limit = max(1, min(int(limit or 100), 500))
        entity = self._entity_col
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if cursor:
                    cur.execute(
                        f"""
                        SELECT {entity}::text AS entity_id, {self._name_col} AS entity_name,
                               bucket_current, bucket_1_30, bucket_31_60, bucket_61_90, bucket_90_plus,
                               total_outstanding, refreshed_at::text
                        FROM erp_reporting.{self._table}
                        WHERE org_id = %s::uuid AND as_of_date = %s::date
                          AND {entity}::text > %s
                        ORDER BY {entity}::text ASC
                        LIMIT %s
                        """,
                        (org_id, as_of_date, cursor, limit + 1),
                    )
                else:
                    cur.execute(
                        f"""
                        SELECT {entity}::text AS entity_id, {self._name_col} AS entity_name,
                               bucket_current, bucket_1_30, bucket_31_60, bucket_61_90, bucket_90_plus,
                               total_outstanding, refreshed_at::text
                        FROM erp_reporting.{self._table}
                        WHERE org_id = %s::uuid AND as_of_date = %s::date
                        ORDER BY {entity}::text ASC
                        LIMIT %s
                        """,
                        (org_id, as_of_date, limit + 1),
                    )
                rows = [dict(r) for r in (cur.fetchall() or [])]
        next_cursor = None
        if len(rows) > limit:
            rows = rows[:limit]
            next_cursor = str(rows[-1].get("entity_id") or "")
        return rows, next_cursor

    def totals(self, org_id: str, *, as_of_date: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT
                      COALESCE(SUM(bucket_current), 0)::numeric(18,2) AS current,
                      COALESCE(SUM(bucket_1_30), 0)::numeric(18,2) AS bucket_1_30,
                      COALESCE(SUM(bucket_31_60), 0)::numeric(18,2) AS bucket_31_60,
                      COALESCE(SUM(bucket_61_90), 0)::numeric(18,2) AS bucket_61_90,
                      COALESCE(SUM(bucket_90_plus), 0)::numeric(18,2) AS bucket_90_plus,
                      COALESCE(SUM(total_outstanding), 0)::numeric(18,2) AS grand_total,
                      MAX(refreshed_at)::text AS refreshed_at
                    FROM erp_reporting.{self._table}
                    WHERE org_id = %s::uuid AND as_of_date = %s::date
                    """,
                    (org_id, as_of_date),
                )
                return dict(cur.fetchone() or {})


ap_aging_repository = AgingRepository("ap_aging_mv", "vendor_id", "vendor_name")
ar_aging_repository = AgingRepository("ar_aging_mv", "customer_id", "customer_name")
