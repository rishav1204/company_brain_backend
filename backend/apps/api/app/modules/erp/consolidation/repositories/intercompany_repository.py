from __future__ import annotations

from typing import Any
from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class IntercompanyRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='erp' AND table_name='intercompany_transactions' LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def create(
        self,
        org_id: str,
        *,
        source_company_id: str,
        target_company_id: str,
        transaction_type: str,
        amount: float,
        currency: str = "INR",
        source_document_type: str | None = None,
        source_document_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.intercompany_transactions (
                        id, org_id, source_company_id, target_company_id,
                        transaction_type, amount, currency,
                        source_document_type, source_document_id, metadata
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                        %s, %s, %s, %s, %s::uuid, %s::jsonb
                    )
                    RETURNING id::text, status, amount, transaction_type, created_at
                    """,
                    (
                        row_id,
                        org_id,
                        source_company_id,
                        target_company_id,
                        transaction_type,
                        amount,
                        currency,
                        source_document_type,
                        source_document_id,
                        Json(metadata or {}),
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                self._upsert_balance(
                    cur_conn=conn,
                    org_id=org_id,
                    source_company_id=source_company_id,
                    target_company_id=target_company_id,
                    delta=float(amount),
                )
                return {
                    "id": row[0],
                    "status": row[1],
                    "amount": float(row[2]),
                    "transaction_type": row[3],
                    "created_at": row[4],
                }

    def _upsert_balance(
        self,
        *,
        cur_conn,
        org_id: str,
        source_company_id: str,
        target_company_id: str,
        delta: float,
    ) -> None:
        with cur_conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO erp.intercompany_balances (
                    id, org_id, source_company_id, target_company_id, amount
                )
                VALUES (gen_random_uuid(), %s::uuid, %s::uuid, %s::uuid, %s)
                ON CONFLICT (org_id, source_company_id, target_company_id, balance_type)
                DO UPDATE SET amount = erp.intercompany_balances.amount + EXCLUDED.amount,
                              updated_at = now()
                """,
                (org_id, source_company_id, target_company_id, delta),
            )
            cur_conn.commit()

    def list_transactions(
        self,
        org_id: str,
        *,
        source_company_id: str | None = None,
        target_company_id: str | None = None,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        clauses = ["org_id = %s::uuid"]
        params: list[Any] = [org_id]
        if source_company_id:
            clauses.append("source_company_id = %s::uuid")
            params.append(source_company_id)
        if target_company_id:
            clauses.append("target_company_id = %s::uuid")
            params.append(target_company_id)
        if status:
            clauses.append("status = %s")
            params.append(status)
        params.append(limit)
        sql = f"""
            SELECT id::text, source_company_id::text, target_company_id::text,
                   transaction_type, amount, currency, status, created_at
            FROM erp.intercompany_transactions
            WHERE {' AND '.join(clauses)}
            ORDER BY created_at DESC
            LIMIT %s
        """
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def list_balances(self, org_id: str) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT source_company_id::text, target_company_id::text, amount, balance_type, updated_at
                    FROM erp.intercompany_balances
                    WHERE org_id = %s::uuid
                    ORDER BY updated_at DESC
                    """,
                    (org_id,),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]

    def match_pair(self, org_id: str, *, tx_id: str, matched_tx_id: str) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.intercompany_transactions
                    SET status = 'matched', matched_transaction_id = %s::uuid
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status
                    """,
                    (matched_tx_id, org_id, tx_id),
                )
                row = cur.fetchone()
                cur.execute(
                    """
                    UPDATE erp.intercompany_transactions
                    SET status = 'matched', matched_transaction_id = %s::uuid
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (tx_id, org_id, matched_tx_id),
                )
                conn.commit()
                return {"id": row[0], "status": row[1]}


intercompany_repository = IntercompanyRepository()
