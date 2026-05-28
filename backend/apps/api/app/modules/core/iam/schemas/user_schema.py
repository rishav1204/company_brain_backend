from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: str
    org_id: str
    email: str
    display_name: str
    status: str
    mfa_enabled: bool = False
    phone: str | None = None


class UserListResponse(BaseModel):
    request_id: str
    items: list[UserResponse]
    total: int
    limit: int
    offset: int
    confidence: float
    verification_status: str


class AssignRoleRequest(BaseModel):
    role_name: str
    company_id: str | None = None
    branch_id: str | None = None
    idempotency_key: str | None = None
