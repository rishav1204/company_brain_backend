from pydantic import BaseModel, Field

from app.modules.platform.operator.services.operator_service import VALID_USER_STATUSES


class UserStatusRequest(BaseModel):
    status: str = Field(pattern="^(active|suspended|deactivated)$")
    reason: str | None = Field(default=None, max_length=500)


class OperatorListResponse(BaseModel):
    request_id: str
    items: list[dict]
    count: int
    total: int
    verification_status: str


class UsageResponse(BaseModel):
    request_id: str
    items: list[dict]
    count: int
    window_days: int
    verification_status: str


class UserStatusResponse(BaseModel):
    request_id: str
    user: dict
    org_name: str
    sessions_revoked: int
    verification_status: str


class SessionRevokeResponse(BaseModel):
    request_id: str
    user_id: str
    org_id: str
    email: str
    sessions_revoked: int
    verification_status: str


__all__ = [
    "OperatorListResponse",
    "SessionRevokeResponse",
    "UsageResponse",
    "UserStatusRequest",
    "UserStatusResponse",
    "VALID_USER_STATUSES",
]
