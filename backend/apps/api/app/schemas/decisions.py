from datetime import datetime
from pydantic import BaseModel

from app.schemas.common import Citation


class DecisionCreateRequest(BaseModel):
    decision_type: str
    title: str
    rationale: str
    made_by: str
    citations: list[Citation] = []


class DecisionItem(BaseModel):
    id: str
    decision_type: str
    title: str
    rationale: str
    made_by: str
    decided_at: datetime


class DecisionListResponse(BaseModel):
    request_id: str
    items: list[DecisionItem]
    confidence: float
    verification_status: str
