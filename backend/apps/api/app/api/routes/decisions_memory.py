"""Legacy decisions/memory routes — prefer /finance-os/memory/* (see LEGACY_ROUTE_MIGRATION.md)."""
from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.schemas.decisions import DecisionCreateRequest, DecisionItem, DecisionListResponse
from app.schemas.memory import MemoryListResponse, MemoryRecordItem, MemoryRecordRequest
from app.services.event_bus import event_bus
from app.services.principal_context import principal_from_request_context
from app.services.repositories import audit_repo, decisions_repo, memory_repo

router = APIRouter(tags=["decisions-memory"])


@router.post("/decisions", response_model=DecisionItem)
def create_decision(request: DecisionCreateRequest, context=Depends(build_request_context)) -> DecisionItem:
    decision = decisions_repo.create_decision(
        org_id=context.org_id,
        decision_type=request.decision_type,
        title=request.title,
        rationale=request.rationale,
        made_by=request.made_by,
    )
    event_bus.publish(
        event_type="decision.recorded",
        org_id=context.org_id,
        source="api.decisions",
        trace_id=context.request_id,
        payload={"decision_id": decision["id"]},
        principal=principal_from_request_context(context),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="decision.created",
        object_ref=f"decision:{decision['id']}",
        payload_jsonb={"decision_type": request.decision_type, "title": request.title},
    )
    return DecisionItem(**decision)


@router.get("/decisions", response_model=DecisionListResponse)
def list_decisions(context=Depends(build_request_context)) -> DecisionListResponse:
    rows = [DecisionItem(**row) for row in decisions_repo.list_decisions(org_id=context.org_id)]
    return DecisionListResponse(
        request_id=context.request_id,
        items=rows,
        confidence=0.95,
        verification_status="verified",
    )


@router.get("/memory", response_model=MemoryListResponse)
def list_memory(subject_ref: str | None = None, memory_type: str | None = None, context=Depends(build_request_context)) -> MemoryListResponse:
    items = [
        MemoryRecordItem(**row)
        for row in memory_repo.list_memory(org_id=context.org_id, subject_ref=subject_ref, memory_type=memory_type)
    ]
    return MemoryListResponse(
        request_id=context.request_id,
        items=items,
        confidence=0.92,
        verification_status="verified",
    )


@router.post("/memory", response_model=MemoryRecordItem)
def create_memory(request: MemoryRecordRequest, context=Depends(build_request_context)) -> MemoryRecordItem:
    row = memory_repo.create_memory(
        org_id=context.org_id,
        memory_type=request.memory_type,
        subject_ref=request.subject_ref,
        payload_jsonb=request.payload_jsonb,
        relevance_score=request.relevance_score,
    )
    event_bus.publish(
        event_type="memory.write",
        org_id=context.org_id,
        source="api.memory",
        trace_id=context.request_id,
        payload={
            "memory_record_id": row["id"],
            "subject_ref": request.subject_ref,
            "memory_type": request.memory_type,
            "relevance_score": request.relevance_score,
            "title": request.payload_jsonb.get("title") if isinstance(request.payload_jsonb, dict) else None,
            "content": request.payload_jsonb.get("content") if isinstance(request.payload_jsonb, dict) else None,
        },
        principal=principal_from_request_context(context),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="memory.created",
        object_ref=f"memory:{row['id']}",
        payload_jsonb={"memory_type": request.memory_type, "subject_ref": request.subject_ref},
    )
    return MemoryRecordItem(**row)
