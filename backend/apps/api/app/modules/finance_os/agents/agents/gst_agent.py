from __future__ import annotations

from app.modules.finance_os.agents.agents.base_agent import BaseAgent
from app.modules.finance_os.agents.schemas.agents_schema import AgentPlan, AgentContext


class GstAgent(BaseAgent):
    name = "gst_agent"

    def plan(self, context: AgentContext) -> AgentPlan:
        entity_id = context.entity_id or "gst_return"
        return AgentPlan(
            agent_name=self.name,
            task_type="gst_review",
            recommendation_type="workflow_launch",
            recommendation=f"Prepare GST review package for {entity_id}; human must file.",
            proposed_actions=[
                {"tool": "memory", "method": "search", "params": {"query": "GST compliance", "top_k": 5}},
                {"tool": "email", "method": "send", "params": {"subject": "GST review", "body": "Review before filing."}},
            ],
            workflow_key="GST_REVIEW",
            metadata={"entity_id": entity_id, "filing_forbidden": True},
        )
