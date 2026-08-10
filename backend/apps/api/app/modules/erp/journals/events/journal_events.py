from __future__ import annotations

from app.core.config import settings
from app.services.logger import log_event


def _emit_pair(
    emit_fn_name: str,
    org_id: str,
    journal_id: str,
    *,
    payload: dict | None,
    actor_id: str | None = None,
) -> None:
    """Publish both legacy `journal.*` and namespaced `erp.journal.*` counterparts."""
    from app.modules.platform.events.services.event_service import platform_event_service

    base_payload = dict(payload or {})
    if "journal_id" not in base_payload:
        base_payload["journal_id"] = journal_id
    pairs = {
        "created": ("journal.created", "erp.journal.created"),
        "approved": ("journal.approved", "erp.journal.approved"),
        "posted": ("journal.posted", "erp.journal.posted"),
        "reversed": ("journal.reversed", "erp.journal.reversed"),
    }
    if emit_fn_name not in pairs:
        raise ValueError(emit_fn_name)
    for event_type in pairs[emit_fn_name]:
        platform_event_service.publish(
            event_type=event_type,
            org_id=org_id,
            source="erp.journals",
            entity_type="journal",
            entity_id=journal_id if emit_fn_name != "reversed" else str(
                base_payload.get("original_journal_id") or journal_id
            ),
            actor_id=actor_id,
            payload=base_payload,
        )


def _safe_emit(kind: str, org_id: str, journal_id: str, **kwargs) -> None:
    try:
        _emit_pair(kind, org_id, journal_id, **kwargs)
    except Exception as exc:
        log_event(
            "journal.emit_failed",
            org_id=org_id,
            journal_id=journal_id,
            kind=kind,
            error=str(exc),
        )
        if not getattr(settings, "event_financial_emit_fail_open", True):
            raise


def emit_journal_created(org_id: str, journal_id: str, *, payload: dict | None = None) -> None:
    _safe_emit("created", org_id, journal_id, payload=payload)


def emit_journal_approved(org_id: str, journal_id: str, *, approved_by: str | None = None) -> None:
    _safe_emit(
        "approved",
        org_id,
        journal_id,
        payload={"journal_id": journal_id, "approved_by": approved_by},
        actor_id=approved_by,
    )


def emit_journal_posted(org_id: str, journal_id: str, *, batch_id: str, posted_by: str | None = None) -> None:
    _safe_emit(
        "posted",
        org_id,
        journal_id,
        payload={"journal_id": journal_id, "batch_id": batch_id, "posted_by": posted_by},
        actor_id=posted_by,
    )


def emit_journal_reversed(org_id: str, original_journal_id: str, *, reversal_journal_id: str) -> None:
    _safe_emit(
        "reversed",
        org_id,
        original_journal_id,
        payload={
            "original_journal_id": original_journal_id,
            "reversal_journal_id": reversal_journal_id,
            "journal_id": original_journal_id,
        },
    )
