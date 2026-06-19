from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class CashPositionRepository:
    def upsert(
        self,
        org_id: str,
        *,
        bank_account_id: str,
        position_date: str,
        opening_balance: float,
        inflows: float,
        outflows: float,
        closing_balance: float,
        metadata: dict | None = None,
    ) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.cash_positions (
                      id, org_id, bank_account_id, position_date,
                      opening_balance, inflows, outflows, closing_balance, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s,%s,%s,%s,%s::jsonb)
                    ON CONFLICT (org_id, bank_account_id, position_date)
                    DO UPDATE SET
                      opening_balance = EXCLUDED.opening_balance,
                      inflows = EXCLUDED.inflows,
                      outflows = EXCLUDED.outflows,
                      closing_balance = EXCLUDED.closing_balance,
                      metadata = EXCLUDED.metadata
                    RETURNING id::text, bank_account_id::text, position_date::text, closing_balance
                    """,
                    (pid, org_id, bank_account_id, position_date, opening_balance, inflows, outflows, closing_balance, Json(metadata or {})),
                )
                return dict(cur.fetchone() or {})

    def list_history(self, org_id: str, *, bank_account_id: str | None = None, limit: int = 90) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if bank_account_id:
            where.append("bank_account_id = %s::uuid")
            params.append(bank_account_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, bank_account_id::text, position_date::text,
                           opening_balance, inflows, outflows, closing_balance
                    FROM erp.cash_positions
                    WHERE {' AND '.join(where)}
                    ORDER BY position_date DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def latest_closing(self, org_id: str, *, bank_account_id: str, before_date: str | None = None) -> float | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if before_date:
                    cur.execute(
                        """
                        SELECT closing_balance FROM erp.cash_positions
                        WHERE org_id = %s::uuid AND bank_account_id = %s::uuid AND position_date < %s::date
                        ORDER BY position_date DESC LIMIT 1
                        """,
                        (org_id, bank_account_id, before_date),
                    )
                else:
                    cur.execute(
                        """
                        SELECT closing_balance FROM erp.cash_positions
                        WHERE org_id = %s::uuid AND bank_account_id = %s::uuid
                        ORDER BY position_date DESC LIMIT 1
                        """,
                        (org_id, bank_account_id),
                    )
                row = cur.fetchone()
                return float(row[0]) if row else None


cash_position_repository = CashPositionRepository()
