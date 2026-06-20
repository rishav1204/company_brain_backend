from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ExtractRequest(BaseModel):
    document_id: str
    invoice_type: str = "purchase"


class ExtractResponse(BaseModel):
    extraction_id: str
    document_id: str
    invoice_number: str | None = None
    vendor_name: str | None = None
    vendor_gstin: str | None = None
    total_amount: float = 0
    extraction_confidence: float = 0
    confidence_band: str = "manual_review"


class PredictRequest(BaseModel):
    extraction_id: str


class PredictionItem(BaseModel):
    id: str
    prediction_type: str
    suggested_account_id: str | None = None
    suggested_gst_code: str | None = None
    confidence_score: float = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PredictResponse(BaseModel):
    extraction_id: str
    predictions: list[PredictionItem]
    overall_confidence: float = 0
    confidence_band: str = "manual_review"


class DuplicateScoreResponse(BaseModel):
    extraction_id: str
    status: str
    similarity_score: float = 0
    matched_invoice_id: str | None = None
    score_breakdown: dict[str, Any] = Field(default_factory=dict)


class AnomalyItem(BaseModel):
    id: str
    anomaly_type: str
    anomaly_score: float
    severity: str
    description: str
    status: str = "open"


class AnomalyListResponse(BaseModel):
    extraction_id: str
    anomalies: list[AnomalyItem]


class CopilotRequest(BaseModel):
    extraction_id: str
    question: str


class CopilotResponse(BaseModel):
    answer: str
    extraction_id: str


class ConfirmDuplicateRequest(BaseModel):
    extraction_id: str
    matched_invoice_id: str | None = None
    status: str = "confirmed"


class OverridePredictionRequest(BaseModel):
    prediction_id: str
    suggested_account_id: str | None = None
    suggested_gst_code: str | None = None


class PipelineResult(BaseModel):
    extraction_id: str
    document_id: str
    confidence_band: str
    duplicate_status: str = "clean"
    anomaly_count: int = 0
    auto_draft_eligible: bool = False
