from __future__ import annotations

from app.modules.finance_os.agents.schemas.agents_schema import AgentContext


def summarize(context: AgentContext) -> str:
    parts = [f"Agent {context.agent_name}", f"task={context.task_type}"]
    if context.entity_id:
        parts.append(f"entity={context.entity_id}")
    parts.append(f"memory={len(context.memory_snippets)} graph={len(context.graph_paths)}")
    return "; ".join(parts)
