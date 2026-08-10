from __future__ import annotations

from typing import Callable

from app.modules.finance_os.agents.orchestrator.forbidden_actions import is_forbidden_action
from app.services.action_service import execute_action


ToolHandler = Callable[[str, dict, dict | None, list[str] | None, bool], dict]


class ErpToolRegistry:
    def __init__(self) -> None:
        self._handlers: dict[tuple[str, str], ToolHandler] = {}
        self._compensation: dict[tuple[str, str], str] = {}
        self._read_only: set[tuple[str, str]] = set()
        self._policy_actions: dict[tuple[str, str], str] = {}
        self._security_meta: dict[tuple[str, str], dict] = {}

    def register(
        self,
        tool: str,
        method: str,
        handler: ToolHandler,
        *,
        read_only: bool = False,
        compensation: str | None = None,
        policy_action: str | None = None,
        security_meta: dict | None = None,
    ) -> None:
        key = (tool.lower(), method.lower())
        self._handlers[key] = handler
        if read_only:
            self._read_only.add(key)
        if compensation:
            self._compensation[key] = compensation
        if policy_action:
            self._policy_actions[key] = policy_action
        if security_meta:
            self._security_meta[key] = dict(security_meta)

    def is_read_only(self, tool: str, method: str) -> bool:
        return (tool.lower(), method.lower()) in self._read_only

    def compensation_for(self, tool: str, method: str) -> str | None:
        return self._compensation.get((tool.lower(), method.lower()))

    def policy_action_for(self, tool: str, method: str) -> str | None:
        return self._policy_actions.get((tool.lower(), method.lower()))

    def security_meta_for(self, tool: str, method: str) -> dict | None:
        return self._security_meta.get((tool.lower(), method.lower()))

    def list_tools(self) -> list[dict]:
        return [
            {
                "tool": k[0],
                "method": k[1],
                "read_only": k in self._read_only,
                "compensation": self._compensation.get(k),
                "policy_action": self._policy_actions.get(k),
                **(self._security_meta.get(k) or {}),
            }
            for k in sorted(self._handlers.keys())
        ]

    def execute(
        self,
        org_id: str,
        tool: str,
        method: str,
        params: dict,
        *,
        actor_id: str,
        roles: list[str] | None = None,
        attrs: dict | None = None,
        human_approved: bool = False,
    ) -> dict:
        if is_forbidden_action(tool, method):
            return {"status": "error", "detail": "forbidden_action", "target": tool}
        key = (tool.lower(), method.lower())
        handler = self._handlers.get(key)
        if not handler:
            if tool in {"memory", "graph", "workflow", "email", "slack", "jira", "linear"}:
                return execute_action(
                    org_id,
                    actor_id=actor_id,
                    tool=tool,
                    method=method,
                    params=params,
                    attrs=attrs,
                    roles=roles,
                    human_approved=human_approved,
                )
            return {"status": "error", "detail": f"unknown_tool:{tool}.{method}", "target": tool}
        try:
            return handler(org_id, params, attrs, roles, human_approved)
        except ValueError as exc:
            return {"status": "error", "detail": str(exc), "target": tool, "retryable": False}
        except Exception as exc:
            return {"status": "error", "detail": str(exc), "target": tool, "retryable": True}


tool_registry = ErpToolRegistry()
