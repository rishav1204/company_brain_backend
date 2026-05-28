from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import build_request_context
from app.core.config import settings
from app.services.embedding_worker_service import ingest_document_for_embedding
from app.services.identity_resolution_service import resolve_identity
from app.services.ingestion_service import (
    ConnectorMode,
    complete_ingestion_run,
    score_source_reliability,
    start_ingestion_run,
)
from app.services.principal_context import principal_from_request_context
from app.services.repositories import audit_repo, ingestion_repo, sources_repo
from app.services.worker_service import run_queue_worker_once

router = APIRouter(tags=["ingestion"])


class IngestionStartRequest(BaseModel):
    source_id: str
    trigger_mode: str


class IngestionCompleteRequest(BaseModel):
    run_id: str
    success: bool
    error_summary: str | None = None


class IdentityResolveRequest(BaseModel):
    aliases: list[str]
    canonical_type: str = "entity"
    source: str = "api"
    source_key: str = "alias"


class EmbeddingIngestRequest(BaseModel):
    source_id: str
    title: str
    content: str
    doc_type: str = "ops_note"
    permission_ref: str | None = None


@router.post("/ingestion/runs/start")
def start_run(request: IngestionStartRequest, context=Depends(build_request_context)) -> dict:
    source = sources_repo.get_source(org_id=context.org_id, source_id=request.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    if request.trigger_mode not in {ConnectorMode.WEBHOOK, ConnectorMode.POLLING, ConnectorMode.CDC}:
        raise HTTPException(status_code=422, detail="Unsupported trigger mode")
    run = start_ingestion_run(
        org_id=context.org_id,
        source_id=request.source_id,
        trigger_mode=request.trigger_mode,
        trace_id=context.request_id,
        principal=principal_from_request_context(context),
    )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="ingestion.run.started",
        object_ref=f"ingestion_run:{run['id']}",
        payload_jsonb={"source_id": request.source_id, "trigger_mode": request.trigger_mode},
    )
    return {
        "request_id": context.request_id,
        "run_id": run["id"],
        "status": run["status"],
        "trigger_mode": request.trigger_mode,
        "confidence": 0.95,
        "verification_status": "accepted",
    }


@router.post("/ingestion/runs/complete")
def complete_run(request: IngestionCompleteRequest, context=Depends(build_request_context)) -> dict:
    row = complete_ingestion_run(
        org_id=context.org_id,
        run_id=request.run_id,
        trace_id=context.request_id,
        success=request.success,
        error_summary=request.error_summary,
        principal=principal_from_request_context(context),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="ingestion.run.completed" if request.success else "ingestion.run.failed",
        object_ref=f"ingestion_run:{request.run_id}",
        payload_jsonb={"error_summary": request.error_summary},
    )
    success_count, failure_count = ingestion_repo.reliability_counts(org_id=context.org_id)
    reliability = score_source_reliability(success_count=success_count, failure_count=failure_count)
    return {
        "request_id": context.request_id,
        "run_id": request.run_id,
        "status": row["status"],
        "source_reliability_score": reliability,
        "confidence": 0.94,
        "verification_status": "updated",
    }


@router.post("/identity/resolve")
def identity_resolve(request: IdentityResolveRequest, context=Depends(build_request_context)) -> dict:
    aliases = request.aliases
    resolved = resolve_identity(aliases, canonical_type=request.canonical_type)
    profile = ingestion_repo.upsert_identity_profile(
        org_id=context.org_id,
        canonical_type=resolved["canonical_type"],
        canonical_key=resolved["canonical_key"],
        confidence=resolved["confidence"],
    )
    for alias in resolved["aliases"]:
        ingestion_repo.upsert_identity_alias(
            org_id=context.org_id,
            profile_id=profile["id"],
            source=request.source,
            source_key=request.source_key,
            raw_value=alias,
        )
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="identity.resolve",
        object_ref="identity:resolve",
        payload_jsonb={
            "aliases": aliases,
            "canonical_type": resolved.get("canonical_type"),
            "canonical_key": resolved.get("canonical_key"),
            "profile_id": profile.get("id"),
        },
    )
    return {
        "request_id": context.request_id,
        "resolved": resolved,
        "profile": profile,
        "confidence": resolved["confidence"],
        "verification_status": "identity_resolution_v2",
    }


@router.post("/ingestion/workers/webhook/consume")
def webhook_consume(connector: str, payload: dict, context=Depends(build_request_context)) -> dict:
    worker_result = run_queue_worker_once()
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="system",
        actor_id="webhook-worker",
        event_type="ingestion.webhook.consumed",
        object_ref=f"connector:{connector}",
        payload_jsonb={"payload_size": len(str(payload)), "worker_status": worker_result.get("status")},
    )
    return {
        "request_id": context.request_id,
        "connector": connector,
        "status": "accepted",
        "worker_result": worker_result,
        "payload_size": len(str(payload)),
        "confidence": 0.9,
        "verification_status": "webhook_worker_consumed",
    }


@router.post("/ingestion/workers/embeddings/ingest")
def embedding_worker_ingest(request: EmbeddingIngestRequest, context=Depends(build_request_context)) -> dict:
    if not settings.enable_worker_routes:
        raise HTTPException(status_code=403, detail="Embedding worker routes are disabled")
    source = sources_repo.get_source(org_id=context.org_id, source_id=request.source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    result = ingest_document_for_embedding(
        org_id=context.org_id,
        source_id=request.source_id,
        title=request.title,
        content=request.content,
        doc_type=request.doc_type,
        permission_ref=request.permission_ref,
    )
    if result.get("status") == "skipped":
        raise HTTPException(status_code=503, detail=str(result.get("detail", "Embedding worker unavailable")))
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="system",
        actor_id="embedding-worker",
        event_type="ingestion.embedding.completed",
        object_ref=f"document:{result.get('document_id', 'unknown')}",
        payload_jsonb={"chunks_written": result.get("chunks_written", 0), "source_id": request.source_id},
    )
    return {
        "request_id": context.request_id,
        "embedding_result": result,
        "confidence": 0.92,
        "verification_status": "embedding_worker_completed",
    }
