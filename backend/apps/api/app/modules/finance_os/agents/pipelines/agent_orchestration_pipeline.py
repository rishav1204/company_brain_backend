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
from app.core.config import settings
from app.modules.finance_os.platform_ai_runtime.runtime_router import delegate_to_m38_runtime, should_use_m38_runtime
from app.services.langgraph_runner import run_langgraph_flow
from app.services.repositories import audit_repo
from app.modules.platform.billing.billing_hooks import billing_ai_operation


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
        op = "custom_workflow_agent" if trigger_type == "workflow" else "agent_execution"
        with billing_ai_operation(org_id, feature="agents", operation_code=op):
            return self._run_inner(
                org_id,
                agent_type,
                trigger_type,
                payload,
                trace_id=trace_id,
                principal_roles=principal_roles,
                principal_attrs=principal_attrs,
                user_id=user_id,
                source_event_type=source_event_type,
            )

    def _run_inner(
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

        if should_use_m38_runtime(payload):
            delegated = delegate_to_m38_runtime(
                org_id,
                agent_name,
                trigger_type,
                payload,
                principal_roles=principal_roles,
                principal_attrs={**(principal_attrs or {}), "user_id": user_id or "m29-delegate"},
            )
            if delegated is not None:
                return self._format_m38_delegate_response(
                    org_id,
                    agent_name,
                    delegated,
                    user_id=user_id,
                    trace_id=trace_id,
                )

        delegated = self._try_m38_delegate(
            org_id,
            agent_name,
            trigger_type,
            payload,
            user_id=user_id,
            principal_roles=principal_roles,
            principal_attrs=principal_attrs,
            source_event_type=source_event_type,
        )
        if delegated is not None:
            return delegated

        if settings.m38_default_runtime:
            from app.modules.finance_os.platform_ai_runtime.services.runtime_service import runtime_service

            if runtime_service.schema_ready():
                return {
                    "execution_id": None,
                    "platform_run_id": None,
                    "status": "failed",
                    "delegated_to_m38": True,
                    "error": "m38_runtime_unavailable",
                    "confidence": 0,
                    "confidence_band": "manual",
                    "verification_status": "m38_runtime_failed",
                    "recommendations": [],
                    "flow_result": {"mode": "failed"},
                    "workflow_instance_id": None,
                }

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
            try:
                from app.modules.platform.governance.services.ai_trace_service import ai_trace_service

                ai_trace_service.record_agent_decision(
                    org_id,
                    agent_run_id=execution["id"],
                    workflow_id=None,
                    prompt=f"{agent_name}:{plan.recommendation[:200]}",
                    summary=str(plan.recommendation)[:500],
                    confidence=float(confidence.score),
                    decision={
                        "recommendation_type": plan.recommendation_type,
                        "recommendation_id": recommendation.get("id"),
                    },
                    evidence_refs=[str(recommendation.get("id") or "")],
                )
            except Exception:
                pass

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

    def _format_m38_delegate_response(
        self,
        org_id: str,
        agent_name: str,
        delegated: dict,
        *,
        user_id: str | None,
        trace_id: str | None,
    ) -> dict:
        m38 = delegated.get("m38") or {}
        status = str(delegated.get("status") or m38.get("status") or "completed")
        graph = delegated.get("graph_runtime") or {}
        return {
            "execution_id": None,
            "platform_run_id": graph.get("goal_run_id") or m38.get("goal_run_id"),
            "status": status,
            "delegated_to_m38": True,
            "goal_id": graph.get("goal_id") or m38.get("goal_id"),
            "m38": m38,
            "confidence": (m38.get("plan") or {}).get("confidence", 0) if isinstance(m38.get("plan"), dict) else 0,
            "confidence_band": (m38.get("plan") or {}).get("confidence_band", "manual")
            if isinstance(m38.get("plan"), dict)
            else "manual",
            "verification_status": "m38_runtime",
            "recommendations": [],
            "flow_result": {
                "mode": graph.get("mode") or m38.get("mode"),
                "progress_percent": graph.get("progress_percent") or m38.get("progress_percent"),
                "graph_runtime": graph,
            },
            "workflow_instance_id": None,
        }

    def _try_m38_delegate(
        self,
        org_id: str,
        agent_name: str,
        trigger_type: str,
        payload: dict,
        *,
        user_id: str | None,
        principal_roles: list[str] | None,
        principal_attrs: dict | None,
        source_event_type: str | None,
    ) -> dict | None:
        """Legacy M38 delegate helper — prefer runtime_router when m38_default_runtime is enabled."""
        if should_use_m38_runtime(payload):
            return None
        try:
            from app.modules.finance_os.platform_ai_runtime.services.runtime_service import runtime_service

            if not runtime_service.schema_ready():
                return None
            message = str(payload.get("user_message") or payload.get("query") or "").strip()
            if not message:
                entity = str(payload.get("entity_id") or payload.get("invoice_id") or "")
                message = f"Run {agent_name} analysis"
                if entity:
                    message += f" for entity {entity}"
                if source_event_type:
                    message += f" (event: {source_event_type})"
            resp = runtime_service.chat(
                org_id,
                message=message,
                user_id=user_id or "m29-delegate",
                roles=principal_roles,
                attrs={**(principal_attrs or {}), "user_id": user_id or "m29-delegate", "m29_agent": agent_name},
                human_approved=bool(payload.get("human_approved")),
            )
            return {
                "execution_id": None,
                "platform_run_id": resp.goal_run_id,
                "status": resp.status,
                "delegated_to_m38": True,
                "goal_id": resp.goal_id,
                "m38": resp.model_dump(),
                "confidence": resp.plan.confidence if resp.plan else 0,
                "confidence_band": resp.plan.confidence_band if resp.plan else "manual",
                "verification_status": "m38_runtime",
                "recommendations": [],
                "flow_result": {"mode": resp.mode, "progress_percent": resp.progress_percent},
                "workflow_instance_id": None,
            }
        except Exception:
            return None


agent_orchestration_pipeline = AgentOrchestrationPipeline()
