from __future__ import annotations

from app.modules.platform.documents.repositories.evidence_repository import evidence_repository


class EvidenceService:
    def link(
        self,
        org_id: str,
        *,
        document_id: str,
        entity_type: str,
        entity_id: str,
        workflow_id: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        return evidence_repository.link_document(
            org_id,
            document_id=document_id,
            entity_type=entity_type,
            entity_id=entity_id,
            workflow_id=workflow_id,
            metadata=metadata or {},
        )

    def list_for_entity(self, org_id: str, *, entity_type: str, entity_id: str) -> list[dict]:
        return evidence_repository.list_for_entity(org_id, entity_type=entity_type, entity_id=entity_id)


evidence_service = EvidenceService()
