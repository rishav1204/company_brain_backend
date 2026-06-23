from __future__ import annotations

import re

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.I,
)


def require_org_id(org_id: str | None, *, context: str = "event_publish") -> str:
    normalized = str(org_id or "").strip()
    if not normalized:
        raise ValueError(f"org_id is required for {context}")
    if not _UUID_RE.match(normalized):
        raise ValueError(f"org_id must be a valid UUID for {context}")
    return normalized


def assert_event_erp_company_scope(
    *,
    org_id: str,
    company_id: str | None,
    operation: str,
) -> str:
    from app.modules.erp.security.company_scope import require_company_id_for_erp_write

    return require_company_id_for_erp_write(
        org_id=org_id,
        company_id=company_id,
        operation=operation,
        attrs=None,
    )
