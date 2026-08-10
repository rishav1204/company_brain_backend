from __future__ import annotations

from dataclasses import dataclass, field
import inspect
from typing import Any, Callable

from app.core.prompt_sanitizer import ToolParamsRejectedError, validate_tool_invocation
from app.modules.finance_os.agents.orchestrator.forbidden_actions import is_forbidden_action
from app.modules.finance_os.platform_ai_runtime.tools.registry import ErpToolRegistry, ToolHandler

# Frozen at registration — no runtime importlib (SEC-38).
_HANDLER_CACHE: dict[tuple[str, str, str], Callable[..., Any]] = {}
_SECURITY_META: dict[tuple[str, str], dict] = {}


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
    # Phase 8 Wave 3 — security metadata (defaults filled at registration if blank)
    category: str = ""
    mutation_type: str = ""  # none | create | update | delete | submit | execute | other
    approval_policy: str = ""  # none | required | policy_engine
    rollback_policy: str = ""  # none | compensate | irreversible
    audit_classification: str = ""
    required_permissions: tuple[str, ...] = ()


def normalize_tool_security(spec: ToolSpec) -> ToolSpec:
    """Fill mandatory security metadata without mutating frozen instance."""
    category = spec.category or ("read" if spec.read_only else "draft")
    if spec.read_only:
        mutation = "none"
        approval = "none"
        rollback = "none"
        audit = spec.audit_classification or "read"
    else:
        mutation = spec.mutation_type or (
            "submit"
            if any(x in spec.method for x in ("submit", "confirm", "approve"))
            else "create"
            if any(x in spec.method for x in ("create", "add", "generate", "receive"))
            else "delete"
            if any(x in spec.method for x in ("cancel", "void", "deactivate", "dispose"))
            else "update"
        )
        approval = spec.approval_policy or ("required" if spec.requires_approval else "policy_engine")
        if spec.compensation:
            rollback = "compensate"
        elif mutation in {"submit", "execute"}:
            rollback = "irreversible"
        else:
            rollback = "none"
        audit = spec.audit_classification or "mutation"
    return ToolSpec(
        tool=spec.tool,
        method=spec.method,
        module=spec.module,
        service=spec.service,
        fn=spec.fn,
        read_only=spec.read_only,
        requires_approval=spec.requires_approval,
        compensation=spec.compensation,
        policy_action=spec.policy_action or f"{spec.tool}.{spec.method}",
        defaults=spec.defaults,
        required=spec.required,
        id_aliases=spec.id_aliases,
        actor_kwarg=spec.actor_kwarg,
        result_as=spec.result_as,
        org_style=spec.org_style,
        category=category,
        mutation_type=mutation if not spec.mutation_type else spec.mutation_type,
        approval_policy=approval if not spec.approval_policy else spec.approval_policy,
        rollback_policy=spec.rollback_policy or rollback,
        audit_classification=audit,
        required_permissions=spec.required_permissions,
    )


def validate_tool_security_metadata(spec: ToolSpec) -> None:
    if not spec.tool or not spec.method:
        raise ValueError("tool/method required")
    if not spec.module or not spec.service or not spec.fn:
        raise ValueError(f"tool {spec.tool}.{spec.method} missing target module/service/fn")
    if not spec.policy_action:
        raise ValueError(f"tool {spec.tool}.{spec.method} missing policy_action")
    if not spec.category:
        raise ValueError(f"tool {spec.tool}.{spec.method} missing category")
    if not spec.mutation_type:
        raise ValueError(f"tool {spec.tool}.{spec.method} missing mutation_type")
    if not spec.approval_policy:
        raise ValueError(f"tool {spec.tool}.{spec.method} missing approval_policy")
    if not spec.audit_classification:
        raise ValueError(f"tool {spec.tool}.{spec.method} missing audit_classification")


def _resolve_kwargs(spec: ToolSpec, params: dict, attrs: dict | None) -> dict[str, Any]:
    kwargs = dict(spec.defaults)
    _skip = {"reverses_node", "forensics", "_forensics_advisory"}
    for key, value in params.items():
        if key.startswith("_") or key in _skip:
            continue
        if str(key).lower() in {
            "org_id",
            "organization_id",
            "human_approved",
            "roles",
            "permissions",
            "actor_id",
        }:
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


