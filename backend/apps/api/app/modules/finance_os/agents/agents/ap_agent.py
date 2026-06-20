from __future__ import annotations

from app.modules.finance_os.agents.agents.base_agent import BaseAgent
from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


class ApAgent(BaseAgent):
    name = "ap_agent"

    def plan(self, context: AgentContext) -> AgentPlan:
        entity_id = context.entity_id or "invoice"
        return AgentPlan(
            agent_name=self.name,
            task_type="invoice_review",
            recommendation_type="workflow_launch",
            recommendation=f"Review AP invoice {entity_id} for exceptions and launch approval workflow if needed.",
            proposed_actions=[
                {"tool": "memory", "method": "search", "params": {"query": f"AP {entity_id}", "top_k": 5}},
                {"tool": "graph", "method": "traverse", "params": {"entity_id": entity_id, "max_depth": 4}},
                {"tool": "email", "method": "send", "params": {"subject": "AP review", "body": "AP agent recommendation ready."}},
            ],
            workflow_key="AP_INVOICE_APPROVAL",
            metadata={"entity_id": entity_id},
        )
