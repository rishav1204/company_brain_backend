from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.core.iam.middleware.permission_guard import require_permission
from app.modules.platform.integrations.services.connector_uat_service import connector_uat_service

router = APIRouter()


@router.get("/connectors/uat")
def run_connector_uat(context=Depends(require_permission("org.admin"))) -> dict:
    """Production connector configuration + connectivity check (ERP-17/19/20)."""
    result = connector_uat_service.run_all(require_reachable=True)
    return {"request_id": context.request_id, **result}


@router.get("/connectors/uat/env")
def connector_env_check(context=Depends(require_permission("org.admin"))) -> dict:
    return {"request_id": context.request_id, "env": connector_uat_service.validate_env()}
