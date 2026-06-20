from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.memory.schemas.memory_schema import MemoryCorrectionRequest
from app.modules.finance_os.memory.security.memory_guard import require_memory_write
from app.modules.finance_os.memory.services.memory_cleanup_service import apply_cleanup
from app.modules.finance_os.memory.services.memory_summarization_service import summarize_entity
from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service
from app.services.repositories import audit_repo

router = APIRouter(tags=["finance-os-memory-admin"])


@router.post("/admin/decay/run")
def run_decay(context=Depends(build_request_context)) -> dict:
    require_memory_write(context.user)
    return apply_cleanup(context.org_id, trace_id=context.request_id)


@router.post("/admin/summarize")
def run_summarize(
    entity_type: str,
    entity_id: str,
    memory_type: str,
    threshold: int = 20,
    context=Depends(build_request_context),
) -> dict:
    require_memory_write(context.user)
    result = summarize_entity(
        context.org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        memory_type=memory_type,
        threshold=threshold,
        trace_id=context.request_id,
    )
    return {"item": result}


@router.patch("/entries/{memory_id}")
def correct_entry(
    memory_id: str,
    request: MemoryCorrectionRequest,
    context=Depends(build_request_context),
) -> dict:
    require_memory_write(context.user)
    updated = memory_writer_service.update(
        context.org_id,
        memory_id,
        title=request.title,
        content=request.content,
        trace_id=context.request_id,
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="memory.corrected",
        object_ref=f"memory:{memory_id}",
        payload_jsonb={"title": request.title, "content": request.content},
    )
    return {"item": updated}


@router.delete("/entries/{memory_id}")
def archive_entry(memory_id: str, context=Depends(build_request_context)) -> dict:
    require_memory_write(context.user)
    memory_writer_service.archive(context.org_id, memory_id, trace_id=context.request_id)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="memory.archived",
        object_ref=f"memory:{memory_id}",
        payload_jsonb={},
    )
    return {"status": "archived", "memory_id": memory_id}
