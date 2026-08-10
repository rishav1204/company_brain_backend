"""Strict LLM planner / structured-output validation (Phase 8 Wave 3 / AI-16)."""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.prompt_sanitizer import ToolParamsRejectedError, validate_tool_invocation
from app.modules.finance_os.agents.orchestrator.forbidden_actions import is_forbidden_action
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import GraphNodeSpec


class LLMOutputValidationError(ValueError):
    """Planner / LLM structured output rejected by deterministic validator."""


_ALLOWED_NODE_KEYS = frozenset(
    {
        "id",
        "tool",
        "method",
        "params",
        "label",
        "requires_approval",
        "compensation_tool",
        "status",
        "depends_on",
    }
)


def _catalogs():
    from app.modules.finance_os.platform_ai_runtime.tools.catalog_draft import DRAFT_SPECS
    from app.modules.finance_os.platform_ai_runtime.tools.catalog_read import READ_SPECS

    allowed = frozenset(f"{s.tool}.{s.method}" for s in (*READ_SPECS, *DRAFT_SPECS))
    specs = {f"{s.tool}.{s.method}": s for s in (*READ_SPECS, *DRAFT_SPECS)}
    return allowed, specs


def _filter_params_to_allowed(params: dict, *, allowed_keys: set[str] | None) -> dict:
    cleaned: dict[str, Any] = {}
    for k, v in (params or {}).items():
        if str(k).startswith("_"):
            continue
        if str(k).lower() in {
            "org_id",
            "organization_id",
            "human_approved",
            "roles",
            "permissions",
            "actor_id",
            "user_id",
            "session_token",
            "api_key",
        }:
            continue
        if allowed_keys is not None and k not in allowed_keys:
            continue
        cleaned[k] = v
    return cleaned


def validate_llm_plan_nodes(nodes: list, *, max_nodes: int | None = None) -> list[GraphNodeSpec]:
    """Never trust LLM tool/params. Catalog allowlist + injection filter + required fields."""
    allowed_tools, tool_specs = _catalogs()
    limit = max_nodes if max_nodes is not None else int(settings.m38_max_plan_nodes or 25)
    if not isinstance(nodes, list):
        raise LLMOutputValidationError("nodes must be a list")
    if len(nodes) > limit:
        raise LLMOutputValidationError(f"plan exceeds max nodes ({limit})")

    validated: list[GraphNodeSpec] = []
    seen_ids: set[str] = set()
    for idx, raw in enumerate(nodes):
        if not isinstance(raw, dict):
            if hasattr(raw, "model_dump"):
                raw = raw.model_dump()
            else:
                raise LLMOutputValidationError(f"node[{idx}] is not an object")
        unknown = set(raw.keys()) - _ALLOWED_NODE_KEYS
        if unknown:
            raise LLMOutputValidationError(f"node[{idx}] unexpected fields: {sorted(unknown)}")

        tool = str(raw.get("tool") or "").strip().lower()
        method = str(raw.get("method") or "").strip().lower()
        if not tool or not method:
            raise LLMOutputValidationError(f"node[{idx}] missing tool/method")
        if is_forbidden_action(tool, method):
            raise LLMOutputValidationError(f"forbidden tool: {tool}.{method}")
        tool_key = f"{tool}.{method}"
        if tool_key not in allowed_tools:
            raise LLMOutputValidationError(f"unknown tool: {tool_key}")

        spec = tool_specs[tool_key]
        allowed_param_keys = set(spec.required) | set(spec.defaults.keys()) | set(spec.id_aliases)
        for extra in ("limit", "query", "status", "workflow_key", "branch_id", "company_id"):
            allowed_param_keys.add(extra)

        try:
            params = validate_tool_invocation(
                _filter_params_to_allowed(raw.get("params") or {}, allowed_keys=allowed_param_keys),
                required=(),
            )
        except ToolParamsRejectedError as exc:
            raise LLMOutputValidationError(f"node[{idx}] params rejected: {exc}") from exc

        node_id = str(raw.get("id") or f"step_{idx + 1}")
        if node_id in seen_ids:
            raise LLMOutputValidationError(f"duplicate node id: {node_id}")
        seen_ids.add(node_id)

        depends_on = raw.get("depends_on") or []
        if not isinstance(depends_on, list):
            raise LLMOutputValidationError(f"node[{idx}] depends_on must be list")

        requires_approval = bool(spec.requires_approval) if not spec.read_only else False
        compensation = spec.compensation if not spec.read_only else None

        validated.append(
            GraphNodeSpec(
                id=node_id,
                tool=tool,
                method=method,
                params=params,
                label=str(raw.get("label") or f"{tool}.{method}")[:200],
                requires_approval=requires_approval,
                compensation_tool=compensation,
                status="pending",
                depends_on=[str(d) for d in depends_on],
            )
        )
    return validated
