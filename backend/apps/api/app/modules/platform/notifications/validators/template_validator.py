import re


def validate_template_body(body: str) -> None:
    if not body.strip():
        raise ValueError("body_template required")
    if len(body) > 50000:
        raise ValueError("body_template too large")


def validate_template_key(template_key: str) -> None:
    if not re.match(r"^[a-z0-9_]+$", template_key):
        raise ValueError("template_key must be lowercase alphanumeric with underscores")
