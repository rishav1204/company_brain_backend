"""Normalize user identifiers (email vs UUID) for SoD and audit consistency."""

from __future__ import annotations

from app.modules.core.iam.repositories import user_repo

DEV_USER_UUID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
DEV_USER_EMAIL = "dev@example.com"


def resolve_user_id(org_id: str, raw_user_id: str | None) -> str | None:
    if not raw_user_id or not str(raw_user_id).strip():
        return None
    value = str(raw_user_id).strip()
    if "@" in value:
        row = user_repo.get_by_email(value)
        if row and str(row.get("org_id")) == str(org_id):
            return str(row["id"])
        if value.lower() == DEV_USER_EMAIL.lower():
            return DEV_USER_UUID
        return value
    return value


def same_actor(org_id: str, left: str | None, right: str | None) -> bool:
    left_id = resolve_user_id(org_id, left)
    right_id = resolve_user_id(org_id, right)
    if not left_id or not right_id:
        return False
    return left_id == right_id
