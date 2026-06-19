from __future__ import annotations

from app.modules.erp.fiscal.validators.close_validator import validate_close_readiness
from app.modules.erp.fiscal.repositories.fiscal_period_repository import checklist_repository
from app.modules.erp.fiscal.services.period_lock_service import period_lock_service
from app.modules.erp.fiscal.events.period_events import (
    emit_period_closed,
    emit_period_soft_locked,
    emit_period_hard_locked,
)


class CloseService:
    def init_close(self, org_id: str, *, period_id: str) -> dict:
        seeded = checklist_repository.seed_for_period(org_id, period_id=period_id)
        items = checklist_repository.list_for_period(org_id, period_id=period_id)
        return {"period_id": period_id, "checklist_seeded": seeded, "items": items}

    def complete_checklist_item(self, org_id: str, *, period_id: str, check_name: str, actor_id: str) -> dict:
        return checklist_repository.complete(org_id, period_id=period_id, check_name=check_name, completed_by=actor_id)

    def list_checklist(self, org_id: str, *, period_id: str) -> list[dict]:
        return checklist_repository.list_for_period(org_id, period_id=period_id)

    def submit_for_approval(self, org_id: str, *, period_id: str, started_by: str | None) -> dict:
        if not checklist_repository.all_complete(org_id, period_id=period_id):
            raise ValueError("All checklist items must be completed before close approval")
        try:
            from app.modules.workflows.services.erp_workflow_consumer import handle_entity_created

            handle_entity_created(
                org_id=org_id,
                payload={
                    "entity_type": "fiscal_period",
                    "entity_id": period_id,
                    "workflow_key": "PERIOD_CLOSE",
                    "started_by": started_by,
                    "metadata": {"period_id": period_id},
                },
            )
        except Exception:
            pass
        return {"period_id": period_id, "status": "pending_approval"}

    def execute_close(self, org_id: str, *, period_id: str, actor_id: str) -> dict:
        validate_close_readiness(org_id, period_id=period_id)
        soft = period_lock_service.soft_lock(org_id, period_id=period_id, actor_id=actor_id)
        emit_period_soft_locked(org_id, period_id=period_id)
        validate_close_readiness(org_id, period_id=period_id, final=True)
        hard = period_lock_service.hard_lock(org_id, period_id=period_id, actor_id=actor_id)
        emit_period_hard_locked(org_id, period_id=period_id)
        closed = period_lock_service.close(org_id, period_id=period_id, closed_by=actor_id)
        emit_period_closed(org_id, period_id=period_id)
        self._audit(org_id, period_id=period_id, action="fiscal.period.closed", actor_id=actor_id)
        return {"soft_lock": soft, "hard_lock": hard, "closed": closed}

    def lock_legacy(self, org_id: str, *, period_id: str) -> dict:
        item = period_lock_service.hard_lock(org_id, period_id=period_id)
        emit_period_hard_locked(org_id, period_id=period_id)
        return item

    def close_legacy(self, org_id: str, *, period_id: str, actor_id: str) -> dict:
        closed = period_lock_service.close(org_id, period_id=period_id, closed_by=actor_id)
        emit_period_closed(org_id, period_id=period_id)
        return closed

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


close_service = CloseService()
