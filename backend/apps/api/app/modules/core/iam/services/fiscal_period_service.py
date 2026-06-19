from app.services.db import get_db_conn, set_rls_org


def is_fiscal_period_open(org_id: str, company_id: str | None = None, period_key: str | None = None) -> bool:
    """Date-aware fiscal check against erp.fiscal_periods (canonical M12)."""
    if not org_id:
        return True
    try:
        from datetime import date

        from app.modules.erp.fiscal.services.posting_validation_service import posting_validation_service

        posting_date = date.today().isoformat()
        if period_key and len(period_key) >= 7:
            posting_date = f"{period_key[:7]}-01"
        return posting_validation_service.is_period_open_for_date(org_id, posting_date, company_id=company_id)
    except Exception:
        try:
            with get_db_conn() as conn:
                set_rls_org(conn, org_id)
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT status FROM core.fiscal_periods WHERE org_id = %s::uuid AND status = 'open' LIMIT 1",
                        (org_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return True
                    return str(row.get("status", "")).lower() == "open"
        except Exception:
            return True
