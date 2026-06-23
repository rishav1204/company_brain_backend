from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org

MUTABLE_STATUSES = {"draft", "pending_approval", "approved"}
IMMUTABLE_STATUSES = {"posted", "reversed", "cancelled"}


class JournalRepository:
    def create(
        self,
        org_id: str,
        *,
        journal_number: str,
        journal_type: str,
        posting_date: str,
        description: str | None,
        source_type: str | None,
        source_id: str | None,
        currency_code: str,
        exchange_rate: float,
        created_by: str | None,
        company_id: str | None = None,
        idempotency_key: str | None = None,
        ai_confidence: dict | None = None,
    ) -> dict:
        jid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.journals (
                      id, org_id, company_id, journal_number, journal_type, journal_status,
                      posting_date, description, source_type, source_id,
                      currency_code, exchange_rate, created_by, idempotency_key, ai_confidence
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s, %s, 'draft',
                      %s::date, %s, %s, %s::uuid,
                      %s, %s::numeric, %s::uuid, %s, %s::jsonb
                    )
                    RETURNING id::text, journal_number, journal_type, journal_status,
                              posting_date::text, description, source_type, source_id::text,
                              currency_code, exchange_rate::float8, created_by::text,
                              idempotency_key, ai_confidence, created_at::text
                    """,
                    (
                        jid,
                        org_id,
                        company_id,
                        journal_number,
                        journal_type,
                        posting_date,
                        description,
                        source_type,
                        source_id,
                        currency_code,
                        exchange_rate,
                        created_by,
                        idempotency_key,
                        Json(ai_confidence or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": jid})

    def create_conn(
        self,
        conn,
        org_id: str,
        *,
        journal_number: str,
        journal_type: str,
        posting_date: str,
        description: str | None,
        source_type: str | None,
        source_id: str | None,
        currency_code: str,
        exchange_rate: float,
        created_by: str | None,
        company_id: str | None = None,
        idempotency_key: str | None = None,
        ai_confidence: dict | None = None,
    ) -> dict:
        jid = str(uuid4())
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO erp.journals (
                  id, org_id, company_id, journal_number, journal_type, journal_status,
                  posting_date, description, source_type, source_id,
                  currency_code, exchange_rate, created_by, idempotency_key, ai_confidence
                )
                VALUES (
                  %s::uuid, %s::uuid, %s::uuid, %s, %s, 'draft',
                  %s::date, %s, %s, %s::uuid,
                  %s, %s::numeric, %s::uuid, %s, %s::jsonb
                )
                RETURNING id::text, journal_number, journal_type, journal_status,
                          posting_date::text, description, source_type, source_id::text,
                          currency_code, exchange_rate::float8, created_by::text,
                          idempotency_key, ai_confidence, created_at::text
                """,
                (
                    jid,
                    org_id,
                    company_id,
                    journal_number,
                    journal_type,
                    posting_date,
                    description,
                    source_type,
                    source_id,
                    currency_code,
                    exchange_rate,
                    created_by,
                    idempotency_key,
                    Json(ai_confidence or {}),
                ),
            )
            return dict(cur.fetchone() or {"id": jid})

    def get(self, org_id: str, *, journal_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, journal_number, journal_type, journal_status,
                           posting_date::text, description, source_type, source_id::text,
                           currency_code, exchange_rate::float8,
                           created_by::text, approved_by::text, posted_by::text,
                           ledger_batch_id::text, idempotency_key, ai_confidence,
                           company_id::text, created_at::text, updated_at::text, posted_at::text
                    FROM erp.journals
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, journal_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_by_idempotency(self, org_id: str, *, idempotency_key: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, journal_number, journal_status, ledger_batch_id::text
                    FROM erp.journals
                    WHERE org_id = %s::uuid AND idempotency_key = %s
                    LIMIT 1
                    """,
                    (org_id, idempotency_key),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        journal_status: str | None = None,
        journal_type: str | None = None,
        company_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 100), 200))
        offset = max(0, int(offset or 0))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if journal_status:
            where.append("journal_status = %s")
            params.append(journal_status)
        if journal_type:
            where.append("journal_type = %s")
            params.append(journal_type)
        if company_id:
            where.append("company_id = %s::uuid")
            params.append(company_id)
        sql = f"""
            SELECT id::text, journal_number, journal_type, journal_status,
                   posting_date::text, description, source_type, source_id::text,
                   company_id::text, branch_id::text,
                   created_by::text, approved_by::text, posted_at::text, created_at::text
            FROM erp.journals
            WHERE {' AND '.join(where)}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                return [dict(r) for r in (cur.fetchall() or [])]

    def update_draft(
        self,
        org_id: str,
        *,
        journal_id: str,
        posting_date: str | None = None,
        description: str | None = None,
        journal_type: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.journals
                    SET posting_date = COALESCE(%s::date, posting_date),
                        description = COALESCE(%s, description),
                        journal_type = COALESCE(%s, journal_type),
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                      AND journal_status IN ('draft', 'pending_approval')
                    RETURNING id::text, journal_status, posting_date::text, description, journal_type
                    """,
                    (posting_date, description, journal_type, org_id, journal_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Journal not found or not editable")
                return dict(row)

    def set_status(
        self,
        org_id: str,
        *,
        journal_id: str,
        journal_status: str,
        approved_by: str | None = None,
        posted_by: str | None = None,
        ledger_batch_id: str | None = None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            return self.set_status_conn(
                conn,
                org_id,
                journal_id=journal_id,
                journal_status=journal_status,
                approved_by=approved_by,
                posted_by=posted_by,
                ledger_batch_id=ledger_batch_id,
            )

    def set_status_conn(
        self,
        conn,
        org_id: str,
        *,
        journal_id: str,
        journal_status: str,
        approved_by: str | None = None,
        posted_by: str | None = None,
        ledger_batch_id: str | None = None,
    ) -> dict:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE erp.journals
                SET journal_status = %s,
                    approved_by = COALESCE(%s::uuid, approved_by),
                    posted_by = COALESCE(%s::uuid, posted_by),
                    ledger_batch_id = COALESCE(%s::uuid, ledger_batch_id),
                    posted_at = CASE WHEN %s = 'posted' THEN NOW() ELSE posted_at END,
                    updated_at = NOW()
                WHERE org_id = %s::uuid AND id = %s::uuid
                  AND (
                    journal_status NOT IN ('posted', 'reversed', 'cancelled')
                    OR (%s = 'reversed' AND journal_status = 'posted')
                    OR (%s = 'posted' AND journal_status = 'approved')
                  )
                RETURNING id::text, journal_status, approved_by::text, posted_by::text,
                          ledger_batch_id::text, posted_at::text
                """,
                (
                    journal_status,
                    approved_by,
                    posted_by,
                    ledger_batch_id,
                    journal_status,
                    org_id,
                    journal_id,
                    journal_status,
                    journal_status,
                ),
            )
            row = cur.fetchone()
            if not row:
                raise ValueError("Journal not found or not postable")
            return dict(row)

    def get_conn(self, conn, org_id: str, *, journal_id: str) -> dict | None:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id::text, journal_number, journal_type, journal_status,
                       posting_date::text, description, source_type, source_id::text,
                       currency_code, exchange_rate::float8,
                       created_by::text, approved_by::text, posted_by::text,
                       ledger_batch_id::text, idempotency_key, ai_confidence,
                       company_id::text, created_at::text, updated_at::text, posted_at::text
                FROM erp.journals
                WHERE org_id = %s::uuid AND id = %s::uuid
                FOR UPDATE
                """,
                (org_id, journal_id),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def clear_ai_review_flag(self, org_id: str, *, journal_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.journals
                    SET ai_confidence = ai_confidence || '{"requires_review": false, "reviewed_at": true}'::jsonb,
                        updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                      AND journal_status IN ('draft', 'pending_approval')
                    """,
                    (org_id, journal_id),
                )


journal_repository = JournalRepository()
