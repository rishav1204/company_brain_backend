from __future__ import annotations

from pydantic import BaseModel, Field, HttpUrl


class WebhookSubscriptionCreateRequest(BaseModel):
    endpoint_url: HttpUrl
    event_types: list[str] = Field(default_factory=list)

