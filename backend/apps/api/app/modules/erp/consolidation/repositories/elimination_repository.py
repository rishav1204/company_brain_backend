from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from typing import Any
from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class EliminationRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='erp' AND table_name='elimination_entries' LIMIT 1
                        """
                    )
                    return cur.fetchone() is not None
        except Exception:
            return False

    def record(
        self,
        org_id: str,
        *,
        consolidation_run_id: str,
        elimination_type: str,
        source_company_id: str | None = None,
        target_company_id: str | None = None,
        account_id: str | None = None,
        debit_amount: float = 0,
        credit_amount: float = 0,
        journal_id: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.elimination_entries (
                        id, org_id, consolidation_run_id, elimination_type,
                        source_company_id, target_company_id, account_id,
                        debit_amount, credit_amount, journal_id, description
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s,
                        %s::uuid, %s::uuid, %s::uuid,
                        %s, %s, %s::uuid, %s
                    )
                    RETURNING id::text, elimination_type, debit_amount, credit_amount
                    """,
                    (
                        row_id,
                        org_id,
                        consolidation_run_id,
                        elimination_type,
                        source_company_id,
                        target_company_id,
                        account_id,
                        debit_amount,
                        credit_amount,
                        journal_id,
                        description,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return {
                    "id": row[0],
                    "elimination_type": row[1],
                    "debit_amount": float(row[2]),
                    "credit_amount": float(row[3]),
                }

    def list_for_run(self, org_id: str, consolidation_run_id: str, limit: int = 500) -> list[dict[str, Any]]:
        if not self.schema_ready():
            limit = clamp_limit(limit)
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, elimination_type, source_company_id::text, target_company_id::text,
                           debit_amount, credit_amount, description, journal_id::text
                    FROM erp.elimination_entries
                    WHERE org_id = %s::uuid AND consolidation_run_id = %s::uuid
                    ORDER BY created_at ASC
                    LIMIT %s
                    """,
                    (org_id, consolidation_run_id),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]


elimination_repository = EliminationRepository()
