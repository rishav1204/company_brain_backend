from pydantic import BaseModel, Field


class TemplateOut(BaseModel):
    id: str
    template_key: str
    channel: str
    subject_template: str | None = None
    is_active: bool = True


class TemplateCreateIn(BaseModel):
    template_key: str
    channel: str
    body_template: str
    subject_template: str | None = None
    variables: list[str] = Field(default_factory=list)
