from __future__ import annotations

from app.modules.finance_os.platform_ai_runtime.context.schemas.context_schema import PlatformContext
from app.modules.finance_os.platform_ai_runtime.context.world_state_engine import world_state_engine
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import WorldState, WorldStateOrg, WorldStateScreen


def enrich_world_state_from_context(world_state: WorldState, platform_ctx: PlatformContext | None) -> WorldState:
    """Fold compressed context highlights into WorldState.recent_entities for planner/observer."""
    if not platform_ctx:
        return world_state
    recent: list[dict] = list(world_state.recent_entities or [])
    for e in platform_ctx.entities[:5]:
        if e.entity_id:
            recent.append({"type": e.entity_type, "entity_id": e.entity_id, "label": e.label})
    for snippet in platform_ctx.memory[:5]:
        recent.append({"type": "memory", "snippet": str(snippet.get("content", snippet.get("title", "")))[:300]})
    for key, text in list(platform_ctx.summaries.items())[:3]:
        recent.append({"type": f"summary_{key}", "snippet": text[:300]})
    data = world_state.model_dump()
    data["recent_entities"] = recent[-25:]
    return WorldState(**data)


def build_world_state(
    org_id: str,
    *,
    payload: dict | None = None,
    roles: list[str] | None = None,
    user_id: str | None = None,
    platform_ctx: PlatformContext | None = None,
    goal_id: str | None = None,
    explicit: WorldState | None = None,
) -> WorldState:
    """Build world state from UI payload, merging persisted session state when goal_id set."""
    if explicit is not None:
        published = explicit
    else:
        payload = payload or {}
        ws_raw = payload.get("world_state") if isinstance(payload.get("world_state"), dict) else {}
        screen_raw = ws_raw.get("screen") if isinstance(ws_raw.get("screen"), dict) else {}
        org_raw = ws_raw.get("org") if isinstance(ws_raw.get("org"), dict) else {}
        published = WorldState(
            screen=WorldStateScreen(
                module=screen_raw.get("module") or payload.get("module"),
                route=screen_raw.get("route") or payload.get("route"),
                entity_type=screen_raw.get("entity_type")
                or payload.get("entity_type")
                or payload.get("object_type"),
                entity_id=screen_raw.get("entity_id")
                or payload.get("entity_id")
                or payload.get("object_id")
                or payload.get("invoice_id"),
                title=screen_raw.get("title"),
                breadcrumb=screen_raw.get("breadcrumb"),
                tab=screen_raw.get("tab"),
                panel=screen_raw.get("panel"),
                modal=screen_raw.get("modal"),
                current_action=screen_raw.get("current_action"),
            ),
            org=WorldStateOrg(
                company_id=org_raw.get("company_id") or payload.get("company_id"),
                branch_id=org_raw.get("branch_id") or payload.get("branch_id"),
                department_id=org_raw.get("department_id") or payload.get("department_id"),
                legal_entity_id=org_raw.get("legal_entity_id") or payload.get("legal_entity_id"),
                fiscal_period_id=org_raw.get("fiscal_period_id") or payload.get("period_id"),
                fiscal_period_open=org_raw.get("fiscal_period_open"),
            ),
            selection=ws_raw.get("selection") if isinstance(ws_raw.get("selection"), dict) else {},
            filters=ws_raw.get("filters") if isinstance(ws_raw.get("filters"), dict) else {},
            search=ws_raw.get("search") if isinstance(ws_raw.get("search"), dict) else {},
            sort=ws_raw.get("sort") if isinstance(ws_raw.get("sort"), dict) else {},
            active_workflows=ws_raw.get("active_workflows") if isinstance(ws_raw.get("active_workflows"), list) else [],
            pending_approvals=ws_raw.get("pending_approvals") if isinstance(ws_raw.get("pending_approvals"), list) else [],
            permissions=list(roles or ws_raw.get("permissions") or []),
            roles=list(roles or ws_raw.get("roles") or []),
            recently_viewed=ws_raw.get("recently_viewed") if isinstance(ws_raw.get("recently_viewed"), list) else [],
            recent_navigation=ws_raw.get("recent_navigation") if isinstance(ws_raw.get("recent_navigation"), list) else [],
            selected_records=ws_raw.get("selected_records") if isinstance(ws_raw.get("selected_records"), list) else [],
            dashboard=ws_raw.get("dashboard") if isinstance(ws_raw.get("dashboard"), dict) else {},
        )
    ws = world_state_engine.resolve(org_id, published=published, goal_id=goal_id, roles=roles)
    if platform_ctx:
        return enrich_world_state_from_context(ws, platform_ctx)
    return ws


def refresh_after_step(org_id: str, world_state: WorldState, step_result: dict) -> WorldState:
    data = world_state.model_dump()
    if step_result.get("entity_id"):
        screen = data.get("screen") or {}
        screen["entity_id"] = step_result["entity_id"]
        data["screen"] = screen
        # Also update selection convenience keys by tool if present
        sel = data.get("selection") or {}
        if step_result.get("po_id"):
            sel["po_id"] = step_result["po_id"]
            data["current_po_id"] = step_result["po_id"]
        if step_result.get("invoice_id"):
            sel["invoice_id"] = step_result["invoice_id"]
            data["current_invoice_id"] = step_result["invoice_id"]
        data["selection"] = sel
    return WorldState(**data)
