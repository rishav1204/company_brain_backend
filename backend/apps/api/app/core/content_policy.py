"""LLM content policy layer for user prompts and tool arguments (SEC-31)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Categories beyond regex injection patterns — block credential/PII exfil and unsafe instructions.
_POLICY_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(reveal|dump|export|exfiltrate)\b.{0,40}\b(password|secret|api[_-]?key|token|credential)s?\b"), "credential_exfiltration"),
    (re.compile(r"(?i)\b(show|print|list|give)\b.{0,30}\b(all\s+)?(users?|customers?|employees?)\b.{0,30}\b(pan|ssn|aadhaar|password)s?\b"), "pii_exfiltration"),
    (re.compile(r"(?i)\b(run|execute|eval)\b.{0,20}\b(shell|bash|powershell|sql)\b"), "unsafe_execution"),
    (re.compile(r"(?i)\b(bypass|disable|turn\s+off)\b.{0,30}\b(authentication|auth|mfa|rls|permission)s?\b"), "security_bypass"),
    (re.compile(r"(?i)\b(write|generate|craft)\b.{0,30}\b(phishing|malware|ransomware)\b"), "harmful_content"),
    (re.compile(r"(?i)\baccess\b.{0,20}\b(other\s+)?(tenant|org|organization)s?\b.{0,20}\bdata\b"), "cross_tenant_access"),
    (re.compile(r"(?i)\b(org_id|organization_id)\b.{0,20}(==|:=|=)\s*['\"]?[0-9a-f-]{8,}"), "cross_tenant_param"),
    (re.compile(r"(?i)\bhuman_approved\b\s*[:=]\s*true"), "approval_flag_injection"),
    (re.compile(r"(?i)\b(post|execute)\b.{0,20}\b(journal|payment|gst\s*return)\b"), "forbidden_finance_mutation"),
)


@dataclass(frozen=True)
class ContentPolicyResult:
    allowed: bool
    violations: list[str] = field(default_factory=list)


class ContentPolicyViolation(ValueError):
    """Raised when content violates finance AI safety policy."""


def evaluate_content_policy(text: str, *, field: str = "content") -> ContentPolicyResult:
    raw = (text or "").strip()
    if not raw:
        return ContentPolicyResult(allowed=True)
    violations: list[str] = []
    for pattern, category in _POLICY_RULES:
        if pattern.search(raw):
            violations.append(category)
    return ContentPolicyResult(allowed=len(violations) == 0, violations=violations)


def enforce_content_policy(text: str, *, field: str = "content") -> str:
    result = evaluate_content_policy(text, field=field)
    if not result.allowed:
        raise ContentPolicyViolation(
            f"Content policy violation in {field}: {', '.join(result.violations)}"
        )
    return text
