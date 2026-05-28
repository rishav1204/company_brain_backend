from datetime import datetime
from pydantic import BaseModel


class SourceCreateRequest(BaseModel):
    source_type: str
    config_ref: str
    source_ref: str | None = None


class SourceResponse(BaseModel):
    id: str
    source_type: str
    status: str
    last_sync_at: datetime | None = None


class SourceListResponse(BaseModel):
    request_id: str
    items: list[SourceResponse]
    confidence: float
    verification_status: str


class IngestionRunResponse(BaseModel):
    id: str
    source_id: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    error_summary: str | None = None


class IngestionRunListResponse(BaseModel):
    request_id: str
    items: list[IngestionRunResponse]
    confidence: float
    verification_status: str
