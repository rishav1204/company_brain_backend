from __future__ import annotations

from uuid import uuid4

from psycopg.types.json import Json

from app.services.db import get_db_conn, set_rls_org


class SalaryRunRepository:
    def create(
        self,
        org_id: str,
        *,
        employee_id: str,
        return_period: str,
        gross_salary: float,
        tds_amount: float,
        tds_section: str = "192",
        company_id: str | None = None,
        challan_number: str | None = None,
        payment_date: str | None = None,
        status: str = "calculated",
        metadata: dict | None = None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.payroll_salary_runs (
                      id, org_id, company_id, employee_id, return_period,
                      gross_salary, tds_section, tds_amount, challan_number,
                      payment_date, status, metadata
                    )
                    VALUES (
                      %s::uuid, %s::uuid, %s::uuid, %s::uuid, %s,
                      %s, %s, %s, %s, %s::date, %s, %s::jsonb
                    )
                    RETURNING id::text, employee_id::text, return_period,
                              gross_salary::float8, tds_section, tds_amount::float8,
                              status, company_id::text, payment_date::text, created_at::text
                    """,
                    (
                        rid,
                        org_id,
                        company_id,
                        employee_id,
                        return_period,
                        gross_salary,
                        tds_section,
                        tds_amount,
                        challan_number,
                        payment_date,
                        status,
                        Json(metadata or {}),
                    ),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, run_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT sr.id::text, sr.employee_id::text, sr.return_period,
                           sr.gross_salary::float8, sr.tds_section, sr.tds_amount::float8,
                           sr.status, sr.company_id::text, sr.payment_date::text,
                           sr.challan_number, sr.metadata, sr.created_at::text,
                           e.employee_code, e.pan, e.name AS employee_name
                    FROM erp.payroll_salary_runs sr
                    JOIN erp.payroll_employees e ON e.id = sr.employee_id
                    WHERE sr.org_id = %s::uuid AND sr.id = %s::uuid
                    """,
                    (org_id, run_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        return_period: str | None = None,
        employee_id: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 200), 500))
        where = ["sr.org_id = %s::uuid"]
        params: list = [org_id]
        if return_period:
            where.append("sr.return_period = %s")
            params.append(return_period)
        if employee_id:
            where.append("sr.employee_id = %s::uuid")
            params.append(employee_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT sr.id::text, sr.employee_id::text, sr.return_period,
                           sr.gross_salary::float8, sr.tds_section, sr.tds_amount::float8,
                           sr.status, sr.payment_date::text, sr.created_at::text,
                           e.employee_code, e.pan, e.name AS employee_name
                    FROM erp.payroll_salary_runs sr
                    JOIN erp.payroll_employees e ON e.id = sr.employee_id
                    WHERE {' AND '.join(where)}
                    ORDER BY sr.return_period DESC, e.employee_code ASC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def sum_ytd_tds(self, org_id: str, *, employee_id: str, financial_year: str) -> float:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(SUM(tds_amount), 0)::float8 AS total
                    FROM erp.payroll_salary_runs
                    WHERE org_id = %s::uuid AND employee_id = %s::uuid
                      AND return_period LIKE %s
                    """,
                    (org_id, employee_id, f"{financial_year}%"),
                )
                row = cur.fetchone()
                return float((row or {}).get("total") or 0)


salary_run_repository = SalaryRunRepository()
