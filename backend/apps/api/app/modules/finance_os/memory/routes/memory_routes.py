from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.memory.schemas.memory_schema import (
    MemoryCopilotRequest,
    MemoryCopilotResponse,
    MemoryInsightsResponse,
    MemorySummaryResponse,
    MemoryWriteRequest,
)
from app.modules.finance_os.memory.security.memory_guard import require_memory_read, require_memory_write
from app.modules.finance_os.memory.ai.memory_copilot import answer as copilot_answer
from app.modules.finance_os.memory.pipelines.memory_ingestion_pipeline import memory_ingestion_pipeline
from app.modules.finance_os.memory.services.memory_insight_service import org_insights
from app.modules.finance_os.memory.services.memory_service import finance_os_memory_service
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-memory"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "finance_os.memory"}


@router.get("/entity/{entity_type}/{entity_id}")
def entity_memories(
    entity_type: str,
    entity_id: str,
    memory_type: str | None = None,
    context=Depends(build_request_context),
) -> dict:
    require_memory_read(context.user)
    items = finance_os_memory_service.list_entity(
        context.org_id, entity_type=entity_type, entity_id=entity_id, memory_type=memory_type
    )
    return {"items": items, "count": len(items)}


@router.get("/summary", response_model=MemorySummaryResponse)
def memory_summary(context=Depends(build_request_context)) -> MemorySummaryResponse:
    require_memory_read(context.user)
    data = finance_os_memory_service.summary(context.org_id)
    return MemorySummaryResponse(**data)


@router.get("/insights", response_model=MemoryInsightsResponse)
def memory_insights(context=Depends(build_request_context)) -> MemoryInsightsResponse:
    require_memory_read(context.user)
    return MemoryInsightsResponse(**org_insights(context.org_id))


@router.post("/write")
def write_memory(request: MemoryWriteRequest, context=Depends(build_request_context)) -> dict:
    require_memory_write(context.user)
    result = memory_ingestion_pipeline.run_manual(
        context.org_id,
        data=request.model_dump(),
        force=True,
        trace_id=context.request_id,
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="memory.manual_write",
        object_ref=f"memory:{result.get('id') if result else 'skipped'}",
        payload_jsonb={"memory_type": request.memory_type, "title": request.title},
    )
    return {"item": result}


@router.post("/rebuild")
def rebuild_memories(context=Depends(build_request_context)) -> dict:
    require_memory_write(context.user)
    try:
        from scripts.backfill_finance_os_memory import backfill_org

        summary = backfill_org(context.org_id)
        return {"status": "completed", "summary": summary}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.post("/copilot", response_model=MemoryCopilotResponse)
def memory_copilot(request: MemoryCopilotRequest, context=Depends(build_request_context)) -> MemoryCopilotResponse:
    require_memory_read(context.user)
    result = copilot_answer(context.org_id, request.question, memory_type=request.memory_type)
    return MemoryCopilotResponse(**result)


@router.get("/references/{memory_id}")
def list_references(memory_id: str, context=Depends(build_request_context)) -> dict:
    require_memory_read(context.user)
    entry = finance_os_memory_service.get(context.org_id, memory_id)
    if not entry:
        return {"references": []}
    return {"references": entry.get("references", [])}
