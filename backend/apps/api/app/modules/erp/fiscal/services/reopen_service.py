from __future__ import annotations

from app.modules.core.iam.services.maker_checker_service import MakerCheckerViolation, enforce_maker_checker
from app.modules.erp.fiscal.repositories.fiscal_period_repository import reopen_repository
from app.modules.erp.fiscal.services.period_lock_service import period_lock_service
from app.modules.erp.fiscal.events.period_events import emit_period_reopened


class ReopenService:
    def request_reopen(self, org_id: str, *, period_id: str, reason: str, requested_by: str) -> dict:
        row = reopen_repository.create(org_id, period_id=period_id, reason=reason, requested_by=requested_by)
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "period_reopen",
                    "entity_id": str(row["id"]),
                    "workflow_key": "PERIOD_REOPEN",
                    "started_by": requested_by,
                    "metadata": {"period_id": period_id, "reopen_request_id": str(row["id"])},
                },
            )
        except Exception:
            pass
        return row

    def approve_reopen(self, org_id: str, *, request_id: str, approved_by: str, requested_by: str | None = None) -> dict:
        if requested_by:
            enforce_maker_checker(created_by=requested_by, actor_user_id=approved_by, org_id=org_id)
        approved = reopen_repository.approve(org_id, request_id=request_id, approved_by=approved_by)
        reopened = period_lock_service.reopen(org_id, period_id=str(approved["period_id"]))
        emit_period_reopened(org_id, period_id=str(approved["period_id"]))
        self._audit(org_id, period_id=str(approved["period_id"]), action="fiscal.period.reopened", actor_id=approved_by)
        return {"request": approved, "period": reopened}

    def _audit(self, org_id: str, *, period_id: str, action: str, actor_id: str) -> None:
        try:
            from app.modules.platform.governance.services.audit_service import audit_service

            audit_service.record(
                org_id=org_id,
                actor_type="user",
                actor_id=actor_id,
                action=action,
                object_ref=f"erp:fiscal_period:{period_id}",
                entity_type="fiscal_period",
                entity_id=period_id,
                source_service="erp.fiscal",
            )
        except Exception:
            pass


reopen_service = ReopenService()
