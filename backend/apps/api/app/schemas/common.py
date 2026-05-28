from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_type: str
    source_ref: str
    confidence: float = Field(ge=0, le=1)
    span_start: int | None = None
    span_end: int | None = None


class ApiMeta(BaseModel):
    request_id: str
    confidence: float = Field(ge=0, le=1)
    verification_status: str


class ApiResponse(BaseModel):
    request_id: str
    confidence: float = Field(ge=0, le=1)
    verification_status: str
