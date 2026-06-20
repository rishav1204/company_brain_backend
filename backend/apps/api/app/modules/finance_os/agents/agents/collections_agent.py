from __future__ import annotations

from app.modules.finance_os.agents.agents.base_agent import BaseAgent
from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


class CollectionsAgent(BaseAgent):
    name = "collections_agent"

    def plan(self, context: AgentContext) -> AgentPlan:
        entity_id = context.entity_id or "invoice"
        return AgentPlan(
            agent_name=self.name,
            task_type="collection_followup",
            recommendation_type="collection_action",
            recommendation=f"Send collections follow-up for overdue {entity_id}.",
            proposed_actions=[
                {"tool": "email", "method": "send", "params": {"subject": "Payment reminder", "body": f"Follow up {entity_id}"}},
            ],
            workflow_key="COLLECTION_FOLLOWUP",
            metadata={"entity_id": entity_id},
        )
