from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentPlan


def advise(plan: AgentPlan) -> dict:
    return {
        "workflow_key": plan.workflow_key,
        "action_count": len(plan.proposed_actions),
        "safe": plan.metadata.get("filing_forbidden") is not True,
    }
