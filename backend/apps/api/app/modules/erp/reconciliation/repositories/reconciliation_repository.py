from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class ReconciliationRepository:
    def create(
        self,
        org_id: str,
        *,
        bank_transaction_id: str,
        ledger_entry_id: str | None,
        match_type: str,
        confidence_score: float,
        status: str,
        matched_entity_type: str | None = None,
        matched_entity_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.bank_reconciliations (
                      id, org_id, bank_transaction_id, ledger_entry_id,
                      match_type, confidence_score, status,
                      matched_entity_type, matched_entity_id, metadata
                    )
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s::numeric,%s,%s,%s::uuid,%s::jsonb)
                    RETURNING id::text, bank_transaction_id::text, confidence_score, status
                    """,
                    (
                        rid, org_id, bank_transaction_id, ledger_entry_id,
                        match_type, confidence_score, status,
                        matched_entity_type, matched_entity_id, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, reconciliation_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, bank_transaction_id::text, ledger_entry_id::text,
                           match_type, confidence_score, status, approved_by::text,
                           matched_entity_type, matched_entity_id::text,
                           metadata, created_at::text, approved_at::text
                    FROM erp.bank_reconciliations
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, reconciliation_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        status: str | None = None,
        bank_transaction_id: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        limit = max(1, min(limit, 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if status:
            where.append("status = %s")
            params.append(status)
        if bank_transaction_id:
            where.append("bank_transaction_id = %s::uuid")
            params.append(bank_transaction_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, bank_transaction_id::text, ledger_entry_id::text,
                           match_type, confidence_score, status,
                           matched_entity_type, matched_entity_id::text, created_at::text
                    FROM erp.bank_reconciliations
                    WHERE {' AND '.join(where)}
                    ORDER BY confidence_score DESC, created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def set_status(self, org_id: str, *, reconciliation_id: str, status: str, **kwargs) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.bank_reconciliations
                    SET status = %s, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status
                    """,
                    (status, org_id, reconciliation_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Reconciliation not found")
                return dict(row)

    def approve(
        self,
        org_id: str,
        *,
        reconciliation_id: str,
        approved_by: str,
        ledger_entry_id: str | None = None,
        status: str = "matched",
        match_type: str = "matched",
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.bank_reconciliations
                    SET status = %s, match_type = %s, approved_by = %s::uuid,
                        approved_at = NOW(),
                        ledger_entry_id = COALESCE(%s::uuid, ledger_entry_id), updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, bank_transaction_id::text, ledger_entry_id::text,
                              status, matched_entity_type, matched_entity_id::text
                    """,
                    (status, match_type, approved_by, ledger_entry_id, org_id, reconciliation_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Reconciliation not found")
                return dict(row)

    def reject(self, org_id: str, *, reconciliation_id: str) -> dict:
        return self.set_status(org_id, reconciliation_id=reconciliation_id, status="rejected")


reconciliation_repository = ReconciliationRepository()