def _pack_result(spec: ToolSpec, result: Any, *, scope: dict | None = None) -> dict[str, Any]:
    if scope is not None:
        from app.modules.finance_os.platform_ai_runtime.security.context_boundary import filter_result_payload

        result = filter_result_payload(result, scope)
    if isinstance(result, dict) and result.get("status") == "error" and result.get("detail") == "out_of_scope":
        return result
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


# Direct importlib of ERP services/repos from Finance OS tools is forbidden (Wave 1 ACL).
# Reads → erp.query_services.dispatch; writes → erp_command_bridge.
_ALLOWED_MODULE_PREFIXES = (
    "app.modules.erp.query_services.",
    "app.modules.finance_os.",
    "app.modules.workflows.",
    "app.modules.platform.",
)

_ALLOWED_CALLABLES: set[tuple[str, str, str]] = set()


def _is_erp_target(module: str) -> bool:
    return module.startswith("app.modules.erp.") and not module.startswith("app.modules.erp.query_services.")


def _resolve_callable(spec: ToolSpec) -> Callable[..., Any]:
    key = (spec.module, spec.service, spec.fn)
    if key in _HANDLER_CACHE:
        return _HANDLER_CACHE[key]
    if _is_erp_target(spec.module):
        raise ValueError(f"erp_direct_forbidden:{spec.module} — use bridge/query_services")
    if not any(spec.module.startswith(p) for p in _ALLOWED_MODULE_PREFIXES):
        raise ValueError(f"forbidden_module:{spec.module}")
    import importlib

    mod = importlib.import_module(spec.module)
    svc = getattr(mod, spec.service)
    fn = getattr(svc, spec.fn)
    if not callable(fn):
        raise ValueError(f"not_callable:{spec.module}.{spec.service}.{spec.fn}")
    _HANDLER_CACHE[key] = fn
    return fn


