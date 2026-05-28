from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.modules.platform.notifications.repositories.template_repository import template_repository

_TEMPLATE_ROOT = Path(__file__).resolve().parent.parent / "templates"


def mask_sensitive_value(key: str, value: Any) -> str:
    sensitive = {"pan", "aadhaar", "account_number", "bank_account", "ifsc"}
    if str(key).lower() in sensitive and value:
        raw = str(value)
        return f"XXXXXX{raw[-4:]}" if len(raw) > 4 else "XXXX"
    return str(value)


def _apply_conditionals(template: str, variables: dict) -> str:
    pattern = r"\{%\s*if\s+(\w+)\s*%\}(.*?)\{%\s*endif\s*%\}"
    def repl(match: re.Match) -> str:
        key = match.group(1)
        block = match.group(2)
        return block if variables.get(key) else ""
    return re.sub(pattern, repl, template, flags=re.DOTALL)


def _load_file_template(template_key: str, channel: str) -> str | None:
    for sub in (channel, "email"):
        path = _TEMPLATE_ROOT / sub / f"{template_key}.txt"
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return None


class TemplateService:
    def render(self, org_id: str, *, template_key: str, channel: str, variables: dict) -> tuple[str | None, str]:
        row = None
        try:
            row = template_repository.get_template(org_id, template_key=template_key, channel=channel)
        except Exception:
            row = None
        safe_vars = {k: mask_sensitive_value(k, v) for k, v in variables.items()}

        def repl(match: re.Match) -> str:
            key = match.group(1).strip()
            return safe_vars.get(key, "")

        if row:
            body_tpl = _apply_conditionals(row.get("body_template") or "", safe_vars)
            body = re.sub(r"\{\{\s*(\w+)\s*\}\}", repl, body_tpl)
            subject = row.get("subject_template")
            if subject:
                subject = re.sub(r"\{\{\s*(\w+)\s*\}\}", repl, _apply_conditionals(subject, safe_vars))
            return subject, body

        file_tpl = _load_file_template(template_key, channel)
        if file_tpl:
            body = re.sub(r"\{\{\s*(\w+)\s*\}\}", repl, _apply_conditionals(file_tpl, safe_vars))
            subject = variables.get("subject") or f"Finance OS — {template_key.replace('_', ' ').title()}"
            return str(subject) if subject else None, body

        body = variables.get("body") or f"[{template_key}] {safe_vars}"
        return variables.get("subject"), str(body)


template_service = TemplateService()
