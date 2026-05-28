from dataclasses import dataclass


@dataclass
class ClassificationModel:
    id: str
    document_id: str
    classification: str
    confidence_score: float
