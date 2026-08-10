"""Cross-org operator actions.

Mutations here resolve the target user's org and then delegate to the ordinary
org-scoped IAM repositories. Nothing about suspending a user differs because a
platform operator did it, so reusing those paths keeps one implementation of the
behaviour — including "suspend also kills live sessions", which is the whole
point of a block button.

Every action is written to the *target tenant's* audit log, so a customer
investigating their own history sees that the platform operator acted, not a
phantom change with no actor.
"""
from typing import Any

from app.modules.core.iam.repositories import session_repo, user_repo
from app.modules.platform.operator.repositories import operator_repository
from app.services.repositories import audit_repo

VALID_USER_STATUSES = ("active", "suspended", "deactivated")


class OperatorError(Exception):
    """Raised for operator actions that are refused on policy grounds."""


class UserNotFound(OperatorError):
    pass


class OperatorService:
    def __init__(self, *, repository=None, users=None, sessions=None, audit=None) -> None:
        self._repo = repository or operator_repository
        self._users = users or user_repo
        self._sessions = sessions or session_repo
        self._audit_repo = audit or audit_repo

    def list_organizations(self, *, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        items = self._repo.list_organizations(limit=limit, offset=offset)
        return {"items": items, "count": len(items), "total": self._repo.count_organizations()}

    def list_users(
        self,
        *,
        org_id: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        items = self._repo.list_users(
            org_id=org_id, status=status, search=search, limit=limit, offset=offset
        )
        total = self._repo.count_users(org_id=org_id, status=status, search=search)
        return {"items": items, "count": len(items), "total": total}

    def usage_by_org(self, *, days: int = 30, limit: int = 100) -> dict[str, Any]:
        items = self._repo.usage_by_org(days=days, limit=limit)
        return {"items": items, "count": len(items), "window_days": days}

    def set_user_status(
        self,
        *,
        user_id: str,
        status: str,
        actor_user_id: str,
        actor_org_id: str,
    ) -> dict[str, Any]:
        if status not in VALID_USER_STATUSES:
            raise OperatorError(f"status must be one of {', '.join(VALID_USER_STATUSES)}")
        if str(user_id) == str(actor_user_id):
            raise OperatorError("Refusing to change your own status: you would lock yourself out")

        target = self._repo.find_user(user_id)
        if not target:
            raise UserNotFound(f"User not found: {user_id}")

        target_org_id = target["org_id"]
        row = self._users.update_status(target_org_id, user_id, status)
        if not row:
            raise UserNotFound(f"User not found: {user_id}")

        revoked = 0
        if status in ("suspended", "deactivated"):
            revoked = self._sessions.revoke_all_for_user(target_org_id, user_id)

        self._audit(
            org_id=target_org_id,
            actor_user_id=actor_user_id,
            event_type="platform.user.status_changed",
            object_ref=f"user:{user_id}",
            payload={
                "new_status": status,
                "previous_status": target["status"],
                "email": target["email"],
                "sessions_revoked": revoked,
                "actor_org_id": actor_org_id,
                "cross_org": str(actor_org_id) != str(target_org_id),
            },
        )
        return {"user": row, "org_name": target["org_name"], "sessions_revoked": revoked}

    def revoke_all_sessions(
        self,
        *,
        user_id: str,
        actor_user_id: str,
        actor_org_id: str,
    ) -> dict[str, Any]:
        target = self._repo.find_user(user_id)
        if not target:
            raise UserNotFound(f"User not found: {user_id}")

        target_org_id = target["org_id"]
        revoked = self._sessions.revoke_all_for_user(target_org_id, user_id)

        self._audit(
            org_id=target_org_id,
            actor_user_id=actor_user_id,
            event_type="platform.user.sessions_revoked",
            object_ref=f"user:{user_id}",
            payload={
                "email": target["email"],
                "sessions_revoked": revoked,
                "actor_org_id": actor_org_id,
                "cross_org": str(actor_org_id) != str(target_org_id),
            },
        )
        return {
            "user_id": user_id,
            "org_id": target_org_id,
            "email": target["email"],
            "sessions_revoked": revoked,
        }

    def _audit(
        self,
        *,
        org_id: str,
        actor_user_id: str,
        event_type: str,
        object_ref: str,
        payload: dict[str, Any],
    ) -> None:
        self._audit_repo.create_log(
            org_id=org_id,
            actor_type="platform_operator",
            actor_id=actor_user_id,
            event_type=event_type,
            object_ref=object_ref,
            payload_jsonb=payload,
        )


operator_service = OperatorService()
