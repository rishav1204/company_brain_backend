from __future__ import annotations

from app.services.repository_pagination import clamp_limit

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class RecurringRepository:
    def create(
        self,
        org_id: str,
        *,
        template_name: str,
        frequency: str,
        next_run_date: str,
        journal_template: dict,
        company_id: str | None = None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.recurring_journals (
                      id, org_id, company_id, template_name, frequency, next_run_date,
                      is_active, journal_template
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s::date, true, %s::jsonb)
                    RETURNING id::text, template_name, frequency, next_run_date::text,
                              is_active, journal_template, created_at::text
                    """,
                    (rid, org_id, company_id, template_name, frequency, next_run_date, Json(journal_template)),
                )
                return dict(cur.fetchone() or {"id": rid})

    def list(self, org_id: str, *, active_only: bool = True, limit: int = 100) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if active_only:
                    cur.execute(
                        """
                        SELECT id::text, template_name, frequency, next_run_date::text,
                               is_active, journal_template, created_at::text
                        FROM erp.recurring_journals
                        WHERE org_id = %s::uuid AND is_active = true
                        ORDER BY next_run_date ASC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text, template_name, frequency, next_run_date::text,
                               is_active, journal_template, created_at::text
                        FROM erp.recurring_journals
                        WHERE org_id = %s::uuid
                        ORDER BY created_at DESC
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return [dict(r) for r in (cur.fetchall() or [])]

    def list_due(self, org_id: str, *, as_of_date: str, limit: int = 500) -> list[dict]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, template_name, frequency, next_run_date::text, journal_template
                    FROM erp.recurring_journals
                    WHERE org_id = %s::uuid AND is_active = true AND next_run_date <= %s::date
                    ORDER BY next_run_date ASC
                    LIMIT %s
                    """,
                    (org_id, as_of_date),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def advance_next_run(self, org_id: str, *, recurring_id: str, next_run_date: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.recurring_journals
                    SET next_run_date = %s::date, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, next_run_date::text
                    """,
                    (next_run_date, org_id, recurring_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": recurring_id}

    def deactivate(self, org_id: str, *, recurring_id: str) -> dict:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE erp.recurring_journals
                    SET is_active = false, updated_at = NOW()
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, is_active
                    """,
                    (org_id, recurring_id),
                )
                row = cur.fetchone()
                return dict(row) if row else {"id": recurring_id, "is_active": False}


recurring_repository = RecurringRepository()
