from __future__ import annotations

from app.modules.finance_os.memory.engine.summarization_engine import build_summary_title, summarize_entries
from app.modules.finance_os.memory.repositories.entry_repository import entry_repository
from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service

DEFAULT_THRESHOLD = 20


def summarize_entity(
    org_id: str,
    *,
    entity_type: str,
    entity_id: str,
    memory_type: str,
    threshold: int = DEFAULT_THRESHOLD,
    trace_id: str | None = None,
) -> dict | None:
    entries = entry_repository.list_active(
        org_id, entity_type=entity_type, entity_id=entity_id, memory_type=memory_type, limit=500
    )
    active = [e for e in entries if e.get("status", "active") == "active"]
    if len(active) < threshold:
        return None
    summary_text = summarize_entries(active)
    title = build_summary_title(memory_type, entity_type, len(active))
    for e in active:
        entry_repository.update_status(org_id, e["id"], "summarized")
    result = memory_writer_service.write(
        org_id,
        memory_type=memory_type,
        entity_type=entity_type,
        entity_id=entity_id,
        title=title,
        content=summary_text,
        importance_score=72.0,
        ttl_policy="forever",
        source_event_type="memory.summarized",
        metadata={"summarized_count": len(active)},
        force=True,
        trace_id=trace_id,
    )
    if result:
        from app.modules.finance_os.memory.events.memory_events import emit_memory_summarized

        emit_memory_summarized(
            org_id,
            {"memory_id": result.get("id"), "entity_type": entity_type, "entity_id": entity_id},
            trace_id=trace_id,
        )
    return result
