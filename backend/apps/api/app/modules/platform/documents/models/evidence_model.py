from dataclasses import dataclass


@dataclass
class EvidenceModel:
    id: str
    document_id: str
    entity_type: str
    entity_id: str
