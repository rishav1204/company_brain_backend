from __future__ import annotations


def write_outcome(org_id: str, agent_name: str, execution_id: str, summary: str) -> None:
    if len(summary) < 20:
        return
    try:
        from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service

        memory_writer_service.write(
            org_id,
            memory_type="approval",
            entity_type="agent_execution",
            entity_id=execution_id,
            title=f"{agent_name} outcome",
            content=summary[:800],
            importance_score=65.0,
            source_event_type="agent.completed",
            force=False,
        )
    except Exception:
        pass
