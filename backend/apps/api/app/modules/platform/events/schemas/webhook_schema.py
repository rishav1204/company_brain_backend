from pydantic import BaseModel, Field


class WebhookSubscriptionOut(BaseModel):
    id: str
    name: str
    target_url: str
    event_types: list[str] = Field(default_factory=list)
    is_active: bool = True
    rate_limit_per_minute: int = 60
