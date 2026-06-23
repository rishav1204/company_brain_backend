from typing import Any

from app.services.db import get_db_conn, set_rls_org
from app.services.repository_pagination import clamp_limit


class OrganizationRepository:
    def create_organization(
        self,
        name: str,
        slug: str,
        country_code: str = "IN",
        timezone: str = "Asia/Kolkata",
        currency: str = "INR",
        plan: str = "starter",
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.organizations (name, slug, status, country_code, timezone, currency, plan)
                    VALUES (%s, %s, 'active', %s, %s, %s, %s)
                    RETURNING id::text AS id, name, slug, status, country_code, timezone, currency, plan
                    """,
                    (name, slug.strip().lower(), country_code, timezone, currency, plan),
                )
                return cur.fetchone()

    def get_organization(self, org_id: str) -> dict[str, Any] | None:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, name, slug, status, country_code, timezone,
                           currency, plan, created_at, updated_at
                    FROM core.organizations
                    WHERE id = %s::uuid
                    """,
                    (org_id,),
                )
                return cur.fetchone()

    def list_companies(self, org_id: str, limit: int = 500) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, legal_name, gstin, pan, tan, cin,
                           base_currency, financial_year_start, status, created_at
                    FROM core.companies
                    WHERE org_id = %s::uuid
                    ORDER BY legal_name
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return list(cur.fetchall())

    def list_branches(self, org_id: str, company_id: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id:
                    cur.execute(
                        """
                        SELECT id::text AS id, company_id::text AS company_id, org_id::text AS org_id,
                               branch_code, branch_name, state_code, address, created_at
                        FROM core.branches
                        WHERE org_id = %s::uuid AND company_id = %s::uuid
                        ORDER BY branch_code
                        LIMIT %s
                        """,
                        (org_id, company_id, limit),
                    )
                else:
                    cur.execute(
                        """
                        SELECT id::text AS id, company_id::text AS company_id, org_id::text AS org_id,
                               branch_code, branch_name, state_code, address, created_at
                        FROM core.branches
                        WHERE org_id = %s::uuid
                        ORDER BY branch_code
                        LIMIT %s
                        """,
                        (org_id, limit),
                    )
                return list(cur.fetchall())

    def update_organization(
        self,
        org_id: str,
        *,
        name: str | None = None,
        timezone: str | None = None,
        currency: str | None = None,
    ) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        if name is not None:
            sets.append("name = %s")
            params.append(name)
        if timezone is not None:
            sets.append("timezone = %s")
            params.append(timezone)
        if currency is not None:
            sets.append("currency = %s")
            params.append(currency)
        if not sets:
            return self.get_organization(org_id)
        params.append(org_id)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE core.organizations SET {", ".join(sets)}, updated_at = NOW()
                    WHERE id = %s::uuid
                    RETURNING id::text AS id, name, slug, status, country_code, timezone, currency, plan
                    """,
                    tuple(params),
                )
                return cur.fetchone()

    def create_company(
        self,
        org_id: str,
        legal_name: str,
        base_currency: str = "INR",
        financial_year_start: str = "04-01",
        gstin: str | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.companies (org_id, legal_name, base_currency, financial_year_start, gstin, status)
                    VALUES (%s::uuid, %s, %s, %s, %s, 'active')
                    RETURNING id::text AS id, org_id::text AS org_id, legal_name, base_currency, financial_year_start
                    """,
                    (org_id, legal_name, base_currency, financial_year_start, gstin),
                )
                return cur.fetchone()

    def create_branch(
        self,
        org_id: str,
        company_id: str,
        branch_code: str,
        branch_name: str,
        state_code: str | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.branches (org_id, company_id, branch_code, branch_name, state_code)
                    VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                    RETURNING id::text AS id, company_id::text AS company_id, org_id::text AS org_id,
                              branch_code, branch_name
                    """,
                    (org_id, company_id, branch_code, branch_name, state_code),
                )
                return cur.fetchone()

    def update_company(
        self,
        org_id: str,
        company_id: str,
        *,
        legal_name: str | None = None,
        gstin: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        if legal_name is not None:
            sets.append("legal_name = %s")
            params.append(legal_name)
        if gstin is not None:
            sets.append("gstin = %s")
            params.append(gstin)
        if status is not None:
            sets.append("status = %s")
            params.append(status)
        if not sets:
            return None
        params.extend([company_id, org_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE core.companies SET {", ".join(sets)}
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id, org_id::text AS org_id, legal_name, gstin, status
                    """,
                    tuple(params),
                )
                return cur.fetchone()

    def update_branch(
        self,
        org_id: str,
        branch_id: str,
        *,
        branch_name: str | None = None,
        state_code: str | None = None,
    ) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        if branch_name is not None:
            sets.append("branch_name = %s")
            params.append(branch_name)
        if state_code is not None:
            sets.append("state_code = %s")
            params.append(state_code)
        if not sets:
            return None
        params.extend([branch_id, org_id])
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    UPDATE core.branches SET {", ".join(sets)}
                    WHERE id = %s::uuid AND org_id = %s::uuid
                    RETURNING id::text AS id, company_id::text AS company_id, branch_code, branch_name, state_code
                    """,
                    tuple(params),
                )
                return cur.fetchone()

    def list_business_units(self, org_id: str, limit: int = 500) -> list[dict[str, Any]]:
        limit = clamp_limit(limit)
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, org_id::text AS org_id, company_id::text AS company_id,
                           unit_code, unit_name, created_at
                    FROM core.business_units
                    WHERE org_id = %s::uuid
                    ORDER BY unit_code
                    LIMIT %s
                    """,
                    (org_id, limit),
                )
                return list(cur.fetchall())

    def create_business_unit(
        self,
        org_id: str,
        unit_code: str,
        unit_name: str,
        company_id: str | None = None,
    ) -> dict[str, Any]:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO core.business_units (org_id, company_id, unit_code, unit_name)
                    VALUES (%s::uuid, %s::uuid, %s, %s)
                    RETURNING id::text AS id, org_id::text AS org_id, company_id::text AS company_id,
                              unit_code, unit_name
                    """,
                    (org_id, company_id, unit_code, unit_name),
                )
                return cur.fetchone()


organization_repository = OrganizationRepository()
