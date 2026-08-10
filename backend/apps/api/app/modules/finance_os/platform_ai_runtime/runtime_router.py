"""Shared M38 runtime routing — single entry for LangGraph and M29 adapters."""

from __future__ import annotations

from datetime import datetime, timezone

from app.core.config import settings


def should_use_m38_runtime(payload: dict | None) -> bool:
    if not isinstance(payload, dict):
        return settings.m38_default_runtime
    if payload.get("use_legacy_langgraph") is True:
        return False
    if payload.get("use_m38_runtime") is False:
        return False
    return settings.m38_default_runtime or bool(payload.get("use_m38_runtime"))


def delegate_to_m38_runtime(
    org_id: str,
    agent_type: str,
    trigger_type: str,
    payload: dict,
    principal_roles: list[str] | None = None,
    principal_attrs: dict | None = None,
) -> dict | None:
    """Route to M38 Platform AI Runtime when configured. Returns None only when M38 is not selected."""
    if not should_use_m38_runtime(payload):
        return None
    try:
        from app.modules.finance_os.platform_ai_runtime.services.runtime_service import runtime_service

        if not runtime_service.schema_ready():
            if settings.m38_default_runtime:
                return {
                    "status": "failed",
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                    "failure_contract": {
                        "code": "M38_SCHEMA_UNAVAILABLE",
                        "retryable": True,
                        "step": "runtime_router",
                    },
                    "graph_runtime": {"delegated_to": "m38", "schema_ready": False},
                }
            return None

        message = str(
            payload.get("user_message")
            or payload.get("query")
            or payload.get("question")
            or f"Run {agent_type} via unified runtime"
        ).strip()
        if not message:
            entity = str(payload.get("entity_id") or payload.get("invoice_id") or "")
            message = f"Run {agent_type} analysis"
            if entity:
                message += f" for entity {entity}"

        resp = runtime_service.chat(
            org_id,
            message=message,
            user_id=str((principal_attrs or {}).get("user_id") or "unified-runtime"),
            roles=principal_roles,
            attrs={
                **(principal_attrs or {}),
                "user_id": str((principal_attrs or {}).get("user_id") or "unified-runtime"),
                "m29_agent": agent_type,
                "trigger_type": trigger_type,
            },
            human_approved=bool(payload.get("human_approved")),
            goal_id=str(payload.get("goal_id")) if payload.get("goal_id") else None,
        )
        return {
            "status": resp.status,
            "executed_at": datetime.now(timezone.utc).isoformat(),
            "proposed_actions": [],
            "graph_runtime": {
                "delegated_to": "m38",
                "goal_run_id": resp.goal_run_id,
                "goal_id": resp.goal_id,
                "mode": resp.mode,
                "progress_percent": resp.progress_percent,
            },
            "m38": resp.model_dump(),
            "delegated_to_m38": True,
        }
    except Exception as exc:
        if settings.m38_default_runtime:
            return {
                "status": "failed",
                "executed_at": datetime.now(timezone.utc).isoformat(),
                "failure_contract": {
                    "code": "M38_RUNTIME_ERROR",
                    "retryable": True,
                    "step": "runtime_router",
                    "detail": str(exc),
                },
                "graph_runtime": {"delegated_to": "m38", "error": str(exc)},
            }
        return None
