from __future__ import annotations

from typing import Any

from app.modules.platform.governance.repositories.ai_trace_repository import ai_trace_repository
from app.modules.platform.governance.services.audit_service import audit_service


def track_ai_reasoning(
    org_id: str,
    *,
    prompt: str,
    reasoning_summary: str,
    confidence_score: float | None,
    decision: dict,
    retrieved_context: dict | None = None,
    policy_checks: list | None = None,
    agent_run_id: str | None = None,
    workflow_id: str | None = None,
    step_id: str | None = None,
) -> dict[str, Any]:
    if not ai_trace_repository.schema_ready():
        return {
            "id": "skipped",
            "prompt_hash": audit_service.hash_prompt(prompt),
            "reasoning_summary": reasoning_summary[:500],
        }
    return ai_trace_repository.append(
        org_id,
        prompt_hash=audit_service.hash_prompt(prompt),
        reasoning_summary=reasoning_summary,
        confidence_score=confidence_score,
        decision=decision,
        retrieved_context=retrieved_context,
        policy_checks=policy_checks,
        agent_run_id=agent_run_id,
        workflow_id=workflow_id,
        step_id=step_id,
    )
