from __future__ import annotations

from fastapi import HTTPException


from app.modules.platform.billing.security.billing_enforce import enforce_billing


def require_invoice_ai_read(user: dict) -> None:
    enforce_billing(user.get("org_id"), "invoice_ai")
    perms = set(user.get("permissions") or [])
    if "invoice_ai.read" in perms or "ap.read" in perms or "documents.read" in perms:
        return
    raise HTTPException(status_code=403, detail="invoice_ai.read permission required")


def require_invoice_ai_write(user: dict) -> None:
    enforce_billing(user.get("org_id"), "invoice_ai")
    perms = set(user.get("permissions") or [])
    if "invoice_ai.write" in perms or "ap.write" in perms:
        return
    raise HTTPException(status_code=403, detail="invoice_ai.write permission required")
