from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentContext, AgentPlan


class BaseAgent:
    name: str = "base_agent"

    def plan(self, context: AgentContext) -> AgentPlan | None:
        raise NotImplementedError