def build_handler(spec: ToolSpec) -> ToolHandler:
    key = (spec.module, spec.service, spec.fn)
    _ALLOWED_CALLABLES.add(key)
    meta_key = (spec.tool.lower(), spec.method.lower())
    _SECURITY_META[meta_key] = {
        "category": spec.category,
        "mutation_type": spec.mutation_type,
        "approval_policy": spec.approval_policy,
        "rollback_policy": spec.rollback_policy,
        "audit_classification": spec.audit_classification,
        "required_permissions": list(spec.required_permissions),
        "requires_approval": spec.requires_approval,
        "read_only": spec.read_only,
        "compensation": spec.compensation,
        "policy_action": spec.policy_action,
    }

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
        # Policy Engine decides authorization for mutations (planner never does).
        if not spec.read_only and not (spec.requires_approval and human_approved):
            from app.modules.finance_os.platform_ai_runtime.policy.unified_policy_gate import (
                evaluate_tool_invocation,
            )

            actor_id = str((attrs or {}).get("user_id") or "platform-runtime")
            decision = evaluate_tool_invocation(
                org_id,
                tool=spec.tool,
                method=spec.method,
                params=params,
                policy_action=spec.policy_action,
                actor_id=actor_id,
                roles=[str(r) for r in (roles or [])],
                attrs=attrs,
                human_approved=human_approved,
                read_only=spec.read_only,
            )
            if not decision.allowed:
                return {
                    "status": "error",
                    "detail": decision.reason or "policy_denied",
                    "target": spec.tool,
                    "retryable": False,
                    "policy_action": spec.policy_action,
                    "policy_code": decision.code,
                }
            if decision.requires_human_approval:
                return {
                    "status": "pending_approval",
                    "detail": "approval_required",
                    "target": spec.tool,
                    "draft": params,
                    "policy_action": spec.policy_action,
                }
        try:
            params = validate_tool_invocation(params or {}, required=spec.required)
            kwargs = _resolve_kwargs(spec, params, attrs)
            if isinstance(attrs, dict):
                allowed = attrs.get("allowed_branch_ids")
                if allowed and isinstance(allowed, list):
                    if "branch_ids" not in kwargs:
                        kwargs["branch_ids"] = [str(b) for b in allowed]
                    if "branch_id" not in kwargs and len(allowed) == 1:
                        kwargs["branch_id"] = str(allowed[0])

            actor_id = str((attrs or {}).get("user_id") or "platform-runtime")

            # Wave 1: ERP mutations always through command bridge
            if not spec.read_only and _is_erp_target(spec.module):
                from app.modules.finance_os.bridges.erp_command_bridge.services.command_service import (
                    erp_command_service,
                )

                packed = erp_command_service.execute_tool_mutation(
                    org_id,
                    tool=spec.tool,
                    method=spec.method,
                    erp_module=spec.module,
                    erp_service=spec.service,
                    erp_fn=spec.fn,
                    kwargs=kwargs,
                    actor_id=actor_id,
                    roles=[str(r) for r in (roles or [])],
                    attrs=attrs if isinstance(attrs, dict) else None,
                    human_approved=human_approved,
                    policy_action=spec.policy_action,
                    requires_approval=spec.requires_approval,
                    org_style=spec.org_style,
                    skip_bridge_approval_gate=True,
                )
                if packed.get("status") != "completed":
                    return packed
                scope = None
                if isinstance(attrs, dict):
                    from app.modules.finance_os.platform_ai_runtime.security.context_boundary import session_scope

                    scope = session_scope(org_id, None, attrs)
                result = packed.get("result")
                payload = _pack_result(spec, result, scope=scope)
                if payload.get("status") == "error":
                    return payload
                return {
                    "status": "completed",
                    "target": spec.tool,
                    "detail": spec.method,
                    "policy_action": spec.policy_action,
                    "command_id": packed.get("command_id"),
                    **payload,
                }

            # Wave 1: ERP reads always through query dispatch
            if spec.read_only and _is_erp_target(spec.module):
                from app.modules.erp.query_services.dispatch import invoke_read

                result = invoke_read(
                    org_id,
                    module=spec.module,
                    service=spec.service,
                    fn=spec.fn,
                    kwargs=kwargs,
                    org_style=spec.org_style,
                )
            else:
                bound_fn = _HANDLER_CACHE.get(key) or _resolve_callable(spec)
                if isinstance(attrs, dict):
                    allowed = attrs.get("allowed_branch_ids")
                    if allowed and isinstance(allowed, list):
                        try:
                            sig = inspect.signature(bound_fn)
                            if "branch_ids" in sig.parameters and "branch_ids" not in kwargs:
                                kwargs["branch_ids"] = [str(b) for b in allowed]
                            if "branch_id" in sig.parameters and "branch_id" not in kwargs and len(allowed) == 1:
                                kwargs["branch_id"] = str(allowed[0])
                        except Exception:
                            pass
                if spec.org_style == "kw":
                    result = bound_fn(org_id=org_id, **kwargs)
                else:
                    result = bound_fn(org_id, **kwargs)

            scope = None
            if isinstance(attrs, dict):
                from app.modules.finance_os.platform_ai_runtime.security.context_boundary import session_scope

                scope = session_scope(org_id, None, attrs)
            payload = _pack_result(spec, result, scope=scope)
            if payload.get("status") == "error":
                return payload
            return {
                "status": "completed",
                "target": spec.tool,
                "detail": spec.method,
                "policy_action": spec.policy_action,
                **payload,
            }
        except ValueError as exc:
            return {"status": "error", "detail": str(exc), "target": spec.tool, "retryable": False}
        except ToolParamsRejectedError as exc:
            return {"status": "error", "detail": str(exc), "target": spec.tool, "retryable": False}
        except PermissionError as exc:
            return {"status": "error", "detail": str(exc), "target": spec.tool, "retryable": False}
        except Exception:
            return {"status": "error", "detail": "tool_execution_failed", "target": spec.tool, "retryable": True}

    return handler


def register_spec(registry: ErpToolRegistry, spec: ToolSpec) -> None:
    normalized = normalize_tool_security(spec)
    validate_tool_security_metadata(normalized)
    _ALLOWED_CALLABLES.add((normalized.module, normalized.service, normalized.fn))
    registry.register(
        normalized.tool,
        normalized.method,
        build_handler(normalized),
        read_only=normalized.read_only,
        compensation=normalized.compensation,
        policy_action=normalized.policy_action,
        security_meta=_SECURITY_META.get((normalized.tool.lower(), normalized.method.lower())),
    )


def register_specs(registry: ErpToolRegistry, specs: list[ToolSpec]) -> None:
    for spec in specs:
        register_spec(registry, spec)


def tool_security_meta(tool: str, method: str) -> dict | None:
    return _SECURITY_META.get((tool.lower(), method.lower()))
