from __future__ import annotations

from typing import Any

from app.modules.platform.events.services.event_service import platform_event_service


def emit_account_created(org_id: str, *, account_id: str, metadata: dict | None = None, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.account.created",
        org_id=org_id,
        source="erp.coa",
        entity_type="account",
        entity_id=account_id,
        payload={"entity_type": "account", "entity_id": account_id, **(metadata or {})},
        trace_id=trace_id,
    )


def emit_account_updated(org_id: str, *, account_id: str, changes: dict | None = None, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.account.updated",
        org_id=org_id,
        source="erp.coa",
        entity_type="account",
        entity_id=account_id,
        payload={"entity_type": "account", "entity_id": account_id, "changes": changes or {}},
        trace_id=trace_id,
    )


def emit_gst_mapping_updated(org_id: str, *, account_id: str, gst_type: str, trace_id: str | None = None) -> dict[str, Any]:
    return platform_event_service.publish(
        event_type="erp.gst.mapping.updated",
        org_id=org_id,
        source="erp.coa",
        entity_type="account",
        entity_id=account_id,
        payload={"entity_type": "account", "entity_id": account_id, "gst_type": gst_type},
        trace_id=trace_id,
    )

