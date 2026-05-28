from fastapi import APIRouter, Depends

from app.api.deps import build_request_context
from app.modules.core.iam.repositories import role_repo
from app.modules.core.iam.schemas.role_schema import RoleListResponse, RoleResponse

router = APIRouter(tags=["iam-roles"])


@router.get("/roles", response_model=RoleListResponse)
def list_roles(context=Depends(build_request_context)) -> RoleListResponse:
    rows = role_repo.list_roles(context.org_id)
    items = [
        RoleResponse(
            id=row["id"],
            org_id=row["org_id"],
            name=row["name"],
            description=row.get("description"),
            system_role=bool(row.get("system_role")),
            policy_context=row.get("policy_context") or {},
        )
        for row in rows
    ]
    return RoleListResponse(
        request_id=context.request_id,
        items=items,
        confidence=0.99,
        verification_status="iam_roles_listed",
    )
