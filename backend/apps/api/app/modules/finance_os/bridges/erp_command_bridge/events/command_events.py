from __future__ import annotations

from typing import Any

from app.modules.finance_os.bridges.erp_command_bridge.contracts.command_envelope import ErpCommand


_SOURCE = "finance_os.erp_command_bridge"


def _publish(event_type: str, command: ErpCommand, payload: dict[str, Any] | None = None) -> None:
    try:
        from app.modules.platform.events.services.event_service import platform_event_service

        platform_event_service.publish(
            event_type=event_type,
            org_id=command.org_id,
            source=_SOURCE,
            payload={
                "command_id": command.command_id,
                "command_type": command.command_type,
                "tool": command.tool,
                "method": command.method,
                "policy_action": command.policy_action,
                "actor_id": command.actor_id,
                "version": command.version,
                "lifecycle_event": event_type,
                **(payload or {}),
            },
            actor_id=command.actor_id,
            entity_type="erp_command",
            entity_id=command.command_id,
            trace_id=command.trace_id,
            idempotency_key=command.idempotency_key,
        )
    except Exception:
        pass


def emit_requested(command: ErpCommand) -> None:
    _publish("erp.command.requested", command)


def emit_approved(command: ErpCommand) -> None:
    _publish("erp.command.approved", command)


def emit_approval_pending(command: ErpCommand) -> None:
    _publish("erp.command.approval_pending", command)


def emit_rejected(command: ErpCommand, *, reason: str) -> None:
    _publish("erp.command.rejected", command, {"reason": reason})


def emit_executed(command: ErpCommand, *, entity_id: str | None = None) -> None:
    _publish("erp.command.executed", command, {"entity_id": entity_id})


def emit_failed(command: ErpCommand, *, reason: str) -> None:
    _publish("erp.command.failed", command, {"reason": reason})


def emit_duplicate(command: ErpCommand, *, cached: dict | None = None) -> None:
    _publish("erp.command.duplicate", command, {"cached": bool(cached)})
