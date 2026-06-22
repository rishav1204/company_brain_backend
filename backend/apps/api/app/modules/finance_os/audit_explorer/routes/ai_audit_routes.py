from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.finance_os.audit_explorer.read_models.audit_timeline_models import AIDecisionResponse
from app.modules.finance_os.audit_explorer.security.audit_explorer_guard import require_audit_read
from app.modules.finance_os.audit_explorer.services.ai_explanation_service import get_ai_decision

router = APIRouter(tags=["finance-os-audit-ai"])


@router.get("/ai-decision/{execution_id}", response_model=AIDecisionResponse)
def ai_decision_trail(execution_id: str, context=Depends(build_request_context)) -> AIDecisionResponse:
    require_audit_read(context.user)
    result = get_ai_decision(context.org_id, execution_id)
    return AIDecisionResponse(
        request_id=context.request_id,
        execution_id=execution_id,
        trails=result.get("trails") or [],
        execution=result.get("execution"),
        recommendations=result.get("recommendations") or [],
        memory_factors=result.get("memory_factors") or [],
    )
