from __future__ import annotations

from app.modules.platform.documents.repositories.document_repository import document_repository
from app.services.event_bus import event_bus


class DocumentRetentionService:
    def enforce_retention(self, org_id: str, *, limit: int = 200) -> dict:
        expired = document_repository.list_retention_expired(org_id, limit=limit)
        for row in expired:
            document_repository.update_status(org_id, document_id=row["id"], status="expired")
            event_bus.publish(
                event_type="document.retention.expired",
                org_id=org_id,
                source="documents.retention",
                trace_id="",
                entity_type="document",
                entity_id=row["id"],
                payload={"document_id": row["id"], "retention_until": row.get("retention_until")},
            )
        return {"expired_count": len(expired)}


document_retention_service = DocumentRetentionService()

