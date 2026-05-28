from pydantic import BaseModel, Field

from app.core.config import DEV_ORG_ID


class MeResponse(BaseModel):
    request_id: str
    user_id: str
    org_id: str
    roles: list[str]
    permissions: list[str] = Field(default_factory=list)
    session_id: str | None = None
    confidence: float
    verification_status: str


class PermissionEvaluateRequest(BaseModel):
    object_type: str
    object_id: str
    action: str


class PermissionEvaluateResponse(BaseModel):
    request_id: str
    allowed: bool
    reason: str
    checks: list[str] = Field(default_factory=list)
    object_context: dict = Field(default_factory=dict)
    confidence: float
    verification_status: str


class PasswordLoginRequest(BaseModel):
    email: str
    password: str
    org_id: str = DEV_ORG_ID
    roles: list[str] = Field(default_factory=lambda: ["tenant_admin"])


class PasswordLoginResponse(BaseModel):
    request_id: str
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    user_id: str | None = None
    org_id: str | None = None
    confidence: float
    verification_status: str


class DevCreateUserRequest(BaseModel):
    email: str
    password: str
    org_id: str = DEV_ORG_ID
    roles: list[str] = Field(default_factory=lambda: ["tenant_admin"])
    display_name: str | None = None


class DevCreateUserResponse(BaseModel):
    request_id: str
    user_id: str
    email: str
    org_id: str
    roles: list[str]
    confidence: float
    verification_status: str


class OidcStartResponse(BaseModel):
    request_id: str
    authorize_url: str
    state: str
    confidence: float
    verification_status: str


class OidcCallbackRequest(BaseModel):
    code: str
    state: str
    mfa_code: str | None = None


class OidcCallbackResponse(BaseModel):
    request_id: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    org_id: str
    confidence: float
    verification_status: str
    refresh_token: str | None = None


class OidcRefreshRequest(BaseModel):
    refresh_token: str
    mfa_code: str | None = None


class OidcRefreshResponse(BaseModel):
    request_id: str
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: str
    org_id: str
    confidence: float
    verification_status: str


class OidcLogoutRequest(BaseModel):
    refresh_token: str | None = None
    access_token: str | None = None


class OidcRevokeRequest(BaseModel):
    access_token: str
