from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.erp.consolidation.security.consolidation_guard import require_consolidation_read
from app.modules.erp.consolidation.services.entity_service import entity_service

router = APIRouter(tags=["consolidation-entities"])


class HierarchyLinkRequest(BaseModel):
    parent_company_id: str
    child_company_id: str
    ownership_percent: float = Field(default=100.0, ge=0, le=100)


@router.get("/entities/hierarchy")
def get_hierarchy(context=Depends(build_request_context)) -> dict:
    require_consolidation_read(context)
    return {
        "request_id": context.request_id,
        "items": entity_service.list_hierarchy(context.org_id),
        "tree": entity_service.build_tree(context.org_id),
    }


@router.post("/entities/hierarchy")
def link_hierarchy(request: HierarchyLinkRequest, context=Depends(build_request_context)) -> dict:
    from app.modules.erp.consolidation.security.consolidation_guard import require_consolidation_run

    require_consolidation_run(context, company_id=request.parent_company_id)
    try:
        row = entity_service.link_entities(
            context.org_id,
            parent_company_id=request.parent_company_id,
            child_company_id=request.child_company_id,
            ownership_percent=request.ownership_percent,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"request_id": context.request_id, "item": row}
