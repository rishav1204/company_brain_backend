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
