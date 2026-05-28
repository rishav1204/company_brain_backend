from __future__ import annotations


def validate_audit_entry(entry: dict) -> None:
    action = str(entry.get("action", "")).strip()
    object_ref = str(entry.get("object_ref", "")).strip()
    if not action:
        raise ValueError("audit action is required")
    if not object_ref:
        raise ValueError("audit object_ref is required")
