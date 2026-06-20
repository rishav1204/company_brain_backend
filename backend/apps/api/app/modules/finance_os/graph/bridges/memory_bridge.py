from __future__ import annotations


def write_causal_summary(org_id: str, entity_id: str, chain: dict) -> None:
    try:
        from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service

        explanation = chain.get("explanation")
        if isinstance(explanation, list):
            content = " | ".join(str(e) for e in explanation[:5])
        else:
            content = str(explanation or "")
        if not content:
            return
        memory_writer_service.write(
            org_id,
            memory_type="accounting",
            entity_type="graph_entity",
            entity_id=entity_id,
            title=f"Causal chain for {entity_id}",
            content=content[:800],
            importance_score=72.0,
            source_event_type="graph.root_cause.generated",
            force=True,
        )
    except Exception:
        pass
