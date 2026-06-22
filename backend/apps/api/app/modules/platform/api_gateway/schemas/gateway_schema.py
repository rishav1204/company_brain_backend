from __future__ import annotations

from pydantic import BaseModel, Field


class ApiKeyCreateRequest(BaseModel):
    name: str
    scopes: list[str] = Field(default_factory=list)
    key_tier: str = "partner"
    ip_allowlist: list[str] = Field(default_factory=list)
    rate_limit_per_minute: int = 100
    rate_limit_per_hour: int = 1000


class WebhookCreateRequest(BaseModel):
    webhook_url: str
    subscribed_events: list[str] = Field(default_factory=list)
    name: str | None = None
