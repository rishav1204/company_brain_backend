from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import build_request_context
from app.modules.finance_os.platform_ai_runtime.repositories.goal_repository import goal_repository
from app.modules.finance_os.platform_ai_runtime.schemas.runtime_schema import (
    CopilotChatRequest,
    CopilotChatResponse,
    GoalAlternativeRequest,
    GoalApproveRequest,
    GoalCreateRequest,
    GoalUndoRequest,
    OperationalGoalRequest,
    WorldStatePublishRequest,
)
from app.modules.finance_os.platform_ai_runtime.services.runtime_service import runtime_service
from app.modules.finance_os.platform_ai_runtime.goals.goal_manager import goal_manager
from app.modules.finance_os.agents.security.agents_guard import require_agent_read, require_agent_run

router = APIRouter(tags=["finance-os-platform-runtime"])


def _require_schema() -> None:
    if not runtime_service.schema_ready():
        raise HTTPException(status_code=503, detail="M38 schema not ready — run migration 069")


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "module": "finance_os.platform_ai_runtime", "schema_ready": runtime_service.schema_ready()}


@router.get("/tools")
def list_tools(context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    from app.modules.finance_os.platform_ai_runtime.tools.registry import tool_registry

    return {"request_id": context.request_id, "tools": tool_registry.list_tools()}


@router.post("/goals", response_model=CopilotChatResponse)
def create_goal(request: GoalCreateRequest, context=Depends(build_request_context)) -> CopilotChatResponse:
    require_agent_run(context.user)
    _require_schema()
    message = request.title if not request.description else f"{request.title}: {request.description}"
    try:
        return runtime_service.chat(
            context.org_id,
            message=message,
            user_id=context.user_id,
            roles=context.roles,
            attrs=context.attrs,
            world_state=request.world_state,
            human_approved=request.human_approved,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/copilot/chat", response_model=CopilotChatResponse)
def copilot_chat(request: CopilotChatRequest, context=Depends(build_request_context)) -> CopilotChatResponse:
    require_agent_run(context.user)
    _require_schema()
    try:
        return runtime_service.chat(
            context.org_id,
            message=request.message,
            user_id=context.user_id,
            roles=context.roles,
            attrs=context.attrs,
            world_state=request.world_state,
            goal_id=request.goal_id,
            human_approved=request.human_approved,
            selected_alternative_index=request.selected_alternative_index,
            prep_only=request.prep_only,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/runs/{run_id}/approve", response_model=CopilotChatResponse)
def approve_goal_run(
    goal_id: str,
    run_id: str,
    request: GoalApproveRequest,
    context=Depends(build_request_context),
) -> CopilotChatResponse:
    require_agent_run(context.user)
    _require_schema()
    try:
        return runtime_service.approve_and_continue(
            context.org_id,
            goal_id=goal_id,
            run_id=run_id,
            user_id=request.approved_by or context.user_id,
            roles=context.roles,
            attrs=context.attrs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/runs/{run_id}/continue", response_model=CopilotChatResponse)
def continue_goal_run(goal_id: str, run_id: str, context=Depends(build_request_context)) -> CopilotChatResponse:
    require_agent_run(context.user)
    _require_schema()
    try:
        return runtime_service.approve_and_continue(
            context.org_id,
            goal_id=goal_id,
            run_id=run_id,
            user_id=context.user_id,
            roles=context.roles,
            attrs=context.attrs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/runs/{run_id}/undo", response_model=CopilotChatResponse)
def undo_goal_run(
    goal_id: str,
    run_id: str,
    request: GoalUndoRequest,
    context=Depends(build_request_context),
) -> CopilotChatResponse:
    require_agent_run(context.user)
    _require_schema()
    try:
        return runtime_service.undo(
            context.org_id,
            goal_id=goal_id,
            run_id=run_id,
            user_id=context.user_id,
            steps=request.steps,
            roles=context.roles,
            attrs=context.attrs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/approvals")
def list_approvals(context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    items = goal_manager.list_approval_queue(context.org_id)
    return {"request_id": context.request_id, "items": [i.model_dump() for i in items], "count": len(items)}


@router.post("/goals/{goal_id}/runs/{run_id}/resume", response_model=CopilotChatResponse)
def resume_goal_run(goal_id: str, run_id: str, context=Depends(build_request_context)) -> CopilotChatResponse:
    require_agent_run(context.user)
    _require_schema()
    try:
        return runtime_service.resume_run(
            context.org_id,
            goal_id=goal_id,
            run_id=run_id,
            user_id=context.user_id,
            roles=context.roles,
            attrs=context.attrs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/goals/{goal_id}/runs/{run_id}/alternative", response_model=CopilotChatResponse)
def apply_alternative(
    goal_id: str,
    run_id: str,
    request: GoalAlternativeRequest,
    context=Depends(build_request_context),
) -> CopilotChatResponse:
    require_agent_run(context.user)
    _require_schema()
    try:
        return runtime_service.apply_alternative(
            context.org_id,
            goal_id=goal_id,
            run_id=run_id,
            alternative_index=request.alternative_index,
            user_id=request.approved_by or context.user_id,
            roles=context.roles,
            attrs=context.attrs,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/goals")
def list_goals(context=Depends(build_request_context), status: str | None = None) -> dict:
    require_agent_read(context.user)
    items = goal_repository.list_goals(context.org_id, status=status)
    return {"request_id": context.request_id, "items": items, "count": len(items)}


@router.get("/goals/{goal_id}")
def get_goal(goal_id: str, context=Depends(build_request_context)) -> dict:
    require_agent_read(context.user)
    goal = goal_repository.get_goal(context.org_id, goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"request_id": context.request_id, "goal": goal}


@router.post("/world-state")
def publish_world_state(request: WorldStatePublishRequest, context=Depends(build_request_context)) -> dict:
    """Frontend UI context bridge — continuous publish of screen/selection/filters (Wave 4)."""
    require_agent_run(context.user)
    from app.modules.finance_os.platform_ai_runtime.context.world_state_engine import world_state_engine

    published = world_state_engine.publish(
        context.org_id,
        request.world_state,
        goal_id=request.goal_id,
        user_id=context.user_id,
    )
    return {
        "request_id": context.request_id,
        "goal_id": request.goal_id,
        "world_state": published.model_dump(),
        "status": "ok",
    }


@router.get("/world-state")
def get_world_state(context=Depends(build_request_context), goal_id: str | None = None) -> dict:
    """Read current session world state (from optional goal)."""
    require_agent_read(context.user)
    from app.modules.finance_os.platform_ai_runtime.context.world_state_engine import world_state_engine

    if not goal_id:
        return {"request_id": context.request_id, "world_state": None, "goal_id": None}
    ws = world_state_engine.load_persisted(context.org_id, goal_id)
    return {
        "request_id": context.request_id,
        "goal_id": goal_id,
        "world_state": ws.model_dump() if ws else None,
    }


@router.post("/goals/operational", response_model=CopilotChatResponse)
def create_operational_goal(
    request: OperationalGoalRequest, context=Depends(build_request_context)
) -> CopilotChatResponse:
    """Create long-running operational goal (period close, AR campaign, etc.) — Wave 5."""
    require_agent_run(context.user)
    _require_schema()
    try:
        data = goal_manager.create_operational_goal(
            context.org_id,
            request,
            user_id=context.user_id,
            roles=context.roles,
        )
        # chat() returns serialized CopilotChatResponse
        return CopilotChatResponse.model_validate(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/goals/{goal_id}/progress")
def goal_progress(goal_id: str, context=Depends(build_request_context)) -> dict:
    """Long-running goal progress snapshot (checkpoint, nodes, approval state)."""
    require_agent_read(context.user)
    snap = goal_manager.progress_snapshot(context.org_id, goal_id)
    if not snap:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"request_id": context.request_id, "progress": snap}


@router.get("/objectives")
def list_objectives(context=Depends(build_request_context)) -> dict:
    """Active Goal Memory objectives across operational goals."""
    require_agent_read(context.user)
    from app.modules.finance_os.platform_ai_runtime.autonomy.goal_memory import goal_memory

    objs = goal_memory.load_active_objectives(context.org_id)
    return {
        "request_id": context.request_id,
        "items": [o.model_dump() for o in objs],
        "count": len(objs),
    }


@router.get("/event-subscriptions")
def list_event_subscriptions(context=Depends(build_request_context)) -> dict:
    """Configurable event subscriptions for the event-driven planner."""
    require_agent_read(context.user)
    from app.modules.finance_os.platform_ai_runtime.autonomy.event_driven_planner import EVENT_SUBSCRIPTIONS

    return {"request_id": context.request_id, "subscriptions": EVENT_SUBSCRIPTIONS}


@router.get("/ai/analytics")
def ai_analytics(context=Depends(build_request_context)) -> dict:
    """Wave 6 AI usage analytics snapshot (cache-backed + optional SQL detail)."""
    require_agent_read(context.user)
    from app.services.ai_gateway.analytics import ai_usage_analytics
    from app.services.ai_gateway.budget_manager import ai_budget_manager

    snap = ai_usage_analytics.snapshot(context.org_id)
    budget = ai_budget_manager.check(context.org_id)
    recent = ai_usage_analytics.from_database(context.org_id, limit=25)
    return {
        "request_id": context.request_id,
        "analytics": snap,
        "budget": {
            "monthly_used": budget.monthly_used,
            "daily_used": budget.daily_used,
            "monthly_limit": budget.monthly_limit,
            "daily_limit": budget.daily_limit,
            "remaining_usd": budget.remaining_usd,
            "soft_warning": budget.soft_warning,
            "reason": budget.reason,
        },
        "recent_usage": recent,
    }


@router.get("/ai/gateway/health")
def ai_gateway_health(context=Depends(build_request_context)) -> dict:
    """Wave 6 gateway status + model route map (no secrets)."""
    require_agent_read(context.user)
    from app.core.config import settings
    from app.services.ai_gateway.model_router import model_router

    return {
        "request_id": context.request_id,
        "gateway_enabled": bool(settings.ai_gateway_enabled),
        "provider": settings.llm_provider,
        "aliases": model_router.aliases(),
        "class_routes": model_router.class_map(),
        "llm_ready": __import__("app.services.llm_provider", fromlist=["llm_provider"]).llm_provider.is_ready(),
    }
