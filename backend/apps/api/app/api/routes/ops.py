from fastapi import APIRouter, Depends, HTTPException

from app.modules.core.iam.middleware.permission_guard import require_permission
from app.core.config import settings
from app.services.repositories import audit_repo
from app.services.scheduler_service import run_scheduled_jobs_once
from app.services.worker_service import run_queue_worker_batch, run_queue_worker_once

router = APIRouter(tags=["ops"])


@router.post("/ops/worker/run-once")
def ops_run_worker(context=Depends(require_permission("ops.worker.manage"))) -> dict:
    if not settings.enable_worker_routes:
        raise HTTPException(status_code=403, detail="Worker routes are disabled")
    result = run_queue_worker_once()
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="ops.worker.run_once",
        object_ref="ops:worker",
        payload_jsonb={"worker_status": result.get("status")},
    )
    return {
        "request_id": context.request_id,
        "worker_result": result,
        "confidence": 0.92,
        "verification_status": "worker_invoked",
    }


@router.post("/ops/worker/run-batch")
def ops_run_worker_batch(iterations: int = 25, context=Depends(require_permission("ops.worker.manage"))) -> dict:
    if not settings.enable_worker_routes:
        raise HTTPException(status_code=403, detail="Worker routes are disabled")
    summary = run_queue_worker_batch(iterations=iterations)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="ops.worker.run_batch",
        object_ref="ops:worker:batch",
        payload_jsonb=summary,
    )
    return {
        "request_id": context.request_id,
        "batch_summary": summary,
        "confidence": 0.93,
        "verification_status": "worker_batch_invoked",
    }


@router.post("/ops/scheduler/run-once")
def ops_run_scheduler(context=Depends(build_request_context)) -> dict:
    if not settings.enable_worker_routes:
        raise HTTPException(status_code=403, detail="Scheduler routes are disabled")
    result = run_scheduled_jobs_once(org_id=context.org_id)
    audit_repo.create_log(
        org_id=context.org_id,
        actor_type="user",
        actor_id=context.user_id,
        event_type="ops.scheduler.run_once",
        object_ref="ops:scheduler",
        payload_jsonb={"decay_summary": result.get("decay_summary")},
    )
    return {
        "request_id": context.request_id,
        "scheduler_result": result,
        "confidence": 0.92,
        "verification_status": "scheduler_invoked",
    }
