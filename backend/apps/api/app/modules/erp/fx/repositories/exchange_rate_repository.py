from __future__ import annotations

from uuid import uuid4

from app.services.db import get_db_conn, set_rls_org


class ExchangeRateRepository:
    def create(
        self,
        org_id: str,
        *,
        from_currency: str,
        to_currency: str,
        rate: float,
        rate_date: str,
        source: str = "manual",
        company_id: str | None = None,
    ) -> dict:
        rid = str(uuid4())
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO erp.exchange_rates (
                      id, org_id, company_id, from_currency, to_currency, rate, rate_date, source
                    )
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s::date, %s)
                    ON CONFLICT (org_id, from_currency, to_currency, rate_date) DO UPDATE
                      SET rate = EXCLUDED.rate, source = EXCLUDED.source, company_id = EXCLUDED.company_id
                    RETURNING id::text, from_currency, to_currency, rate::float8, rate_date::text,
                              source, company_id::text, created_at::text
                    """,
                    (rid, org_id, company_id, from_currency.upper(), to_currency.upper(), rate, rate_date, source),
                )
                return dict(cur.fetchone() or {"id": rid})

    def get(self, org_id: str, *, rate_id: str) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text, from_currency, to_currency, rate::float8, rate_date::text,
                           source, company_id::text, created_at::text
                    FROM erp.exchange_rates
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    """,
                    (org_id, rate_id),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def get_rate_for_date(
        self,
        org_id: str,
        *,
        from_currency: str,
        to_currency: str = "INR",
        rate_date: str,
        company_id: str | None = None,
    ) -> dict | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                params: list = [org_id, from_currency.upper(), to_currency.upper(), rate_date]
                company_clause = ""
                if company_id:
                    company_clause = "AND (company_id IS NULL OR company_id = %s::uuid)"
                    params.append(company_id)
                cur.execute(
                    f"""
                    SELECT id::text, from_currency, to_currency, rate::float8, rate_date::text, source
                    FROM erp.exchange_rates
                    WHERE org_id = %s::uuid
                      AND from_currency = %s AND to_currency = %s
                      AND rate_date <= %s::date
                      {company_clause}
                    ORDER BY rate_date DESC
                    LIMIT 1
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def list(
        self,
        org_id: str,
        *,
        from_currency: str | None = None,
        to_currency: str | None = None,
        company_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        limit = max(1, min(int(limit or 100), 500))
        where = ["org_id = %s::uuid"]
        params: list = [org_id]
        if from_currency:
            where.append("from_currency = %s")
            params.append(from_currency.upper())
        if to_currency:
            where.append("to_currency = %s")
            params.append(to_currency.upper())
        if company_id:
            where.append("(company_id IS NULL OR company_id = %s::uuid)")
            params.append(company_id)
        params.append(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id::text, from_currency, to_currency, rate::float8, rate_date::text,
                           source, company_id::text, created_at::text
                    FROM erp.exchange_rates
                    WHERE {' AND '.join(where)}
                    ORDER BY rate_date DESC, created_at DESC
                    LIMIT %s
                    """,
                    tuple(params),
                )
                return [dict(r) for r in (cur.fetchall() or [])]

    def update(
        self,
        org_id: str,
        *,
        rate_id: str,
        rate: float | None = None,
        source: str | None = None,
    ) -> dict | None:
        sets: list[str] = []
        params: list = []
        if rate is not None:
            sets.append("rate = %s")
            params.append(rate)
        if source is not None:
            sets.append("source = %s")
            params.append(source)
        if not sets:
            return self.get(org_id, rate_id=rate_id)
        params.extend([org_id, rate_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE erp.exchange_rates
                    SET {', '.join(sets)}
                    WHERE org_id = %s::uuid AND id = %s::uuid
                    RETURNING id::text, from_currency, to_currency, rate::float8, rate_date::text,
                              source, company_id::text, created_at::text
                    """,
                    tuple(params),
                )
                row = cur.fetchone()
                return dict(row) if row else None

    def delete(self, org_id: str, *, rate_id: str) -> bool:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM erp.exchange_rates WHERE org_id = %s::uuid AND id = %s::uuid",
                    (org_id, rate_id),
                )
                return cur.rowcount > 0


exchange_rate_repository = ExchangeRateRepository()
