from dataclasses import dataclass


@dataclass
class ExtractionModel:
    id: str
    document_id: str
    extraction_type: str
    confidence_score: float
    extraction_status: str
