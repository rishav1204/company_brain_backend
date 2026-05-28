from __future__ import annotations

from app.modules.platform.integrations.repositories.ingestion_repository import ingestion_repository


class IngestionService:
    def create(self, org_id: str, *, source_type: str, source_reference: str | None, payload: dict) -> dict:
        row = ingestion_repository.create(
            org_id,
            source_type=source_type,
            source_reference=source_reference,
            payload=payload or {},
            status="received",
        )
        # Emit event for workers to process (reuse existing event bus).
        try:
            from app.services.event_bus import event_bus

            event_bus.publish(
                event_type="integration.ingestion.received",
                org_id=org_id,
                source="integrations",
                trace_id="",
                entity_type="ingestion_record",
                entity_id=str(row.get("id") or ""),
                payload={"source_type": source_type, "source_reference": source_reference, "record_id": row.get("id"), **(payload or {})},
            )
        except Exception:
            pass
        return row

    def list(self, org_id: str) -> list[dict]:
        return ingestion_repository.list(org_id)


ingestion_service = IngestionService()

