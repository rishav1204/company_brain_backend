from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentContext


def workflow_hints(context: AgentContext) -> dict:
    wf = context.erp_facts.get("workflow") or {}
    return {"health": wf, "bottleneck_risk": bool(wf.get("bottlenecks"))}
