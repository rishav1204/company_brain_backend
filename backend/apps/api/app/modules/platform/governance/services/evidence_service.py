from __future__ import annotations

from app.modules.platform.governance.explainability.evidence_linker import link_evidence
from app.modules.platform.governance.repositories.evidence_repository import evidence_repository


class EvidenceService:
    def link(self, org_id: str, **kwargs) -> dict:
        return link_evidence(org_id, **kwargs)

    def list_for_entity(self, org_id: str, *, entity_type: str, entity_id: str) -> list[dict]:
        return evidence_repository.list_for_entity(org_id, entity_type=entity_type, entity_id=entity_id)


evidence_service = EvidenceService()
