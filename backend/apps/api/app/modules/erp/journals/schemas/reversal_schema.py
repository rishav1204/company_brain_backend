from __future__ import annotations

from pydantic import BaseModel


class JournalReverseRequest(BaseModel):
    reversal_reason: str | None = None
    approver_id: str | None = None
