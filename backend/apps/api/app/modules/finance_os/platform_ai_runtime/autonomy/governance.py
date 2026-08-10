"""Autonomy governance — every autonomous action declares its envelope (Wave 5)."""

from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    AutonomyEnvelope,
    PlanMetadata,
)


class AutonomyGovernance:
    def build_envelope(
        self,
        *,
        reason: str,
        evidence: list[str] | None = None,
        confidence: float = 0.0,
        risk_level: str = "low",
        prep_only: bool = True,
        approval_points: list[str] | None = None,
        rollback: list[dict] | None = None,
        affected: list[dict] | None = None,
        business_impact: str = "",
        policies: list[str] | None = None,
        time_horizon: str | None = None,
        allowed_tools: list[str] | None = None,
    ) -> AutonomyEnvelope:
        requires_approval = True if not prep_only else bool(approval_points) or risk_level in {"medium", "high"}
        tier = "prepare" if prep_only else ("execute_with_approval" if requires_approval else "recommend")
        if prep_only and not approval_points:
            tier = "recommend" if confidence < 0.7 else "prepare"
        return AutonomyEnvelope(
            reason=reason[:800],
            evidence=list(evidence or [])[:20],
            planner_confidence=float(confidence),
            required_policy=list(policies or ["unified_policy_gate", "rbac", "abac"]),
            required_approval=requires_approval or not prep_only,
            rollback_strategy=list(rollback or []),
            affected_erp_objects=list(affected or []),
            business_impact=business_impact[:500],
            prep_only=prep_only,
            autonomy_tier=tier,  # type: ignore[arg-type]
            time_horizon=time_horizon,
            allowed_tools=list(allowed_tools or []),
        )

    def attach_to_plan(self, meta: PlanMetadata, envelope: AutonomyEnvelope) -> PlanMetadata:
        return meta.model_copy(
            update={
                "envelope": envelope,
                "prep_only": envelope.prep_only or meta.prep_only,
                "collaboration_message": meta.collaboration_message
                or (f"Prepared under governance: {envelope.reason}" if envelope.prep_only else None),
            }
        )

    def assert_mutates_only_with_approval(self, *, human_approved: bool, prep_only: bool, mutates: bool) -> dict:
        """Runtime guard — financial truth never mutates autonomously."""
        if mutates and not human_approved:
            return {
                "allowed": False,
                "status": "pending_approval",
                "detail": "Autonomous mutation blocked — human approval required",
                "code": "AUTONOMY_MUTATION_BLOCKED",
            }
        if prep_only and mutates:
            return {
                "allowed": False,
                "status": "pending_approval",
                "detail": "Prep-only goal — mutation tools deferred to approval",
                "code": "PREP_ONLY_MUTATION",
            }
        return {"allowed": True}

    def declare(self, envelope: AutonomyEnvelope) -> dict:
        return envelope.model_dump()


autonomy_governance = AutonomyGovernance()
