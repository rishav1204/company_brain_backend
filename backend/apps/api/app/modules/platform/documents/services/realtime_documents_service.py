from __future__ import annotations

from app.modules.workflows.services.realtime_hub import workflow_realtime_hub


class RealtimeDocumentsService:
    def publish(self, org_id: str, event: dict) -> None:
        workflow_realtime_hub.publish(org_id, event)

    def push_document_event(self, org_id: str, *, event_type: str, document_id: str, payload: dict | None = None) -> None:
        self.publish(
            org_id,
            {
                "event_type": event_type,
                "channel": "documents",
                "document_id": document_id,
                "payload": payload or {},
            },
        )


realtime_documents_service = RealtimeDocumentsService()

