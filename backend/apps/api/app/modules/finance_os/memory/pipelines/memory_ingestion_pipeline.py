from __future__ import annotations

from app.modules.finance_os.memory.ai.knowledge_extractor import extract_from_event
from app.modules.finance_os.memory.services.memory_writer_service import memory_writer_service


class MemoryIngestionPipeline:
    def run_from_event(self, envelope: dict) -> dict | None:
        event_type = str(envelope.get("event_type", ""))
        payload = envelope.get("payload") or {}
        org_id = str(envelope.get("org_id", ""))
        if not org_id:
            return None
        if payload.get("memory_record_id") and not payload.get("content"):
            return None
        extracted = extract_from_event(event_type, payload)
        if not extracted:
            return None
        return memory_writer_service.write(
            org_id,
            memory_type=extracted["memory_type"],
            entity_type=extracted.get("entity_type"),
            entity_id=extracted.get("entity_id"),
            title=extracted["title"],
            content=extracted["content"],
            importance_score=float(extracted.get("importance_score", 55)),
            references=extracted.get("references"),
            ttl_policy=extracted.get("ttl_policy"),
            source_event_type=event_type,
            metadata=extracted.get("metadata"),
            trace_id=str(envelope.get("trace_id") or ""),
        )

    def run_manual(self, org_id: str, *, data: dict, force: bool = True, trace_id: str | None = None) -> dict | None:
        return memory_writer_service.write(
            org_id,
            memory_type=data["memory_type"],
            entity_type=data.get("entity_type"),
            entity_id=data.get("entity_id"),
            title=data["title"],
            content=data["content"],
            importance_score=float(data.get("importance_score", 60)),
            references=data.get("references"),
            ttl_policy=data.get("ttl_policy"),
            source_event_type=data.get("source_event_type", "manual"),
            metadata=data.get("metadata"),
            force=force,
            trace_id=trace_id,
        )


memory_ingestion_pipeline = MemoryIngestionPipeline()
