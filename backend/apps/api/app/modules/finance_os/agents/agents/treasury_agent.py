from __future__ import annotations

from app.modules.finance_os.agents.agents.base_agent import BaseAgent
from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


class TreasuryAgent(BaseAgent):
    name = "treasury_agent"

    def plan(self, context: AgentContext) -> AgentPlan:
        return AgentPlan(
            agent_name=self.name,
            task_type="liquidity_advisory",
            recommendation_type="exception_raise",
            recommendation="Liquidity risk detected; review cash position and forecasts.",
            proposed_actions=[
                {"tool": "email", "method": "send", "params": {"subject": "Liquidity advisory", "body": "Treasury review recommended."}},
            ],
            workflow_key=None,
            metadata={"advisory_only": True},
        )
