from __future__ import annotations

from pydantic import BaseModel, Field


class CoaImportRow(BaseModel):
    group_code: str = Field(min_length=1, max_length=64)
    group_name: str = Field(min_length=2, max_length=256)
    group_type: str = Field(min_length=3, max_length=32)
    nature: str = Field(min_length=4, max_length=16)
    parent_group_code: str | None = Field(default=None, max_length=64)

    account_code: str = Field(min_length=1, max_length=64)
    account_name: str = Field(min_length=2, max_length=256)
    account_type: str = Field(min_length=3, max_length=32)
    parent_account_code: str | None = Field(default=None, max_length=64)
    is_postable: bool = True
    currency_code: str = Field(default="INR", max_length=8)


class CoaImportRequest(BaseModel):
    rows: list[CoaImportRow] = Field(default_factory=list, max_length=5000)

