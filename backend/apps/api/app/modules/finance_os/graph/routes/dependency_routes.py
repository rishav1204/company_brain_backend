from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.graph.security.graph_guard import require_graph_read
from app.modules.finance_os.graph.services.dependency_service import dependencies

router = APIRouter(tags=["finance-os-graph-dependency"])


@router.get("/dependencies/{entity_id}")
def get_dependencies(entity_id: str, max_depth: int = 4, context=Depends(build_request_context)) -> dict:
    require_graph_read(context.user)
    return dependencies(context.org_id, entity_id, max_depth=max_depth, trace_id=context.request_id)
