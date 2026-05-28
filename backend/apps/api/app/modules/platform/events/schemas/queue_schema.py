from pydantic import BaseModel, Field


class QueueStatusOut(BaseModel):
    name: str
    lag: int = 0
    dlq_depth: int = 0


class QueueSummaryOut(BaseModel):
    queues: dict[str, str] = Field(default_factory=dict)
    lag: dict[str, int] = Field(default_factory=dict)
    dlq_depth: dict[str, int] = Field(default_factory=dict)
