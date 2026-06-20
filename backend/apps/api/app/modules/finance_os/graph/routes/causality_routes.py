from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.graph.security.graph_guard import require_graph_read
from app.modules.finance_os.graph.services.causality_service import root_cause

router = APIRouter(tags=["finance-os-graph-causality"])


@router.get("/root-cause/{entity_id}")
def get_root_cause(entity_id: str, context=Depends(build_request_context)) -> dict:
    require_graph_read(context.user)
    return root_cause(context.org_id, entity_id, trace_id=context.request_id)
