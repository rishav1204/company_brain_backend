from __future__ import annotations

from app.modules.finance_os.memory.engine.importance_engine import compute_importance


def extract(event_type: str, payload: dict) -> dict | None:
    if event_type in {"journal.posted", "erp.journal.posted"}:
        account = payload.get("account_code") or payload.get("ledger_account") or "account"
        return {
            "memory_type": "accounting",
            "entity_type": "account",
            "entity_id": None,
            "title": f"Journal posted to {account}",
            "content": f"Journal entry posted involving {account}",
            "importance_score": compute_importance(event_type=event_type),
            "references": [{"source_type": "journal", "source_id": payload.get("journal_id")}],
            "ttl_policy": "90d",
            "metadata": {"account_code": account},
        }
    if event_type == "invoice.predicted":
        override = bool(payload.get("human_override") or payload.get("override"))
        vendor = payload.get("vendor_name") or "Vendor"
        ledger = payload.get("suggested_ledger") or payload.get("ledger_account")
        if not override and not ledger:
            return None
        content = f"Ledger suggestion for {vendor}"
        if ledger:
            content += f": {ledger}"
        if override:
            content += " (human override applied)"
        return {
            "memory_type": "accounting",
            "entity_type": "vendor",
            "entity_id": str(payload.get("vendor_id")) if payload.get("vendor_id") else None,
            "title": f"{vendor} ledger pattern",
            "content": content,
            "importance_score": compute_importance(event_type=event_type, override=override),
            "references": [{"source_type": "invoice_prediction", "source_id": payload.get("prediction_id")}],
            "ttl_policy": "180d",
        }
    return None
