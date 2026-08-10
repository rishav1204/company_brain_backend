from __future__ import annotations


def validate_close_readiness(org_id: str, *, period_id: str, final: bool = False) -> None:
    from app.modules.erp.fiscal.repositories.fiscal_period_repository import checklist_repository
    from app.modules.erp.gl.services.trial_balance_service import trial_balance_service

    if not checklist_repository.all_complete(org_id, period_id=period_id):
        raise ValueError("Close checklist incomplete")
    from app.modules.erp.compliance.repositories.compliance_repository import compliance_obligation_repository

    overdue = compliance_obligation_repository.count_overdue_critical(org_id)
    if overdue > 0:
        raise ValueError(f"{overdue} critical overdue compliance obligations block period close")

    if final:
        tb = trial_balance_service.generate(org_id, fiscal_period_id=period_id)
        if not tb.get("balanced"):
            raise ValueError("Trial balance not balanced for period close")
        _check_unposted_journals(org_id)


def _check_unposted_journals(org_id: str) -> None:
    from app.services.db import get_db_conn, set_rls_org

    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt FROM erp.journals
                WHERE org_id = %s::uuid AND journal_status IN ('approved', 'pending_approval')
                """,
                (org_id,),
            )
            cnt = int((cur.fetchone() or {}).get("cnt") or 0)
            if cnt > 0:
                raise ValueError(f"{cnt} unposted journals remain")
