from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.modules.finance_os.agents.orchestrator.forbidden_actions import is_forbidden_action
from app.modules.finance_os.platform_ai_runtime.tools.registry import ErpToolRegistry, ToolHandler


@dataclass(frozen=True)
class ToolSpec:
    tool: str
    method: str
    module: str
    service: str
    fn: str
    read_only: bool = False
    requires_approval: bool = False
    compensation: str | None = None
    policy_action: str | None = None
    defaults: dict[str, Any] = field(default_factory=dict)
    required: tuple[str, ...] = ()
    id_aliases: tuple[str, ...] = ("entity_id",)
    actor_kwarg: str | None = None
    result_as: str = "auto"  # auto | items | result
    org_style: str = "first"  # first | kw


def _resolve_kwargs(spec: ToolSpec, params: dict, attrs: dict | None) -> dict[str, Any]:
    kwargs = dict(spec.defaults)
    for key, value in params.items():
        if key.startswith("_"):
            continue
        kwargs[key] = value
    for req in spec.required:
        if req in kwargs:
            continue
        for alias in spec.id_aliases:
            if alias in params:
                kwargs[req] = params[alias]
                break
    if spec.actor_kwarg and attrs:
        kwargs.setdefault(spec.actor_kwarg, attrs.get("user_id") or "platform-runtime")
    missing = [r for r in spec.required if r not in kwargs or kwargs[r] in (None, "")]
    if missing:
        raise ValueError(f"Missing required params: {', '.join(missing)}")
    return kwargs


def _pack_result(spec: ToolSpec, result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if spec.result_as == "items" or (spec.result_as == "auto" and isinstance(result, list)):
        payload["items"] = result
    else:
        payload["result"] = result
    if isinstance(result, dict):
        eid = result.get("id")
        if not eid and isinstance(result.get("invoice"), dict):
            eid = result["invoice"].get("id")
        if not eid and isinstance(result.get("journal"), dict):
            eid = result["journal"].get("id")
        if not eid and isinstance(result.get("po"), dict):
            eid = result["po"].get("id")
        if eid:
            payload["entity_id"] = str(eid)
    elif isinstance(result, list) and result and isinstance(result[0], dict) and result[0].get("id"):
        payload["entity_id"] = str(result[0]["id"])
    return payload


def build_handler(spec: ToolSpec) -> ToolHandler:
    def handler(org_id: str, params: dict, attrs, roles, human_approved: bool) -> dict:
        if is_forbidden_action(spec.tool, spec.method):
            return {"status": "error", "detail": "forbidden_action", "target": spec.tool}
        if spec.requires_approval and not human_approved:
            return {
                "status": "pending_approval",
                "detail": "approval_required",
                "target": spec.tool,
                "draft": params,
                "policy_action": spec.policy_action,
            }
        try:
            import importlib

            mod = importlib.import_module(spec.module)
            svc = getattr(mod, spec.service)
            fn = getattr(svc, spec.fn)
            kwargs = _resolve_kwargs(spec, params, attrs)
            if spec.org_style == "kw":
                result = fn(org_id=org_id, **kwargs)
            else:
                result = fn(org_id, **kwargs)
            payload = _pack_result(spec, result)
            return {
                "status": "completed",
                "target": spec.tool,
                "detail": spec.method,
                "policy_action": spec.policy_action,
                **payload,
            }
        except ValueError as exc:
            return {"status": "error", "detail": str(exc), "target": spec.tool, "retryable": False}
        except Exception as exc:
            return {"status": "error", "detail": str(exc), "target": spec.tool, "retryable": True}

    return handler


def register_spec(registry: ErpToolRegistry, spec: ToolSpec) -> None:
    registry.register(
        spec.tool,
        spec.method,
        build_handler(spec),
        read_only=spec.read_only,
        compensation=spec.compensation,
        policy_action=spec.policy_action,
    )


def register_specs(registry: ErpToolRegistry, specs: list[ToolSpec]) -> None:
    for spec in specs:
        register_spec(registry, spec)
