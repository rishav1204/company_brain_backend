from __future__ import annotations

from app.modules.finance_os.agents.engine.confidence_engine import score as score_confidence
from app.modules.finance_os.agents.events import agents_events
from app.modules.finance_os.agents.orchestrator.agent_registry import get_agent
from app.modules.finance_os.agents.orchestrator.execution_planner import enrich_payload
from app.modules.finance_os.agents.orchestrator.task_router import resolve_agent, task_type_for
from app.modules.finance_os.agents.orchestrator.workflow_launcher import workflow_launcher
from app.modules.finance_os.agents.repositories.execution_repository import execution_repository
from app.modules.finance_os.agents.services.agent_memory_service import write_outcome
from app.modules.finance_os.agents.services.context_service import build as build_context
from app.modules.finance_os.agents.services.execution_service import execution_service
from app.modules.finance_os.agents.services.recommendation_service import recommendation_service
from app.services.langgraph_runner import run_langgraph_flow
from app.services.repositories import audit_repo


FINANCE_OS_AGENTS = {
    "ap_agent",
    "reconciliation_agent",
    "gst_agent",
    "close_agent",
    "collections_agent",
    "treasury_agent",
    "ap_exception_agent",
    "close_orchestration_agent",
    "cashflow_risk_agent",
}


def is_finance_os_agent(agent_type: str) -> bool:
    return resolve_agent(agent_type, {}) in FINANCE_OS_AGENTS or agent_type in FINANCE_OS_AGENTS


class AgentOrchestrationPipeline:
    def run(
        self,
        org_id: str,
        agent_type: str,
        trigger_type: str,
        payload: dict | None = None,
        *,
        trace_id: str | None = None,
        principal_roles: list[str] | None = None,
        principal_attrs: dict | None = None,
        user_id: str | None = None,
        source_event_type: str | None = None,
    ) -> dict:
        payload = payload or {}
        agent_name = resolve_agent(agent_type, payload)
        if agent_name not in FINANCE_OS_AGENTS and agent_name not in {
            "ap_agent",
            "reconciliation_agent",
            "gst_agent",
            "close_agent",
            "collections_agent",
            "treasury_agent",
        }:
            raise ValueError(f"Unknown Finance OS agent: {agent_type}")

        execution = None
        if execution_repository.schema_ready():
            execution = execution_repository.create(
                org_id,
                agent_name=agent_name,
                trigger_type=trigger_type,
                task_type=task_type_for(agent_name, payload),
                source_event_type=source_event_type,
                entity_type=str(payload.get("entity_type") or payload.get("object_type") or "") or None,
                entity_id=str(payload.get("entity_id") or payload.get("object_id") or "") or None,
                metadata={"payload": payload},
            )
            agents_events.emit_started(
                org_id,
                {"execution_id": execution["id"], "agent_name": agent_name},
                trace_id=trace_id,
            )

        context = build_context(org_id, agent_name, payload)
        agent = get_agent(agent_name)
        plan = agent.plan(context)
        confidence = score_confidence(context, plan.metadata if plan else None)

        recommendation = None
        workflow_instance_id = None
        if execution and plan:
            recommendation = recommendation_service.persist(
                org_id,
                execution["id"],
                plan,
                confidence,
            )
            agents_events.emit_recommendation_created(
                org_id,
                {"execution_id": execution["id"], "recommendation_id": recommendation.get("id")},
                trace_id=trace_id,
            )

        enriched = enrich_payload(context, plan)
        if plan and plan.workflow_key and confidence.band in {"very_strong", "strong", "review"}:
            wf = workflow_launcher.launch(
                org_id,
                workflow_key=plan.workflow_key,
                user_id=user_id or "agent-runtime",
                entity_type=str(context.entity_type or "workflow"),
                entity_id=context.entity_id,
                metadata={
                    "agent_execution_id": execution["id"] if execution else None,
                    "recommendation_id": recommendation.get("id") if recommendation else None,
                    "confidence": confidence.score,
                },
                trace_id=trace_id,
            )
            if wf:
                workflow_instance_id = str(wf.get("workflow_id") or wf.get("id") or "")
                agents_events.emit_workflow_created(
                    org_id,
                    {"workflow_instance_id": workflow_instance_id, "workflow_key": plan.workflow_key},
                    trace_id=trace_id,
                )

        flow_result = run_langgraph_flow(
            org_id=org_id,
            agent_type=agent_name,
            trigger_type=trigger_type,
            payload=enriched,
            principal_roles=principal_roles or ["tenant_admin"],
            principal_attrs=principal_attrs or {},
        )

        platform_run = execution_service.create_platform_run(
            org_id,
            agent_type=agent_name,
            trigger_type=trigger_type,
            status=flow_result["status"],
            outputs={"flow_result": flow_result, "plan": plan.__dict__ if plan else None, "confidence": confidence.__dict__},
        )

        final_status = flow_result["status"]
        if final_status == "pending_human_approval":
            final_status = "pending_approval"

        if execution:
            execution_repository.update_status(
                org_id,
                execution["id"],
                status=final_status,
                platform_run_id=platform_run.get("run_id"),
                metadata={"workflow_instance_id": workflow_instance_id},
            )
            write_outcome(org_id, agent_name, execution["id"], plan.recommendation if plan else "")
            agents_events.emit_completed(
                org_id,
                {"execution_id": execution["id"], "status": final_status},
                trace_id=trace_id,
            )

        audit_repo.create_log(
            org_id=org_id,
            actor_type="agent",
            actor_id=agent_name,
            event_type="agent.run.completed",
            object_ref=f"agent_execution:{execution['id'] if execution else platform_run.get('run_id')}",
            payload_jsonb={"confidence": confidence.score, "status": final_status},
        )

        return {
            "execution_id": execution["id"] if execution else None,
            "platform_run_id": platform_run.get("run_id"),
            "status": final_status,
            "confidence": confidence.score,
            "confidence_band": confidence.band,
            "verification_status": "policy_checked",
            "recommendations": [recommendation] if recommendation else [],
            "flow_result": flow_result,
            "workflow_instance_id": workflow_instance_id,
        }


agent_orchestration_pipeline = AgentOrchestrationPipeline()
