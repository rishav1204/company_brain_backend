from __future__ import annotations

from app.modules.erp.consolidation.services.consolidation_service import consolidation_service


def run_consolidation_job(org_id: str, *, group_company_id: str, fiscal_period_id: str, actor_user_id: str) -> dict:
    result = consolidation_service.run(
        org_id,
        group_company_id=group_company_id,
        fiscal_period_id=fiscal_period_id,
        actor_user_id=actor_user_id,
    )
    return {
        "run_id": result.run_id,
        "status": result.status,
        "error": result.error,
        "consolidated_rows": result.consolidated_rows,
    }
