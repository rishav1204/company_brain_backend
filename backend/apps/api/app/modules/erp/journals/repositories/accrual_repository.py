from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class AccrualRepository:
    def create(
        self,
        org_id: str,
        *,
        accrual_type: str,
        accrual_date: str,
        amount: float,
        source_reference: str | None = None,
        reversal_date: str | None = None,
        journal_id: str | None = None,
        metadata: dict | None = None,
        company_id: str | None = None,
    ) -> dict:
        aid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.accrual_entries (
                      id, org_id, company_id, accrual_type, source_reference,
                      accrual_date, reversal_date, journal_id, amount, metadata
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s, %s::uuid,
                      %s::date, %s::date, %s::uuid, %s::numeric, %s::jsonb
                    )
                    RETURNING id::text, accrual_type, accrual_date::text, reversal_date::text,
                              journal_id::text, amount, metadata, created_at::text
                    """,
                    (
                        aid,
                        org_id,
                        company_id,
                        accrual_type,
                        source_reference,
                        accrual_date,
                        reversal_date,
                        journal_id,
                        amount,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": aid})

    def list(self, org_id: str, *, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, accrual_type, accrual_date::text, reversal_date::text,
                           journal_id::text, amount, metadata, created_at::text
                    FROM erp.accrual_entries
                    WHERE org_id = %s::uuid
                    ORDER BY accrual_date DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def list_due_reversals(self, org_id: str, *, as_of_date: str, limit: int = 500) -> list[dict]:
        limit = max(1, min(int(limit or 500), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, accrual_type, accrual_date::text, reversal_date::text,
                           journal_id::text, amount, metadata, company_id::text
                    FROM erp.accrual_entries
                    WHERE org_id = %s::uuid
                      AND reversal_date IS NOT NULL
                      AND reversal_date <= %s::date
                      AND COALESCE(metadata->>'reversed', 'false') = 'false'
                    ORDER BY reversal_date ASC
                    LIMIT %s
                    """,
                    (org_id, as_of_date, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def mark_reversed(self, org_id: str, *, accrual_id: str, reversal_journal_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.accrual_entries
                    SET metadata = metadata || %s::jsonb
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text
                    """,
                    (
                        Json({"reversed": True, "reversal_journal_id": reversal_journal_id}),
                        org_id,
                        accrual_id,
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": accrual_id}

    def link_journal(self, org_id: str, *, accrual_id: str, journal_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.accrual_entries
                    SET journal_id = %s::uuid
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, journal_id::text
                    """,
                    (journal_id, org_id, accrual_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": accrual_id}


accrual_repository = AccrualRepository()
