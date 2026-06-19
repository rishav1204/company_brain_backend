from __future__ import annotations

from app.modules.erp.fiscal.exceptions import PeriodClosedError
from app.modules.erp.fiscal.repositories.fiscal_period_repository import fiscal_period_repository

SOFT_POST_ROLES = {"cfo", "controller", "finance_manager", "tenant_admin"}
SOFT_POST_PERMS = {"fiscal.soft_post", "erp.fiscal.admin", "*"}


class PostingValidationService:
    def validate_period(
        self,
        org_id: str,
        posting_date: str,
        *,
        company_id: str | None = None,
        actor_id: str | None = None,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
        allow_soft_lock: bool = False,
    ) -> dict:
        row = fiscal_period_repository.find_for_date(org_id, posting_date=posting_date[:10], company_id=company_id)
        if not row:
            raise PeriodClosedError(
                code="PERIOD_NOT_FOUND",
                message=f"No fiscal period found for posting date {posting_date[:10]}",
            )
        lock_status = str(row.get("lock_status") or row.get("status") or "open").lower()
        if lock_status in {"locked", "hard_locked"}:
            lock_status = "hard_locked"
        period_name = str(row.get("period_name") or "")
        if lock_status == "open":
            return row
        if lock_status == "soft_locked" and (allow_soft_lock or self._can_soft_post(roles, permissions)):
            return row
        if lock_status == "soft_locked":
            raise PeriodClosedError(
                code="PERIOD_SOFT_LOCKED",
                message=f"Posting not allowed. Period {period_name} is soft-locked.",
                period_name=period_name,
            )
        raise PeriodClosedError(
            code="PERIOD_CLOSED",
            message=f"Posting not allowed. Period {period_name} is closed.",
            period_name=period_name,
        )

    def validate_period_open(
        self,
        org_id: str,
        posting_date: str,
        *,
        company_id: str | None = None,
        actor_id: str | None = None,
        roles: list[str] | None = None,
        permissions: list[str] | None = None,
    ) -> dict:
        return self.validate_period(
            org_id,
            posting_date,
            company_id=company_id,
            actor_id=actor_id,
            roles=roles,
            permissions=permissions,
            allow_soft_lock=False,
        )

    def is_period_open_for_date(self, org_id: str, posting_date: str, *, company_id: str | None = None) -> bool:
        try:
            self.validate_period_open(org_id, posting_date, company_id=company_id)
            return True
        except PeriodClosedError:
            return False

    def _can_soft_post(self, roles: list[str] | None, permissions: list[str] | None) -> bool:
        role_set = {r.lower() for r in (roles or [])}
        perm_set = {p.lower() for p in (permissions or [])}
        if perm_set & SOFT_POST_PERMS:
            return True
        return bool(role_set & SOFT_POST_ROLES)


posting_validation_service = PostingValidationService()
