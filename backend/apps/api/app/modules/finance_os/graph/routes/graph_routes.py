from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.graph.schemas.graph_schema import GraphCopilotRequest, GraphCopilotResponse, GraphSearchResponse
from app.modules.finance_os.graph.security.graph_guard import require_graph_read, require_graph_write
from app.modules.finance_os.graph.services.finance_graph_service import get_entity
from app.modules.finance_os.graph.services.graph_search_service import search
from app.modules.finance_os.graph.services.graph_projection_service import rebuild_org
from app.modules.finance_os.graph.ai.graph_copilot import answer as copilot_answer
from app.modules.finance_os.graph.pipelines.graph_ingestion_pipeline import graph_ingestion_pipeline
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-graph"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "finance_os.graph"}


@router.get("/entity/{entity_id}")
def entity_graph(entity_id: str, context=Depends(build_request_context)) -> dict:
    require_graph_read(context.user)
    result = get_entity(context.org_id, entity_id)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="graph.query.entity",
        object_ref=f"graph:{entity_id}",
        payload_jsonb={"count": result.get("count")},
    )
    return result


@router.get("/search", response_model=GraphSearchResponse)
def graph_search(q: str = "", label: str | None = None, top_k: int = 20, context=Depends(build_request_context)) -> GraphSearchResponse:
    require_graph_read(context.user)
    items = search(context.org_id, query=q, label=label, top_k=top_k)
    return GraphSearchResponse(items=items, count=len(items))


@router.post("/sync")
def sync_entity(entity_type: str, entity_id: str, context=Depends(build_request_context)) -> dict:
    require_graph_write(context.user)
    return {"status": "queued", "entity_type": entity_type, "entity_id": entity_id}


@router.post("/rebuild")
def rebuild(context=Depends(build_request_context)) -> dict:
    require_graph_write(context.user)
    result = rebuild_org(context.org_id, trace_id=context.request_id)
    return {"status": "completed", "result": result}


@router.post("/copilot", response_model=GraphCopilotResponse)
def graph_copilot(request: GraphCopilotRequest, context=Depends(build_request_context)) -> GraphCopilotResponse:
    require_graph_read(context.user)
    result = copilot_answer(context.org_id, request.question, entity_id=request.entity_id)
    return GraphCopilotResponse(**result)
