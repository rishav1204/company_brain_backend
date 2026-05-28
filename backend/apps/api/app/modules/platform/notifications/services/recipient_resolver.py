from __future__ import annotations


def resolve_user_contact(org_id: str, user_id: str | None) -> dict[str, str | None]:
    if not user_id:
        return {"user_id": None, "email": None, "display_name": None}
    try:
        from app.modules.core.iam.repositories.user_repository import UserRepository

        user = UserRepository().get_by_id(org_id, user_id)
        if not user:
            return {"user_id": user_id, "email": None, "display_name": None}
        return {
            "user_id": user_id,
            "email": user.get("email"),
            "display_name": user.get("display_name"),
        }
    except Exception:
        return {"user_id": user_id, "email": None, "display_name": None}


def enrich_recipients(org_id: str, recipients: list[dict]) -> list[dict]:
    out: list[dict] = []
    for recipient in recipients:
        uid = recipient.get("user_id")
        contact = resolve_user_contact(org_id, str(uid) if uid else None)
        out.append(
            {
                "user_id": contact.get("user_id") or uid,
                "email": recipient.get("email") or contact.get("email"),
                "display_name": contact.get("display_name"),
            }
        )
    return out
