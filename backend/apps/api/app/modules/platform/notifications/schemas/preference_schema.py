from pydantic import BaseModel, Field


class PreferenceOut(BaseModel):
    channel: str
    notification_type: str
    enabled: bool
    quiet_hours: dict = Field(default_factory=dict)
