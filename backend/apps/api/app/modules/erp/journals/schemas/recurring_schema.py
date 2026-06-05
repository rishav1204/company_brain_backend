from __future__ import annotations

from pydantic import BaseModel, Field


class RecurringJournalCreateRequest(BaseModel):
    template_name: str = Field(min_length=2, max_length=128)
    frequency: str = Field(min_length=4, max_length=32)
    next_run_date: str = Field(min_length=10, max_length=10)
    journal_template: dict = Field(default_factory=dict)
    company_id: str | None = None
