from pydantic import BaseModel, Field


class RoleResponse(BaseModel):
    id: str
    org_id: str
    name: str
    description: str | None = None
    system_role: bool = False
    policy_context: dict = Field(default_factory=dict)


class RoleListResponse(BaseModel):
    request_id: str
    items: list[RoleResponse]
    confidence: float
    verification_status: str
