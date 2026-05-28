from app.services.db import get_db_conn, set_rls_org


def is_fiscal_period_open(org_id: str, company_id: str | None = None, period_key: str | None = None) -> bool:
    if not org_id:
        return True
    try:
        with get_db_conn() as conn:
            set_rls_org(conn, org_id)
            with conn.cursor() as cur:
                if company_id and period_key:
                    cur.execute(
                        """
                        SELECT status FROM core.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id = %s::uuid AND period_key = %s
                        LIMIT 1
                        """,
                        (org_id, company_id, period_key),
                    )
                elif company_id:
                    cur.execute(
                        """
                        SELECT status FROM core.fiscal_periods
                        WHERE org_id = %s::uuid AND company_id = %s::uuid AND status = 'open'
                        LIMIT 1
                        """,
                        (org_id, company_id),
                    )
                else:
                    cur.execute(
                        """
                        SELECT status FROM core.fiscal_periods
                        WHERE org_id = %s::uuid AND status = 'open'
                        LIMIT 1
                        """,
                        (org_id,),
                    )
                row = cur.fetchone()
                if not row:
                    return True
                return str(row.get("status", "")).lower() == "open"
    except Exception:
        return True
