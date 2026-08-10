from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class FxRevaluationRepository:
    def create(
        self,
        org_id: str,
        *,
        company_id: str | None,
        fiscal_period_id: str | None,
        revaluation_date: str,
        total_unrealized_gain: float,
        total_unrealized_loss: float,
        journal_id: str | None = None,
        details: dict | None = None,
        status: str = "completed",
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.fx_revaluation_runs (
                      id, org_id, company_id, fiscal_period_id, revaluation_date, status,
                      total_unrealized_gain, total_unrealized_loss, journal_id, details
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s::date, %s,
                      %s, %s, %s::uuid, %s::jsonb
                    )
                    RETURNING id::text, revaluation_date::text, status,
                              total_unrealized_gain::float8, total_unrealized_loss::float8,
                              journal_id::text, company_id::text, fiscal_period_id::text, created_at::text
                    """,
                    (
                        rid,
                        org_id,
                        company_id,
                        fiscal_period_id,
                        revaluation_date,
                        status,
                        total_unrealized_gain,
                        total_unrealized_loss,
                        journal_id,
                        Json(details or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, run_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, revaluation_date::text, status,
                           total_unrealized_gain::float8, total_unrealized_loss::float8,
                           journal_id::text, company_id::text, fiscal_period_id::text,
                           details, created_at::text
                    FROM erp.fx_revaluation_runs
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(self, org_id: str, *, limit: int = 50) -> list[dict]:
        limit = max(1, min(int(limit or 50), 200))
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, revaluation_date::text, status,
                           total_unrealized_gain::float8, total_unrealized_loss::float8,
                           journal_id::text, company_id::text, fiscal_period_id::text, created_at::text
                    FROM erp.fx_revaluation_runs
                    WHERE org_id = %s::uuid
                    ORDER BY revaluation_date DESC, created_at DESC
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return [dict(r) for r in (cur.fetchall() or [])]


fx_revaluation_repository = FxRevaluationRepository()
