from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState, WorldStateOrg, WorldStateScreen


def enrich_world_state_from_context(world_state: WorldState, platform_ctx: PlatformContext | None) -> WorldState:
    """Fold compressed context highlights into WorldState.recent_entities for planner/observer."""
    if not platform_ctx:
        return world_state
    recent: list[dict] = []
    for snippet in platform_ctx.memory[:5]:
        recent.append({"type": "memory", "snippet": str(snippet.get("content", snippet.get("title", "")))[:300]})
    for key, text in list(platform_ctx.summaries.items())[:3]:
        recent.append({"type": f"summary_{key}", "snippet": text[:300]})
    data = world_state.model_dump()
    data["recent_entities"] = recent
    return WorldState(**data)


def build_world_state(
    org_id: str,
    *,
    payload: dict | None = None,
    roles: list[str] | None = None,
    user_id: str | None = None,
    platform_ctx: PlatformContext | None = None,
) -> WorldState:
    payload = payload or {}
    ws_raw = payload.get("world_state") if isinstance(payload.get("world_state"), dict) else {}
    screen_raw = ws_raw.get("screen") if isinstance(ws_raw.get("screen"), dict) else {}
    org_raw = ws_raw.get("org") if isinstance(ws_raw.get("org"), dict) else {}

    screen = WorldStateScreen(
        module=screen_raw.get("module") or payload.get("module"),
        route=screen_raw.get("route") or payload.get("route"),
        entity_type=screen_raw.get("entity_type") or payload.get("entity_type") or payload.get("object_type"),
        entity_id=screen_raw.get("entity_id") or payload.get("entity_id") or payload.get("object_id") or payload.get("invoice_id"),
    )
    org = WorldStateOrg(
        company_id=org_raw.get("company_id") or payload.get("company_id"),
        branch_id=org_raw.get("branch_id") or payload.get("branch_id"),
        fiscal_period_id=org_raw.get("fiscal_period_id") or payload.get("period_id"),
        fiscal_period_open=org_raw.get("fiscal_period_open"),
    )

    ws = WorldState(
        screen=screen,
        org=org,
        selection=ws_raw.get("selection") if isinstance(ws_raw.get("selection"), dict) else {},
        active_workflows=ws_raw.get("active_workflows") if isinstance(ws_raw.get("active_workflows"), list) else [],
        permissions=list(roles or ws_raw.get("permissions") or []),
        recent_entities=[],
    )
    if platform_ctx:
        return enrich_world_state_from_context(ws, platform_ctx)
    return ws


def refresh_after_step(org_id: str, world_state: WorldState, step_result: dict) -> WorldState:
    data = world_state.model_dump()
    if step_result.get("entity_id"):
        screen = data.get("screen") or {}
        screen["entity_id"] = step_result["entity_id"]
        data["screen"] = screen
    return WorldState(**data)
