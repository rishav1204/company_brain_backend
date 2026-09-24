from __future__ import annotations

from typing import Any

from fastapi import HTTPException


from app.modules.platform.billing.security.billing_enforce import enforce_billing

_ADMIN_ROLES = {"tenant_admin", "cfo", "controller"}


def _field(user: Any, name: str) -> Any:
    if isinstance(user, dict):
        return user.get(name)
    return getattr(user, name, None)


def _check(user: Any, allowed_perms: set[str], detail: str) -> None:
    enforce_billing(_field(user, "org_id"), "invoice_ai")
    perms = {str(p).lower() for p in (_field(user, "permissions") or [])}
    roles = {str(r).lower() for r in (_field(user, "roles") or [])}
    if "*" in perms or perms & allowed_perms or roles & _ADMIN_ROLES:
        return
    raise HTTPException(status_code=403, detail=detail)


def require_invoice_ai_read(user: Any) -> None:
    _check(
        user,
        {"invoice_ai.read", "invoice_ai.write", "ap.read", "ap.write", "documents.read"},
        "invoice_ai.read permission required",
    )


def require_invoice_ai_write(user: Any) -> None:
    _check(user, {"invoice_ai.write", "ap.write"}, "invoice_ai.write permission required")
