from datetime import datetime, timezone

from app.services.logger import log_event
from app.services.memory_service import apply_memory_decay
from app.services.repositories import memory_repo
from app.services.redis_client import get_redis_client


def run_scheduled_jobs_once(org_id: str) -> dict:
    # RQ-08: scheduler idempotency (defense-in-depth beyond leader election).
    client = get_redis_client()
    if client is not None:
        window = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        if not client.set(f"scheduler:tick:{org_id}:{window}", "1", nx=True, ex=180):
            return {"ran_at": datetime.now(timezone.utc).isoformat(), "org_id": org_id, "skipped": True, "reason": "idempotent_tick"}
    decay_summary = apply_memory_decay(org_id=org_id)
    m27_decay: dict = {}
    try:
        from app.modules.finance_os.memory.services.memory_cleanup_service import apply_cleanup

        m27_decay = apply_cleanup(org_id)
    except Exception as exc:
        m27_decay = {"error": str(exc)}
    workflow_summary: dict = {}
    platform_summary: dict = {}
    try:
        from app.modules.platform.events.services.scheduling_service import scheduling_service

        platform_summary = scheduling_service.run_org_scheduled_emissions(org_id)
    except Exception as exc:
        platform_summary = {"error": str(exc)}
    try:
        from app.modules.workflows.services.workflow_service import workflow_service

        if workflow_service.schema_ready():
            from app.modules.workflows.workers.timeout_worker import run_timeout_checks
            from app.modules.workflows.workers.retry_worker import run_retry_queue_drain

            workflow_summary = {
                "timeouts": run_timeout_checks(org_id),
                "retries": run_retry_queue_drain(org_id),
                "note": "sla/escalation/reconciliation emitted via platform scheduler events",
            }
    except Exception as exc:
        workflow_summary = {"error": str(exc)}
    now = datetime.now(timezone.utc).isoformat()
    log_event(
        "scheduler.jobs.ran",
        org_id=org_id,
        at=now,
        decay_summary=decay_summary,
        workflow=workflow_summary,
        platform=platform_summary,
    )
    return {
        "ran_at": now,
        "org_id": org_id,
        "decay_summary": decay_summary,
        "m27_decay_summary": m27_decay,
        "platform_summary": platform_summary,
        "workflow_summary": workflow_summary,
        "memory_records_total": len(memory_repo.list_all_for_decay(org_id=org_id)),
    }
