from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


def plan_to_payload_actions(plan: AgentPlan) -> list[dict]:
    return list(plan.proposed_actions)


def enrich_payload(context: AgentContext, plan: AgentPlan | None) -> dict:
    payload = dict(context.raw_payload)
    payload["agent_context"] = {
        "agent_name": context.agent_name,
        "task_type": context.task_type,
        "memory_count": len(context.memory_snippets),
        "graph_count": len(context.graph_paths),
        "policy_flags": context.policy_flags,
        "data_quality_score": context.data_quality_score,
    }
    if plan:
        payload["agent_plan"] = {
            "recommendation": plan.recommendation,
            "workflow_key": plan.workflow_key,
            "actions": plan.proposed_actions,
        }
    return payload
