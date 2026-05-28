from __future__ import annotations


def format_object_ref(domain: str, entity_type: str, entity_id: str) -> str:
    """Canonical object_ref: erp:invoice:{uuid}, workflow:instance:{uuid}."""
    return f"{domain}:{entity_type}:{entity_id}"


def format_erp_ref(entity_type: str, entity_id: str) -> str:
    return format_object_ref("erp", entity_type, entity_id)


def format_workflow_ref(entity_id: str) -> str:
    return format_object_ref("workflow", "instance", entity_id)


def format_event_ref(event_id: str) -> str:
    return format_object_ref("platform", "event", event_id)
