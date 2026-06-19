from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class FiscalPeriodRepository:
    def create(self, org_id: str, **fields) -> dict:
        pid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.fiscal_periods (
                      id, org_id, company_id, fiscal_year_id, period_name, period_number,
                      start_date, end_date, status, is_locked, lock_status
                    ) VALUES (%s::uuid,%s::uuid,%s::uuid,%s::uuid,%s,%s,%s::date,%s::date,'open',false,'open')
                    RETURNING id::text, period_name, start_date::text, end_date::text, lock_status, fiscal_year_id::text
                    """,
                    (
                        pid, org_id, fields.get("company_id"), fields.get("fiscal_year_id"),
                        fields["period_name"], fields.get("period_number"),
                        fields["start_date"], fields["end_date"],
                    ),
                )
                return dict(cur.fetchone() or {"id": pid})

    def list(self, org_id: str, *, fiscal_year_id: str | None = None, company_id: str | None = None, limit: int = 100) -> list[dict]:
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if fiscal_year_id:
            where.append("fiscal_year_id = %s::uuid")
            params.append(fiscal_year_id)
        if company_id:
            where.append("company_id = %s::uuid")
            params.append(company_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, period_name, period_number, start_date::text, end_date::text,
                           status, is_locked, lock_status, fiscal_year_id::text, closed_at::text, closed_by::text
                    FROM erp.fiscal_periods WHERE {' AND '.join(where)}
                    ORDER BY start_date DESC LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def get(self, org_id: str, *, period_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, period_name, period_number, start_date::text, end_date::text,
                           status, is_locked, lock_status, fiscal_year_id::text, company_id::text,
                           closed_at::text, closed_by::text
                    FROM erp.fiscal_periods WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, period_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def find_for_date(self, org_id: str, *, posting_date: str, company_id: str | None = None) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text, period_name, lock_status, status, is_locked, start_date::text, end_date::text
                        FROM erp.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                          AND %s::date BETWEEN start_date AND end_date
                        LIMIT 1
                        """,
                        (org_id, company_id, posting_date),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, period_name, lock_status, status, is_locked, start_date::text, end_date::text
                        FROM erp.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id IS NULL
                          AND %s::date BETWEEN start_date AND end_date
                        LIMIT 1
                        """,
                        (org_id, posting_date),
                    )
                row = cur.fetchone()
                return dict(row) if row else None

    def set_lock_status(
        self,
        org_id: str,
        *,
        period_id: str,
        lock_status: str,
        closed_by: str | None = None,
    ) -> dict:
        legacy_status = "open"
        is_locked = False
        if lock_status == "soft_locked":
            legacy_status = "soft_locked"
            is_locked = True
        elif lock_status == "hard_locked":
            legacy_status = "locked"
            is_locked = True
        elif lock_status == "closed":
            legacy_status = "closed"
            is_locked = True
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.fiscal_periods
                    SET lock_status = %s, status = %s, is_locked = %s,
                        closed_at = CASE WHEN %s = 'closed' THEN NOW() ELSE closed_at END,
                        closed_by = COALESCE(%s::uuid, closed_by)
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, period_name, lock_status, status, is_locked
                    """,
                    (lock_status, legacy_status, is_locked, lock_status, closed_by, org_id, period_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Fiscal period not found")
                return dict(row)


class ChecklistRepository:
    DEFAULT_CHECKS = [
        "bank_reconciliation_complete",
        "vendor_reconciliation_complete",
        "customer_reconciliation_complete",
        "gst_validation_complete",
        "compliance_obligations_complete",
        "tds_returns_filed",
        "pending_journals_reviewed",
        "suspense_accounts_cleared",
    ]

    def seed_for_period(self, org_id: str, *, period_id: str) -> int:
        count = 0
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                for name in self.DEFAULT_CHECKS:
                    cur.execute(
                        """
                        INSERT INTO erp.period_close_checklists (id, org_id, period_id, check_name, status)
                        VALUES (%s::uuid, %s::uuid, %s::uuid, %s, 'pending')
                        ON CONFLICT (org_id, period_id, check_name) DO NOTHING
                        """,
                        (str(uuid4()), org_id, period_id, name),
                    )
                    count += cur.rowcount
        return count

    def list_for_period(self, org_id: str, *, period_id: str) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, check_name, status, completed_by::text, completed_at::text
                    FROM erp.period_close_checklists
                    WHERE org_id = %s::uuid AND period_id = %s::uuid ORDER BY check_name
                    """,
                    (org_id, period_id),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def complete(self, org_id: str, *, period_id: str, check_name: str, completed_by: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.period_close_checklists
                    SET status = 'completed', completed_by = %s::uuid, completed_at = NOW()
                    WHERE org_id = %s::uuid AND period_id = %s::uuid AND check_name = %s
                    RETURNING id::text, check_name, status
                    """,
                    (completed_by, org_id, period_id, check_name),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Checklist item not found")
                return dict(row)

    def all_complete(self, org_id: str, *, period_id: str) -> bool:
        items = self.list_for_period(org_id, period_id=period_id)
        return bool(items) and all(str(i.get("status")) == "completed" for i in items)


class ReopenRepository:
    def create(self, org_id: str, *, period_id: str, reason: str, requested_by: str) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.period_reopen_requests (id, org_id, period_id, reason, requested_by, status)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,%s,%s::uuid,'pending')
                    RETURNING id::text, status
                    """,
                    (rid, org_id, period_id, reason, requested_by),
                )
                return dict(cur.fetchone() or {"id": rid})

    def approve(self, org_id: str, *, request_id: str, approved_by: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.period_reopen_requests
                    SET status = 'approved', approved_by = %s::uuid, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, period_id::text, status
                    """,
                    (approved_by, org_id, request_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Reopen request not found")
                return dict(row)


class YearEndRepository:
    def create(self, org_id: str, *, fiscal_year_id: str, run_by: str | None) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.year_end_runs (id, org_id, fiscal_year_id, status, run_by)
                    VALUES (%s::uuid,%s::uuid,%s::uuid,'pending',%s::uuid)
                    RETURNING id::text, status
                    """,
                    (rid, org_id, fiscal_year_id, run_by),
                )
                return dict(cur.fetchone() or {"id": rid})

    def complete(
        self,
        org_id: str,
        *,
        run_id: str,
        closing_journal_id: str | None,
        closing_batch_id: str | None,
        next_fiscal_year_id: str | None,
    ) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.year_end_runs
                    SET status = 'completed', closing_journal_id = %s::uuid, closing_batch_id = %s::uuid,
                        next_fiscal_year_id = %s::uuid, completed_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, status
                    """,
                    (closing_journal_id, closing_batch_id, next_fiscal_year_id, org_id, run_id),
                )
                row = cur.fetchone()
                if not row:
                    raise ValueError("Year-end run not found")
                return dict(row)


fiscal_period_repository = FiscalPeriodRepository()
checklist_repository = ChecklistRepository()
reopen_repository = ReopenRepository()
year_end_repository = YearEndRepository()
