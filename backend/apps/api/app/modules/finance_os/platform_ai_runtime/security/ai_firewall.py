"""AI Firewall — prompt trust boundary for M38 runtime (Phase 8 Wave 3 / AI-15).

Extends core.prompt_sanitizer + content_policy. Does not replace the Policy Engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from app.core.config import settings
from app.core.content_policy import ContentPolicyViolation, evaluate_content_policy
from app.core.prompt_sanitizer import (
    PromptRejectedError,
    detect_adversarial_patterns,
    sanitize_user_prompt,
)
from app.services.logger import log_event

try:
    from app.services.repositories import audit_repo
except Exception:  # pragma: no cover
    audit_repo = None  # type: ignore


class AttackSeverity(str, Enum):
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


_SEVERITY_BY_LABEL: dict[str, AttackSeverity] = {
    "prompt_injection": AttackSeverity.HIGH,
    "jailbreak": AttackSeverity.CRITICAL,
    "system_prompt_extraction": AttackSeverity.HIGH,
    "policy_bypass": AttackSeverity.CRITICAL,
    "approval_bypass": AttackSeverity.CRITICAL,
    "tool_manipulation": AttackSeverity.HIGH,
    "hidden_instruction": AttackSeverity.HIGH,
    "context_poisoning": AttackSeverity.MEDIUM,
    "recursive_prompting": AttackSeverity.MEDIUM,
    "credential_exfiltration": AttackSeverity.CRITICAL,
    "pii_exfiltration": AttackSeverity.CRITICAL,
    "unsafe_execution": AttackSeverity.CRITICAL,
    "security_bypass": AttackSeverity.CRITICAL,
    "harmful_content": AttackSeverity.HIGH,
    "cross_tenant_access": AttackSeverity.CRITICAL,
    "cross_tenant_param": AttackSeverity.CRITICAL,
    "approval_flag_injection": AttackSeverity.CRITICAL,
    "forbidden_finance_mutation": AttackSeverity.HIGH,
    "exceeds_max_length": AttackSeverity.LOW,
}


def _max_severity(labels: list[str]) -> AttackSeverity:
    order = [
        AttackSeverity.NONE,
        AttackSeverity.LOW,
        AttackSeverity.MEDIUM,
        AttackSeverity.HIGH,
        AttackSeverity.CRITICAL,
    ]
    rank = 0
    for label in labels:
        sev = _SEVERITY_BY_LABEL.get(label, AttackSeverity.MEDIUM)
        rank = max(rank, order.index(sev))
    return order[rank]


@dataclass
class FirewallDecision:
    allowed: bool
    sanitized_text: str
    original_text: str
    detections: list[str] = field(default_factory=list)
    severity: AttackSeverity = AttackSeverity.NONE
    stage: str = "prompt"
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "allowed": self.allowed,
            "detections": list(self.detections),
            "severity": self.severity.value,
            "stage": self.stage,
            "reason": self.reason,
            "original_length": len(self.original_text or ""),
            "sanitized_length": len(self.sanitized_text or ""),
            "details": self.details,
        }


class AIFirewallError(PermissionError):
    """Raised when the AI firewall blocks input."""

    def __init__(self, decision: FirewallDecision) -> None:
        self.decision = decision
        super().__init__(decision.reason or "AI firewall blocked request")


class AIFirewall:
    """Single ingress firewall for user prompts, documents treated as data, and tool strings."""

    def inspect(
        self,
        text: str,
        *,
        org_id: str | None = None,
        user_id: str | None = None,
        stage: str = "user_prompt",
        block: bool | None = None,
        goal_id: str | None = None,
    ) -> FirewallDecision:
        original = text or ""
        detections = list(detect_adversarial_patterns(original))
        policy = evaluate_content_policy(original, field=stage)
        for v in policy.violations:
            if v not in detections:
                detections.append(v)
        severity = _max_severity(detections) if detections else AttackSeverity.NONE
        block_on = settings.m38_ai_firewall_block_on_detection if block is None else block
        firewall_on = bool(settings.m38_ai_firewall_enabled)

        allowed = True
        reason = None
        sanitized = original
        if firewall_on and detections and block_on:
            # Critical/high always block; medium blocks on prompt stages
            if severity in {AttackSeverity.CRITICAL, AttackSeverity.HIGH} or stage in {
                "user_prompt",
                "tool_param",
                "planner",
            }:
                allowed = False
                reason = f"AI firewall blocked ({severity.value}): {', '.join(detections[:5])}"
        if allowed and firewall_on:
            try:
                sanitized = sanitize_user_prompt(original, reject_on_detection=False)
            except PromptRejectedError as exc:
                allowed = False
                reason = str(exc)
                detections = detections or ["prompt_rejected"]
                severity = max(severity, AttackSeverity.HIGH, key=lambda s: list(AttackSeverity).index(s))

        decision = FirewallDecision(
            allowed=allowed,
            sanitized_text=sanitized if allowed else original,
            original_text=original,
            detections=detections,
            severity=severity,
            stage=stage,
            reason=reason,
            details={"firewall_enabled": firewall_on},
        )
        if detections or not allowed:
            self._emit(decision, org_id=org_id, user_id=user_id, goal_id=goal_id)
        return decision

    def enforce(
        self,
        text: str,
        *,
        org_id: str | None = None,
        user_id: str | None = None,
        stage: str = "user_prompt",
        goal_id: str | None = None,
    ) -> str:
        decision = self.inspect(
            text, org_id=org_id, user_id=user_id, stage=stage, goal_id=goal_id
        )
        if not decision.allowed:
            raise AIFirewallError(decision)
        return decision.sanitized_text

    def inspect_document_as_data(
        self,
        text: str,
        *,
        org_id: str | None = None,
        user_id: str | None = None,
    ) -> FirewallDecision:
        """Retrieved / uploaded documents: scan for instruction payloads but never execute them.

        Documents are treated as DATA. Instruction-like content is flagged and neutralized
        (stripped markers) without elevating document text into system instructions.
        """
        original = text or ""
        capped = original[: int(settings.m38_max_document_instruction_scan or 8000)]
        decision = self.inspect(
            capped,
            org_id=org_id,
            user_id=user_id,
            stage="retrieved_document",
            block=False,  # data path: neutralize rather than fail whole run
        )
        if decision.detections:
            # Neutralize known instruction envelopes in the sanitized/data view
            neutralized = decision.sanitized_text
            for marker in ("system:", "[[INST]]", "<<SYS>>", "<instruction>", "</instruction>"):
                neutralized = neutralized.replace(marker, "[data]")
                neutralized = neutralized.replace(marker.upper(), "[data]")
            decision.sanitized_text = neutralized
            decision.details["treated_as"] = "data_not_instructions"
            decision.allowed = True
            self._emit(decision, org_id=org_id, user_id=user_id, goal_id=None)
        return decision

    def _emit(
        self,
        decision: FirewallDecision,
        *,
        org_id: str | None,
        user_id: str | None,
        goal_id: str | None,
    ) -> None:
        payload = {
            **decision.to_dict(),
            "org_id": org_id or "",
            "user_id": user_id or "",
            "goal_id": goal_id or "",
            # Never log full prompt content for security; store hash-length only
            "original_preview": (decision.original_text or "")[:120],
        }
        log_event(
            "m38.security.firewall",
            **{k: v for k, v in payload.items() if k not in {"details"}},
            blocked=not decision.allowed,
        )
        if audit_repo and org_id:
            try:
                audit_repo.create_log(
                    org_id=org_id,
                    actor_type="agent",
                    actor_id=user_id or "ai_firewall",
                    event_type="m38.security.firewall",
                    object_ref=f"goal:{goal_id or 'none'}:{decision.stage}",
                    payload_jsonb={
                        "allowed": decision.allowed,
                        "detections": decision.detections,
                        "severity": decision.severity.value,
                        "stage": decision.stage,
                        "reason": decision.reason,
                        "original_length": len(decision.original_text or ""),
                    },
                )
            except Exception as exc:
                log_event("m38.security.firewall_audit_failed", detail=str(exc))


ai_firewall = AIFirewall()
