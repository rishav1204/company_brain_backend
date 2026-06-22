from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.erp.consolidation.security.consolidation_guard import require_consolidation_read
from app.modules.erp.consolidation.services.elimination_service import elimination_service

router = APIRouter(tags=["consolidation-eliminations"])


@router.get("/consolidation/runs/{run_id}/eliminations")
def list_eliminations(run_id: str, context=Depends(build_request_context)) -> dict:
    require_consolidation_read(context)
    items = elimination_service.list_for_run(context.org_id, run_id)
    return {"request_id": context.request_id, "items": items}
