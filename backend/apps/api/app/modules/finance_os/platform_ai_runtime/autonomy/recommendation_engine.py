"""Autonomous recommendation engine — evidence-based, prep-first, explainable (Wave 5)."""

from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.autonomy.governance import autonomy_governance
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    AutonomyEnvelope,
    AutonomyRecommendation,
    EventPlanDecision,
    PlanMetadata,
    WorldState,
)
from app.services.logger import log_event


_TEMPLATES: dict[str, dict] = {
    "treasury_advisory": {
        "type": "cash_optimization",
        "title": "Treasury / cash position review",
        "impact": "Improve liquidity visibility and funding readiness",
        "benefit": "Fewer surprise cash shortfalls",
        "approvals": ["treasury.review"],
    },
    "collections_followup": {
        "type": "receivable_risk",
        "title": "Collections follow-up preparation",
        "impact": "Reduce DSO / overdue AR exposure",
        "benefit": "Faster cash conversion",
        "approvals": ["ar.collect"],
    },
    "ap_review": {
        "type": "vendor_negotiation",
        "title": "AP exception / duplicate review",
        "impact": "Prevent duplicate or anomalous payments",
        "benefit": "Lower payment leakage",
        "approvals": ["ap.approve"],
    },
    "recon_review": {
        "type": "bank_reconciliation",
        "title": "Reconciliation exception preparation",
        "impact": "Clear unmatched bank items",
        "benefit": "Faster close",
        "approvals": ["banking.reconcile"],
    },
    "period_close": {
        "type": "close_readiness",
        "title": "Period-end close preparation",
        "impact": "Reduce close risk across inventory, AR/AP, GST, GL",
        "benefit": "Fewer close-day blockers",
        "approvals": ["fiscal.close"],
    },
    "compliance_review": {
        "type": "gst_compliance",
        "title": "Compliance / GST preparation",
        "impact": "Reduce filing and penalty risk",
        "benefit": "Lower compliance errors",
        "approvals": ["tax.review"],
    },
    "payment_batch": {
        "type": "payment_batch",
        "title": "Payment batch proposal",
        "impact": "Prepare payments without executing rails",
        "benefit": "Controlled cash-out",
        "approvals": ["payment.approve"],
    },
}


class AutonomyRecommendationEngine:
    def from_template(
        self,
        template_key: str,
        *,
        reason: str,
        evidence: list[str] | None = None,
        confidence: float = 0.7,
        entity_id: str | None = None,
    ) -> AutonomyRecommendation:
        tpl = _TEMPLATES.get(template_key) or {
            "type": "general",
            "title": f"Operational recommendation ({template_key})",
            "impact": "Support continuous finance operations",
            "benefit": None,
            "approvals": ["agent.run"],
        }
        affected = [{"entity_id": entity_id}] if entity_id else []
        envelope = autonomy_governance.build_envelope(
            reason=reason,
            evidence=evidence,
            confidence=confidence,
            prep_only=True,
            approval_points=list(tpl["approvals"]),
            affected=affected,
            business_impact=str(tpl["impact"]),
            policies=["unified_policy_gate"],
        )
        return AutonomyRecommendation(
            recommendation_type=str(tpl["type"]),
            title=str(tpl["title"]),
            reason=reason,
            evidence=list(evidence or []),
            confidence=confidence,
            business_impact=str(tpl["impact"]),
            required_approvals=list(tpl["approvals"]),
            estimated_benefit=tpl.get("benefit"),
            affected_objects=affected,
            prep_only=True,
            envelope=envelope,
        )

    def from_plan(
        self,
        meta: PlanMetadata,
        *,
        template_key: str | None = None,
        world_state: WorldState | None = None,
    ) -> AutonomyRecommendation:
        entity_id = (
            world_state.screen.entity_id
            if world_state and world_state.screen
            else None
        )
        return self.from_template(
            template_key or "general",
            reason=meta.reasoning or "Plan prepared for review",
            evidence=[meta.reasoning] if meta.reasoning else [],
            confidence=(meta.confidence or 0) / 100.0 if (meta.confidence or 0) > 1 else (meta.confidence or 0.5),
            entity_id=entity_id,
        )

    def from_event_decision(self, decision: EventPlanDecision) -> AutonomyRecommendation | None:
        if decision.action not in {"recommend", "prepare_workflow", "notify_user", "approval_required"}:
            return None
        return self.from_template(
            decision.template_key or "general",
            reason=decision.reason,
            evidence=decision.evidence,
            confidence=decision.confidence,
        )

    def collaboration_message(self, rec: AutonomyRecommendation) -> str:
        return (
            f"I prepared a recommendation: {rec.title}. "
            f"Reason: {rec.reason} "
            f"(confidence {round(rec.confidence * 100)}%). "
            f"Impact: {rec.business_impact}. "
            f"Approvals required: {', '.join(rec.required_approvals) or 'review'}. "
            "No financial truth was changed."
        )

    def persist_soft(
        self,
        org_id: str,
        *,
        run_id: str,
        rec: AutonomyRecommendation,
    ) -> dict | None:
        """Persist via existing M29 recommendation repository when available."""
        try:
            from app.modules.finance_os.agents.schemas.agents_schema import AgentPlan, ConfidenceResult
            from app.modules.finance_os.agents.services.recommendation_service import recommendation_service

            plan = AgentPlan(
                agent_name="platform_ai_runtime",
                task_type="autonomous_recommendation",
                recommendation_type=rec.recommendation_type,
                recommendation=f"{rec.title}: {rec.reason}",
                proposed_actions=[{"type": "review", "approvals": rec.required_approvals}],
                metadata={
                    "evidence": rec.evidence,
                    "business_impact": rec.business_impact,
                    "estimated_benefit": rec.estimated_benefit,
                    "prep_only": True,
                    "envelope": rec.envelope.model_dump() if rec.envelope else None,
                },
            )
            conf = ConfidenceResult(
                score=float(rec.confidence),
                band="review" if rec.confidence < 0.8 else "strong",
                approval_required=True,
            )
            return recommendation_service.persist(org_id, run_id, plan, conf)
        except Exception as exc:
            log_event("m38.recommendation.persist_soft_failed", org_id=org_id, detail=str(exc))
            return rec.model_dump()


autonomy_recommendation_engine = AutonomyRecommendationEngine()
