from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import build_request_context
from app.modules.platform.notifications.repositories.template_repository import template_repository
from app.modules.platform.notifications.validators.template_validator import validate_template_body

router = APIRouter(tags=["notification-templates"])


class TemplateCreate(BaseModel):
    template_key: str
    channel: str
    body_template: str
    subject_template: str | None = None
    variables: list[str] = Field(default_factory=list)


class TemplateUpdate(BaseModel):
    subject_template: str | None = None
    body_template: str | None = None
    is_active: bool | None = None


@router.get("/templates")
def list_templates(context=Depends(build_request_context)) -> dict:
    return {"request_id": context.request_id, "items": template_repository.list_templates(context.org_id)}


@router.post("/templates")
def create_template(request: TemplateCreate, context=Depends(build_request_context)) -> dict:
    validate_template_body(request.body_template)
    row = template_repository.create(
        context.org_id,
        template_key=request.template_key,
        channel=request.channel,
        body_template=request.body_template,
        subject_template=request.subject_template,
        variables=request.variables,
    )
    return {"request_id": context.request_id, "template": row}


@router.put("/templates/{template_id}")
def update_template(
    template_id: str, request: TemplateUpdate, context=Depends(build_request_context)
) -> dict:
    if request.body_template:
        validate_template_body(request.body_template)
    row = template_repository.update(
        context.org_id,
        template_id,
        subject_template=request.subject_template,
        body_template=request.body_template,
        is_active=request.is_active,
    )
    if not row:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"request_id": context.request_id, "template": row}
