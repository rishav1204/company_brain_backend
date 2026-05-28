from dataclasses import dataclass


@dataclass
class TemplateRecord:
    id: str
    template_key: str
    channel: str
    body_template: str
    subject_template: str | None = None
