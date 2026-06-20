from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


def build_steps(context: AgentContext, plan: AgentPlan) -> list[dict]:
    steps = [{"step": "gather_context", "detail": f"memory={len(context.memory_snippets)}"}]
    for idx, action in enumerate(plan.proposed_actions, start=1):
        steps.append({"step": f"action_{idx}", "tool": action.get("tool"), "method": action.get("method")})
    if plan.workflow_key:
        steps.append({"step": "workflow_launch", "workflow_key": plan.workflow_key})
    return steps
