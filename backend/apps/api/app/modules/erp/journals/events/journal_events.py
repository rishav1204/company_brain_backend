from __future__ import annotations


def emit_journal_created(org_id: str, journal_id: str, *, payload: dict | None = None) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        platform_event_service.publish(
            event_type="journal.created",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id,
            payload=payload or {"journal_id": journal_id},
        )
        platform_event_service.publish(
            event_type="erp.journal.created",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id,
            payload=payload or {"journal_id": journal_id},
        )
    except Exception:
        pass


def emit_journal_approved(org_id: str, journal_id: str, *, approved_by: str | None = None) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        payload = {"journal_id": journal_id, "approved_by": approved_by}
        platform_event_service.publish(
            event_type="journal.approved",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id,
            payload=payload,
        )
        platform_event_service.publish(
            event_type="erp.journal.approved",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id,
            payload=payload,
        )
    except Exception:
        pass


def emit_journal_posted(org_id: str, journal_id: str, *, batch_id: str, posted_by: str | None = None) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        payload = {"journal_id": journal_id, "batch_id": batch_id, "posted_by": posted_by}
        platform_event_service.publish(
            event_type="journal.posted",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id,
            payload=payload,
        )
        platform_event_service.publish(
            event_type="erp.journal.posted",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id,
            payload=payload,
        )
    except Exception:
        pass


def emit_journal_reversed(org_id: str, original_journal_id: str, *, reversal_journal_id: str) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        payload = {
            "original_journal_id": original_journal_id,
            "reversal_journal_id": reversal_journal_id,
        }
        platform_event_service.publish(
            event_type="journal.reversed",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=original_journal_id,
            payload=payload,
        )
        platform_event_service.publish(
            event_type="erp.journal.reversed",
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=original_journal_id,
            payload=payload,
        )
    except Exception:
        pass
