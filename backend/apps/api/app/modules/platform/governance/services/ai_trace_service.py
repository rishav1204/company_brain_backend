from __future__ import annotations

import hashlib

from typing import Any

from app.core.prompt_sanitizer import detect_adversarial_patterns, sanitize_user_prompt
from app.modules.platform.governance.explainability.ai_reasoning_tracker import track_ai_reasoning
from app.modules.platform.governance.repositories.ai_trace_repository import ai_trace_repository
from app.modules.platform.governance.services.audit_service import audit_service


class AITraceService:
    def record_reasoning(
        self,
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
        adversarial_flags = detect_adversarial_patterns(prompt)
        sanitized_prompt = sanitize_user_prompt(prompt)
        ctx = dict(retrieved_context or {})
        ctx["raw_prompt_sha256"] = hashlib.sha256((prompt or "").encode("utf-8")).hexdigest()
        if adversarial_flags:
            ctx["adversarial_input_flags"] = adversarial_flags
            ctx["raw_prompt_length"] = len(prompt or "")
        return track_ai_reasoning(
            org_id,
            prompt=sanitized_prompt,
            reasoning_summary=reasoning_summary,
            confidence_score=confidence_score,
            decision=decision,
            retrieved_context=ctx,
            policy_checks=policy_checks,
            agent_run_id=agent_run_id,
            workflow_id=workflow_id,
            step_id=step_id,
        )

    def get_trace(self, org_id: str, trace_id: str) -> dict | None:
        return ai_trace_repository.get(org_id, trace_id)

    def record_agent_decision(
        self,
        org_id: str,
        *,
        agent_run_id: str,
        workflow_id: str | None,
        prompt: str,
        summary: str,
        confidence: float,
        decision: dict,
        evidence_refs: list[str] | None = None,
    ) -> dict:
        row = self.record_reasoning(
            org_id,
            prompt=prompt,
            reasoning_summary=summary,
            confidence_score=confidence,
            decision=decision,
            retrieved_context={"evidence_refs": evidence_refs or []},
            agent_run_id=agent_run_id,
            workflow_id=workflow_id,
        )
        audit_service.record(
            org_id=org_id,
            actor_type="system",
            actor_id="ai.runtime",
            action="ai.decision.recorded",
            object_ref=f"ai_trace:{row.get('id', '')}",
            payload={"confidence": confidence, "summary": summary[:500]},
            entity_type="agent_run",
            entity_id=agent_run_id,
            source_service="governance.ai_trace",
        )
        return row


ai_trace_service = AITraceService()
