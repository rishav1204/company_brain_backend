from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class VoucherRepository:
    def create(
        self,
        org_id: str,
        *,
        voucher_number: str,
        voucher_type: str,
        voucher_date: str,
        total_amount: float,
        narration: str | None,
        company_id: str | None,
        branch_id: str | None,
        reference_type: str | None,
        reference_id: str | None,
        source_module: str | None,
        created_by: str | None,
        idempotency_key: str | None,
        metadata: dict | None,
    ) -> dict:
        vid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.vouchers (
                      id, org_id, company_id, branch_id, voucher_number, voucher_type, voucher_date,
                      status, total_amount, narration, reference_type, reference_id, source_module,
                      created_by, idempotency_key, metadata
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s, %s, %s::date,
                      'draft', %s::numeric, %s, %s, %s::uuid, %s,
                      %s::uuid, %s, %s::jsonb
                    )
                    RETURNING id::text, voucher_number, voucher_type, voucher_date::text, status,
                              total_amount::float8, narration, journal_id::text, reference_type,
                              reference_id::text, source_module, created_by::text, created_at::text
                    """,
                    (
                        vid, org_id, company_id, branch_id, voucher_number, voucher_type, voucher_date,
                        total_amount, narration, reference_type, reference_id, source_module,
                        created_by, idempotency_key, Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": vid})

    def get_by_idempotency(self, org_id: str, *, idempotency_key: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text FROM erp.vouchers
                    WHERE org_id = %s::uuid AND idempotency_key = %s LIMIT 1
                    """,
                    (org_id, idempotency_key),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get(self, org_id: str, *, voucher_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, org_id::text, company_id::text, branch_id::text, voucher_number,
                           voucher_type, voucher_date::text, status, journal_id::text, workflow_id::text,
                           total_amount::float8, narration, reference_type, reference_id::text,
                           source_module, reversal_of_voucher_id::text, idempotency_key, metadata,
                           created_by::text, approved_by::text, posted_by::text,
                           created_at::text, updated_at::text, approved_at::text, posted_at::text
                    FROM erp.vouchers
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, voucher_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        voucher_type: str | None = None,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        offset = max(0, int(offset or 0))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if voucher_type:
            where.append("voucher_type = %s")
            params.append(voucher_type)
        if status:
            where.append("status = %s")
            params.append(status)
        params.extend([limit, offset])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, voucher_number, voucher_type, voucher_date::text, status,
                           total_amount::float8, journal_id::text, reference_type, source_module,
                           created_at::text
                    FROM erp.vouchers
                    WHERE {' AND '.join(where)}
                    ORDER BY voucher_date DESC, created_at DESC
                    LIMIT %s OFFSET %s
                    """,
                    params,
                )
                return [dict(r) for r in cur.fetchall()]

    def set_status(
        self,
        org_id: str,
        *,
        voucher_id: str,
        status: str,
        journal_id: str | None = None,
        workflow_id: str | None = None,
        approved_by: str | None = None,
        posted_by: str | None = None,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.vouchers
                    SET status = %s,
                        journal_id = COALESCE(%s::uuid, journal_id),
                        workflow_id = COALESCE(%s::uuid, workflow_id),
                        approved_by = COALESCE(%s::uuid, approved_by),
                        posted_by = COALESCE(%s::uuid, posted_by),
                        approved_at = CASE WHEN %s IS NOT NULL AND approved_at IS NULL THEN now() ELSE approved_at END,
                        posted_at = CASE WHEN %s IS NOT NULL AND posted_at IS NULL THEN now() ELSE posted_at END,
                        updated_at = now()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status, journal_id::text
                    """,
                    (
                        status, journal_id, workflow_id, approved_by, posted_by,
                        approved_by, posted_by, org_id, voucher_id,
                    ),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def link_journal(self, org_id: str, *, voucher_id: str, journal_id: str) -> None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.vouchers SET journal_id = %s::uuid, status = 'journal_generated', updated_at = now()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (journal_id, org_id, voucher_id),
                )
                cur.execute(
                    """
                    UPDATE erp.journals SET voucher_id = %s::uuid, updated_at = now()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (voucher_id, org_id, journal_id),
                )


voucher_repository = VoucherRepository()
