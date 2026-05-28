from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.core.iam.services.finance_route_guard import enforce_finance_route_access
from app.schemas.sources import (
    IngestionRunListResponse,
    IngestionRunResponse,
    SourceCreateRequest,
    SourceListResponse,
    SourceResponse,
)
from app.services.event_bus import event_bus
from app.services.policy_service import source_acl_allows
from app.services.principal_context import principal_from_request_context
from app.services.repositories import audit_repo, ingestion_repo, sources_repo

router = APIRouter(tags=["sources"])


@router.post("/sources", response_model=SourceResponse)
def create_source(request: SourceCreateRequest, context=Depends(build_request_context)) -> SourceResponse:
    enforce_finance_route_access(context, object_type="source", mode="write", required_scope="source.create")
    source_ref = request.source_ref or request.config_ref
    if not source_acl_allows(context.source_acl, source_ref):
        raise HTTPException(status_code=403, detail="Source ACL denies this source reference")
    source = sources_repo.create_source(
        org_id=context.org_id,
        source_type=request.source_type,
        config_ref=request.config_ref,
    )
    event_bus.publish(
        event_type="source.sync.started",
        org_id=context.org_id,
        source="api.sources",
        trace_id=context.request_id,
        payload={"source_id": source["id"], "config_ref": request.config_ref},
        principal=principal_from_request_context(context),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="source.created",
        object_ref=f"source:{source['id']}",
        payload_jsonb={"source_type": request.source_type, "config_ref": request.config_ref},
    )
    return SourceResponse(**source)


@router.get("/sources", response_model=SourceListResponse)
def list_sources(context=Depends(build_request_context)) -> SourceListResponse:
    enforce_finance_route_access(context, object_type="source", mode="read")
    items = [SourceResponse(**row) for row in sources_repo.list_sources(org_id=context.org_id)]
    return SourceListResponse(
        request_id=context.request_id,
        items=items,
        confidence=0.97,
        verification_status="verified",
    )


@router.post("/sources/{source_id}/sync", response_model=IngestionRunResponse)
def trigger_source_sync(source_id: str, context=Depends(build_request_context)) -> IngestionRunResponse:
    enforce_finance_route_access(context, object_type="source", mode="write", required_scope="source.sync")
    source = sources_repo.get_source(org_id=context.org_id, source_id=source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    run = ingestion_repo.create_run(org_id=context.org_id, source_id=source_id, status="started")
    event_bus.publish(
        event_type="source.sync.started",
        org_id=context.org_id,
        source="api.sources",
        trace_id=context.request_id,
        payload={"source_id": source_id, "ingestion_run_id": run["id"]},
        principal=principal_from_request_context(context),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="source.sync.requested",
        object_ref=f"source:{source_id}",
        payload_jsonb={"ingestion_run_id": run["id"]},
    )
    return IngestionRunResponse(**run)


@router.get("/ingestion-runs", response_model=IngestionRunListResponse)
def list_ingestion_runs(context=Depends(build_request_context)) -> IngestionRunListResponse:
    items = [IngestionRunResponse(**row) for row in ingestion_repo.list_runs(org_id=context.org_id)]
    return IngestionRunListResponse(
        request_id=context.request_id,
        items=items,
        confidence=0.97,
        verification_status="verified",
    )
