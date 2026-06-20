from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.graph.security.graph_guard import require_graph_read
from app.modules.finance_os.graph.services.lineage_service import lineage

router = APIRouter(tags=["finance-os-graph-lineage"])


@router.get("/lineage/{entity_id}")
def get_lineage(
    entity_id: str,
    direction: str = "both",
    max_depth: int = 6,
    context=Depends(build_request_context),
) -> dict:
    require_graph_read(context.user)
    return lineage(context.org_id, entity_id, direction=direction, max_depth=max_depth, trace_id=context.request_id)
