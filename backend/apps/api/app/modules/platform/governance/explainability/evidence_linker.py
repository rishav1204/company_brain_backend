from __future__ import annotations

from app.modules.platform.governance.repositories.evidence_repository import evidence_repository


def auto_link_entity_evidence(
    org_id: str,
    *,
    entity_type: str,
    entity_id: str,
    evidence_type: str,
    evidence_ref: str,
    metadata: dict | None = None,
) -> dict:
    return link_evidence(
        org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        evidence_type=evidence_type,
        evidence_ref=evidence_ref,
        metadata=metadata,
    )


def link_evidence(
    org_id: str,
    *,
    entity_type: str,
    entity_id: str,
    evidence_type: str,
    evidence_ref: str,
    metadata: dict | None = None,
) -> dict:
    if not evidence_repository.schema_ready():
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "evidence_type": evidence_type,
            "evidence_ref": evidence_ref,
            "status": "skipped",
        }
    return evidence_repository.link(
        org_id,
        entity_type=entity_type,
        entity_id=entity_id,
        evidence_type=evidence_type,
        evidence_ref=evidence_ref,
        metadata=metadata,
    )
