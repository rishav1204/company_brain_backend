from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.graph.security.graph_guard import require_graph_read
from app.modules.finance_os.graph.services.visualization_service import visualization

router = APIRouter(tags=["finance-os-graph-visualization"])


@router.get("/visualization/{entity_id}")
def get_visualization(entity_id: str, context=Depends(build_request_context)) -> dict:
    require_graph_read(context.user)
    return visualization(context.org_id, entity_id)
