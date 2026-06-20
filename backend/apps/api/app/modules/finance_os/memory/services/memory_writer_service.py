from __future__ import annotations

from app.modules.finance_os.memory.engine.embedding_engine import embed_text
from app.modules.finance_os.memory.engine.importance_engine import (
    default_ttl_for_band,
    importance_band,
    passes_importance_gate,
)
from app.modules.finance_os.memory.events.memory_events import (
    emit_high_importance_detected,
    emit_memory_created,
    emit_memory_updated,
)
from app.modules.finance_os.memory.repositories.embedding_repository import embedding_repository
from app.modules.finance_os.memory.repositories.entry_repository import entry_repository
from app.modules.finance_os.memory.repositories.reference_repository import reference_repository
from app.services.repositories import memory_repo


def _subject_ref(entity_type: str | None, entity_id: str | None, memory_type: str) -> str:
    if entity_type and entity_id:
        return f"{entity_type}:{entity_id}"
    if entity_type:
        return entity_type
    return memory_type


def _link_memory_record(org_id: str, memory_id: str, memory_record_id: str | None) -> None:
    if not memory_record_id:
        return
    from app.services.db import get_db_conn, set_rls_org

    with get_db_conn() as conn:
        set_rls_org(conn, org_id)
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE finance_os.memory_entries
                SET memory_record_id = %s::uuid, updated_at = NOW()
                WHERE org_id = %s::uuid AND id = %s::uuid
                """,
                (memory_record_id, org_id, memory_id),
            )


class MemoryWriterService:
    def write(
        self,
        org_id: str,
        *,
        memory_type: str,
        title: str,
        content: str,
        importance_score: float,
        entity_type: str | None = None,
        entity_id: str | None = None,
        references: list[dict] | None = None,
        ttl_policy: str | None = None,
        source_event_type: str | None = None,
        metadata: dict | None = None,
        force: bool = False,
        trace_id: str | None = None,
    ) -> dict | None:
        band = importance_band(importance_score)
        if not passes_importance_gate(importance_score, force=force):
            return None
        policy = ttl_policy or default_ttl_for_band(band)
        prior = 0
        if entity_type and entity_id:
            prior = entry_repository.count_by_entity(org_id, entity_type=entity_type, entity_id=entity_id, memory_type=memory_type)
        entry = entry_repository.create(
            org_id,
            data={
                "memory_type": memory_type,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "title": title,
                "content": content,
                "importance_score": importance_score,
                "importance_band": band,
                "ttl_policy": policy,
                "source_event_type": source_event_type,
                "metadata": {**(metadata or {}), "prior_count": prior},
            },
        )
        memory_id = entry.get("id")
        if not memory_id:
            return None
        reference_repository.create_batch(org_id, memory_id=memory_id, references=references or [])
        try:
            vec = embed_text(org_id, f"{title}\n{content}")
            embedding_repository.create(org_id, memory_id=memory_id, embedding=vec)
        except Exception:
            pass
        subject = _subject_ref(entity_type, entity_id, memory_type)
        legacy = memory_repo.create_memory(
            org_id=org_id,
            memory_type=memory_type,
            subject_ref=subject,
            payload_jsonb={
                "title": title,
                "content": content,
                "finance_os_memory_id": memory_id,
                "status": "active",
                "importance_band": band,
            },
            relevance_score=importance_score / 100.0,
        )
        _link_memory_record(org_id, memory_id, legacy.get("id"))
        emit_memory_created(
            org_id,
            {
                "memory_id": memory_id,
                "memory_type": memory_type,
                "importance_score": importance_score,
                "importance_band": band,
                "memory_record_id": legacy.get("id"),
            },
            trace_id=trace_id,
        )
        if band == "critical":
            emit_high_importance_detected(org_id, {"memory_id": memory_id, "title": title}, trace_id=trace_id)
        return {**entry, "memory_record_id": legacy.get("id")}

    def update(
        self,
        org_id: str,
        memory_id: str,
        *,
        title: str | None = None,
        content: str | None = None,
        trace_id: str | None = None,
    ) -> dict | None:
        updated = entry_repository.update_content(org_id, memory_id, title=title, content=content)
        if updated:
            emit_memory_updated(org_id, {"memory_id": memory_id}, trace_id=trace_id)
        return updated

    def archive(self, org_id: str, memory_id: str, *, trace_id: str | None = None) -> None:
        entry_repository.update_status(org_id, memory_id, "archived")
        emit_memory_updated(org_id, {"memory_id": memory_id, "status": "archived"}, trace_id=trace_id)


memory_writer_service = MemoryWriterService()
