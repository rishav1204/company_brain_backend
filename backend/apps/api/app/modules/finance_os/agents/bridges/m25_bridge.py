from __future__ import annotations


def invoice_context(org_id: str, invoice_id: str) -> dict:
    if not invoice_id:
        return {}
    return {"invoice_id": invoice_id, "org_id": org_id}
