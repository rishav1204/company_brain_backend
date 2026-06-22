from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class OwnershipSnapshotRepository:
    def schema_ready(self) -> bool:
        try:
            with get_db_conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='erp' AND table_name='ownership_snapshots' LIMIT 1
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
        subsidiary_company_id: str,
        ownership_percent: float,
        subsidiary_profit: float,
        parent_share: float,
        minority_interest: float,
    ) -> dict[str, Any]:
        row_id = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.ownership_snapshots (
                        id, org_id, consolidation_run_id, subsidiary_company_id,
                        ownership_percent, subsidiary_profit, parent_share, minority_interest
                    )
                    VALUES (
                        %s::uuid, %s::uuid, %s::uuid, %s::uuid,
                        %s, %s, %s, %s
                    )
                    RETURNING id::text, subsidiary_company_id::text
                    """,
                    (
                        row_id,
                        org_id,
                        consolidation_run_id,
                        subsidiary_company_id,
                        ownership_percent,
                        subsidiary_profit,
                        parent_share,
                        minority_interest,
                    ),
                )
                row = cur.fetchone()
                conn.commit()
                return {"id": row[0], "subsidiary_company_id": row[1]}

    def list_for_run(self, org_id: str, consolidation_run_id: str) -> list[dict[str, Any]]:
        if not self.schema_ready():
            return []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT subsidiary_company_id::text, ownership_percent, subsidiary_profit,
                           parent_share, minority_interest
                    FROM erp.ownership_snapshots
                    WHERE org_id = %s::uuid AND consolidation_run_id = %s::uuid
                    ORDER BY created_at ASC
                    """,
                    (org_id, consolidation_run_id),
                )
                cols = [d[0] for d in cur.description]
                return [dict(zip(cols, row)) for row in cur.fetchall()]


ownership_snapshot_repository = OwnershipSnapshotRepository()
