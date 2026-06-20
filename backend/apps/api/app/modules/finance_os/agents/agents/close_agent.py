from __future__ import annotations

from app.modules.finance_os.agents.agents.base_agent import BaseAgent
from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


class CloseAgent(BaseAgent):
    name = "close_agent"

    def plan(self, context: AgentContext) -> AgentPlan:
        period = context.entity_id or context.raw_payload.get("period_id", "current")
        return AgentPlan(
            agent_name=self.name,
            task_type="period_close",
            recommendation_type="workflow_launch",
            recommendation=f"Run period close checklist for {period}.",
            proposed_actions=[
                {"tool": "workflow", "method": "updateStatus", "params": {"state": "close_orchestration_running"}},
                {"tool": "jira", "method": "createIssue", "params": {"summary": "Period close", "description": "Agent checklist"}},
            ],
            workflow_key="PERIOD_CLOSE",
            metadata={"period_id": period},
        )
