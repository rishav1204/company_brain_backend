from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class MatchLineRepository:
    def create_batch(self, org_id: str, lines: list[dict]) -> list[dict]:
        created: list[dict] = []
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                for line in lines:
                    lid = str(uuid4())
                    cur.execute(
                        """
                        INSERT INTO erp.reconciliation_match_lines (
                          id, org_id, reconciliation_id, bank_transaction_id,
                          entity_type, entity_id, allocated_amount, remaining_amount,
                          match_group_id, metadata
                        )
                        VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s::uuid,%s,%s,%s::uuid,%s::jsonb)
                        RETURNING id::text
                        """,
                        (
                            lid, org_id, line["reconciliation_id"],
                            line.get("bank_transaction_id"), line["entity_type"], line["entity_id"],
                            line["allocated_amount"], line["remaining_amount"],
                            line.get("match_group_id"), Json(line.get("metadata") or {}),
                        ),
                    )
                    created.append(dict(cur.fetchone() or {"id": lid}))
        return created

    def list_for_reconciliation(self, org_id: str, *, reconciliation_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, entity_type, entity_id::text, allocated_amount, remaining_amount,
                           match_group_id::text, bank_transaction_id::text
                    FROM erp.reconciliation_match_lines
                    WHERE org_id = %s::uuid AND reconciliation_id = %s::uuid
                    ORDER BY created_at
                    """,
                    (org_id, reconciliation_id),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


match_line_repository = MatchLineRepository()
