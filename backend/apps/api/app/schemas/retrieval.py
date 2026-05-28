from pydantic import BaseModel

from app.schemas.common import Citation


class QueryContextRequest(BaseModel):
    query: str
    subject_ref: str | None = None
    top_k: int = 5
    metadata_filter: dict | None = None


class QueryContextResponse(BaseModel):
    request_id: str
    context: list[str]
    citations: list[Citation]
    confidence: float
    verification_status: str


class QueryExplainRequest(BaseModel):
    query: str
    subject_ref: str | None = None


class QueryExplainResponse(BaseModel):
    request_id: str
    answer: str
    graph_trace: list[str]
    citations: list[Citation]
    confidence: float
    verification_status: str
