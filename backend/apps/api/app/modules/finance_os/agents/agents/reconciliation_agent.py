from __future__ import annotations

from app.modules.finance_os.agents.agents.base_agent import BaseAgent
from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


class ReconciliationAgent(BaseAgent):
    name = "reconciliation_agent"

    def plan(self, context: AgentContext) -> AgentPlan:
        entity_id = context.entity_id or "bank_account"
        return AgentPlan(
            agent_name=self.name,
            task_type="bank_match",
            recommendation_type="exception_raise",
            recommendation=f"Investigate reconciliation exceptions for {entity_id}.",
            proposed_actions=[
                {"tool": "memory", "method": "search", "params": {"query": "reconciliation", "top_k": 5}},
                {"tool": "slack", "method": "postMessage", "params": {"channel": "#recon", "text": f"Review {entity_id}"}},
            ],
            workflow_key="RECONCILIATION_REVIEW",
            metadata={"entity_id": entity_id},
        )
