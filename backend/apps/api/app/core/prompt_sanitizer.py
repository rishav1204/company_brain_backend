"""Prompt injection sanitization and structured validation for AI inputs (SEC-31)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.content_policy import ContentPolicyViolation, enforce_content_policy

_INJECTION_PATTERNS = (
    re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions"),
    re.compile(r"(?i)system\s*:\s*"),
    re.compile(r"(?i)you\s+are\s+now\s+"),
    re.compile(r"(?i)disregard\s+(all\s+)?(safety|policy|rules)"),
    re.compile(r"(?i)jailbreak"),
    re.compile(r"(?i)```\s*system"),
    re.compile(r"(?i)<\s*/?\s*system\s*>"),
    re.compile(r"(?i)\bDAN\b"),
    re.compile(r"(?i)override\s+(safety|policy|instructions)"),
    # Phase 8 Wave 3 — expanded attack surface (AI-15)
    re.compile(r"(?i)forget\s+(everything|all)\s+(you\s+)?(know|were\s+told)"),
    re.compile(r"(?i)do\s+not\s+follow\s+(your\s+)?(system|safety)\s+(prompt|policy|rules)"),
    re.compile(r"(?i)(reveal|print|show|dump)\s+(your\s+)?(system\s+prompt|hidden\s+instructions|developer\s+message)"),
    re.compile(r"(?i)(act|behave|respond)\s+as\s+(if\s+)?(you\s+have\s+)?no\s+(restrictions|limits|guardrails)"),
    re.compile(r"(?i)(tool|function)\s*:\s*\{"),
    re.compile(r"(?i)call\s+tool\s+[`'\"]?journal\.post"),
    re.compile(r"(?i)force\s+(approval|human_approved)\s*(=|:)\s*true"),
    re.compile(r"(?i)(skip|bypass)\s+(approval|policy|governance|abac|maker.?checker)"),
    re.compile(r"(?i)begin\s+(new\s+)?(system|developer)\s*(message|prompt|mode)"),
    re.compile(r"(?i)</?\s*(instruction|hidden|policy)\s*>"),
    re.compile(r"(?i)repeat\s+the\s+(above|previous)\s+(prompt|instructions)\s+(verbatim|exactly)"),
    re.compile(r"(?i)\[\s*INST\s*\]"),
    re.compile(r"(?i)<<\s*SYS\s*>>"),
)

# Pattern labels for attack classification (severity mapping is firewall-owned).
_INJECTION_LABELS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)ignore\s+(all\s+)?(previous|prior)\s+instructions"), "prompt_injection"),
    (re.compile(r"(?i)jailbreak|no\s+restrictions|no\s+guardrails"), "jailbreak"),
    (re.compile(r"(?i)(reveal|print|show|dump)\s+(your\s+)?(system\s+prompt|hidden\s+instructions)"), "system_prompt_extraction"),
    (re.compile(r"(?i)(skip|bypass)\s+(approval|policy|governance|abac)"), "policy_bypass"),
    (re.compile(r"(?i)force\s+(approval|human_approved)"), "approval_bypass"),
    (re.compile(r"(?i)(tool|function)\s*:\s*\{|call\s+tool"), "tool_manipulation"),
    (re.compile(r"(?i)</?\s*(instruction|hidden|policy)\s*>|```\s*system|<\s*/?\s*system\s*>"), "hidden_instruction"),
    (re.compile(r"(?i)forget\s+(everything|all)|begin\s+(new\s+)?(system|developer)"), "context_poisoning"),
    (re.compile(r"(?i)repeat\s+the\s+(above|previous)\s+(prompt|instructions)"), "recursive_prompting"),
)

_MAX_USER_MESSAGE_LEN = 16_000
_MAX_TOOL_STRING_LEN = 4_000


class PromptRejectedError(ValueError):
    """Raised when adversarial content is detected and reject policy applies."""


class ToolParamsRejectedError(ValueError):
    """Raised when tool arguments fail structured validation or content policy."""


def detect_adversarial_patterns(text: str) -> list[str]:
    """Return labels for injection patterns found in raw input (SEC-33 / AI-15)."""
    raw = text or ""
    hits: list[str] = []
    seen: set[str] = set()
    for pattern, label in _INJECTION_LABELS:
        if pattern.search(raw) and label not in seen:
            hits.append(label)
            seen.add(label)
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(raw):
            key = pattern.pattern
            if key not in seen:
                hits.append(key)
                seen.add(key)
    if len(raw.strip()) > _MAX_USER_MESSAGE_LEN:
        hits.append("exceeds_max_length")
    return hits


def _reject_if_adversarial(text: str, *, field: str = "prompt") -> str:
    hits = detect_adversarial_patterns(text)
    if hits:
        raise PromptRejectedError(f"Rejected adversarial content in {field}")
    try:
        enforce_content_policy(text, field=field)
    except ContentPolicyViolation as exc:
        raise PromptRejectedError(str(exc)) from exc
    return text


def sanitize_user_prompt(text: str, *, reject_on_detection: bool = True) -> str:
    """Strip injection patterns, cap length, optionally reject adversarial input."""
    cleaned = (text or "").strip()
    if reject_on_detection:
        _reject_if_adversarial(cleaned, field="user_prompt")
    if len(cleaned) > _MAX_USER_MESSAGE_LEN:
        cleaned = cleaned[:_MAX_USER_MESSAGE_LEN]
    for pattern in _INJECTION_PATTERNS:
        cleaned = pattern.sub("[filtered]", cleaned)
    return cleaned


def sanitize_tool_params(params: dict, *, reject_on_detection: bool = True) -> dict:
    """Sanitize string values in tool parameter dicts."""
    out: dict = {}
    for key, value in (params or {}).items():
        if isinstance(value, str):
            if reject_on_detection:
                _reject_if_adversarial(value, field=f"tool_param.{key}")
            out[key] = sanitize_user_prompt(value, reject_on_detection=False)[:_MAX_TOOL_STRING_LEN]
        elif isinstance(value, dict):
            out[key] = sanitize_tool_params(value, reject_on_detection=reject_on_detection)
        elif isinstance(value, list):
            out[key] = [
                sanitize_tool_params(v, reject_on_detection=reject_on_detection)
                if isinstance(v, dict)
                else (
                    sanitize_user_prompt(str(v), reject_on_detection=reject_on_detection)[:_MAX_TOOL_STRING_LEN]
                    if isinstance(v, str)
                    else v
                )
                for v in value
            ]
        else:
            out[key] = value
    return out


def validate_tool_params_against_model(model: type[BaseModel], params: dict) -> dict:
    """Structured validation: coerce and reject invalid tool arguments."""
    try:
        instance = model.model_validate(params or {})
    except ValidationError as exc:
        raise ValueError(f"Invalid tool parameters: {exc}") from exc
    return instance.model_dump()


def validate_tool_params_schema(params: dict, *, required: tuple[str, ...] = (), types: dict[str, type] | None = None) -> dict:
    """Lightweight schema validation when no Pydantic model exists."""
    types = types or {}
    missing = [r for r in required if r not in params or params[r] in (None, "")]
    if missing:
        raise ValueError(f"Missing required params: {', '.join(missing)}")
    out = dict(params)
    for key, expected in types.items():
        if key not in out or out[key] is None:
            continue
        if expected is str and not isinstance(out[key], str):
            out[key] = str(out[key])
        elif expected is int and not isinstance(out[key], int):
            out[key] = int(out[key])
        elif expected is float and not isinstance(out[key], (int, float)):
            out[key] = float(out[key])
    return out


def validate_tool_invocation(
    params: dict,
    *,
    required: tuple[str, ...] = (),
    types: dict[str, type] | None = None,
) -> dict:
    """Structured tool-arg validation: injection filter + content policy + schema."""
    try:
        cleaned = sanitize_tool_params(params or {}, reject_on_detection=True)
        if required or types:
            cleaned = validate_tool_params_schema(cleaned, required=required, types=types)
        return cleaned
    except (PromptRejectedError, ContentPolicyViolation, ValueError) as exc:
        raise ToolParamsRejectedError(str(exc)) from exc
