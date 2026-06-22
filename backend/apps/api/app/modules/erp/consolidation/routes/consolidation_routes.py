from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.modules.erp.consolidation.security.consolidation_guard import (
    require_consolidation_read,
    require_consolidation_run,
)
from app.modules.erp.consolidation.services.consolidation_service import consolidation_service
from app.modules.erp.consolidation.services.elimination_service import elimination_service
from app.services.db import get_db_conn, set_rls_org

router = APIRouter(tags=["consolidation-runs"])


class ConsolidationRunRequest(BaseModel):
    group_company_id: str
    fiscal_period_id: str
    company_ids: list[str] | None = None
    dry_run: bool = False


@router.post("/consolidation/run")
def run_consolidation(request: ConsolidationRunRequest, context=Depends(build_request_context)) -> dict:
    require_consolidation_run(context, company_id=request.group_company_id)
    if not request.dry_run:
        from app.modules.platform.governance.engine.policy_engine import evaluate

        policy = evaluate(
            context.org_id,
            action="consolidation.run",
            attrs={"group_company_id": request.group_company_id},
            roles=context.roles or [],
            actor_user_id=context.user_id,
            dry_run=True,
        )
        if not policy.allowed:
            raise HTTPException(status_code=403, detail=policy.reason or "policy_denied")
    result = consolidation_service.run(
        context.org_id,
        group_company_id=request.group_company_id,
        fiscal_period_id=request.fiscal_period_id,
        company_ids=request.company_ids,
        actor_user_id=context.user_id,
        dry_run=request.dry_run,
    )
    if result.status == "failed":
        raise HTTPException(status_code=400, detail=result.error or "consolidation_failed")
    return {
        "request_id": context.request_id,
        "run_id": result.run_id,
        "status": result.status,
        "eliminations": result.eliminations,
        "consolidated_rows": result.consolidated_rows,
        "ownership_snapshots": result.ownership_snapshots,
    }


@router.get("/consolidation/runs")
def list_runs(context=Depends(build_request_context), limit: int = Query(default=50, ge=1, le=200)) -> dict:
    require_consolidation_read(context)
    items = consolidation_service.list_runs(context.org_id, limit=limit)
    return {"request_id": context.request_id, "items": items}


@router.get("/consolidation/runs/{run_id}")
def get_run(run_id: str, context=Depends(build_request_context)) -> dict:
    require_consolidation_read(context)
    item = consolidation_service.get_run(context.org_id, run_id)
    if not item:
        raise HTTPException(status_code=404, detail="Run not found")
    eliminations = elimination_service.list_for_run(context.org_id, run_id)
    return {"request_id": context.request_id, "item": item, "eliminations": eliminations}


@router.get("/consolidation/runs/{run_id}/reports/trial-balance")
def consolidated_trial_balance(run_id: str, context=Depends(build_request_context)) -> dict:
    require_consolidation_read(context)
    with get_db_conn() as conn:
        set_rls_org(conn, context.org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT account_id::text, account_code, account_name,
                       debit_total, credit_total, balance
                FROM erp_reporting.consolidated_trial_balance_mv
                WHERE org_id = %s::uuid AND consolidation_run_id = %s::uuid
                ORDER BY account_code
                """,
                (context.org_id, run_id),
            )
            cols = [d[0] for d in cur.description]
            items = [dict(zip(cols, row)) for row in cur.fetchall()]
    return {"request_id": context.request_id, "items": items}


@router.get("/reports/entity/{company_id}/trial-balance")
def entity_trial_balance(
    company_id: str,
    context=Depends(build_request_context),
    fiscal_period_id: str = Query(...),
) -> dict:
    require_consolidation_read(context)
    from app.modules.erp.consolidation.engine.reporting_engine import aggregate_entity_trial_balance

    items = aggregate_entity_trial_balance(
        context.org_id, fiscal_period_id=fiscal_period_id, company_id=company_id
    )
    return {"request_id": context.request_id, "items": items}
