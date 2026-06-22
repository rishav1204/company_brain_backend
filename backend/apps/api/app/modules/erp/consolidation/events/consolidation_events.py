from __future__ import annotations

from app.services.event_bus import event_bus


def emit_completed(org_id: str, *, run_id: str) -> None:
    event_bus.publish(
        event_type="consolidation.completed",
        org_id=org_id,
        source="erp.consolidation",
        payload={"consolidation_run_id": run_id},
    )


def emit_requested(org_id: str, *, group_company_id: str) -> None:
    event_bus.publish(
        event_type="consolidation.requested",
        org_id=org_id,
        source="erp.consolidation",
        payload={"group_company_id": group_company_id},
    )


def emit_intercompany_created(org_id: str, *, transaction_id: str) -> None:
    event_bus.publish(
        event_type="intercompany.created",
        org_id=org_id,
        source="erp.consolidation",
        payload={"intercompany_transaction_id": transaction_id},
    )


def emit_elimination_generated(org_id: str, *, run_id: str, count: int) -> None:
    event_bus.publish(
        event_type="elimination.generated",
        org_id=org_id,
        source="erp.consolidation",
        payload={"consolidation_run_id": run_id, "elimination_count": count},
    )


def emit_ic_mismatch(org_id: str, *, mismatch: dict) -> None:
    event_bus.publish(
        event_type="intercompany.mismatch.detected",
        org_id=org_id,
        source="erp.consolidation",
        payload=mismatch,
    )


def emit_entity_closed(org_id: str, *, company_id: str, period_id: str) -> None:
    event_bus.publish(
        event_type="entity.closed",
        org_id=org_id,
        source="erp.consolidation",
        payload={"company_id": company_id, "fiscal_period_id": period_id},
    )
