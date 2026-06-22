from __future__ import annotations

from app.modules.finance_os.workflow_intelligence.events.workflow_intelligence_events import (
    emit_bottleneck_detected,
    emit_health_updated,
    emit_intelligence_completed,
    emit_optimization_recommended,
    emit_sla_risk_detected,
)
from app.modules.finance_os.workflow_intelligence.services.approval_optimization_service import approval_optimization_service
from app.modules.finance_os.workflow_intelligence.services.bottleneck_service import bottleneck_service
from app.modules.finance_os.workflow_intelligence.services.sla_prediction_service import sla_prediction_service
from app.modules.finance_os.workflow_intelligence.services.workflow_analysis_service import workflow_analysis_service
from app.modules.finance_os.workflow_intelligence.services.workflow_insight_service import workflow_insight_service
from app.modules.finance_os.workflow_intelligence.retrieval.workflow_memory import write_pattern_memory
from app.modules.platform.billing.billing_hooks import billing_ai_operation


class WorkflowIntelligencePipeline:
    def run(
        self,
        org_id: str,
        *,
        workflow_instance_id: str | None = None,
        workflow_type: str | None = None,
        trace_id: str | None = None,
    ) -> dict:
        with billing_ai_operation(org_id, feature="workflow_intelligence", operation_code="workflow_intelligence"):
            return self._run_inner(
                org_id,
                workflow_instance_id=workflow_instance_id,
                workflow_type=workflow_type,
                trace_id=trace_id,
            )

    def _run_inner(
        self,
        org_id: str,
        *,
        workflow_instance_id: str | None = None,
        workflow_type: str | None = None,
        trace_id: str | None = None,
    ) -> dict:
        instance_id = workflow_instance_id
        wf_type = workflow_type

        if instance_id:
            ingest = workflow_analysis_service.ingest_instance(org_id, workflow_instance_id=instance_id)
            if not wf_type:
                snap = ingest.get("snapshot") or {}
                wf_type = snap.get("workflow_type")
        elif wf_type:
            ingest = {"snapshot": None, "graph": []}
        else:
            raise ValueError("workflow_instance_id or workflow_type required")

        bottlenecks = bottleneck_service.list_bottlenecks(org_id, workflow_type=wf_type)
        if bottlenecks:
            emit_bottleneck_detected(
                org_id,
                {"workflow_type": wf_type, "bottlenecks": bottlenecks[:5], "workflow_instance_id": instance_id},
                trace_id=trace_id,
            )

        sla_result = None
        if instance_id:
            try:
                sla_result = sla_prediction_service.predict_for_instance(org_id, workflow_instance_id=instance_id)
                if sla_result.get("breach_risk") in {"high", "medium"}:
                    emit_sla_risk_detected(
                        org_id,
                        {"workflow_instance_id": instance_id, **sla_result},
                        trace_id=trace_id,
                    )
            except Exception:
                sla_result = None

        recommendations: list[dict] = []
        if wf_type:
            recommendations = approval_optimization_service.generate(
                org_id, workflow_type=wf_type, workflow_instance_id=instance_id
            )
            if recommendations:
                emit_optimization_recommended(
                    org_id,
                    {"workflow_type": wf_type, "recommendations": recommendations},
                    trace_id=trace_id,
                )
                if bottlenecks:
                    top = bottlenecks[0]
                    write_pattern_memory(
                        org_id,
                        workflow_type=wf_type,
                        pattern=f"bottleneck at {top.get('step_key')}",
                    )

        health = workflow_insight_service.health(org_id)
        emit_health_updated(org_id, health, trace_id=trace_id)

        result = {
            "workflow_instance_id": instance_id,
            "workflow_type": wf_type,
            "bottleneck_count": len(bottlenecks),
            "recommendation_count": len(recommendations),
            "health": health,
            "sla": sla_result,
        }
        emit_intelligence_completed(org_id, result, trace_id=trace_id)
        return result


workflow_intelligence_pipeline = WorkflowIntelligencePipeline()
