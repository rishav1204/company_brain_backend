from datetime import datetime
from pydantic import BaseModel, Field


class MemoryRecordRequest(BaseModel):
    memory_type: str
    subject_ref: str
    payload_jsonb: dict
    relevance_score: float = Field(ge=0, le=1)


class MemoryRecordItem(BaseModel):
    id: str
    memory_type: str
    subject_ref: str
    payload_jsonb: dict
    relevance_score: float
    created_at: datetime


class MemoryListResponse(BaseModel):
    request_id: str
    items: list[MemoryRecordItem]
    confidence: float
    verification_status: str
