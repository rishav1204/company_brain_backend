from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.tools.registry import tool_registry


class Executor:
    def run(
        self,
        org_id: str,
        *,
        tool: str,
        method: str,
        params: dict,
        actor_id: str,
        roles: list[str] | None = None,
        attrs: dict | None = None,
        human_approved: bool = False,
    ) -> dict:
        read_only = tool_registry.is_read_only(tool, method)
        effective_approved = human_approved or read_only
        return tool_registry.execute(
            org_id,
            tool,
            method,
            params,
            actor_id=actor_id,
            roles=roles,
            attrs=attrs,
            human_approved=effective_approved,
        )


executor = Executor()
