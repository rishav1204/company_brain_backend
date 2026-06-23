from __future__ import annotations

from app.modules.platform.events.queues.queue_manager import queue_manager
from app.modules.workflows.services.workflow_orchestrator import workflow_orchestrator
from app.core.config import settings


def run_retry_queue_drain(org_id: str) -> dict:
    queue = settings.queue_workflow_retries
    processed = 0
    for _ in range(20):
        claim = queue_manager.claim_next(queue=queue)
        if claim.status != "claimed" or not claim.envelope:
            break
        envelope = claim.envelope
        if str(envelope.get("org_id")) != org_id:
            queue_manager.complete_claim(queue, envelope, claim.claim_token)
            continue
        payload = envelope.get("payload", {})
        instance_id = payload.get("workflow_instance_id")
        if instance_id:
            workflow_orchestrator.run_from_step(org_id=org_id, instance_id=str(instance_id))
            processed += 1
        queue_manager.complete_claim(queue, envelope, claim.claim_token)
    return {"org_id": org_id, "retries_processed": processed}


def schedule_retry(*, retry_count: int) -> dict:
    from app.modules.workflows.services.retry_service import retry_delay_seconds, should_retry

    if not should_retry(retry_count):
        return {"scheduled": False, "reason": "max_retries_exceeded"}
    return {"scheduled": True, "delay_seconds": retry_delay_seconds(retry_count)}
